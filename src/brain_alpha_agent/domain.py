from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AlphaCandidate:
    id: str
    formula: str
    hypothesis: str
    fields: tuple[str, ...]
    operators: tuple[str, ...]
    region: str
    universe: str
    delay: int
    neutralization: str
    source: str = "template"


@dataclass(frozen=True)
class EvaluationResult:
    alpha_id: str
    fitness: float
    sharpe: float
    returns: float
    turnover: float
    drawdown: float
    weight: float
    sub_universe_sharpe: float
    period_stability: float
    evaluated_at: datetime
    evaluator: str = "mock"

    @property
    def quality_score(self) -> float:
        robustness = (max(0.0, min(1.0, self.sub_universe_sharpe / 2.0)) + self.period_stability) / 2.0
        return (
            0.30 * max(0.0, min(1.0, self.fitness / 2.0))
            + 0.20 * max(0.0, min(1.0, self.sharpe / 2.0))
            + 0.15 * robustness
            + 0.15 * max(0.0, min(1.0, self.weight))
            + 0.10 * max(0.0, min(1.0, self.returns / 0.1))
            - 0.10 * max(0.0, min(1.0, self.turnover))
            - 0.10 * max(0.0, min(1.0, self.drawdown))
        )


@dataclass(frozen=True)
class KnowledgeItem:
    id: str
    domain: str
    topic: str
    hypothesis: str
    confidence: float
    source_agent: str
    observed_at: datetime
    evidence: str = ""
