from __future__ import annotations

import re
from collections.abc import Iterable

from .domain import AlphaCandidate


def formula_signature(formula: str) -> str:
    """Return a stable signature for formatting-only formula duplicates."""
    return re.sub(r"\s+", "", formula).casefold()


def deduplicate_candidates(candidates: Iterable[AlphaCandidate]) -> tuple[AlphaCandidate, ...]:
    seen: set[str] = set()
    unique: list[AlphaCandidate] = []
    for candidate in candidates:
        signature = formula_signature(candidate.formula)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(candidate)
    return tuple(unique)
