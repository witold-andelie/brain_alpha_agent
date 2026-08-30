from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, pstdev
from typing import Any, Iterable


_SUCCESS_STATES = frozenset({"COMPLETE", "COMPLETED", "DONE", "SUCCESS"})


@dataclass(frozen=True)
class QualityThresholds:
    min_sharpe: float = 1.0
    min_fitness: float = 0.5
    max_turnover: float = 0.8
    max_whipsaw_turnover: float = 0.6
    max_drawdown: float = 0.25
    min_coverage: float = 0.5
    min_scenarios: int = 3
    min_distinct_scenarios: int = 3
    max_sharpe_dispersion: float = 1.0
    max_whipsaw_sharpe_drop: float = 0.75
    max_correlation_to_existing: float = 0.8
    required_regimes: tuple[str, ...] = ("baseline", "whipsaw")

    def __post_init__(self) -> None:
        if self.min_scenarios < 1:
            raise ValueError("min_scenarios must be at least 1")
        if not 1 <= self.min_distinct_scenarios <= self.min_scenarios:
            raise ValueError(
                "min_distinct_scenarios must be between 1 and min_scenarios"
            )
        numeric = (
            self.min_sharpe,
            self.min_fitness,
            self.max_turnover,
            self.max_whipsaw_turnover,
            self.max_drawdown,
            self.min_coverage,
            self.max_sharpe_dispersion,
            self.max_whipsaw_sharpe_drop,
            self.max_correlation_to_existing,
        )
        if not all(math.isfinite(value) for value in numeric):
            raise ValueError("quality thresholds must be finite")
        if self.max_turnover < 0 or self.max_whipsaw_turnover < 0:
            raise ValueError("turnover thresholds cannot be negative")
        if self.max_drawdown < 0 or self.max_sharpe_dispersion < 0:
            raise ValueError("risk thresholds cannot be negative")
        if not 0 <= self.min_coverage <= 1:
            raise ValueError("min_coverage must be between 0 and 1")
        if not 0 <= self.max_correlation_to_existing <= 1:
            raise ValueError("max_correlation_to_existing must be between 0 and 1")
        if any(not regime.strip() for regime in self.required_regimes):
            raise ValueError("required regime labels cannot be empty")
        if len(set(self.required_regimes)) != len(self.required_regimes):
            raise ValueError("required regime labels must be unique")


@dataclass(frozen=True)
class QualityAssessment:
    passed: bool
    score: float | None
    reasons: tuple[str, ...]
    scenarios: int
    distinct_scenarios: int = 0
    regimes: tuple[str, ...] = ()


