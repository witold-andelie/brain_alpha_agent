from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReferenceExpression:
    id: str
    expression: str
    source_path: str
    notes: str = ""


def load_reference_project(path: str | Path) -> tuple[ReferenceExpression, ...]:
    root = Path(path)
    expression_file = root / "brain" / "brain_expressions.txt"
    if not expression_file.exists():
        raise FileNotFoundError(f"BRAIN expression file not found: {expression_file}")
    expressions: list[ReferenceExpression] = []
    current_id: str | None = None
    current: list[str] = []
    for raw in expression_file.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^Alpha #(\d+):\s*(.*)$", raw.strip())
        if match:
            if current_id is not None and current:
                expressions.append(_make(current_id, " ".join(current), expression_file))
            current_id = match.group(1)
            current = [match.group(2)]
        elif current_id is not None and raw.strip() and not raw.startswith("="):
            current.append(raw.strip())
    if current_id is not None and current:
        expressions.append(_make(current_id, " ".join(current), expression_file))
    return tuple(expressions)


def _make(number: str, expression: str, source: Path) -> ReferenceExpression:
    digest = hashlib.sha256(f"{number}:{expression}".encode()).hexdigest()[:12]
    return ReferenceExpression(f"reference-{number.zfill(3)}-{digest}", expression, str(source))
