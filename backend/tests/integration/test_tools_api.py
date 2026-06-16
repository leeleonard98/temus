"""Integration tests for /tools/web_search."""
from __future__ import annotations

import sys
import types

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_web_search_endpoint_returns_results(
    client: AsyncClient, monkeypatch
) -> None:
    """Smoke-test the endpoint with a fake DDGS that returns three rows."""

    class _Fake:
        def __enter__(self):  # noqa: ANN001
            return self

        def __exit__(self, *a, **kw):  # noqa: ANN002
            return False

        def text(self, query, max_results):  # noqa: ANN001
            return [
                {"title": f"R{i}", "href": f"http://x/{i}", "body": f"snip{i}"}
                for i in range(max_results)
            ]

    fake_mod = types.ModuleType("duckduckgo_search")
    fake_mod.DDGS = _Fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "duckduckgo_search", fake_mod)

    res = await client.post(
        "/api/v1/tools/web_search",
        json={"query": "ETF tax", "k": 3},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "ETF tax"
    assert len(body["results"]) == 3
    assert body["results"][0] == {"title": "R0", "url": "http://x/0", "snippet": "snip0"}
