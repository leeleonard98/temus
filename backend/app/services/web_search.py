"""Web search tool (A9).

Uses DuckDuckGo via the `duckduckgo-search` library if available — no API key
required. Falls back to a small canned set of stub results otherwise so the
agent loop and tests remain deterministic offline.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_STUB_RESULTS: list[dict[str, Any]] = [
    {
        "title": "Investopedia — What is Diversification?",
        "url": "https://www.investopedia.com/terms/d/diversification.asp",
        "snippet": (
            "Diversification is a risk-management strategy that mixes a wide "
            "variety of investments within a portfolio."
        ),
    },
    {
        "title": "Vanguard — Principles for Investing Success",
        "url": "https://corporate.vanguard.com/content/corporatesite/us/en/corp/research/investing-principles.html",
        "snippet": (
            "Four enduring principles for long-term investing success: goals, "
            "balance, cost, discipline."
        ),
    },
]


async def web_search(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Return up to `k` web results for `query`.

    Each item: `{title, url, snippet}`. Synchronous DDG library is run in a
    worker thread; on any error we log and return the stub set so callers
    never see exceptions.
    """
    try:
        from duckduckgo_search import DDGS  # type: ignore
    except Exception:  # pragma: no cover -- dep missing
        logger.info("duckduckgo-search not installed; returning stub results")
        return _STUB_RESULTS[:k]

    def _run() -> list[dict[str, Any]]:
        with DDGS() as ddg:
            return [
                {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                for r in ddg.text(query, max_results=k)
            ]

    try:
        results = await asyncio.to_thread(_run)
    except Exception as e:  # network / rate-limit / API change
        logger.warning("web_search failed (%s); falling back to stubs", e)
        return _STUB_RESULTS[:k]

    return results or _STUB_RESULTS[:k]
