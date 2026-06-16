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
