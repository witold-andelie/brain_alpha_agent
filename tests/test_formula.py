import pytest

from brain_alpha_agent.formula import FormulaValidationError, validate_formula


def test_formula_allowlist_returns_fields() -> None:
    assert validate_formula("rank(zscore(roic))") == ("roic",)


def test_formula_rejects_unknown_and_code() -> None:
    with pytest.raises(FormulaValidationError):
        validate_formula("rank(secret_field)")
    with pytest.raises(FormulaValidationError):
        validate_formula("__import__('os')")


@pytest.mark.parametrize(
    "formula",
    ["rank()", "rank(zscore(roic))+", "close open", ".", "add(close)"],
)
def test_formula_rejects_syntactically_incomplete_expressions(formula) -> None:
    with pytest.raises(FormulaValidationError):
        validate_formula(formula)


def test_formula_supports_grouped_official_style_expression() -> None:
    fields = validate_formula("-group_rank(close-open, subindustry)")

    assert fields == ("close", "open", "subindustry")
