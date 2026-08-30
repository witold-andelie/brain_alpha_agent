from __future__ import annotations

import hashlib

from .domain import AlphaCandidate, KnowledgeItem
from .deduplication import deduplicate_candidates
from .formula import validate_formula


TEMPLATES = (
    ("value_quality", "质量与估值相对优势", "rank(add(zscore(roic), zscore(earnings_yield)))"),
    ("growth_quality", "成长质量的行业中性排序", "rank(add(zscore(revenue_growth), zscore(cashflow_yield)))"),
    ("mean_reversion", "短期价格偏离后的均值回归", "rank(subtract(zscore(delay(close, 5)), zscore(close)))"),
    ("volume_confirmation", "成交量确认价格趋势", "rank(multiply(zscore(returns), zscore(adv20)))"),
    ("low_volatility", "低波动资产的风险调整优势", "rank(subtract(zscore(earnings_yield), zscore(volatility_20d)))"),
)

REFERENCE_PRINCIPLES = (
    "按持有周期区分短期信号和长期基本面信号",
    "优先寻找与现有候选低相关的因子，而不是只追逐单因子 Sharpe",
    "把波动率作为收益状态变量和风险条件，不把 turnover 当成唯一解释变量",
    "用多个时间段、sub-universe 和 region 检查稳健性",
)


def generate_candidates(
    *,
    region: str = "USA",
    universe: str = "TOP3000",
    delay: int = 1,
    neutralization: str = "SUBINDUSTRY",
    knowledge: tuple[KnowledgeItem, ...] = (),
) -> tuple[AlphaCandidate, ...]:
    bias = "；参考共享市场经验：" + "、".join(item.topic for item in knowledge[:3]) if knowledge else ""
    candidates = []
    for key, hypothesis, formula in TEMPLATES:
        fields = validate_formula(formula)
        alpha_id = hashlib.sha256(f"{region}|{universe}|{delay}|{neutralization}|{formula}".encode()).hexdigest()[:12]
        candidates.append(AlphaCandidate(alpha_id, formula, hypothesis + bias, fields, tuple(sorted(set(_operators(formula)))), region, universe, delay, neutralization))
    return deduplicate_candidates(candidates)


def _operators(formula: str) -> tuple[str, ...]:
    from .formula import DEFAULT_OPERATORS
    return tuple(token for token in formula.replace("(", " ").replace(")", " ").replace(",", " ").split() if token in DEFAULT_OPERATORS)
