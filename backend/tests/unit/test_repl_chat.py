"""Unit tests for the REPL chat client.

We test the pure helpers (`_build_messages`, `_parse_args`) that don't need
a DB. The DB-touching path is exercised end-to-end via the chat API tests
(test_chat_api.py::test_chat_multi_turn_replays_full_history) which cover
the same replay invariant.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.db.models import ChatMessage, MessageRole, UserRole
from scripts import repl_chat


def _msg(role: MessageRole, content: str, at: int) -> ChatMessage:
    return ChatMessage(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        role=role,
        content=content,
        created_at=datetime(2026, 1, 1, 0, 0, at, tzinfo=UTC),
    )


def test_build_messages_prepends_client_system_prompt_and_replays_in_order() -> None:
    history = [
        _msg(MessageRole.user, "hi", 1),
        _msg(MessageRole.assistant, "hello", 2),
        _msg(MessageRole.user, "what's my name?", 3),
    ]
    msgs = repl_chat._build_messages(UserRole.client, history)

    assert msgs[0]["role"] == "system"
    assert "financial GPS" in msgs[0]["content"]  # client persona
    assert [m["role"] for m in msgs[1:]] == ["user", "assistant", "user"]
    assert [m["content"] for m in msgs[1:]] == ["hi", "hello", "what's my name?"]


def test_build_messages_uses_advisor_prompt_for_advisor_role() -> None:
    msgs = repl_chat._build_messages(UserRole.advisor, [])
    assert len(msgs) == 1
    assert msgs[0]["role"] == "system"
    assert "command center" in msgs[0]["content"]


def test_build_messages_does_not_truncate_long_history() -> None:
    """Phase 1 = full replay (A12 will add summarization)."""
    history = [_msg(MessageRole.user, f"turn-{i}", i) for i in range(50)]
    msgs = repl_chat._build_messages(UserRole.client, history)
    # 1 system + 50 turns = 51.
    assert len(msgs) == 51


def test_parse_args_defaults() -> None:
    ns = repl_chat._parse_args([])
    assert ns.role == "client"
    assert ns.email is None
    assert ns.session is None


def test_parse_args_advisor_with_session() -> None:
    sid = uuid.uuid4()
    ns = repl_chat._parse_args(
        ["--role", "advisor", "--email", "x@y.z", "--session-id", str(sid)]
    )
    assert ns.role == "advisor"
    assert ns.email == "x@y.z"
    assert ns.session == sid


def test_parse_args_rejects_unknown_role() -> None:
    with pytest.raises(SystemExit):
        repl_chat._parse_args(["--role", "intern"])
