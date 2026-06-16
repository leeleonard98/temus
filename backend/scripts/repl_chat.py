"""Terminal REPL for the AuraWealth chat backend.

Spec coverage: C1 (REPL chat with an LLM) + AC2 (multi-turn dialogue
management, state across interactions).

Each turn:
    1. Persist the user message.
    2. Reload the FULL ordered history (oldest → newest) from Postgres.
    3. Prepend the role-aware system prompt.
    4. Stream the assistant reply via `app.services.llm.stream_chat`,
       printing tokens as they arrive.
    5. Persist the assistant reply.

We deliberately do not truncate or window the history. Cross-session
summarization lands in A12 (see implementation plan §5).

Usage:
    python -m scripts.repl_chat --role client --email sam@aura.test
    python -m scripts.repl_chat --role advisor --email mgr@aura.test --session-id <uuid>

Commands inside the REPL:
    /exit, /quit, EOF (Ctrl-D)  — leave cleanly
    /history                    — print the running conversation
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.db.models import ChatMessage, ChatSession, MessageRole, User, UserRole
from app.db.session import AsyncSessionLocal
from app.routers.chat import _system_prompt_for
from app.services import llm


async def _get_or_create_user(email: str, role: UserRole, display_name: str) -> User:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is not None:
            return existing
        user = User(email=email, display_name=display_name, role=role)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _get_or_create_session(
    user: User, session_id: uuid.UUID | None, title: str | None
) -> ChatSession:
    async with AsyncSessionLocal() as session:
        if session_id is not None:
            cs = await session.get(ChatSession, session_id)
            if cs is None:
                raise SystemExit(f"session {session_id} not found")
            if cs.user_id != user.id:
                raise SystemExit(f"session {session_id} does not belong to {user.email}")
            return cs
        cs = ChatSession(user_id=user.id, title=title or "REPL session")
        session.add(cs)
        await session.commit()
        await session.refresh(cs)
        return cs


async def _persist_message(
    chat_session_id: uuid.UUID, role: MessageRole, content: str
) -> ChatMessage:
    async with AsyncSessionLocal() as session:
        msg = ChatMessage(session_id=chat_session_id, role=role, content=content)
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg


async def _load_history(chat_session_id: uuid.UUID) -> list[ChatMessage]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == chat_session_id)
                .order_by(ChatMessage.created_at.asc())
            )
        ).all()
        return list(rows)


def _build_messages(user_role: UserRole, history: list[ChatMessage]) -> list[dict]:
    """System prompt + every prior turn, oldest → newest. No truncation."""
    msgs: list[dict] = [{"role": "system", "content": _system_prompt_for(user_role)}]
    for row in history:
        msgs.append({"role": row.role.value, "content": row.content})
    return msgs


async def _one_turn(user: User, chat_session: ChatSession, content: str) -> None:
    # 1. Persist user message FIRST so it's included in the replay below.
    await _persist_message(chat_session.id, MessageRole.user, content)

    # 2. Reload full history (now ending in the user's just-sent message).
    history = await _load_history(chat_session.id)

    # 3. Prepend the role-aware system prompt.
    messages = _build_messages(user.role, history)

    # 4. Stream tokens.
    print("assistant> ", end="", flush=True)
    chunks: list[str] = []
    async for delta in llm.stream_chat(messages):
        chunks.append(delta)
        print(delta, end="", flush=True)
    print()  # newline after the streamed reply

    # 5. Persist assistant reply.
    full = "".join(chunks)
    await _persist_message(chat_session.id, MessageRole.assistant, full)


async def _repl(user: User, chat_session: ChatSession) -> None:
    print(
        f"AuraWealth REPL — user={user.email} role={user.role.value} "
        f"session={chat_session.id}\n"
        "Commands: /history, /exit (or Ctrl-D)\n",
        flush=True,
    )
    loop = asyncio.get_running_loop()
    while True:
        try:
            # Run blocking input() in a thread so we don't stall the loop.
            line = await loop.run_in_executor(None, lambda: input("you> "))
        except (EOFError, KeyboardInterrupt):
            print()
            return
        line = line.strip()
        if not line:
            continue
        if line in {"/exit", "/quit"}:
            return
        if line == "/history":
            history = await _load_history(chat_session.id)
            if not history:
                print("(no messages yet)")
            else:
                for row in history:
                    print(f"[{row.role.value}] {row.content}")
            continue
        await _one_turn(user, chat_session, line)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AuraWealth REPL chat client.")
    p.add_argument(
        "--role",
        choices=[r.value for r in UserRole],
        default=UserRole.client.value,
        help="Persona for the system prompt + user row (default: client).",
    )
    p.add_argument(
        "--email",
        default=None,
        help="User email; defaults to repl-<role>@aura.test.",
    )
    p.add_argument(
        "--name",
        dest="display_name",
        default=None,
        help="Display name for a freshly created user (default: derived from email).",
    )
    p.add_argument(
        "--session-id",
        dest="session",
        type=uuid.UUID,
        default=None,
        help="Existing chat session UUID to resume; omit to start a new one.",
    )
    p.add_argument(
        "--title",
        default=None,
        help="Title for a newly created session.",
    )
    return p.parse_args(argv)


async def _amain(args: argparse.Namespace) -> None:
    role = UserRole(args.role)
    email = args.email or f"repl-{role.value}@aura.test"
    display_name = args.display_name or email.split("@")[0]

    user = await _get_or_create_user(email, role, display_name)
    chat_session = await _get_or_create_session(user, args.session, args.title)
    await _repl(user, chat_session)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        asyncio.run(_amain(args))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
