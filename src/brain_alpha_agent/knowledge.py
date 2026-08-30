from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .domain import KnowledgeItem


def import_revenue_knowledge(path: str | Path) -> tuple[KnowledgeItem, ...]:
    """Import only aggregate learning observations, never broker positions."""
    connection = sqlite3.connect(path)
    try:
        items: list[KnowledgeItem] = []
        state = connection.execute("SELECT attack_weight, defense_weight, observations, last_return, max_drawdown FROM learning_state WHERE id = 1").fetchone()
        if state:
            topic = "paper portfolio risk regime"
            hypothesis = f"Attack weight {state[0]:.2f}, defense weight {state[1]:.2f}, last return {state[3]:.4f}, max drawdown {state[4]:.4f}."
            item_id = hashlib.sha256(hypothesis.encode()).hexdigest()[:16]
            items.append(KnowledgeItem(item_id, "revenue", topic, hypothesis, 0.5, "revenue_agent", datetime.now(timezone.utc), f"observations={state[2]}"))
        return tuple(items)
    finally:
        connection.close()
