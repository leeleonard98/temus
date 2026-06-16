"""Analyst: takes the Researcher brief + UI context and produces findings.

Findings are short bullet-style facts the Writer can quote. Each carries a
confidence label (high/medium/low) so the UI can pill them.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from app.services import llm
from app.services.agents.base import AgentEvent

SYSTEM_PROMPT = (
    "You are the Analyst in a 3-agent wealth-advice pipeline. You receive a "
    "research brief (topics + rationale) and (optionally) a JSON snapshot of "
    "the user's portfolio UI. Produce 2-4 findings the Writer can use.\n"
    "Return ONLY a JSON object: "
    '{"findings": [{"claim": str, "confidence": "high"|"medium"|"low"}], '
    '"summary": str}. No prose. No code fences.'
)


def _confidence(value: Any) -> str:
    s = str(value).strip().lower()
    return s if s in {"high", "medium", "low"} else "medium"


def _fallback(topics: list[str], ui_context: dict | None) -> dict[str, Any]:
    """Deterministic findings used under the offline stub or on parse failure."""
    findings: list[dict[str, Any]] = []
    for t in topics[:3]:
        findings.append(
            {
                "claim": f"'{t}' is relevant to the user's question.",
                "confidence": "medium",
            }
        )
    if ui_context:
        # Mention one concrete ground-truth datum if present.
        for key in ("market_value", "total_value", "net_worth"):
            if key in ui_context:
                findings.append(
                    {
                        "claim": (
                            f"Portfolio {key.replace('_', ' ')} is "
                            f"{ui_context[key]} per the visible UI."
                        ),
                        "confidence": "high",
                    }
                )
                break
    if not findings:
        findings.append(
            {
                "claim": "No structured data available; answering from general knowledge.",
                "confidence": "low",
            }
        )
    return {
        "findings": findings,
        "summary": "Synthesized topics with available UI context (offline mode).",
    }


def _parse(text: str, topics: list[str], ui_context: dict | None) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?|```$", "", stripped).strip()
    try:
        obj = json.loads(stripped)
        findings_raw = obj.get("findings")
        if isinstance(findings_raw, list) and findings_raw:
            findings: list[dict[str, Any]] = []
            for f in findings_raw[:6]:
                if not isinstance(f, dict):
                    continue
                claim = str(f.get("claim") or "").strip()
                if not claim:
                    continue
                findings.append(
                    {"claim": claim, "confidence": _confidence(f.get("confidence"))}
                )
            if findings:
                return {
                    "findings": findings,
                    "summary": str(obj.get("summary", "")) or "Analyst summary.",
                }
    except (ValueError, AttributeError):
        pass
    return _fallback(topics, ui_context)


async def run(
    question: str,
    research: dict[str, Any],
    ui_context: dict | None,
) -> AsyncIterator[AgentEvent]:
    """Stream Analyst events: start, delta(s), complete."""
    yield AgentEvent(kind="start", agent="analyst")

    sys = SYSTEM_PROMPT
    user_msg = (
        f"Question: {question}\n\n"
        f"Research brief:\n```json\n{json.dumps(research)}\n```\n"
    )
    if ui_context:
        user_msg += f"\nUI snapshot:\n```json\n{json.dumps(ui_context, default=str)}\n```"

    messages = [
        {"role": "system", "content": sys},
        {"role": "user", "content": user_msg},
    ]

    chunks: list[str] = []
    async for delta in llm.stream_chat(messages):
        chunks.append(delta)
        yield AgentEvent(kind="delta", agent="analyst", content=delta)

    topics = research.get("topics", []) if isinstance(research, dict) else []
    output = _parse("".join(chunks), topics, ui_context)
    yield AgentEvent(kind="complete", agent="analyst", output=output)
