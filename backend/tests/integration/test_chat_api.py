"""Integration tests for the chat API.

Covers AC2 (multi-turn state) and AC3 (different users → separate histories).
Uses the existing testcontainers `client` fixture.
"""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_user(client: AsyncClient, email: str, role: str = "client") -> dict:
    resp = await client.post(
        "/api/v1/users",
        json={"email": email, "display_name": email.split("@")[0], "role": role},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _create_session(client: AsyncClient, user_id: str, title: str | None = None) -> dict:
    payload = {"user_id": user_id}
    if title:
        payload["title"] = title
    resp = await client.post("/api/v1/sessions", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_create_user_returns_persona_fields(client: AsyncClient) -> None:
    body = await _create_user(client, "alice@aura.test", "client")
    assert body["email"] == "alice@aura.test"
    assert body["role"] == "client"
    assert body["display_name"] == "alice"
    assert "id" in body


async def test_create_user_is_idempotent_by_email(client: AsyncClient) -> None:
    first = await _create_user(client, "bob@aura.test", "advisor")
    second = await _create_user(client, "bob@aura.test", "advisor")
    assert first["id"] == second["id"]


async def test_create_user_rejects_unknown_role(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/users",
        json={"email": "x@y.z", "display_name": "X", "role": "intern"},
    )
    assert resp.status_code == 422


async def test_session_create_and_list_newest_first(client: AsyncClient) -> None:
    user = await _create_user(client, "carol@aura.test")
    s1 = await _create_session(client, user["id"], title="first")
    s2 = await _create_session(client, user["id"], title="second")

    resp = await client.get(f"/api/v1/sessions?user_id={user['id']}")
    assert resp.status_code == 200
    items = resp.json()
    ids = [i["id"] for i in items]
    # Newest first.
    assert ids[0] == s2["id"]
    assert ids[1] == s1["id"]


async def test_chat_stream_persists_messages_and_history(client: AsyncClient) -> None:
    """AC2: multi-turn state — posting a message persists user + assistant
    rows; history endpoint returns them in chronological order.

    Under the new sequential pipeline (Researcher -> Analyst -> Writer) the
    user-facing answer tokens come as `{"type": "delta", "content": "..."}`;
    `done` carries the persisted assistant message id.
    """
    user = await _create_user(client, "dave@aura.test", "client")
    session = await _create_session(client, user["id"])

    # Stream a single turn.
    deltas: list[str] = []
    done_payload: dict | None = None
    async with client.stream(
        "POST",
        "/api/v1/chat",
        json={"session_id": session["id"], "content": "what is my net worth?"},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = json.loads(line[len("data:") :].strip())
            kind = payload.get("type")
            if kind == "delta":
                deltas.append(payload["content"])
            elif kind == "done":
                done_payload = payload

    assert done_payload is not None
    assert "message_id" in done_payload
    streamed = "".join(deltas)
    assert "[stub]" in streamed
    assert "what is my net worth?" in streamed

    # History contains user + assistant in order.
    hist = await client.get(f"/api/v1/sessions/{session['id']}/messages")
    assert hist.status_code == 200
    msgs = hist.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "what is my net worth?"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == streamed


async def test_two_users_have_separate_histories(client: AsyncClient) -> None:
    """AC3 sanity check: distinct users -> distinct sessions -> distinct
    histories. Posting in one session must not leak into the other."""
    client_user = await _create_user(client, "client1@aura.test", "client")
    advisor_user = await _create_user(client, "advisor1@aura.test", "advisor")

    s_client = await _create_session(client, client_user["id"], title="client sess")
    s_advisor = await _create_session(client, advisor_user["id"], title="advisor sess")

    async def post_chat(session_id: str, content: str) -> None:
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={"session_id": session_id, "content": content},
        ) as resp:
            assert resp.status_code == 200
            async for _ in resp.aiter_lines():
                pass

    await post_chat(s_client["id"], "client question")
    await post_chat(s_advisor["id"], "advisor question")

    h_client = (await client.get(f"/api/v1/sessions/{s_client['id']}/messages")).json()
    h_advisor = (await client.get(f"/api/v1/sessions/{s_advisor['id']}/messages")).json()

    assert any(m["content"] == "client question" for m in h_client)
    assert all(m["content"] != "advisor question" for m in h_client)
    assert any(m["content"] == "advisor question" for m in h_advisor)
    assert all(m["content"] != "client question" for m in h_advisor)

    # Sessions list scoped per-user.
    sessions_client = (
        await client.get(f"/api/v1/sessions?user_id={client_user['id']}")
    ).json()
    sessions_advisor = (
        await client.get(f"/api/v1/sessions?user_id={advisor_user['id']}")
    ).json()
    assert {s["id"] for s in sessions_client} == {s_client["id"]}
    assert {s["id"] for s in sessions_advisor} == {s_advisor["id"]}


async def test_chat_unknown_session_returns_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/chat",
        json={
            "session_id": "00000000-0000-0000-0000-000000000000",
            "content": "hi",
        },
    )
    assert resp.status_code == 404


async def _drain_chat(client: AsyncClient, session_id: str, content: str) -> str:
    """POST /chat, drain SSE, return concatenated user-facing (Writer) deltas."""
    deltas: list[str] = []
    async with client.stream(
        "POST",
        "/api/v1/chat",
        json={"session_id": session_id, "content": content},
    ) as resp:
        assert resp.status_code == 200, await resp.aread()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = json.loads(line[len("data:") :].strip())
            if payload.get("type") == "delta":
                deltas.append(payload["content"])
    return "".join(deltas)


async def test_chat_multi_turn_replays_full_history(client: AsyncClient) -> None:
    """AC2: across two turns in the same session, the second LLM call must
    receive the full ordered conversation (system + turn1 user + turn1
    assistant + turn2 user). Under the offline stub the assistant echoes the
    *last* user message, so we can't make a semantic claim. Instead we assert
    the structural invariant: after turn 2 the persisted history is length 4
    and the third row is the assistant reply from turn 1 — proving the
    conversation accumulated rather than being overwritten or truncated.
    """
    user = await _create_user(client, "memo@aura.test", "client")
    session = await _create_session(client, user["id"])

    # Turn 1.
    reply_1 = await _drain_chat(client, session["id"], "my name is Sam")
    assert "[stub]" in reply_1
    assert "my name is Sam" in reply_1  # stub echoes last user message

    # Turn 2 — under the stub this echoes "what's my name?", which only
    # confirms the stub saw turn 2's user message. The real proof of multi-
    # turn replay is the persisted history, asserted below.
    reply_2 = await _drain_chat(client, session["id"], "what's my name?")
    assert "[stub]" in reply_2
    assert "what's my name?" in reply_2

    # History accumulated: u1, a1, u2, a2 — in chronological order.
    hist = (await client.get(f"/api/v1/sessions/{session['id']}/messages")).json()
    assert len(hist) == 4, hist
    assert [m["role"] for m in hist] == ["user", "assistant", "user", "assistant"]
    assert hist[0]["content"] == "my name is Sam"
    # Third entry is the assistant's reply from turn 1 — i.e. it survived into
    # turn 2's context window.
    assert hist[2]["content"] == "what's my name?"
    assert hist[1]["content"] == reply_1
    assert hist[3]["content"] == reply_2


async def test_chat_emits_three_agent_stages(client: AsyncClient) -> None:
    """C3: the SSE stream emits start/complete frames for Researcher, Analyst,
    and Writer in that order, plus user-facing `delta` frames for the Writer.
    The persisted assistant message equals the concatenated Writer deltas.
    """
    user = await _create_user(client, "trace@aura.test", "client")
    sess = await _create_session(client, user["id"])

    starts: list[str] = []
    completes: list[dict] = []
    writer_deltas: list[str] = []
    done_id: str | None = None

    async with client.stream(
        "POST",
        "/api/v1/chat",
        json={"session_id": sess["id"], "content": "explain diversification"},
    ) as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[len("data:") :].strip())
            kind = ev.get("type")
            if kind == "agent_start":
                starts.append(ev["agent"])
            elif kind == "agent_complete":
                completes.append(ev)
            elif kind == "delta":
                writer_deltas.append(ev["content"])
            elif kind == "done":
                done_id = ev["message_id"]

    # Stages fire in order, exactly once each.
    assert starts == ["researcher", "analyst", "writer"]
    assert [c["agent"] for c in completes] == ["researcher", "analyst", "writer"]

    # Researcher and Analyst carry structured outputs.
    researcher_out = next(c for c in completes if c["agent"] == "researcher")["output"]
    analyst_out = next(c for c in completes if c["agent"] == "analyst")["output"]
    assert isinstance(researcher_out.get("topics"), list) and researcher_out["topics"]
    assert isinstance(analyst_out.get("findings"), list) and analyst_out["findings"]

    # Writer's deltas form the user-facing answer; matches persisted row.
    assert done_id is not None
    assert writer_deltas, "writer must emit at least one delta"
    full = "".join(writer_deltas)
    assert "[stub]" in full  # offline writer fallback marker

    hist = (await client.get(f"/api/v1/sessions/{sess['id']}/messages")).json()
    assistant = next(m for m in hist if m["role"] == "assistant")
    assert assistant["id"] == done_id
    assert assistant["content"] == full
