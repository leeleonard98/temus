"""Unit tests for the LLM stub fallback path.

When `settings.openai_api_key` is empty, `stream_chat` must yield a
deterministic echo string token-by-token, so REPL/tests work offline.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_stream_chat_uses_stub_when_no_api_key() -> None:
    """No key → deterministic '[stub] echo: <last user msg>' streamed in chunks."""
    from app.services import llm

    # Force empty key path even if .env supplied one.
    with patch.object(llm.settings, "openai_api_key", ""):
        chunks: list[str] = []
        async for delta in llm.stream_chat(
            messages=[
                {"role": "system", "content": "ignored"},
                {"role": "user", "content": "hello world"},
            ]
        ):
            chunks.append(delta)

    full = "".join(chunks)
    assert full == "[stub] echo: hello world"
    # Must yield more than one chunk (token-by-token-ish).
    assert len(chunks) > 1


@pytest.mark.asyncio
async def test_stream_chat_stub_handles_empty_history() -> None:
    """No user message → still yields a sane stub string, no crash."""
    from app.services import llm

    with patch.object(llm.settings, "openai_api_key", ""):
        chunks = [c async for c in llm.stream_chat(messages=[])]

    assert "".join(chunks).startswith("[stub]")


@pytest.mark.asyncio
async def test_stream_chat_stub_uses_last_user_message_only() -> None:
    """Stub echoes the last user turn, ignoring earlier turns and assistant turns."""
    from app.services import llm

    with patch.object(llm.settings, "openai_api_key", ""):
        chunks = [
            c
            async for c in llm.stream_chat(
                messages=[
                    {"role": "user", "content": "first"},
                    {"role": "assistant", "content": "ack"},
                    {"role": "user", "content": "second"},
                ]
            )
        ]

    assert "".join(chunks) == "[stub] echo: second"
