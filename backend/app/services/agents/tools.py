"""Tool functions exposed to the agent layer.

The Researcher (in researcher.py) is owned by the chat agent and may call
into these helpers without import cycles. Each tool returns plain dicts so
they can be serialised into agent trace events.

Layout:
- Corpus / web tools (`rag_search`, `web_search`) — used by both pipelines.
- DB tools (`list_clients`, `get_client_*`, `get_user_*`) — wrap the same
  read paths the REST routes use, so the Analyst can ground its findings.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Account,
    AssetClass,
    Goal,
    Position,
    User,
    UserRole,
)
from app.db.session import AsyncSessionLocal
from app.services import rag as rag_service
from app.services import web_search as web_search_service
from app.services.risk import PositionRow, compute_risk_score


# ---------- corpus / web ----------


async def rag_search(
    query: str,
    k: int = 5,
    *,
    session: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    """Hybrid RAG search over the corpus.

    Returns up to `k` chunks shaped as `{title, content, score, doc_id}`.
    If a `session` is provided it is reused (preferred — keeps the call inside
    the request transaction); otherwise a one-shot session is opened.
    """
    if session is not None:
        rows = await rag_service.hybrid_search(session, query, k=k)
    else:
        async with AsyncSessionLocal() as s:
            rows = await rag_service.hybrid_search(s, query, k=k)
    return [
        {
            "doc_id": r["doc_id"],
            "title": r["title"],
            "content": r["content"],
            "score": float(r["score"]),
        }
        for r in rows
    ]


async def web_search(query: str, k: int = 5) -> list[dict[str, Any]]:
    """DuckDuckGo web search (A9). See `app.services.web_search` for fallback."""
    return await web_search_service.web_search(query, k=k)


# ---------- DB tools (advisor + client) ----------


async def _latest_prices(session: AsyncSession, symbols: list[str]) -> dict[str, Decimal]:
    """Map symbol -> most-recent price; missing symbols fall back to avg_cost upstream."""
    if not symbols:
        return {}
    from sqlalchemy import func

    from app.db.models import Price

    latest_ts_subq = (
        select(Price.symbol, func.max(Price.ts).label("ts"))
        .where(Price.symbol.in_(symbols))
        .group_by(Price.symbol)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Price.symbol, Price.price).join(
                latest_ts_subq,
                (Price.symbol == latest_ts_subq.c.symbol)
                & (Price.ts == latest_ts_subq.c.ts),
            )
        )
    ).all()
    return {sym: price for sym, price in rows}


async def _portfolio_for(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Compact portfolio summary for tool consumption (NOT the REST shape).

    Optimised for the LLM: small, scalar-only, easy to ground from. Returns:
        {
          user_id, total_market_value, total_cost_basis, unrealized_pl,
          unrealized_pl_pct, allocation: [{asset_class, weight}],
          top_positions: [{symbol, quantity, market_value, asset_class}, ...],
          account_count,
        }
    """
    accounts = (
        await session.scalars(select(Account).where(Account.user_id == user_id))
    ).all()
    if not accounts:
        return {
            "user_id": str(user_id),
            "total_market_value": "0",
            "total_cost_basis": "0",
            "unrealized_pl": "0",
            "unrealized_pl_pct": 0.0,
            "allocation": [],
            "top_positions": [],
            "account_count": 0,
        }

    positions = (
        await session.scalars(
            select(Position).where(Position.account_id.in_([a.id for a in accounts]))
        )
    ).all()
    symbols = sorted({p.symbol for p in positions})
    prices = await _latest_prices(session, symbols)

    by_class: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    total_mv = Decimal("0")
    total_cost = Decimal("0")
    enriched: list[dict[str, Any]] = []
    for p in positions:
        last_price = prices.get(p.symbol, p.avg_cost)
        mv = (p.quantity * last_price).quantize(Decimal("0.01"))
        cost = (p.quantity * p.avg_cost).quantize(Decimal("0.01"))
        total_mv += mv
        total_cost += cost
        by_class[p.asset_class.value] += mv
        enriched.append(
            {
                "symbol": p.symbol,
                "quantity": str(p.quantity),
                "market_value": str(mv),
                "asset_class": p.asset_class.value,
            }
        )
    pl = total_mv - total_cost
    pl_pct = float(pl / total_cost * 100) if total_cost > 0 else 0.0
    allocation = (
        [
            {"asset_class": ac, "weight": round(float(mv / total_mv), 4)}
            for ac, mv in by_class.items()
        ]
        if total_mv > 0
        else []
    )
    enriched.sort(key=lambda x: Decimal(x["market_value"]), reverse=True)
    return {
        "user_id": str(user_id),
        "total_market_value": str(total_mv),
        "total_cost_basis": str(total_cost),
        "unrealized_pl": str(pl),
        "unrealized_pl_pct": round(pl_pct, 2),
        "allocation": sorted(allocation, key=lambda x: x["weight"], reverse=True),
        "top_positions": enriched[:5],
        "account_count": len(accounts),
    }


