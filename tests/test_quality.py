from brain_alpha_agent.quality import QualityThresholds, assess_quality


def metrics(sharpe=1.4, fitness=0.8, turnover=0.3, drawdown=0.1, coverage=0.9):
    return {"metrics": {"sharpe": sharpe, "fitness": fitness, "turnover": turnover, "drawdown": drawdown, "coverage": coverage}}


def test_quality_requires_multiple_scenarios():
    assessment = assess_quality([metrics()], thresholds=QualityThresholds(min_scenarios=3))

    assert not assessment.passed
    assert "requires at least 3 completed scenarios" in assessment.reasons


def test_quality_passes_only_when_all_scenarios_clear_gates():
    assessment = assess_quality([metrics(), metrics(sharpe=1.2)], thresholds=QualityThresholds(min_scenarios=2))

    assert assessment.passed
    assert assessment.score is not None
    assert assessment.reasons == ()


def test_quality_rejects_risk_or_coverage_failures():
    assessment = assess_quality([metrics(turnover=0.9), metrics(coverage=0.2)], thresholds=QualityThresholds(min_scenarios=2))

    assert not assessment.passed
    assert any("Turnover" in reason for reason in assessment.reasons)
    assert any("Coverage" in reason for reason in assessment.reasons)


def test_quality_rejects_offline_results():
    assessment = assess_quality([{"raw": {"evaluator": "offline"}, **metrics()}], thresholds=QualityThresholds(min_scenarios=1))

    assert not assessment.passed
    assert any("not a real BRAIN result" in reason for reason in assessment.reasons)


def test_quality_rejects_high_correlation_to_existing_alpha():
    result = metrics()
    result["metrics"]["correlation_to_existing"] = 0.9
    assessment = assess_quality([result], thresholds=QualityThresholds(min_scenarios=1))

    assert not assessment.passed
    assert any("correlation to existing" in reason for reason in assessment.reasons)
