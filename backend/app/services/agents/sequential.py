"""Sequential orchestrator: Researcher -> Analyst -> Writer.

Yields a single flat stream of `AgentEvent`s. The router maps these to SSE
frames; the test suite asserts ordering and structure directly.

History handling: prior turns (`role` ∈ {user, assistant}) are passed to the
Researcher and Writer so multi-turn context is preserved end-to-end. The
Analyst sees only the current question + research brief + UI snapshot, since
re-feeding history there mostly burns tokens for no quality gain.
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
) -> AsyncIterator[AgentEvent]:
    """Drive the three agents in sequence, yielding every event."""
    history = history or []

    research_output: dict = {}
    async for ev in researcher.run(question, history, ui_context):
        if ev.kind == "complete" and ev.output is not None:
            research_output = ev.output
        yield ev

    analyst_output: dict = {}
    async for ev in analyst.run(question, research_output, ui_context):
        if ev.kind == "complete" and ev.output is not None:
            analyst_output = ev.output
        yield ev

    async for ev in writer.run(
        question, research_output, analyst_output, history, role, ui_context
    ):
        yield ev
