"""Unit tests for web_search service stub fallback (A9)."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_web_search_returns_stub_when_ddg_errors(monkeypatch) -> None:
    """If DDG raises, we never propagate — return canned stubs instead."""
    from app.services import web_search as ws

    class _Boom:
        def __enter__(self):  # noqa: ANN001
            return self

        def __exit__(self, *a, **kw):  # noqa: ANN002
            return False

        def text(self, *a, **kw):  # noqa: ANN002
            raise RuntimeError("rate limited")

    # Make the import succeed but the call blow up.
    import sys
    import types

    fake_mod = types.ModuleType("duckduckgo_search")
    fake_mod.DDGS = _Boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "duckduckgo_search", fake_mod)

    out = await ws.web_search("anything", k=2)
    assert len(out) <= 2
    assert all({"title", "url", "snippet"} <= set(r.keys()) for r in out)


@pytest.mark.asyncio
async def test_web_search_returns_real_when_ddg_succeeds(monkeypatch) -> None:
    """Happy-path shape contract: title/url/snippet keys, k respected."""
    from app.services import web_search as ws

    class _Fake:
        def __enter__(self):  # noqa: ANN001
            return self

        def __exit__(self, *a, **kw):  # noqa: ANN002
            return False

        def text(self, query, max_results):  # noqa: ANN001
            return [
                {"title": "T1", "href": "http://a", "body": "b1"},
                {"title": "T2", "href": "http://b", "body": "b2"},
                {"title": "T3", "href": "http://c", "body": "b3"},
            ][:max_results]

    import sys
    import types

    fake_mod = types.ModuleType("duckduckgo_search")
    fake_mod.DDGS = _Fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "duckduckgo_search", fake_mod)

    out = await ws.web_search("hello", k=2)
    assert len(out) == 2
    assert out[0] == {"title": "T1", "url": "http://a", "snippet": "b1"}