async def _risk_for(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Deterministic risk score for a user; mirrors /api/v1/risk shape."""
    rows = (
        await session.execute(
            select(Position, Account.user_id)
            .join(Account, Position.account_id == Account.id)
            .where(Account.user_id == user_id)
        )
    ).all()
    symbols = sorted({p.symbol for (p, _) in rows})
    prices = await _latest_prices(session, symbols)
    inputs: list[PositionRow] = [
        PositionRow(
            symbol=p.symbol,
            asset_class=AssetClass(p.asset_class.value),
            market_value=p.quantity * prices.get(p.symbol, p.avg_cost),
        )
        for (p, _) in rows
    ]
    a = compute_risk_score(inputs)
    return {
        "user_id": str(user_id),
        "score": a.score,
        "label": a.label,
        "drivers": a.drivers,
    }


async def list_clients(*, session: AsyncSession | None = None) -> list[dict[str, Any]]:
    """Advisor tool — list every client + a one-line portfolio summary.

    Mirrors GET /api/v1/clients but returns simple scalar dicts so the LLM
    can quote them. Sorted by descending market_value (book-of-business view).
    """
    async def _run(s: AsyncSession) -> list[dict[str, Any]]:
        clients = (
            await s.scalars(
                select(User).where(User.role == UserRole.client).order_by(User.email.asc())
            )
        ).all()
        out: list[dict[str, Any]] = []
        for c in clients:
            p = await _portfolio_for(s, c.id)
            out.append(
                {
                    "client_id": str(c.id),
                    "email": c.email,
                    "display_name": c.display_name,
                    "market_value": p["total_market_value"],
                    "account_count": p["account_count"],
                }
            )
        out.sort(key=lambda x: Decimal(x["market_value"]), reverse=True)
        return out

    if session is not None:
        return await _run(session)
    async with AsyncSessionLocal() as s:
        return await _run(s)


async def get_client_portfolio(
    client_id: str, *, session: AsyncSession | None = None
) -> dict[str, Any]:
    """Advisor tool — full portfolio summary for one client_id (UUID string)."""
    try:
        uid = uuid.UUID(client_id)
    except ValueError:
        return {"error": f"invalid client_id: {client_id!r}"}

    async def _run(s: AsyncSession) -> dict[str, Any]:
        user = await s.get(User, uid)
        if user is None:
            return {"error": f"client not found: {client_id}"}
        return await _portfolio_for(s, uid)

    if session is not None:
        return await _run(session)
    async with AsyncSessionLocal() as s:
        return await _run(s)


async def get_client_risk(
    client_id: str, *, session: AsyncSession | None = None
) -> dict[str, Any]:
    """Advisor tool — risk score for one client_id."""
    try:
        uid = uuid.UUID(client_id)
    except ValueError:
        return {"error": f"invalid client_id: {client_id!r}"}

    async def _run(s: AsyncSession) -> dict[str, Any]:
        user = await s.get(User, uid)
        if user is None:
            return {"error": f"client not found: {client_id}"}
        return await _risk_for(s, uid)

    if session is not None:
        return await _run(session)
    async with AsyncSessionLocal() as s:
        return await _run(s)


async def get_user_portfolio(
    user_id: str, *, session: AsyncSession | None = None
) -> dict[str, Any]:
    """Client tool — caller's own portfolio. Same shape as get_client_portfolio."""
    return await get_client_portfolio(user_id, session=session)


async def get_user_goals(
    user_id: str, *, session: AsyncSession | None = None
) -> list[dict[str, Any]]:
    """Client tool — caller's own goals."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return []

    async def _run(s: AsyncSession) -> list[dict[str, Any]]:
        rows = (
            await s.scalars(
                select(Goal).where(Goal.user_id == uid).order_by(Goal.created_at.asc())
            )
        ).all()
        return [
            {
                "id": str(g.id),
                "name": g.name,
                "target_amount": str(g.target_amount),
                "target_date": g.target_date.isoformat(),
                "current_amount": str(g.current_amount),
            }
            for g in rows
        ]

    if session is not None:
        return await _run(session)
    async with AsyncSessionLocal() as s:
        return await _run(s)


# ---------- OpenAI tool-call schemas ----------
# These describe the tools above to the model. Built once at import; immutable.
ADVISOR_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_clients",
            "description": (
                "List every client this advisor manages, with each client's "
                "id, name, email, total market value, and account count. "
                "Use this FIRST for any question about 'my book' or 'my clients'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_client_portfolio",
            "description": (
                "Get a single client's full portfolio: totals, allocation, "
                "and top positions. Requires a client_id from list_clients."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "UUID from list_clients"}
                },
                "required": ["client_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_client_risk",
            "description": (
                "Get a client's risk assessment: score (0-100), label "
                "(conservative|moderate|aggressive), and the driver bullets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "UUID from list_clients"}
                },
                "required": ["client_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search the firm's knowledge corpus for guidance, policy, or product info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
]

CLIENT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_user_portfolio",
            "description": (
                "Get the user's own portfolio: totals, allocation, and top "
                "positions. Use whenever the user asks about THEIR holdings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "the caller's own user_id (UUID)"}
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_goals",
            "description": "List the user's saved financial goals with progress.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "the caller's own user_id (UUID)"}
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search the firm's knowledge corpus for guidance or product info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
]


# Map name -> async callable. Used by analyst.py to dispatch tool_calls.
TOOL_DISPATCH: dict[str, Any] = {
    "list_clients": list_clients,
    "get_client_portfolio": get_client_portfolio,
    "get_client_risk": get_client_risk,
    "get_user_portfolio": get_user_portfolio,
    "get_user_goals": get_user_goals,
    "rag_search": rag_search,
}
