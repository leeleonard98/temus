"""Analyst: takes the Researcher brief and produces grounded findings.

Two variants share most of the file:

- `run_for_client(question, research, ui_context, *, user_id=None)` — old
  prose-from-context-window path, plus an optional tool-call loop when
  `user_id` is provided so the Analyst can fetch the client's own portfolio
  / goals when the dashboard didn't publish a UI snapshot (e.g. REPL).

- `run_for_advisor(question, research, *, advisor_id=None)` — tool-call
  loop with `list_clients` / `get_client_portfolio` / `get_client_risk` /
  `rag_search` exposed. The Analyst MUST ground every claim in tool output;
  the system prompt enforces that.

Both stream `agent_delta` events the trace UI renders, then emit a
structured `agent_complete` with the same shape:
    {"findings": [{"claim", "confidence"}], "summary"}

The legacy `run(...)` is preserved as an alias for `run_for_client(...)`
so existing tests / callers don't break.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings
from app.services import llm
from app.services.agents import tools as agent_tools
from app.services.agents.base import AgentEvent

# ---------- shared parsing / fallback ----------

SYSTEM_PROMPT_CLIENT = (
    "You are the Analyst in a 3-agent wealth-advice pipeline. You receive a "
    "research brief (topics + rationale) and (optionally) a JSON snapshot of "
    "the user's portfolio UI. Produce 2-4 findings the Writer can use.\n"
    "Return ONLY a JSON object: "
    '{"findings": [{"claim": str, "confidence": "high"|"medium"|"low"}], '
    '"summary": str}. No prose. No code fences.\n\n'
    "## Grounding rule (mandatory)\n"
    "Every claim MUST be supported by the UI snapshot, the research brief, "
    "or a tool result. NEVER invent client names, holdings, tickers, "
    "prices, or risk scores. If you don't have the data, return a SINGLE "
    'finding {"claim": "I don\'t have that data in this view", '
    '"confidence": "low"}. Use confidence="high" only when you can cite '
    "a specific value from the UI snapshot or a tool result."
)

SYSTEM_PROMPT_ADVISOR = (
    "You are the Analyst in a 3-agent wealth-advice pipeline serving a "
    "WEALTH MANAGER (advisor). You receive a research brief with a `task` "
    "(client-triage | risk-review | portfolio-review | rebalancing | "
    "market-summary | compliance | general). Use the available tools to "
    "fetch real data from the database, THEN produce 2-4 grounded findings.\n\n"
    "Tool playbook (call as needed):\n"
    "- ANY question about 'my book' or 'my clients' → call `list_clients` first.\n"
    "- For per-client risk → `get_client_risk(client_id)` per relevant client.\n"
    "- For per-client holdings → `get_client_portfolio(client_id)`.\n"
    "- For firm-policy / product questions → `rag_search(query)`.\n\n"
    "When done with tools, return ONLY a JSON object: "
    '{"findings": [{"claim": str, "confidence": "high"|"medium"|"low"}], '
    '"summary": str}. No prose. No code fences.\n\n'
    "## Grounding rule (mandatory)\n"
    "Every named entity (client, ticker) and every number (score, %, $) "
    "MUST come from a tool result. NEVER invent client names, holdings, "
    "scores, or dollar amounts. If a tool returned an error or no data, "
    "say 'I don't have that data' explicitly. Use confidence='high' ONLY "
    "for values you cited verbatim from a tool result."
)


def _confidence(value: Any) -> str:
    s = str(value).strip().lower()
    return s if s in {"high", "medium", "low"} else "medium"


def _fallback(topics: list[str], ui_context: dict | None) -> dict[str, Any]:
    """Deterministic findings used under the offline stub or on parse failure."""
    findings: list[dict[str, Any]] = []
    for t in topics[:3]:
        findings.append(
            {"claim": f"'{t}' is relevant to the user's question.", "confidence": "medium"}
        )
    if ui_context:
        for key in ("market_value", "total_value", "net_worth"):
            if key in ui_context:
                findings.append(
                    {
                        "claim": f"Portfolio {key.replace('_', ' ')} is {ui_context[key]} per the visible UI.",
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
    """JSON-parse the analyst output with a deterministic fallback."""
    stripped = (text or "").strip()
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


# ---------- client variant ----------


async def run_for_client(
    question: str,
    research: dict[str, Any],
    ui_context: dict | None,
    *,
    user_id: str | None = None,
) -> AsyncIterator[AgentEvent]:
    """Stream Analyst events for the client pipeline.

    If `user_id` is provided AND no `ui_context` was supplied, we run a
    one-shot tool-call to fetch the user's own portfolio / goals before
    finalising findings. Keeps the REPL grounded the same way the web UI is.
    """
    yield AgentEvent(kind="start", agent="analyst")

    # Augment ui_context with tool data if missing and we have a user_id.
    augmented_context = dict(ui_context) if ui_context else {}
    if user_id and not augmented_context and settings.openai_api_key:
        try:
            yield AgentEvent(
                kind="delta", agent="analyst", content="Fetching portfolio…\n"
            )
            portfolio = await agent_tools.get_user_portfolio(user_id)
            goals = await agent_tools.get_user_goals(user_id)
            if not portfolio.get("error"):
                augmented_context["market_value"] = portfolio.get("total_market_value")
                augmented_context["allocation"] = portfolio.get("allocation")
                augmented_context["top_positions"] = portfolio.get("top_positions")
            if goals:
                augmented_context["goals"] = goals
        except Exception:  # pragma: no cover -- defensive
            pass

    user_msg = (
        f"Question: {question}\n\n"
        f"Research brief:\n```json\n{json.dumps(research)}\n```\n"
    )
    if augmented_context:
        user_msg += (
            f"\nUI snapshot:\n```json\n{json.dumps(augmented_context, default=str)}\n```"
        )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_CLIENT},
        {"role": "user", "content": user_msg},
    ]

    chunks: list[str] = []
    async for delta in llm.stream_chat(messages):
        chunks.append(delta)
        yield AgentEvent(kind="delta", agent="analyst", content=delta)

    topics = research.get("topics", []) if isinstance(research, dict) else []
    output = _parse("".join(chunks), topics, augmented_context)
    yield AgentEvent(kind="complete", agent="analyst", output=output)


# Back-compat alias (preserves old `analyst.run(...)` callers and tests).
run = run_for_client


# ---------- advisor variant ----------


async def run_for_advisor(
    question: str,
    research: dict[str, Any],
) -> AsyncIterator[AgentEvent]:
    """Stream Analyst events for the advisor pipeline using tool-calls.

    Loop:
      1. Send (system, brief, question, current message stack) to the model.
      2. If `tool_calls` come back, dispatch via `agent_tools.TOOL_DISPATCH`,
         append `role: tool` messages with their JSON results, and loop.
      3. Otherwise, parse the assistant's `content` as the analyst JSON.
    Capped at 4 iterations so a misbehaving model can't burn loops.
    """
    yield AgentEvent(kind="start", agent="analyst")

    topics = research.get("topics", []) if isinstance(research, dict) else []

    if not settings.openai_api_key:
        # Offline stub: no tools fire. Just return the legacy fallback.
        out = _fallback(topics, None)
        out["summary"] = "Advisor analyst (offline stub) — no tool calls executed."
        yield AgentEvent(kind="delta", agent="analyst", content="[stub] no-op\n")
        yield AgentEvent(kind="complete", agent="analyst", output=out)
        return

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT_ADVISOR},
        {
            "role": "user",
            "content": (
                f"Advisor question: {question}\n\n"
                f"Research brief:\n```json\n{json.dumps(research)}\n```\n\n"
                "Use tools first to ground your findings, then return the JSON."
            ),
        },
    ]

    final_content = ""
    for iteration in range(4):
        result = await llm.chat_with_tools(
            messages, agent_tools.ADVISOR_TOOL_SCHEMAS
        )
        tool_calls = result.get("tool_calls") or []
        if not tool_calls:
            final_content = result.get("content") or ""
            break

        # Trace event so the UI can show "Calling list_clients..." etc.
        names = ", ".join(tc["name"] for tc in tool_calls)
        yield AgentEvent(
            kind="delta",
            agent="analyst",
            content=f"[iter {iteration + 1}] tool calls: {names}\n",
        )

        # Append the assistant's tool-call message.
        messages.append(
            {
                "role": "assistant",
                "content": result.get("content") or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        # Dispatch each tool, append its result.
        for tc in tool_calls:
            name = tc["name"]
            args = tc["arguments"] or {}
            fn = agent_tools.TOOL_DISPATCH.get(name)
            if fn is None:
                tool_result: Any = {"error": f"unknown tool {name}"}
            else:
                try:
                    tool_result = await fn(**args)
                except TypeError as e:
                    tool_result = {"error": f"bad args for {name}: {e}"}
                except Exception as e:  # pragma: no cover -- defensive
                    tool_result = {"error": f"{name} failed: {e}"}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_result, default=str),
                }
            )
    else:
        # Loop exhausted — force one more turn without tools to extract JSON.
        result = await llm.chat_with_tools(
            messages + [
                {
                    "role": "user",
                    "content": "Stop calling tools. Return the analyst JSON now.",
                }
            ],
            tools=[],
        )
        final_content = result.get("content") or ""

    output = _parse(final_content, topics, None)
    yield AgentEvent(kind="complete", agent="analyst", output=output)
