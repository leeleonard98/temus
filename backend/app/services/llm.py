"""Thin async wrapper over OpenAI chat-completions streaming.

If `settings.openai_api_key` is empty, `stream_chat` yields a deterministic
stub response token-by-token. This keeps the REPL and the test suite
operable without network or credentials.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from app.core.config import settings

logger = logging.getLogger(__name__)
_warned_stub = False


def _last_user_message(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content", ""))
    return ""


async def _stub_stream(messages: list[dict]) -> AsyncIterator[str]:
    """Deterministic offline stand-in for the LLM."""
    global _warned_stub
    if not _warned_stub:
        logger.warning(
            "OPENAI_API_KEY is empty — using offline stub LLM. "
            "Set OPENAI_API_KEY to use a real model."
        )
        _warned_stub = True

    text = f"[stub] echo: {_last_user_message(messages)}".rstrip()
    # Yield a few chars at a time to mimic streaming. Tiny sleep so consumers
    # can interleave (e.g. SSE flush, REPL print).
    chunk_size = 4
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
        await asyncio.sleep(0)


async def stream_chat(
    messages: list[dict], model: str | None = None
) -> AsyncIterator[str]:
    """Stream content deltas from the configured chat model.

    Falls back to a deterministic stub when no API key is configured.
    """
    if not settings.openai_api_key:
        async for chunk in _stub_stream(messages):
            yield chunk
        return

    # Live path — imported lazily so missing creds don't crash module import
    # in offline test runs.
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=model or settings.openai_model,
        messages=messages,
        stream=True,
    )
    async for event in response:
        # Each event has .choices[0].delta.content (may be None on role frames).
        if not event.choices:
            continue
        delta = event.choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            yield content


# Wrap with Langfuse tracing if keys are configured. No-op identity wrap when
# they're not (so offline tests stay unchanged). Imported here, after the
# function is defined, so the module is self-contained.
from app.services.tracing import wrap_stream_chat as _wrap  # noqa: E402

stream_chat = _wrap(stream_chat)  # type: ignore[assignment]


# ---------- non-streaming tool-call helper ----------


async def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    *,
    model: str | None = None,
) -> dict:
    """Single-shot chat completion with tool-call support.

    Returns a dict mirroring the assistant message: {"content": str|None,
    "tool_calls": [{"id": str, "name": str, "arguments": dict}, ...]}.
    Falls back to {"content": "[stub-no-tools]", "tool_calls": []} when no
    API key is configured — tests then patch this function directly.
    """
    if not settings.openai_api_key:
        return {"content": "[stub-no-tools]", "tool_calls": []}

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    kwargs: dict = {
        "model": model or settings.openai_model,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = await client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    out_calls: list[dict] = []
    for tc in msg.tool_calls or []:
        try:
            import json as _json

            args = _json.loads(tc.function.arguments or "{}")
        except ValueError:
            args = {}
        out_calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
    return {"content": msg.content, "tool_calls": out_calls}
