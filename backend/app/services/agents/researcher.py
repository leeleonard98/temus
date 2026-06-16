"""Researcher: turns the user's question into a small research brief.

Produces a structured `{topics: list[str], rationale: str}` output. Uses the
configured LLM via `app.services.llm.stream_chat`; if the LLM is the offline
stub (or the response can't be parsed as JSON), we fall back to a
deterministic extractor so the pipeline still produces a useful trace.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from app.services import llm
from app.services.agents.base import AgentEvent

SYSTEM_PROMPT = (
    "You are the Researcher in a 3-agent wealth-advice pipeline. Your job is "
    "to read the user's question and produce a SHORT research brief: 2-4 "
    "topics to investigate, plus a one-sentence rationale.\n"
    "Return ONLY a JSON object with keys `topics` (array of strings) and "
    "`rationale` (string). No prose. No code fences.\n\n"
    "## Grounding rule (mandatory)\n"
    "Every named entity (client, person, ticker, account) and every "
    "quantitative claim (numbers, percentages, dollar amounts) MUST come "
    "from the conversation history or the UI snapshot below. NEVER invent "
    "client names, holdings, prices, or risk scores. If the user asks about "
    "data not present, list a topic like 'request: <what the user wants>' "
    "and let downstream agents respond 'I don't have that data.'"
)


_STOPWORDS = {
    "the", "a", "an", "is", "are", "what", "how", "why", "do", "does",
    "i", "my", "me", "you", "your", "to", "of", "in", "on", "for", "and",
    "or", "but", "with", "should", "can", "could", "would", "about", "this",
    "that", "it", "be", "been", "if", "so", "as", "at", "by", "from", "have",
    "has", "had", "was", "were", "will", "just", "any", "we", "us", "our",
}


def _fallback_topics(question: str) -> list[str]:
    """Heuristic keyword extraction so the trace UI is meaningful under the stub."""
    words = re.findall(r"[A-Za-z][A-Za-z\-']+", question.lower())
    seen: list[str] = []
    for w in words:
        if w in _STOPWORDS or len(w) <= 2:
            continue
        if w not in seen:
            seen.append(w)
        if len(seen) >= 4:
            break
    return seen or ["general financial guidance"]


def _parse(text: str, question: str) -> dict[str, Any]:
    """Best-effort JSON parse with a deterministic fallback."""
    # Strip code fences if a real model added them despite instructions.
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?|```$", "", stripped).strip()

    try:
        obj = json.loads(stripped)
        topics_raw = obj.get("topics")
        rationale_raw = obj.get("rationale", "")
        if isinstance(topics_raw, list) and topics_raw:
            topics = [str(t) for t in topics_raw][:6]
            rationale = str(rationale_raw) or "Identified relevant topics."
            return {"topics": topics, "rationale": rationale}
    except (ValueError, AttributeError):
        pass

    return {
        "topics": _fallback_topics(question),
        "rationale": "Extracted topics from the question (offline mode).",
    }


async def run(
    question: str,
    history: list[dict],
    ui_context: dict | None,
) -> AsyncIterator[AgentEvent]:
    """Stream Researcher events: start, delta(s), complete."""
    yield AgentEvent(kind="start", agent="researcher")

    sys = SYSTEM_PROMPT
    if ui_context:
        sys = f"{sys}\n\n## Visible UI State\n```json\n{json.dumps(ui_context, default=str)}\n```"

    # Researcher gets the system prompt + (optional) prior turns + the question.
    messages: list[dict] = [{"role": "system", "content": sys}]
    for row in history:
        messages.append(row)
    messages.append({"role": "user", "content": question})

    chunks: list[str] = []
    async for delta in llm.stream_chat(messages):
        chunks.append(delta)
        yield AgentEvent(kind="delta", agent="researcher", content=delta)

    output = _parse("".join(chunks), question)
    yield AgentEvent(kind="complete", agent="researcher", output=output)


# ---------- advisor variant ----------

ADVISOR_SYSTEM_PROMPT = (
    "You are the Researcher in a 3-agent wealth-advice pipeline serving a "
    "WEALTH MANAGER (advisor). Classify the advisor's question into ONE task "
    "type and list the topics to investigate.\n"
    "Allowed task types: client-triage | risk-review | portfolio-review | "
    "rebalancing | market-summary | compliance | general.\n"
    "Return ONLY a JSON object with keys `task` (string, one of the above), "
    "`topics` (array of 2-4 strings), and `rationale` (one sentence). "
    "No prose. No code fences.\n\n"
    "## Grounding rule (mandatory)\n"
    "NEVER invent client names, holdings, or numbers. The Analyst will fetch "
    "real data via tools — your job is to label what to look up, not to "
    "answer. If the advisor asks about something outside their book of "
    "clients, set task='general'."
)


_ADVISOR_TASKS = {
    "client-triage", "risk-review", "portfolio-review",
    "rebalancing", "market-summary", "compliance", "general",
}


def _parse_advisor(text: str, question: str) -> dict[str, Any]:
    """Best-effort JSON parse with deterministic fallback for advisor brief."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?|```$", "", stripped).strip()
    try:
        obj = json.loads(stripped)
        task_raw = str(obj.get("task", "")).strip().lower()
        task = task_raw if task_raw in _ADVISOR_TASKS else "general"
        topics_raw = obj.get("topics")
        if isinstance(topics_raw, list) and topics_raw:
            topics = [str(t) for t in topics_raw][:6]
            rationale = str(obj.get("rationale") or "Identified advisor task and topics.")
            return {"task": task, "topics": topics, "rationale": rationale}
    except (ValueError, AttributeError):
        pass
    # Heuristic fallback for the offline stub: keyword-based task pick.
    lower = question.lower()
    if any(w in lower for w in ("rebalance", "drift", "target allocation")):
        task = "rebalancing"
    elif any(w in lower for w in ("risk", "aggressive", "conservative", "exposure")):
        task = "risk-review"
    elif any(w in lower for w in ("client", "book", "my clients", "who needs")):
        task = "client-triage"
    elif any(w in lower for w in ("market", "rate", "fed", "macro")):
        task = "market-summary"
    elif any(w in lower for w in ("compliance", "regulation", "audit")):
        task = "compliance"
    else:
        task = "general"
    return {
        "task": task,
        "topics": _fallback_topics(question),
        "rationale": "Classified from keywords (offline mode).",
    }


async def run_for_advisor(
    question: str,
    history: list[dict],
) -> AsyncIterator[AgentEvent]:
    """Advisor Researcher — classifies the request into a task type."""
    yield AgentEvent(kind="start", agent="researcher")

    messages: list[dict] = [{"role": "system", "content": ADVISOR_SYSTEM_PROMPT}]
    for row in history:
        messages.append(row)
    messages.append({"role": "user", "content": question})

    chunks: list[str] = []
    async for delta in llm.stream_chat(messages):
        chunks.append(delta)
        yield AgentEvent(kind="delta", agent="researcher", content=delta)

    output = _parse_advisor("".join(chunks), question)
    yield AgentEvent(kind="complete", agent="researcher", output=output)
