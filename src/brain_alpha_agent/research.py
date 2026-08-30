from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any, Callable, Iterable

from .brain_api import BrainSimulationAdapter
from .domain import AlphaCandidate


_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}")


def render_payload(template: Any, candidate: AlphaCandidate, scenario: dict[str, Any]) -> Any:
    """Render a JSON-compatible payload template without evaluating code."""
    context: dict[str, Any] = {**asdict(candidate), **scenario}
    for key, value in asdict(candidate).items():
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
        if exact and exact.group(1) in context:
            return context[exact.group(1)]
        return _PLACEHOLDER.sub(lambda match: str(context.get(match.group(1), match.group(0))), value)

    return render(template)


def load_json_object(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def run_research(
    candidates: Iterable[AlphaCandidate],
    scenarios: Iterable[dict[str, Any]],
    payload_template: Any,
    adapter: BrainSimulationAdapter,
    save_result: Callable[[str, dict[str, Any]], None],
    *,
    timeout: float = 300,
    poll_interval: float = 2,
) -> list[dict[str, str]]:
    completed: list[dict[str, str]] = []
    for candidate in candidates:
        for scenario in scenarios:
            payload = render_payload(payload_template, candidate, scenario)
            result = adapter.simulate(payload, timeout=timeout, poll_interval=poll_interval)
            save_result(candidate.id, result)
            simulation_id = str(result.get("id") or result.get("simulation_id") or result.get("simulationId") or "")
            completed.append({"alpha_id": candidate.id, "simulation_id": simulation_id})
    return completed
