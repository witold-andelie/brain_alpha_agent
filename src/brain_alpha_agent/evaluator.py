from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Protocol

from .domain import AlphaCandidate, EvaluationResult


class BrainEvaluator(Protocol):
    def evaluate(self, candidate: AlphaCandidate) -> EvaluationResult:
        ...


class MockBrainEvaluator:
    """Deterministic local evaluator used until an official BRAIN adapter is configured."""

    def evaluate(self, candidate: AlphaCandidate) -> EvaluationResult:
        digest = hashlib.sha256(candidate.formula.encode()).digest()
        raw = [byte / 255 for byte in digest[:7]]
        return EvaluationResult(
            candidate.id,
            fitness=0.4 + raw[0] * 1.2,
            sharpe=0.2 + raw[1] * 1.6,
            returns=-0.02 + raw[2] * 0.12,
            turnover=0.1 + raw[3] * 0.7,
            drawdown=0.02 + raw[4] * 0.25,
            weight=0.4 + raw[5] * 0.6,
            sub_universe_sharpe=raw[6] * 1.8,
            period_stability=0.4 + raw[0] * 0.5,
            evaluated_at=datetime.now(timezone.utc),
        )
