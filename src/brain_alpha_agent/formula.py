from __future__ import annotations

import re
from dataclasses import dataclass


class FormulaValidationError(ValueError):
    pass


DEFAULT_FIELDS = frozenset(
    {
        "close",
        "open",
        "high",
        "low",
        "volume",
        "returns",
        "vwap",
        "cap",
        "adv5",
        "adv10",
        "adv15",
        "adv20",
        "adv30",
        "adv40",
        "adv50",
        "adv60",
        "adv81",
        "adv120",
        "adv150",
        "adv180",
        "volatility_20d",
        "book_value",
        "earnings_yield",
        "roic",
        "revenue_growth",
        "cashflow_yield",
        "market",
        "sector",
        "industry",
        "subindustry",
    }
)
DEFAULT_OPERATORS = frozenset(
    {
        "rank",
        "zscore",
        "log",
        "abs",
        "sign",
        "delta",
        "delay",
        "ts_mean",
        "ts_std_dev",
        "ts_rank",
        "ts_decay_linear",
        "ts_sum",
        "ts_product",
        "ts_correlation",
        "ts_covariance",
        "ts_arg_max",
        "ts_arg_min",
        "ts_delta",
        "add",
        "subtract",
        "multiply",
        "divide",
        "min",
        "max",
        "sqrt",
        "power",
        "if_else",
        "indneutralize",
        "group_rank",
        "group_neutralize",
        "signed_power",
        "scale",
        "correlation",
        "covariance",
        "product",
    }
)

# Known operator arities. None means no upper bound.
_ARITY: dict[str, tuple[int, int | None]] = {
    **{name: (1, 1) for name in ("rank", "zscore", "log", "abs", "sign", "sqrt")},
    "scale": (1, 2),
    **{
        name: (2, 2)
        for name in (
            "delta",
            "delay",
            "ts_mean",
            "ts_std_dev",
            "ts_rank",
            "ts_decay_linear",
            "ts_sum",
            "ts_product",
            "ts_arg_max",
            "ts_arg_min",
            "ts_delta",
            "subtract",
            "divide",
            "power",
            "signed_power",
            "indneutralize",
            "group_rank",
            "group_neutralize",
        )
    },
    **{
        name: (3, 3)
        for name in (
            "ts_correlation",
            "ts_covariance",
            "correlation",
            "covariance",
            "if_else",
        )
    },
    **{name: (2, None) for name in ("add", "multiply", "min", "max", "product")},
}

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|(?:\d+(?:\.\d+)?|\.\d+)|[(),+*/-]")


def validate_formula(
    formula: str,
    *,
    fields: frozenset[str] = DEFAULT_FIELDS,
    operators: frozenset[str] = DEFAULT_OPERATORS,
    max_length: int = 500,
    max_depth: int = 8,
) -> tuple[str, ...]:
    """Parse and validate a BRAIN-style arithmetic expression without execution."""
    text = formula.strip()
    if not text or len(text) > max_length:
        raise FormulaValidationError("formula is empty or exceeds the length limit")
    if any(char in text for char in "{}[];=\\\"'"):
        raise FormulaValidationError("formula contains a forbidden character")

    tokens = _TOKEN.findall(text)
    if "".join(tokens) != re.sub(r"\s+", "", text):
        raise FormulaValidationError("formula contains an unsupported token")

    parser = _FormulaParser(tokens, fields, operators, max_depth)
    parser.parse()
    return tuple(sorted(parser.seen_fields))


@dataclass
class _FormulaParser:
    tokens: list[str]
    fields: frozenset[str]
    operators: frozenset[str]
    max_depth: int
    position: int = 0
    depth: int = 0

    def __post_init__(self) -> None:
        self.seen_fields: set[str] = set()

    def parse(self) -> None:
        self._expression()
        if self._peek() is not None:
            raise FormulaValidationError(f"unexpected token: {self._peek()}")

    def _expression(self, minimum_precedence: int = 0) -> None:
        self._unary()
        precedence = {"+": 1, "-": 1, "*": 2, "/": 2}
        while (token := self._peek()) in precedence and precedence[
            token
        ] >= minimum_precedence:
            self._take()
            self._expression(precedence[token] + 1)

    def _unary(self) -> None:
        if self._peek() in {"+", "-"}:
            self._take()
            self._unary()
            return
        self._primary()

    def _primary(self) -> None:
        token = self._take()
        if token is None:
            raise FormulaValidationError(
                "formula ends before an expression is complete"
            )
        if token == "(":
            self._enter_depth()
            self._expression()
            self._expect(")")
            self.depth -= 1
            return
        if token[0].isdigit() or token.startswith("."):
            return
        if token[0].isalpha() or token[0] == "_":
            if self._peek() == "(":
                self._function_call(token)
                return
            if token not in self.fields:
                raise FormulaValidationError(f"unknown field: {token}")
            self.seen_fields.add(token)
            return
        raise FormulaValidationError(f"unexpected token: {token}")

    def _function_call(self, operator: str) -> None:
        if operator not in self.operators:
            raise FormulaValidationError(f"unknown operator: {operator}")
        self._expect("(")
        self._enter_depth()
        arguments = 0
        if self._peek() != ")":
            while True:
                self._expression()
                arguments += 1
                if self._peek() != ",":
                    break
                self._take()
        self._expect(")")
        self.depth -= 1
        minimum, maximum = _ARITY.get(operator, (1, None))
        if arguments < minimum or (maximum is not None and arguments > maximum):
            expected = (
                str(minimum) if minimum == maximum else f"{minimum}-{maximum or 'many'}"
            )
            raise FormulaValidationError(
                f"operator {operator} expects {expected} arguments, got {arguments}"
            )

    def _enter_depth(self) -> None:
        self.depth += 1
        if self.depth > self.max_depth:
            raise FormulaValidationError("formula nesting exceeds the depth limit")

    def _peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def _take(self) -> str | None:
        token = self._peek()
        if token is not None:
            self.position += 1
        return token

    def _expect(self, expected: str) -> None:
        actual = self._take()
        if actual != expected:
            raise FormulaValidationError(
                f"expected {expected}, got {actual or 'end of formula'}"
            )
