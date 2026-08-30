from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from .domain import KnowledgeItem


MOLTBOOK_BASE_URL = "https://www.moltbook.com/api/v1"


class MoltbookError(RuntimeError):
    pass


class MoltbookClient:
    """Read-only Moltbook client. It deliberately exposes no write methods."""

    def __init__(self, *, api_key: str | None = None, session: Any | None = None) -> None:
        self.api_key = api_key or os.getenv("MOLTBOOK_API_KEY", "")
        if not self.api_key:
            raise MoltbookError("MOLTBOOK_API_KEY is required")
        try:
            import requests
        except ImportError as error:
            raise MoltbookError("install the optional research dependency: pip install -e '.[research]'") from error
        self.session = session or requests.Session()

    def search(self, query: str, *, limit: int = 20, result_type: str = "all", cursor: str | None = None) -> dict[str, Any]:
        if not query.strip() or len(query) > 500:
            raise ValueError("query must contain 1-500 characters")
        if result_type not in {"posts", "comments", "all"}:
            raise ValueError("result_type must be posts, comments, or all")
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        params: dict[str, Any] = {"q": query, "type": result_type, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        url = f"{MOLTBOOK_BASE_URL}/search?{urlencode(params)}"
        response = self.session.get(url, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=30)
        if response.status_code >= 400:
            raise MoltbookError(f"Moltbook search failed: HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise MoltbookError("Moltbook search response must be a JSON object")
        return payload


def search_as_knowledge(client: MoltbookClient, query: str, *, limit: int = 20) -> tuple[KnowledgeItem, ...]:
    payload = client.search(query, limit=limit, result_type="all")
    items: list[KnowledgeItem] = []
    for result in payload.get("results", []):
        content = str(result.get("content") or "").strip()
        title = str(result.get("title") or "Moltbook research discussion").strip()
        if not content:
            continue
        post_id = str(result.get("post_id") or result.get("id") or hashlib.sha256(content.encode()).hexdigest()[:16])
        source_url = f"https://www.moltbook.com/post/{post_id}"
        evidence = f"source={source_url}; similarity={result.get('similarity', '')}; query={query}"
        hypothesis = content[:2000]
        observed_at = _parse_datetime(result.get("created_at"))
        item_id = hashlib.sha256(f"moltbook:{post_id}:{content}".encode()).hexdigest()[:16]
        items.append(KnowledgeItem(item_id, "moltbook", title[:200], hypothesis, 0.2, "moltbook", observed_at, evidence))
    return tuple(items)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)
