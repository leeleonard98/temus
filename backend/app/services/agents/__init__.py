"""Sequential 3-agent pipeline (Researcher -> Analyst -> Writer).

The pipeline drives `/api/v1/chat`. The Writer's streamed tokens form the
user-facing assistant reply; the Researcher and Analyst stages emit structured
trace events the UI renders as a "Show reasoning" disclosure.
"""
from app.services.agents.base import AgentEvent, AgentName
from app.services.agents.sequential import run_sequential

__all__ = ["AgentEvent", "AgentName", "run_sequential"]
