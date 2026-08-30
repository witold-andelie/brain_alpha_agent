from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from typing import Any, Callable, Iterable

from .brain_api import BrainSimulationAdapter
from .deduplication import formula_signature
from .domain import AlphaCandidate
from .formula import validate_formula


class PayloadTemplateError(ValueError):
    pass


_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}")
_RESERVED_CANDIDATE_KEYS = frozenset(
    {"id", "formula", "hypothesis", "fields", "operators", "source"}
)
_SCENARIO_METADATA_KEYS = frozenset({"regime", "label", "name", "notes"})


def render_payload(
    template: Any, candidate: AlphaCandidate, scenario: dict[str, Any]
) -> Any:
    """Render a JSON-compatible payload while protecting candidate identity fields."""
    candidate_values = asdict(candidate)
    context: dict[str, Any] = dict(candidate_values)
    for key, value in scenario.items():
        if key not in _RESERVED_CANDIDATE_KEYS:
            context[key] = value
    for key, value in candidate_values.items():
        context[f"candidate.{key}"] = value
    for key, value in scenario.items():
        context[f"scenario.{key}"] = value

    def render(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: render(item) for key, item in value.items()}
        if isinstance(value, list):
            return [render(item) for item in value]
        if not isinstance(value, str):
            return value
        exact = _PLACEHOLDER.fullmatch(value)
        if exact:
            key = exact.group(1)
            if key not in context:
                raise PayloadTemplateError(f"unknown payload placeholder: {key}")
            return context[key]

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in context:
                raise PayloadTemplateError(f"unknown payload placeholder: {key}")
            return str(context[key])

        return _PLACEHOLDER.sub(replace, value)

    rendered = render(template)
    if unresolved := _unresolved_placeholders(rendered):
        raise PayloadTemplateError(
            f"unresolved payload placeholders: {', '.join(sorted(unresolved))}"
        )
    return rendered


def bind_payload_to_candidate(
    payload: Any, candidate: AlphaCandidate
) -> dict[str, Any]:
    """Fail unless a request contains the exact validated candidate formula."""
    if not isinstance(payload, dict):
        raise PayloadTemplateError("simulation payload must be a JSON object")
    validate_formula(candidate.formula)
    signature = formula_signature(candidate.formula)
    if not _contains_formula(payload, signature):
        raise PayloadTemplateError(
            "simulation payload does not contain the selected candidate formula"
        )
    return payload


def scenario_fingerprint(scenario: dict[str, Any]) -> str:
    """Hash material scenario settings; labels alone cannot create a distinct run."""
    material = {
        key: value
        for key, value in scenario.items()
        if key not in _SCENARIO_METADATA_KEYS
    }
    return _stable_hash(material)


def request_fingerprint(payload: dict[str, Any]) -> str:
    return _stable_hash(payload)


def load_json_object(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def run_research(
    candidates: Iterable[AlphaCandidate],
    scenarios: Iterable[dict[str, Any]],
    payload_template: Any,
    adapter: BrainSimulationAdapter,
    save_result: Callable[[str, dict[str, Any]], None] | None = None,
    *,
    save_run: Callable[
        [AlphaCandidate, dict[str, Any], dict[str, Any], dict[str, Any], str],
        str | None,
    ]
    | None = None,
    evaluator: str = "brain",
    timeout: float = 300,
    poll_interval: float = 2,
    max_runs: int = 50,
) -> list[dict[str, str]]:
    candidate_list = list(candidates)
    scenario_list = list(scenarios)
    if not candidate_list:
        raise ValueError("research requires at least one candidate")
    if not scenario_list:
        raise ValueError("research requires at least one scenario")
    if max_runs <= 0:
        raise ValueError("max_runs must be positive")
    planned_runs = len(candidate_list) * len(scenario_list)
    if planned_runs > max_runs:
        raise ValueError(
            f"research plans {planned_runs} simulations, above max_runs={max_runs}"
        )

    fingerprints: list[str] = []
    for index, scenario in enumerate(scenario_list, start=1):
        regime = scenario.get("regime")
        if not isinstance(regime, str) or not regime.strip():
            raise ValueError(f"scenario {index} must include a non-empty regime label")
        fingerprints.append(scenario_fingerprint(scenario))
    if len(set(fingerprints)) != len(fingerprints):
        raise ValueError("research scenarios must have distinct material settings")

    if save_result is None and save_run is None:
        raise ValueError("research requires a result persistence callback")

    completed: list[dict[str, str]] = []
    for candidate in candidate_list:
        for scenario, scenario_hash in zip(scenario_list, fingerprints, strict=True):
            payload = bind_payload_to_candidate(
                render_payload(payload_template, candidate, scenario), candidate
            )
            result = adapter.simulate(
                payload, timeout=timeout, poll_interval=poll_interval
            )
            run_id = ""
            if save_run is not None:
                run_id = str(
                    save_run(candidate, payload, result, scenario, evaluator) or ""
                )
            elif save_result is not None:
                save_result(candidate.id, result)
            simulation_id = str(
                result.get("id")
                or result.get("simulation_id")
                or result.get("simulationId")
                or ""
            )
            completed.append(
                {
                    "alpha_id": candidate.id,
                    "simulation_id": simulation_id,
                    "run_id": run_id,
                    "scenario_hash": scenario_hash,
                    "regime": str(scenario["regime"]),
                }
            )
    return completed


def _contains_formula(value: Any, signature: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_formula(item, signature) for item in value.values())
    if isinstance(value, list):
        return any(_contains_formula(item, signature) for item in value)
    return isinstance(value, str) and formula_signature(value) == signature


def _unresolved_placeholders(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_unresolved_placeholders(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_unresolved_placeholders(item) for item in value))
    if isinstance(value, str):
        return {match.group(1) for match in _PLACEHOLDER.finditer(value)}
    return set()


def _stable_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    except (TypeError, ValueError) as error:
        raise ValueError(
            "research payloads and scenarios must be finite JSON values"
        ) from error
    return hashlib.sha256(encoded).hexdigest()
