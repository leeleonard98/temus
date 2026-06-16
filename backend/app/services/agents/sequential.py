"""Sequential orchestrator: Researcher -> Analyst -> Writer.

Yields a single flat stream of `AgentEvent`s. The router maps these to SSE
frames; the test suite asserts ordering and structure directly.

Routing:
  - role="advisor" → advisor Researcher (task classifier) + advisor Analyst
    with tool-calling against `list_clients` / `get_client_*` / `rag_search`.
  - role="client"  → client Researcher (topic extractor) + client Analyst
    grounded on the UI snapshot (or, when missing, the user's own portfolio
    fetched via tools when `user_id` is supplied).

The Writer is unchanged; it still picks ADVISOR_SYSTEM vs CLIENT_SYSTEM by
role and consumes whatever findings the Analyst produced.

History handling: prior turns (`role` ∈ {user, assistant}) are passed to the
Researcher and Writer so multi-turn context is preserved end-to-end. The
Analyst sees only the current question + research brief + (UI snapshot or
tool results), since re-feeding history mostly burns tokens for no quality
gain.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.services.agents import analyst, researcher, writer
from app.services.agents.base import AgentEvent


async def run_sequential(
    question: str,
    *,
    history: list[dict] | None = None,
    role: str = "client",
    ui_context: dict | None = None,
    user_id: str | None = None,
) -> AsyncIterator[AgentEvent]:
    """Drive the three agents in sequence, yielding every event."""
    history = history or []

    research_output: dict = {}
    if role == "advisor":
        async for ev in researcher.run_for_advisor(question, history):
            if ev.kind == "complete" and ev.output is not None:
                research_output = ev.output
            yield ev
    else:
        async for ev in researcher.run(question, history, ui_context):
            if ev.kind == "complete" and ev.output is not None:
                research_output = ev.output
            yield ev

    analyst_output: dict = {}
    if role == "advisor":
        async for ev in analyst.run_for_advisor(question, research_output):
            if ev.kind == "complete" and ev.output is not None:
                analyst_output = ev.output
            yield ev
    else:
        async for ev in analyst.run_for_client(
            question, research_output, ui_context, user_id=user_id
        ):
            if ev.kind == "complete" and ev.output is not None:
                analyst_output = ev.output
            yield ev

    async for ev in writer.run(
        question, research_output, analyst_output, history, role, ui_context
    ):
        yield ev
