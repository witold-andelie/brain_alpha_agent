from brain_alpha_agent.evaluator import MockBrainEvaluator
from brain_alpha_agent.generator import generate_candidates
from brain_alpha_agent.storage import AlphaStore
from brain_alpha_agent.reference import load_reference_project


def test_candidates_are_deterministic_and_rankable(tmp_path) -> None:
    candidates = generate_candidates()
    assert len(candidates) == 5
    assert candidates == generate_candidates()
    store = AlphaStore(tmp_path / "alpha.db")
    try:
        result = MockBrainEvaluator().evaluate(candidates[0])
        store.save_candidate(candidates[0])
        store.save_evaluation(result)
        assert store.ranked()[0]["id"] == candidates[0].id
    finally:
        store.close()


def test_evaluation_uses_saved_candidate_configuration(tmp_path) -> None:
    candidate = generate_candidates(region="CHN", universe="TOP500", delay=5)[0]
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
        store.save_simulation_result("alpha-1", {"id": "sim-1", "status": "COMPLETE", "Sharpe": 1.2, "Long-Count": 4, "Short-Count": 6, "Universe-Count": 20})
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
    payload_path.write_text(json.dumps({"type": "offline-test"}), encoding="utf-8")

    assert main(["--db", str(db_path), "generate"]) == 0
    store = AlphaStore(db_path)
    try:
        alpha_id = store.ranked()[0]["id"]
    finally:
        store.close()

    assert main(["--db", str(db_path), "simulate", alpha_id, "--payload", str(payload_path), "--offline"]) == 0
    store = AlphaStore(db_path)
    try:
        result = store.simulation_result("offline-simulation-1")
        assert result["alpha_id"] == alpha_id
        assert result["metrics"]["coverage"] == 0.9
    finally:
        store.close()


def test_reference_project_imports_brain_expressions() -> None:
    expressions = load_reference_project(r"D:\CS_materials\量化\101_Alphas_项目")
    assert len(expressions) >= 90
    assert expressions[0].id.startswith("reference-")
