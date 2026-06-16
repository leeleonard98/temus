"""Chat API — users, sessions, messages, and the streaming chat endpoint.

Used by both the web UI (Phase 1 frontend) and the REPL (`scripts/repl_chat.py`).

The system-prompt persona is selected from the user's role. Clients get a
"financial GPS" tone; advisors get a "command center / book of business" tone.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_session
from app.db.models import ChatMessage, ChatSession, MessageRole, User, UserRole
from app.schemas.chat import (
    ChatRequest,
    MessageOut,
    SessionCreate,
    SessionOut,
    UserCreate,
    UserOut,
)
from app.services.agents import run_sequential

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

CLIENT_SYSTEM_PROMPT = (
    "You are AuraWealth, the user's personal financial GPS. "
    "You speak directly to an everyday investor about their net worth, goals, "
    "and progress. Be concise, plain-spoken, and encouraging. Avoid jargon. "
    "When you don't know something, say so and suggest who or what to consult."
)

ADVISOR_SYSTEM_PROMPT = (
    "You are AuraWealth's advisor command center. You speak to a wealth manager "
    "running a book of business. Be precise and analytical. Surface portfolio "
    "risk, rebalancing opportunities, and clients who need attention. "
    "Prefer tabular thinking; cite the data you used."
)


def _system_prompt_for(role: UserRole) -> str:
    return ADVISOR_SYSTEM_PROMPT if role == UserRole.advisor else CLIENT_SYSTEM_PROMPT


# ---------- users ----------


@router.post("/users", response_model=UserOut)
async def create_or_get_user(
    payload: UserCreate, session: AsyncSession = Depends(get_session)
) -> UserOut:
    """Idempotent upsert by email — returns the existing row if email matches."""
    existing = await session.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        return UserOut.model_validate(existing)

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        role=UserRole(payload.role),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


# ---------- sessions ----------


@router.post("/sessions", response_model=SessionOut)
async def create_session(
    payload: SessionCreate, session: AsyncSession = Depends(get_session)
) -> SessionOut:
    user = await session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    cs = ChatSession(user_id=payload.user_id, title=payload.title)
    session.add(cs)
    await session.commit()
    await session.refresh(cs)
    return SessionOut.model_validate(cs)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[SessionOut]:
    rows = (
        await session.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.created_at.desc())
        )
    ).all()
    return [SessionOut.model_validate(r) for r in rows]


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[MessageOut]:
    cs = await session.get(ChatSession, session_id)
    if cs is None:
        raise HTTPException(status_code=404, detail="session not found")

    rows = (
        await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
    ).all()
    return [MessageOut.model_validate(r) for r in rows]


# ---------- chat (SSE) ----------


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/chat")
async def chat_stream(
    payload: ChatRequest, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    """Stream the sequential 3-agent pipeline (Researcher -> Analyst -> Writer).

    The Writer's tokens are the user-facing assistant reply (and what gets
    persisted as a single `chat_messages` row). Researcher and Analyst stages
    emit trace events the UI renders as a "Show reasoning" disclosure.
    """
    cs = await session.get(ChatSession, payload.session_id)
    if cs is None:
        raise HTTPException(status_code=404, detail="session not found")

    user = await session.get(User, cs.user_id)
    if user is None:  # pragma: no cover — FK guarantees this
        raise HTTPException(status_code=404, detail="user not found")

    # Persist the user turn FIRST so it (a) survives a client disconnect and
    # (b) is included verbatim when we reload history for the agents below.
    user_msg = ChatMessage(
        session_id=payload.session_id,
        role=MessageRole.user,
        content=payload.content,
        ui_context=payload.ui_context,
    )
    session.add(user_msg)
    await session.commit()
    await session.refresh(user_msg)

    # AC2: replay the full ordered conversation (oldest -> newest, EXCLUDING
    # the just-persisted user turn — agents add it themselves) so multi-turn
    # context is preserved end-to-end.
    prior_rows = (
        await session.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == payload.session_id,
                ChatMessage.id != user_msg.id,
            )
            .order_by(ChatMessage.created_at.asc())
        )
    ).all()
    history: list[dict] = [
        {"role": row.role.value, "content": row.content} for row in prior_rows
    ]

    role_str = "advisor" if user.role == UserRole.advisor else "client"

    async def event_stream() -> AsyncIterator[str]:
        writer_chunks: list[str] = []
        try:
            async for ev in run_sequential(
                payload.content,
                history=history,
                role=role_str,
                ui_context=payload.ui_context,
                user_id=str(user.id),
            ):
                if ev.kind == "start":
                    yield _sse({"type": "agent_start", "agent": ev.agent})
                elif ev.kind == "delta":
                    if ev.agent == "writer":
                        # User-facing answer tokens.
                        writer_chunks.append(ev.content or "")
                        yield _sse({"type": "delta", "content": ev.content or ""})
                    else:
                        # Internal-stage tokens — for trace UI only.
                        yield _sse(
                            {
                                "type": "agent_delta",
                                "agent": ev.agent,
                                "content": ev.content or "",
                            }
                        )
                elif ev.kind == "complete":
                    yield _sse(
                        {
                            "type": "agent_complete",
                            "agent": ev.agent,
                            "output": ev.output or {},
                        }
                    )
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("agent pipeline failed")
            yield _sse({"type": "error", "error": str(exc)})
            return

        full = "".join(writer_chunks)
        assistant_msg = ChatMessage(
            session_id=payload.session_id,
            role=MessageRole.assistant,
            content=full,
        )
        session.add(assistant_msg)
        await session.commit()
        await session.refresh(assistant_msg)
        yield _sse({"type": "done", "message_id": str(assistant_msg.id)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        status_code=status.HTTP_200_OK,
        headers={"Cache-Control": "no-cache"},
    )
