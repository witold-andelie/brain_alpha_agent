from brain_alpha_agent.course_reference import load_course_alpha_templates
from brain_alpha_agent.metrics import coverage, extract_simulation_metrics


def test_course_templates_and_coverage() -> None:
    templates = load_course_alpha_templates(r"D:\CS_materials\量化\Course2_作业答案\src\必做4_批量生成Alpha.py")
    assert len(templates) == 25
    assert coverage(400, 500, 1000) == 0.9
    assert extract_simulation_metrics({"longCount": 400, "shortCount": 500, "universeCount": 1000})["coverage"] == 0.9


def test_simulation_metrics_accept_brain_labels() -> None:
    metrics = extract_simulation_metrics({"Sharpe": 1.4, "Fitness": 0.8, "Returns": 0.12, "Turnover": 0.3, "Drawdown": 0.1, "Long-Count": 400, "Short-Count": 500, "Universe-Count": 1000})

    assert metrics["sharpe"] == 1.4
    assert metrics["returns"] == 0.12
    assert metrics["drawdown"] == 0.1
    assert metrics["coverage"] == 0.9
