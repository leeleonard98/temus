"""Unit tests for tracing decorator no-op behaviour."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_traced_is_passthrough_when_keys_unset() -> None:
    """No Langfuse keys → @traced runs the function and returns its result."""
    from app.services import tracing

    with patch.object(tracing.settings, "langfuse_public_key", ""), patch.object(
        tracing.settings, "langfuse_secret_key", ""
    ):
        # Reset the module-level memo so the patched settings take effect.
        tracing._client = None
        tracing._initialised = False

        @tracing.traced("unit-test")
        async def f(x: int) -> int:
            return x * 2

        assert await f(21) == 42


def test_wrap_stream_chat_is_identity_when_disabled() -> None:
    """Tracing off → wrap_stream_chat returns the same callable unchanged."""
    from app.services import tracing

    with patch.object(tracing.settings, "langfuse_public_key", ""), patch.object(
        tracing.settings, "langfuse_secret_key", ""
    ):
        tracing._client = None
        tracing._initialised = False

        async def fn():
            return 1

        wrapped = tracing.wrap_stream_chat(fn)
        assert wrapped is fn


@pytest.mark.asyncio
async def test_wrap_stream_chat_handles_async_generators() -> None:
    """When tracing is on, wrap must yield through an async-generator stream
    rather than awaiting it (stream_chat is an async generator, not a coroutine).
    """
    from app.services import tracing

    # Fake "client" + observation context that records the span lifecycle.
    events: list[str] = []

    class _Obs:
        def update(self, **kw):
            events.append(f"update:{kw.get('output', '')}")

    class _Ctx:
        def __enter__(self):
            events.append("enter")
            return _Obs()

        def __exit__(self, *a):
            events.append("exit")
            return False

    class _Client:
        def start_as_current_observation(self, **kw):
            events.append(f"start:{kw.get('name')}:{kw.get('model')}")
            return _Ctx()

    tracing._client = _Client()
    tracing._initialised = True
    try:
        async def fake_stream(messages, model=None):
            for tok in ["a", "b", "c"]:
                yield tok

        wrapped = tracing.wrap_stream_chat(fake_stream)
        out: list[str] = []
        async for tok in wrapped([{"role": "user", "content": "hi"}], model="m"):
            out.append(tok)
        assert out == ["a", "b", "c"]
        assert events == [
            "start:stream_chat:m",
            "enter",
            "update:abc",
            "exit",
        ]
    finally:
        tracing._client = None
        tracing._initialised = False


@pytest.mark.asyncio
async def test_stream_chat_module_wrapped_remains_async_generator() -> None:
    """`llm.stream_chat` is wrapped at module load; the wrap must preserve the
    async-generator contract so existing callers (chat router, REPL) work.
    """
    from app.services import llm

    msgs = [{"role": "user", "content": "hello"}]
    chunks: list[str] = []
    async for tok in llm.stream_chat(msgs):
        chunks.append(tok)
    assert "".join(chunks).startswith("[stub]")
