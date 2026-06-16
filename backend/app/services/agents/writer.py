"""Writer: synthesizes findings into the final user-facing answer.

The Writer's `delta` events are what the user sees in the chat bubble. The
`complete` event carries no structured output (the answer IS the streamed
text); we still emit it so the UI can mark the stage complete.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from app.core.config import settings
from app.services import llm
from app.services.agents.base import AgentEvent

GROUNDING_RULE = (
    "\n\n## Grounding rule (mandatory)\n"
    "Every named entity (client, person, ticker, account) and every "
    "quantitative claim (numbers, percentages, dollar amounts) MUST come "
    "from the Analyst findings, the research brief, the UI snapshot, or "
    "the conversation history. NEVER invent client names, holdings, "
    "prices, or risk scores. If the user asks about data you do not have, "
    "say 'I don't have that data in this view' and stop — do NOT fill in "
    "plausible-sounding placeholders.\n\n"
    "## Formatting\n"
    "Use GitHub-flavored markdown. For tabular comparisons, use a markdown "
    "table (`| col | col |\\n|---|---|\\n| val | val |`). Do not draw "
    "tables in ASCII or with extra whitespace columns."
)

CLIENT_SYSTEM = (
    "You are AuraWealth, the user's personal financial GPS. You are the "
    "Writer in a 3-agent pipeline: a Researcher gave you topics, an Analyst "
    "gave you findings; weave them into a concise, plain-spoken answer for "
    "an everyday investor. No jargon. No bullet lists unless the user asked. "
    "When you don't know something, say so."
) + GROUNDING_RULE

ADVISOR_SYSTEM = (
    "You are AuraWealth's advisor command center. You are the Writer in a "
    "3-agent pipeline: the Researcher and Analyst have done the legwork. "
    "Produce a precise, analytical answer for a wealth manager. Cite the "
    "findings you used. Prefer tabular thinking when comparing items."
) + GROUNDING_RULE


def _system_for(role: str) -> str:
    return ADVISOR_SYSTEM if role == "advisor" else CLIENT_SYSTEM


def _stub_paragraph(question: str, analyst: dict, role: str) -> str:
    """Deterministic Writer fallback used when no API key is configured.

    Mentions `[stub]` so the existing chat integration tests, which assert
    the offline stub marker is in the streamed body, continue to pass.
    """
    findings = analyst.get("findings", []) if isinstance(analyst, dict) else []
    parts: list[str] = []
    parts.append(f"[stub] echo: {question}")
    if findings:
        bullets = "; ".join(f["claim"] for f in findings[:3] if "claim" in f)
        if bullets:
            parts.append(f"Findings: {bullets}")
    parts.append(
        "Speaking as your advisor command center."
        if role == "advisor"
        else "Here as your financial GPS."
    )
    return " ".join(parts)


async def run(
    question: str,
    research: dict,
    analyst: dict,
    history: list[dict],
    role: str,
    ui_context: dict | None,
) -> AsyncIterator[AgentEvent]:
    """Stream Writer events: start, delta(s) (the user-facing answer), complete."""
    yield AgentEvent(kind="start", agent="writer")

    if not settings.openai_api_key:
        # Offline path: yield a deterministic paragraph token-by-token.
        text = _stub_paragraph(question, analyst, role)
        chunk_size = 4
        for i in range(0, len(text), chunk_size):
            yield AgentEvent(
                kind="delta", agent="writer", content=text[i : i + chunk_size]
            )
        yield AgentEvent(kind="complete", agent="writer", output={})
        return

    sys = _system_for(role)
    sys += (
        f"\n\n## Research brief\n```json\n{json.dumps(research)}\n```"
        f"\n\n## Analyst findings\n```json\n{json.dumps(analyst)}\n```"
    )
    if ui_context:
        sys += f"\n\n## UI snapshot\n```json\n{json.dumps(ui_context, default=str)}\n```"

    messages: list[dict] = [{"role": "system", "content": sys}]
    for row in history:
        messages.append(row)
    messages.append({"role": "user", "content": question})

    async for delta in llm.stream_chat(messages):
        yield AgentEvent(kind="delta", agent="writer", content=delta)

    yield AgentEvent(kind="complete", agent="writer", output={})
