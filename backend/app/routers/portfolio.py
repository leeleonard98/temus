"""Portfolio, goals, risk, and clients endpoints (Phase 2).

All read-only. The portfolio endpoint joins positions to the latest price
per symbol and computes totals + asset-class allocation in one pass.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_session
from app.db.models import (
    Account,
    AssetClass,
    Goal,
    Position,
    Price,
    User,
    UserRole,
)
from app.schemas.portfolio import (
    AccountOut,
    AllocationSlice,
    ClientSummary,
    GoalOut,
    PortfolioOut,
    PortfolioTotals,
    PositionOut,
    RiskOut,
)
from app.services.risk import PositionRow, compute_risk_score

router = APIRouter(tags=["portfolio"])


async def _latest_prices(
    session: AsyncSession, symbols: list[str]
) -> dict[str, Decimal]:
    """Return a dict mapping symbol → most-recent price.

    Falls back to 0 if no price row exists for a symbol; the caller can detect
    that and treat it as unknown (the UI shows the avg_cost in that case).
    """
    if not symbols:
        return {}
    # Window-function approach is overkill; group-max is fine here.
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


@router.get("/portfolio", response_model=PortfolioOut)
async def get_portfolio(
    user_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
) -> PortfolioOut:
    """Return the user's full portfolio with totals and allocation."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    # Pull accounts + positions in two queries (FK indexed, cheap).
    accounts = (
        await session.scalars(
            select(Account)
            .where(Account.user_id == user_id)
            .order_by(Account.created_at.asc())
        )
    ).all()

    if not accounts:
        return PortfolioOut(
            user_id=user_id,
            accounts=[],
            totals=PortfolioTotals(
                market_value=Decimal("0"),
                cost_basis=Decimal("0"),
                unrealized_pl=Decimal("0"),
                unrealized_pl_pct=0.0,
            ),
            allocation=[],
        )

    account_ids = [a.id for a in accounts]
    positions = (
        await session.scalars(
            select(Position).where(Position.account_id.in_(account_ids))
        )
    ).all()

    symbols = sorted({p.symbol for p in positions})
    prices = await _latest_prices(session, symbols)

    # Build per-account position lists + accumulate totals & allocation.
    by_acct: dict[uuid.UUID, list[PositionOut]] = defaultdict(list)
    total_mv = Decimal("0")
    total_cost = Decimal("0")
    by_class_mv: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for p in positions:
        last_price = prices.get(p.symbol, p.avg_cost)  # graceful fallback
        mv = (p.quantity * last_price).quantize(Decimal("0.01"))
        cost = (p.quantity * p.avg_cost).quantize(Decimal("0.01"))
        total_mv += mv
        total_cost += cost
        by_class_mv[p.asset_class.value] += mv
        by_acct[p.account_id].append(
            PositionOut(
                symbol=p.symbol,
                quantity=p.quantity,
                avg_cost=p.avg_cost,
                last_price=last_price,
                market_value=mv,
                asset_class=p.asset_class.value,
            )
        )

    accounts_out = [
        AccountOut(
            id=a.id,
            name=a.name,
            kind=a.kind.value,
            positions=sorted(
                by_acct.get(a.id, []), key=lambda x: x.market_value, reverse=True
            ),
        )
        for a in accounts
    ]

    pl = total_mv - total_cost
    pl_pct = float(pl / total_cost * 100) if total_cost > 0 else 0.0
    totals = PortfolioTotals(
        market_value=total_mv,
        cost_basis=total_cost,
        unrealized_pl=pl,
        unrealized_pl_pct=round(pl_pct, 2),
    )

    if total_mv > 0:
        allocation = sorted(
            [
                AllocationSlice(asset_class=ac, weight=round(float(mv / total_mv), 4))
                for ac, mv in by_class_mv.items()
            ],
            key=lambda s: s.weight,
            reverse=True,
        )
    else:
        allocation = []

    return PortfolioOut(
        user_id=user_id,
        accounts=accounts_out,
        totals=totals,
        allocation=allocation,
    )


@router.get("/goals", response_model=list[GoalOut])
async def list_goals(
    user_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[GoalOut]:
    """List a user's goals, oldest first (matches typical "set in this order" UI)."""
    rows = (
        await session.scalars(
            select(Goal)
            .where(Goal.user_id == user_id)
            .order_by(Goal.created_at.asc())
        )
    ).all()
    return [GoalOut.model_validate(r) for r in rows]


@router.get("/risk", response_model=RiskOut)
async def get_risk(
    user_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RiskOut:
    """AC5: deterministic risk score over the user's positions."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    rows = (
        await session.execute(
            select(Position, Account.user_id)
            .join(Account, Position.account_id == Account.id)
            .where(Account.user_id == user_id)
        )
    ).all()

    symbols = sorted({p.symbol for (p, _) in rows})
    prices = await _latest_prices(session, symbols)

    inputs: list[PositionRow] = []
    for p, _ in rows:
        last_price = prices.get(p.symbol, p.avg_cost)
        inputs.append(
            PositionRow(
                symbol=p.symbol,
                asset_class=AssetClass(p.asset_class.value),
                market_value=p.quantity * last_price,
            )
        )

    assessment = compute_risk_score(inputs)
    return RiskOut(
        user_id=user_id,
        score=assessment.score,
        label=assessment.label,
        drivers=assessment.drivers,
    )


@router.get("/clients", response_model=list[ClientSummary])
async def list_clients(
    session: AsyncSession = Depends(get_session),
) -> list[ClientSummary]:
    """Advisor view: every user with role=client + a one-line portfolio summary."""
    clients = (
        await session.scalars(
            select(User).where(User.role == UserRole.client).order_by(User.email.asc())
        )
    ).all()

    summaries: list[ClientSummary] = []
    for c in clients:
        # Account count + market value via positions × latest prices.
        accts = (
            await session.scalars(
                select(Account).where(Account.user_id == c.id)
            )
        ).all()
        if not accts:
            summaries.append(
                ClientSummary(
                    id=c.id,
                    email=c.email,
                    display_name=c.display_name,
                    market_value=Decimal("0"),
                    account_count=0,
                )
            )
            continue
        positions = (
            await session.scalars(
                select(Position).where(
                    Position.account_id.in_([a.id for a in accts])
                )
            )
        ).all()
        symbols = sorted({p.symbol for p in positions})
        prices = await _latest_prices(session, symbols)
        mv = sum(
            (p.quantity * prices.get(p.symbol, p.avg_cost) for p in positions),
            start=Decimal("0"),
        )
        summaries.append(
            ClientSummary(
                id=c.id,
                email=c.email,
                display_name=c.display_name,
                market_value=mv.quantize(Decimal("0.01")),
                account_count=len(accts),
            )
        )
    return summaries