def assess_quality(
    results: Iterable[dict[str, Any]],
    *,
    thresholds: QualityThresholds = QualityThresholds(),
) -> QualityAssessment:
    scenarios = list(results)
    reasons: list[str] = []
    required = ("sharpe", "fitness", "turnover", "drawdown", "coverage")
    normalized: list[dict[str, float | str]] = []
    distinct_scenarios: set[str] = set()
    regimes: set[str] = set()

    for index, result in enumerate(scenarios, start=1):
        raw = result.get("raw", {})
        status = str(
            result.get("status") or raw.get("status") or raw.get("state") or ""
        ).upper()
        if status not in _SUCCESS_STATES:
            reasons.append(f"scenario {index} is not a completed simulation")
            continue

        evaluator = str(
            result.get("evaluator") or raw.get("evaluator") or "unknown"
        ).casefold()
        if evaluator != "brain":
            reasons.append(f"scenario {index} does not have verified BRAIN provenance")
            continue

        scenario_hash = str(result.get("scenario_hash") or "").strip()
        if not scenario_hash:
            reasons.append(
                f"scenario {index} is missing a material scenario fingerprint"
            )
            continue
        distinct_scenarios.add(scenario_hash)

        scenario = result.get("scenario", {})
        regime = str(
            (scenario.get("regime") if isinstance(scenario, dict) else None)
            or result.get("regime")
            or ""
        ).strip()
        if not regime:
            reasons.append(f"scenario {index} is missing a regime label")
            continue
        regimes.add(regime)

        metrics = result.get("metrics", result)
        missing = [name for name in required if metrics.get(name) is None]
        if missing:
            reasons.append(f"scenario {index} is missing metrics: {', '.join(missing)}")
            continue
        try:
            values = {name: float(metrics[name]) for name in required}
        except (TypeError, ValueError):
            reasons.append(f"scenario {index} contains non-numeric metrics")
            continue
        if not all(math.isfinite(value) for value in values.values()):
            reasons.append(f"scenario {index} contains non-finite metrics")
            continue
        if values["turnover"] < 0 or values["drawdown"] < 0:
            reasons.append(f"scenario {index} contains a negative risk metric")
            continue
        if not 0 <= values["coverage"] <= 1:
            reasons.append(f"scenario {index} Coverage is outside 0-1")
            continue

        normalized.append({**values, "regime": regime})
        if values["sharpe"] < thresholds.min_sharpe:
            reasons.append(f"scenario {index} Sharpe is below {thresholds.min_sharpe}")
        if values["fitness"] < thresholds.min_fitness:
            reasons.append(
                f"scenario {index} Fitness is below {thresholds.min_fitness}"
            )
        if values["turnover"] > thresholds.max_turnover:
            reasons.append(
                f"scenario {index} Turnover is above {thresholds.max_turnover}"
            )
        if regime == "whipsaw" and values["turnover"] > thresholds.max_whipsaw_turnover:
            reasons.append(
                f"scenario {index} whipsaw Turnover is above {thresholds.max_whipsaw_turnover}"
            )
        if values["drawdown"] > thresholds.max_drawdown:
            reasons.append(
                f"scenario {index} Drawdown is above {thresholds.max_drawdown}"
            )
        if values["coverage"] < thresholds.min_coverage:
            reasons.append(
                f"scenario {index} Coverage is below {thresholds.min_coverage}"
            )

        correlation = metrics.get("correlation_to_existing")
        if correlation is not None:
            try:
                correlation_value = float(correlation)
            except (TypeError, ValueError):
                reasons.append(f"scenario {index} has a non-numeric correlation")
            else:
                if (
                    not math.isfinite(correlation_value)
                    or not -1 <= correlation_value <= 1
                ):
                    reasons.append(f"scenario {index} has an invalid correlation")
                elif abs(correlation_value) > thresholds.max_correlation_to_existing:
                    reasons.append(
                        f"scenario {index} correlation to existing alphas is above "
                        f"{thresholds.max_correlation_to_existing}"
                    )

    if len(normalized) < thresholds.min_scenarios:
        reasons.append(
            f"requires at least {thresholds.min_scenarios} valid completed scenarios"
        )
    if len(distinct_scenarios) < thresholds.min_distinct_scenarios:
        reasons.append(
            f"requires at least {thresholds.min_distinct_scenarios} distinct material scenarios"
        )
    missing_regimes = set(thresholds.required_regimes) - regimes
    if missing_regimes:
        reasons.append(
            f"missing required regimes: {', '.join(sorted(missing_regimes))}"
        )

    score = None
    if normalized:
        sharpes = [float(item["sharpe"]) for item in normalized]
        if len(sharpes) > 1 and pstdev(sharpes) > thresholds.max_sharpe_dispersion:
            reasons.append(
                f"Sharpe dispersion is above {thresholds.max_sharpe_dispersion}"
            )

        baseline_sharpes = [
            float(item["sharpe"]) for item in normalized if item["regime"] == "baseline"
        ]
        whipsaw_sharpes = [
            float(item["sharpe"]) for item in normalized if item["regime"] == "whipsaw"
        ]
        if baseline_sharpes and whipsaw_sharpes:
            drop = fmean(baseline_sharpes) - fmean(whipsaw_sharpes)
            if drop > thresholds.max_whipsaw_sharpe_drop:
                reasons.append(
                    f"Whipsaw Sharpe drop is above {thresholds.max_whipsaw_sharpe_drop}"
                )

        score = round(
            fmean(
                min(1.0, max(0.0, float(item["sharpe"]) / 2.0)) for item in normalized
            )
            * 0.35
            + fmean(
                min(1.0, max(0.0, float(item["fitness"]) / 2.0)) for item in normalized
            )
            * 0.25
            + fmean(1.0 - min(1.0, float(item["turnover"])) for item in normalized)
            * 0.15
            + fmean(1.0 - min(1.0, float(item["drawdown"])) for item in normalized)
            * 0.15
            + fmean(float(item["coverage"]) for item in normalized) * 0.10,
            6,
        )

    unique_reasons = tuple(dict.fromkeys(reasons))
    return QualityAssessment(
        not unique_reasons,
        score,
        unique_reasons,
        len(normalized),
        len(distinct_scenarios),
        tuple(sorted(regimes)),
    )
