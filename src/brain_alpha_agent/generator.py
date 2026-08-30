from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .deduplication import deduplicate_candidates
from .domain import AlphaCandidate, KnowledgeItem
from .formula import DEFAULT_OPERATORS, validate_formula


@dataclass(frozen=True)
class AlphaTemplate:
    key: str
    target_regime: str
    hypothesis: str
    formula: str
    profiles: frozenset[str]


TEMPLATES = (
    AlphaTemplate(
        "value_quality",
        "baseline",
        "质量与估值相对优势",
        "rank(add(zscore(roic), zscore(earnings_yield)))",
        frozenset({"baseline", "robust"}),
    ),
    AlphaTemplate(
        "growth_quality",
        "baseline",
        "成长质量的横截面排序",
        "rank(add(zscore(revenue_growth), zscore(cashflow_yield)))",
        frozenset({"baseline", "robust"}),
    ),
    AlphaTemplate(
        "mean_reversion",
        "whipsaw",
        "短期价格偏离后的均值回归",
        "rank(subtract(zscore(delay(close, 5)), zscore(close)))",
        frozenset({"baseline", "robust", "whipsaw"}),
    ),
    AlphaTemplate(
        "volume_confirmation",
        "trend",
        "成交量确认价格趋势；用于与反转候选形成低相关对照",
        "rank(multiply(zscore(returns), zscore(adv20)))",
        frozenset({"baseline", "robust"}),
    ),
    AlphaTemplate(
        "low_volatility",
        "stress",
        "低波动资产的风险调整优势",
        "rank(subtract(zscore(earnings_yield), zscore(volatility_20d)))",
        frozenset({"baseline", "robust", "whipsaw"}),
    ),
    AlphaTemplate(
        "smoothed_reversion",
        "whipsaw",
        "对短期反转信号做线性衰减，降低快速翻向造成的换手",
        "rank(ts_decay_linear(subtract(delay(close, 5), close), 10))",
        frozenset({"robust", "whipsaw"}),
    ),
    AlphaTemplate(
        "slow_momentum_defensive",
        "transition",
        "慢速收益趋势减去短期波动，用作转折期的风险调整趋势对照",
        "rank(subtract(zscore(ts_mean(returns, 20)), zscore(ts_std_dev(returns, 20))))",
        frozenset({"robust"}),
    ),
    AlphaTemplate(
        "fundamental_anchor",
        "stress",
        "使用质量与现金流收益率构成低频锚，减少价格甩尾主导候选排序",
        "rank(add(zscore(roic), zscore(cashflow_yield)))",
        frozenset({"robust", "whipsaw"}),
    ),
)

STRATEGY_PROFILES = frozenset({"baseline", "robust", "whipsaw"})
GENERATION_VERSION = "v2"


def generate_candidates(
    *,
    region: str = "USA",
    universe: str = "TOP3000",
    delay: int = 1,
    neutralization: str = "SUBINDUSTRY",
    knowledge: tuple[KnowledgeItem, ...] = (),
    profile: str = "robust",
) -> tuple[AlphaCandidate, ...]:
    if profile not in STRATEGY_PROFILES:
        raise ValueError(f"unknown strategy profile: {profile}")
    if delay not in {0, 1}:
        raise ValueError("candidate delay must be 0 or 1")

    trusted_topics = [
        item.topic
        for item in knowledge
        if 0.0 <= item.confidence <= 1.0 and item.confidence >= 0.5
    ][:3]
    bias = (
        "；参考已筛选研究经验：" + "、".join(trusted_topics) if trusted_topics else ""
    )
    candidates = []
    for template in TEMPLATES:
        if profile not in template.profiles:
            continue
        fields = validate_formula(template.formula)
        alpha_id = hashlib.sha256(
            f"{region}|{universe}|{delay}|{neutralization}|{template.formula}".encode()
        ).hexdigest()[:16]
        source = (
            f"template:{GENERATION_VERSION}:{template.key}:{template.target_regime}"
        )
        candidates.append(
            AlphaCandidate(
                alpha_id,
                template.formula,
                template.hypothesis + bias,
                fields,
                tuple(sorted(set(_operators(template.formula)))),
                region,
                universe,
                delay,
                neutralization,
                source,
            )
        )
    return deduplicate_candidates(candidates)


def candidate_strategy(candidate: AlphaCandidate) -> dict[str, str]:
    parts = candidate.source.split(":", 3)
    if len(parts) == 4 and parts[0] == "template":
        return {"version": parts[1], "family": parts[2], "target_regime": parts[3]}
    return {
        "version": "unknown",
        "family": candidate.source,
        "target_regime": "unknown",
    }


def _operators(formula: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
        if token in DEFAULT_OPERATORS
    )
