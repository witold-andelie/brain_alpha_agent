from __future__ import annotations

import re


class FormulaValidationError(ValueError):
    pass


DEFAULT_FIELDS = frozenset({
    "close", "open", "high", "low", "volume", "returns", "vwap", "cap", "adv5", "adv10", "adv15", "adv20", "adv30", "adv40", "adv50", "adv60", "adv81", "adv120", "adv150", "adv180", "volatility_20d",
    "book_value", "earnings_yield", "roic", "revenue_growth", "cashflow_yield",
})
DEFAULT_OPERATORS = frozenset({
    "rank", "zscore", "log", "abs", "sign", "delta", "delay", "ts_mean", "ts_std_dev",
    "ts_rank", "ts_decay_linear", "ts_sum", "ts_product", "ts_correlation", "ts_covariance", "ts_arg_max", "ts_arg_min", "ts_delta", "add", "subtract", "multiply", "divide", "min", "max", "sqrt", "power", "if_else", "indneutralize", "signed_power", "scale", "correlation", "covariance", "product",
})
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[-+]?\d+(?:\.\d+)?|[(),.+*/-]")


def validate_formula(
    formula: str,
    *,
    fields: frozenset[str] = DEFAULT_FIELDS,
    operators: frozenset[str] = DEFAULT_OPERATORS,
    max_length: int = 500,
    max_depth: int = 8,
) -> tuple[str, ...]:
    """Validate a BRAIN-style expression without executing arbitrary code."""
    text = formula.strip()
    if not text or len(text) > max_length:
        raise FormulaValidationError("formula is empty or exceeds the length limit")
    if any(char in text for char in "{}[];=\\\"'"):
        raise FormulaValidationError("formula contains a forbidden character")
    tokens = _TOKEN.findall(text)
    if "".join(tokens).replace(" ", "") != re.sub(r"\s+", "", text):
        raise FormulaValidationError("formula contains an unsupported token")
    depth = 0
    seen_fields: set[str] = set()
    for token in tokens:
        if token == "(":
            depth += 1
            if depth > max_depth:
                raise FormulaValidationError("formula nesting exceeds the depth limit")
        elif token == ")":
            depth -= 1
            if depth < 0:
                raise FormulaValidationError("unbalanced parentheses")
        elif token[0].isalpha() or token[0] == "_":
            if token in operators:
                continue
            if token not in fields:
                raise FormulaValidationError(f"unknown field or operator: {token}")
            seen_fields.add(token)
    if depth != 0:
        raise FormulaValidationError("unbalanced parentheses")
    return tuple(sorted(seen_fields))
