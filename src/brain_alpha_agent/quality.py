from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, pstdev
from typing import Any, Iterable


@dataclass(frozen=True)
class QualityThresholds:
    min_sharpe: float = 1.0
    min_fitness: float = 0.5
    max_turnover: float = 0.8
    max_drawdown: float = 0.25
    min_coverage: float = 0.5
    min_scenarios: int = 3
    max_sharpe_dispersion: float = 1.0
    max_correlation_to_existing: float = 0.8


@dataclass(frozen=True)
class QualityAssessment:
    passed: bool
    score: float | None
    reasons: tuple[str, ...]
    scenarios: int


def assess_quality(
    results: Iterable[dict[str, Any]],
    *,
    thresholds: QualityThresholds = QualityThresholds(),
) -> QualityAssessment:
    scenarios = list(results)
    reasons: list[str] = []
    if len(scenarios) < thresholds.min_scenarios:
        reasons.append(f"requires at least {thresholds.min_scenarios} completed scenarios")

    required = ("sharpe", "fitness", "turnover", "drawdown", "coverage")
    normalized: list[dict[str, float]] = []
    for index, result in enumerate(scenarios, start=1):
        raw = result.get("raw", {})
        if raw.get("evaluator") in {"offline", "mock"} or result.get("evaluator") in {"offline", "mock"}:
            reasons.append(f"scenario {index} is not a real BRAIN result")
            continue
        metrics = result.get("metrics", result)
        missing = [name for name in required if metrics.get(name) is None]
        if missing:
            reasons.append(f"scenario {index} is missing metrics: {', '.join(missing)}")
            continue
        values = {name: float(metrics[name]) for name in required}
        normalized.append(values)
        if values["sharpe"] < thresholds.min_sharpe:
            reasons.append(f"scenario {index} Sharpe is below {thresholds.min_sharpe}")
        if values["fitness"] < thresholds.min_fitness:
            reasons.append(f"scenario {index} Fitness is below {thresholds.min_fitness}")
        if values["turnover"] > thresholds.max_turnover:
            reasons.append(f"scenario {index} Turnover is above {thresholds.max_turnover}")
        if values["drawdown"] > thresholds.max_drawdown:
            reasons.append(f"scenario {index} Drawdown is above {thresholds.max_drawdown}")
        if values["coverage"] < thresholds.min_coverage:
            reasons.append(f"scenario {index} Coverage is below {thresholds.min_coverage}")
        correlation = metrics.get("correlation_to_existing")
        if correlation is not None and abs(float(correlation)) > thresholds.max_correlation_to_existing:
            reasons.append(f"scenario {index} correlation to existing alphas is above {thresholds.max_correlation_to_existing}")

    score = None
    if normalized:
        sharpes = [item["sharpe"] for item in normalized]
        if len(sharpes) > 1 and pstdev(sharpes) > thresholds.max_sharpe_dispersion:
            reasons.append(f"Sharpe dispersion is above {thresholds.max_sharpe_dispersion}")
        score = round(
            fmean(min(1.0, max(0.0, item["sharpe"] / 2.0)) for item in normalized) * 0.4
            + fmean(min(1.0, max(0.0, item["fitness"] / 2.0)) for item in normalized) * 0.3
            + fmean(1.0 - min(1.0, max(0.0, item["turnover"])) for item in normalized) * 0.15
            + fmean(1.0 - min(1.0, max(0.0, item["drawdown"])) for item in normalized) * 0.15,
            6,
        )
    return QualityAssessment(not reasons, score, tuple(reasons), len(scenarios))
