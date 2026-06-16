"""AC4 — chat with ui_context payload persists it on the user message row."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, MessageRole

pytestmark = pytest.mark.asyncio


async def _bootstrap(client: AsyncClient) -> tuple[str, str]:
    u = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "ui@aura.test",
                "display_name": "UI Tester",
                "role": "client",
            },
        )
    ).json()
    s = (
        await client.post("/api/v1/sessions", json={"user_id": u["id"]})
    ).json()
    return u["id"], s["id"]


async def test_chat_persists_ui_context_on_user_row(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    _user_id, session_id = await _bootstrap(client)

    ui_context = {
        "market_value": 412345.67,
        "top_positions": [{"symbol": "AAPL", "weight": 0.42}],
        "asset_class_mix": {"equity": 0.85, "bond": 0.10, "cash": 0.05},
    }

    async with client.stream(
        "POST",
        "/api/v1/chat",
        json={
            "session_id": session_id,
            "content": "What's my AAPL exposure?",
            "ui_context": ui_context,
        },
    ) as resp:
        assert resp.status_code == 200
        async for _ in resp.aiter_bytes():
            pass

    # The user message row should have ui_context round-tripped via JSONB.
    row = await async_session.scalar(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == MessageRole.user,
        )
    )
    assert row is not None
    assert row.ui_context == ui_context


async def test_chat_without_ui_context_keeps_column_null(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    _user_id, session_id = await _bootstrap(client)

    async with client.stream(
        "POST",
        "/api/v1/chat",
        json={"session_id": session_id, "content": "hello"},
    ) as resp:
        assert resp.status_code == 200
        async for _ in resp.aiter_bytes():
            pass

    row = await async_session.scalar(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == MessageRole.user,
        )
    )
    assert row is not None
    assert row.ui_context is None
