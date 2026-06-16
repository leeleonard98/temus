"""Shared types for the sequential agent pipeline.

`AgentEvent` is the single envelope the pipeline yields. Routers/tests can
discriminate on `kind` to map to SSE frames or assertions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AgentName = Literal["researcher", "analyst", "writer"]
EventKind = Literal["start", "delta", "complete"]


@dataclass(slots=True)
class AgentEvent:
    """One step in the agent stream.

    - `start`     -> agent began work; `output` is None
    - `delta`     -> token from the agent; `content` carries the chunk
    - `complete`  -> agent finished; `output` carries the structured result
    """

    kind: EventKind
    agent: AgentName
    content: str | None = None
    output: dict[str, Any] | None = field(default=None)
