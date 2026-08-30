import math

import pytest

from brain_alpha_agent.quality import QualityThresholds, assess_quality


def metrics(
    sharpe=1.4,
    fitness=0.8,
    turnover=0.3,
    drawdown=0.1,
    coverage=0.9,
    *,
    scenario_hash="scenario-1",
    regime="baseline",
    evaluator="brain",
    status="COMPLETE",
):
    return {
        "status": status,
        "evaluator": evaluator,
        "scenario_hash": scenario_hash,
        "scenario": {"regime": regime},
        "metrics": {
            "sharpe": sharpe,
            "fitness": fitness,
            "turnover": turnover,
            "drawdown": drawdown,
            "coverage": coverage,
        },
    }


def passing_scenarios():
    return [
        metrics(scenario_hash="baseline-1", regime="baseline", sharpe=1.4),
        metrics(scenario_hash="whipsaw-1", regime="whipsaw", sharpe=1.2),
        metrics(scenario_hash="stress-1", regime="stress", sharpe=1.3),
    ]


def test_quality_requires_multiple_distinct_regime_scenarios():
    assessment = assess_quality([metrics()])

    assert not assessment.passed
    assert "requires at least 3 valid completed scenarios" in assessment.reasons
    assert "requires at least 3 distinct material scenarios" in assessment.reasons
    assert any("whipsaw" in reason for reason in assessment.reasons)


def test_quality_passes_only_when_all_regimes_clear_gates():
    assessment = assess_quality(passing_scenarios())

    assert assessment.passed
    assert assessment.score is not None
    assert assessment.distinct_scenarios == 3
    assert assessment.regimes == ("baseline", "stress", "whipsaw")
    assert assessment.reasons == ()


def test_quality_rejects_risk_or_coverage_failures():
    scenarios = passing_scenarios()
    scenarios[0] = metrics(turnover=0.9, scenario_hash="baseline-1", regime="baseline")
    scenarios[1] = metrics(coverage=0.2, scenario_hash="whipsaw-1", regime="whipsaw")
    assessment = assess_quality(scenarios)

    assert not assessment.passed
    assert any("Turnover" in reason for reason in assessment.reasons)
    assert any("Coverage" in reason for reason in assessment.reasons)


def test_quality_rejects_offline_results():
    assessment = assess_quality(
        [metrics(evaluator="offline")],
        thresholds=QualityThresholds(
            min_scenarios=1,
            min_distinct_scenarios=1,
            required_regimes=(),
        ),
    )

    assert not assessment.passed
    assert any("verified BRAIN provenance" in reason for reason in assessment.reasons)


def test_quality_rejects_high_correlation_to_existing_alpha():
    result = metrics()
    result["metrics"]["correlation_to_existing"] = 0.9
    assessment = assess_quality(
        [result],
        thresholds=QualityThresholds(
            min_scenarios=1,
            min_distinct_scenarios=1,
            required_regimes=(),
        ),
    )

    assert not assessment.passed
    assert any("correlation to existing" in reason for reason in assessment.reasons)


def test_quality_rejects_non_finite_metrics_and_invalid_thresholds():
    assessment = assess_quality(
        [metrics(sharpe=math.nan)],
        thresholds=QualityThresholds(
            min_scenarios=1,
            min_distinct_scenarios=1,
            required_regimes=(),
        ),
    )

    assert not assessment.passed
    assert any("non-finite" in reason for reason in assessment.reasons)
    with pytest.raises(ValueError, match="at least 1"):
        QualityThresholds(min_scenarios=0, min_distinct_scenarios=1)


def test_quality_rejects_duplicate_scenarios_and_whipsaw_turnover():
    scenarios = passing_scenarios()
    scenarios[1]["scenario_hash"] = scenarios[0]["scenario_hash"]
    scenarios[1]["metrics"]["turnover"] = 0.7
    assessment = assess_quality(scenarios)

    assert not assessment.passed
    assert any("distinct material scenarios" in reason for reason in assessment.reasons)
    assert any("whipsaw Turnover" in reason for reason in assessment.reasons)
