from brain_alpha_agent.evaluator import MockBrainEvaluator
from brain_alpha_agent.generator import generate_candidates
from brain_alpha_agent.quality import QualityThresholds, assess_quality
from brain_alpha_agent.storage import AlphaStore
from brain_alpha_agent.reference import load_reference_project


def test_candidates_are_deterministic_and_rankable(tmp_path) -> None:
    candidates = generate_candidates()
    assert len(candidates) == 8
    assert candidates == generate_candidates()
    assert len(generate_candidates(profile="baseline")) == 5
    assert len(generate_candidates(profile="whipsaw")) == 4
    store = AlphaStore(tmp_path / "alpha.db")
    try:
        result = MockBrainEvaluator().evaluate(candidates[0])
        store.save_candidate(candidates[0])
        store.save_evaluation(result)
        assert store.ranked()[0]["id"] == candidates[0].id
    finally:
        store.close()


def test_evaluation_uses_saved_candidate_configuration(tmp_path) -> None:
    candidate = generate_candidates(region="CHN", universe="TOP500", delay=0)[0]
    store = AlphaStore(tmp_path / "alpha.db")
    try:
        store.save_candidate(candidate)
        loaded = store.candidate(candidate.id)
        assert loaded == candidate
    finally:
        store.close()


def test_simulation_result_is_persisted_with_normalized_metrics(tmp_path) -> None:
    store = AlphaStore(tmp_path / "alpha.db")
    try:
        store.save_simulation_result(
            "alpha-1",
            {
                "id": "sim-1",
                "status": "COMPLETE",
                "Sharpe": 1.2,
                "Long-Count": 4,
                "Short-Count": 6,
                "Universe-Count": 20,
            },
        )
        result = store.simulation_result("sim-1")
        assert result["alpha_id"] == "alpha-1"
        assert result["raw"]["status"] == "COMPLETE"
        assert result["metrics"]["sharpe"] == 1.2
        assert result["metrics"]["coverage"] == 0.5
    finally:
        store.close()


def test_simulate_cli_offline_runs_end_to_end(tmp_path) -> None:
    import json

    from brain_alpha_agent.cli import main

    db_path = tmp_path / "alpha.db"
    payload_path = tmp_path / "simulation.json"
    assert main(["--db", str(db_path), "generate"]) == 0
    store = AlphaStore(db_path)
    try:
        alpha_id = store.ranked()[0]["id"]
        candidate = store.candidate(alpha_id)
        assert candidate is not None
    finally:
        store.close()

    payload_path.write_text(
        json.dumps(
            {
                "type": "offline-test",
                "regular": {"expression": candidate.formula},
                "settings": {"region": candidate.region},
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "--db",
                str(db_path),
                "simulate",
                alpha_id,
                "--payload",
                str(payload_path),
                "--regime",
                "baseline",
                "--offline",
            ]
        )
        == 0
    )
    store = AlphaStore(db_path)
    try:
        result = store.simulation_result("offline-simulation-1")
        assert result["alpha_id"] == alpha_id
        assert result["metrics"]["coverage"] == 0.9
        runs = store.simulation_results_for_alpha(alpha_id)
        assert len(runs) == 1
        assert runs[0]["evaluator"] == "offline"
        assert runs[0]["scenario"]["regime"] == "baseline"
        assert runs[0]["request"]["regular"]["expression"] == candidate.formula
    finally:
        store.close()


def test_simulation_runs_are_append_only_when_external_ids_repeat(tmp_path) -> None:
    candidate = generate_candidates()[0]
    store = AlphaStore(tmp_path / "alpha.db")
    request = {"regular": {"expression": candidate.formula}}
    response = {
        "id": "same-external-id",
        "status": "COMPLETE",
        "Sharpe": 1.2,
        "Fitness": 0.8,
        "Turnover": 0.2,
        "Drawdown": 0.1,
        "Long-Count": 450,
        "Short-Count": 450,
        "Universe-Count": 1000,
    }
    try:
        store.save_candidate(candidate)
        first = store.save_simulation_run(
            candidate,
            request,
            response,
            {"region": "USA", "regime": "baseline"},
            "brain",
        )
        second = store.save_simulation_run(
            candidate,
            request,
            response,
            {"region": "CHN", "regime": "whipsaw"},
            "brain",
        )
        assert first != second
        assert len(store.simulation_results_for_alpha(candidate.id)) == 2
    finally:
        store.close()


def test_real_assessment_replaces_mock_as_rank_source(tmp_path) -> None:
    candidate = generate_candidates()[0]
    store = AlphaStore(tmp_path / "alpha.db")
    try:
        store.save_candidate(candidate)
        for index, scenario in enumerate(
            [
                {"region": "USA", "regime": "baseline"},
                {"region": "CHN", "regime": "whipsaw"},
                {"region": "EUR", "regime": "stress"},
            ],
            start=1,
        ):
            store.save_simulation_run(
                candidate,
                {"regular": {"expression": candidate.formula}, "settings": scenario},
                {
                    "id": f"sim-{index}",
                    "status": "COMPLETE",
                    "Sharpe": 1.3,
                    "Fitness": 0.8,
                    "Turnover": 0.3,
                    "Drawdown": 0.1,
                    "Long-Count": 450,
                    "Short-Count": 450,
                    "Universe-Count": 1000,
                },
                scenario,
                "brain",
            )
        thresholds = QualityThresholds()
        assessment = assess_quality(
            store.simulation_results_for_alpha(candidate.id), thresholds=thresholds
        )
        store.save_quality_assessment(candidate.id, thresholds, assessment)

        ranked = store.ranked()[0]
        assert ranked["passed"] is True
        assert ranked["score_source"] == "brain_assessment"
    finally:
        store.close()


def test_reference_project_imports_brain_expressions() -> None:
    expressions = load_reference_project(r"D:\CS_materials\量化\101_Alphas_项目")
    assert len(expressions) >= 90
    assert expressions[0].id.startswith("reference-")
