from brain_alpha_agent.deduplication import deduplicate_candidates, formula_signature
from brain_alpha_agent.generator import generate_candidates


def test_formula_signature_ignores_formatting():
    assert formula_signature(" rank( zscore(roic) ) ") == formula_signature("rank(zscore(roic))")


def test_deduplicate_candidates_keeps_first_formula():
    candidates = generate_candidates()
    assert len(deduplicate_candidates((candidates[0], candidates[0]))) == 1
