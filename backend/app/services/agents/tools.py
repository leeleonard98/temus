"""Tool functions exposed to the agent layer.

The Researcher (in researcher.py) is owned by the chat agent and may call
into these helpers without import cycles. Each tool returns plain dicts so
they can be serialised into agent trace events.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services import rag as rag_service
from app.services import web_search as web_search_service


async def rag_search(
    query: str,
    k: int = 5,
    *,
    session: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    """Hybrid RAG search over the corpus.

    Returns up to `k` chunks shaped as `{title, content, score, doc_id}`.
    If a `session` is provided it is reused (preferred — keeps the call inside
    the request transaction); otherwise a one-shot session is opened.
    """
    if session is not None:
        rows = await rag_service.hybrid_search(session, query, k=k)
    else:
        async with AsyncSessionLocal() as s:
            rows = await rag_service.hybrid_search(s, query, k=k)
    return [
        {
            "doc_id": r["doc_id"],
            "title": r["title"],
            "content": r["content"],
            "score": float(r["score"]),
        }
        for r in rows
    ]


async def web_search(query: str, k: int = 5) -> list[dict[str, Any]]:
    """DuckDuckGo web search (A9). See `app.services.web_search` for fallback."""
    return await web_search_service.web_search(query, k=k)
