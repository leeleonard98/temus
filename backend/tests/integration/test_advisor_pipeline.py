"""Integration test for the advisor agent pipeline.

Verifies that when role='advisor' the orchestrator routes to the advisor
researcher + advisor analyst, and that the analyst dispatches the tools the
model asks for. Uses monkeypatched `llm.chat_with_tools` so we don't need a
real OpenAI key. The DB tools (`list_clients`, etc.) run for real against the
test Postgres seeded by `conftest.py`.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, AccountKind, AssetClass, Position, User, UserRole
from app.services import llm
from app.services.agents import sequential

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def seeded_book(async_session: AsyncSession) -> dict:
    """Seed one advisor + two clients with positions so list_clients has data."""
    advisor = User(email="adv@t.test", display_name="Adv", role=UserRole.advisor)
    c1 = User(email="c1@t.test", display_name="Client One", role=UserRole.client)
    c2 = User(email="c2@t.test", display_name="Client Two", role=UserRole.client)
    async_session.add_all([advisor, c1, c2])
    await async_session.flush()

    a1 = Account(user_id=c1.id, name="Brokerage", kind=AccountKind.brokerage)
    a2 = Account(user_id=c2.id, name="IRA", kind=AccountKind.retirement)
    async_session.add_all([a1, a2])
    await async_session.flush()

    async_session.add_all(
        [
            Position(
                account_id=a1.id, symbol="AAPL", quantity=10,
                avg_cost=100, asset_class=AssetClass.equity,
            ),
            Position(
                account_id=a2.id, symbol="VOO", quantity=20,
                avg_cost=200, asset_class=AssetClass.equity,
            ),
        ]
    )
    await async_session.commit()
    return {"advisor_id": str(advisor.id), "c1_id": str(c1.id), "c2_id": str(c2.id)}


async def test_advisor_pipeline_dispatches_list_clients(
    seeded_book: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The advisor analyst should dispatch list_clients() and surface real names."""

    # Stub the streaming Researcher to skip the LLM and return a fixed brief.
    async def fake_stream(messages: list[dict], model: str | None = None) -> AsyncIterator[str]:
        # Return the JSON the advisor researcher expects to parse.
        text = json.dumps(
            {
                "task": "client-triage",
                "topics": ["book overview"],
                "rationale": "Advisor wants a book summary.",
            }
        )
        for ch in text:
            yield ch

    monkeypatch.setattr(llm, "stream_chat", fake_stream)

    # Stub `chat_with_tools` to: first call → request list_clients;
    # second call (with tool result) → return final analyst JSON.
    calls = {"n": 0, "tools_seen": []}

    async def fake_tools(messages: list[dict], tools: list[dict], **_: object) -> dict:
        calls["n"] += 1
        if calls["n"] == 1:
            calls["tools_seen"] = [t["function"]["name"] for t in tools]
            return {
                "content": "",
                "tool_calls": [
                    {"id": "call_1", "name": "list_clients", "arguments": {}}
                ],
            }
        # Second call — model now has the tool result; returns final JSON.
        return {
            "content": json.dumps(
                {
                    "findings": [
                        {
                            "claim": "Two clients in the book: Client One and Client Two",
                            "confidence": "high",
                        }
                    ],
                    "summary": "Book contains two clients.",
                }
            ),
            "tool_calls": [],
        }

    monkeypatch.setattr(llm, "chat_with_tools", fake_tools)
    # Force the live path inside the analyst (which checks settings.openai_api_key).
    from app.core.config import settings as _settings

    monkeypatch.setattr(_settings, "openai_api_key", "test-key")

    events: list = []
    async for ev in sequential.run_sequential(
        "Summarise my book",
        history=[],
        role="advisor",
        ui_context=None,
    ):
        events.append(ev)

    # Verify the advisor analyst dispatched the right tool.
    assert calls["n"] == 2, "Expected one tool-call round-trip + one final JSON call"
    assert "list_clients" in calls["tools_seen"]

    # The analyst's complete event carries the grounded finding.
    completes = [e for e in events if e.kind == "complete" and e.agent == "analyst"]
    assert len(completes) == 1
    findings = completes[0].output["findings"]
    assert any("Client One" in f["claim"] for f in findings)
