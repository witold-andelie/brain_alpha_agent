from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from .reference import ReferenceExpression


def load_course_alpha_templates(path: str | Path) -> tuple[ReferenceExpression, ...]:
    """Safely read the literal ALPHA_EXPRESSIONS list from the course script."""
    source_path = Path(path)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "ALPHA_EXPRESSIONS" for target in node.targets):
            values = ast.literal_eval(node.value)
            return tuple(ReferenceExpression(f"course-{item['id']}-{hashlib.sha256(item['expression'].encode()).hexdigest()[:8]}", item["expression"], str(source_path), f"{item.get('group', '')}: {item.get('description', '')}") for item in values)
    raise ValueError("ALPHA_EXPRESSIONS was not found")
