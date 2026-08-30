from __future__ import annotations

import math
from typing import Any


def coverage(
    long_count: int | float,
    short_count: int | float,
    universe_count: int | float | None = None,
) -> float | None:
    """Return a validated 0-1 coverage ratio; never substitute raw position count."""
    if universe_count is None:
        return None
    try:
        long_value = float(long_count)
        short_value = float(short_count)
        universe_value = float(universe_count)
    except (TypeError, ValueError):
        return None
    if not all(
        math.isfinite(value) for value in (long_value, short_value, universe_value)
    ):
        return None
    if long_value < 0 or short_value < 0 or universe_value <= 0:
        return None
    ratio = (long_value + short_value) / universe_value
    return ratio if 0.0 <= ratio <= 1.0 else None


def extract_simulation_metrics(
    payload: dict[str, Any],
) -> dict[str, float | int | None]:
    long_count = _first(payload, "longCount", "long_count", "Long-Count")
    short_count = _first(payload, "shortCount", "short_count", "Short-Count")
    universe_count = _first(
        payload, "universeCount", "universe_count", "Universe-Count"
    )
    return {
        "sharpe": _first(payload, "sharpe", "Sharpe"),
        "fitness": _first(payload, "fitness", "Fitness"),
        "returns": _first(payload, "returns", "Returns"),
        "turnover": _first(payload, "turnover", "Turnover"),
        "drawdown": _first(payload, "drawdown", "Drawdown"),
        "weight": _first(payload, "weight", "Weight"),
        "correlation_to_existing": _first(
            payload, "correlationToExisting", "correlation_to_existing", "Correlation"
        ),
        "long_count": long_count,
        "short_count": short_count,
        "coverage": coverage(long_count, short_count, universe_count)
        if long_count is not None and short_count is not None
        else None,
    }


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if payload.get(key) is not None:
            return payload[key]
    return None
