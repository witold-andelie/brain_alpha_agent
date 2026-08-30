from brain_alpha_agent.brain_api import BrainClient, BrainConfig, BrainSimulationAdapter, OfflineSimulationSession
from brain_alpha_agent.generator import generate_candidates
from brain_alpha_agent.research import render_payload, run_research


def test_render_payload_replaces_candidate_and_scenario_values():
    candidate = generate_candidates(region="USA")[0]
    rendered = render_payload(
        {"expression": "{{formula}}", "settings": {"region": "{{scenario.region}}", "delay": "{{delay}}"}},
        candidate,
        {"region": "CHN", "delay": 5},
    )

    assert rendered["expression"] == candidate.formula
    assert rendered["settings"] == {"region": "CHN", "delay": 5}


def test_run_research_executes_each_candidate_scenario_and_saves_results():
    candidates = generate_candidates()[:2]
    scenarios = [{"region": "USA"}, {"region": "CHN"}]
    client = BrainClient(BrainConfig(username="offline", password="offline"), session=OfflineSimulationSession())
    adapter = BrainSimulationAdapter(client, sleep=lambda _: None)
    saved = []

    completed = run_research(candidates, scenarios, {"expression": "{{formula}}"}, adapter, lambda alpha_id, result: saved.append((alpha_id, result)))

    assert len(completed) == 4
    assert len(saved) == 4
    assert {item["simulation_id"] for item in completed} == {"offline-simulation-1", "offline-simulation-2", "offline-simulation-3", "offline-simulation-4"}
