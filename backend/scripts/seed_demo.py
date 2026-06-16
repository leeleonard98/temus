"""Idempotent seed for the AuraWealth demo (Phase 2).

Creates two users (one client, one advisor), gives the client three accounts
with realistic-looking holdings + two goals, and gives the advisor a sandbox
account so prompts that operate on positions still work for them.

Also seeds one current-time price row per symbol so the portfolio endpoint
has a `last_price` to multiply by.

Usage:
    python -m scripts.seed_demo
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import (
    Account,
    AccountKind,
    AssetClass,
    Goal,
    Position,
    Price,
    User,
    UserRole,
)
from app.db.session import AsyncSessionLocal

log = logging.getLogger("seed_demo")

CLIENT_EMAIL = "client-demo@aura.test"
ADVISOR_EMAIL = "advisor-demo@aura.test"


@dataclass(frozen=True)
class _Holding:
    symbol: str
    quantity: Decimal
    avg_cost: Decimal
    asset_class: AssetClass
    last_price: Decimal  # used to seed the prices table


# Realistic-ish prices as of mid-2026. Tweaked to roughly match the goals.
_CLIENT_HOLDINGS: dict[str, list[_Holding]] = {
    "Joint Brokerage": [
        _Holding("AAPL", Decimal("120"), Decimal("145.20"), AssetClass.equity, Decimal("192.50")),
        _Holding("MSFT", Decimal("80"),  Decimal("310.00"), AssetClass.equity, Decimal("415.30")),
        _Holding("NVDA", Decimal("45"),  Decimal("420.00"), AssetClass.equity, Decimal("740.10")),
        _Holding("VOO",  Decimal("250"), Decimal("380.00"), AssetClass.equity, Decimal("510.75")),
        _Holding("BND",  Decimal("400"), Decimal("72.50"),  AssetClass.bond,   Decimal("69.80")),
    ],
    "Roth IRA": [
        _Holding("VOO",  Decimal("150"), Decimal("330.00"), AssetClass.equity, Decimal("510.75")),
        _Holding("AAPL", Decimal("60"),  Decimal("130.00"), AssetClass.equity, Decimal("192.50")),
        _Holding("BND",  Decimal("250"), Decimal("78.00"),  AssetClass.bond,   Decimal("69.80")),
        _Holding("MSFT", Decimal("30"),  Decimal("250.00"), AssetClass.equity, Decimal("415.30")),
    ],
    "Cash": [
        _Holding("USD",  Decimal("42000"), Decimal("1.00"), AssetClass.cash, Decimal("1.00")),
        _Holding("USDX-MM", Decimal("18000"), Decimal("1.00"), AssetClass.cash, Decimal("1.00")),
        _Holding("VOO",  Decimal("5"), Decimal("470.00"), AssetClass.equity, Decimal("510.75")),
    ],
}

_CLIENT_ACCOUNT_KINDS: dict[str, AccountKind] = {
    "Joint Brokerage": AccountKind.brokerage,
    "Roth IRA": AccountKind.retirement,
    "Cash": AccountKind.cash,
}

_CLIENT_GOALS = [
    {
        "name": "Retirement at 60",
        "target_amount": Decimal("1500000.00"),
        "target_date": date(2055, 1, 1),
        "current_amount": Decimal("180000.00"),
    },
    {
        "name": "House down payment",
        "target_amount": Decimal("120000.00"),
        "target_date": date(2028, 6, 1),
        "current_amount": Decimal("42000.00"),
    },
]

_ADVISOR_HOLDINGS = [
    _Holding("AAPL", Decimal("10"), Decimal("180.00"), AssetClass.equity, Decimal("192.50")),
    _Holding("VOO",  Decimal("20"), Decimal("450.00"), AssetClass.equity, Decimal("510.75")),
]


async def _upsert_user(session, *, email: str, display_name: str, role: UserRole) -> User:
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        return existing
    u = User(email=email, display_name=display_name, role=role)
    session.add(u)
    await session.flush()
    return u


async def _ensure_account(session, *, user_id, name: str, kind: AccountKind) -> Account:
    existing = await session.scalar(
        select(Account).where(Account.user_id == user_id, Account.name == name)
    )
    if existing is not None:
        return existing
    acct = Account(user_id=user_id, name=name, kind=kind)
    session.add(acct)
    await session.flush()
    return acct


async def _ensure_position(session, *, account_id, h: _Holding) -> None:
    existing = await session.scalar(
        select(Position).where(
            Position.account_id == account_id, Position.symbol == h.symbol
        )
    )
    if existing is not None:
        # Update qty/avg_cost in case values were tweaked between runs.
        existing.quantity = h.quantity
        existing.avg_cost = h.avg_cost
        existing.asset_class = h.asset_class
        return
    session.add(
        Position(
            account_id=account_id,
            symbol=h.symbol,
            quantity=h.quantity,
            avg_cost=h.avg_cost,
            asset_class=h.asset_class,
        )
    )


async def _ensure_goal(session, *, user_id, goal: dict) -> None:
    existing = await session.scalar(
        select(Goal).where(Goal.user_id == user_id, Goal.name == goal["name"])
    )
    if existing is not None:
        existing.target_amount = goal["target_amount"]
        existing.target_date = goal["target_date"]
        existing.current_amount = goal["current_amount"]
        return
    session.add(Goal(user_id=user_id, **goal))


async def _seed_prices(session, holdings: list[_Holding]) -> None:
    """Insert one synthetic price row per symbol at "now". ON CONFLICT no-op."""
    now = datetime.now(tz=timezone.utc)
    seen: set[str] = set()
    for h in holdings:
        if h.symbol in seen:
            continue
        seen.add(h.symbol)
        stmt = (
            pg_insert(Price)
            .values(symbol=h.symbol, ts=now, price=h.last_price)
            .on_conflict_do_nothing(index_elements=["symbol", "ts"])
        )
        await session.execute(stmt)


async def seed() -> dict:
    """Seed the demo data. Returns a small summary for logging / tests."""
    async with AsyncSessionLocal() as session:
        client = await _upsert_user(
            session,
            email=CLIENT_EMAIL,
            display_name="Demo Client",
            role=UserRole.client,
        )
        advisor = await _upsert_user(
            session,
            email=ADVISOR_EMAIL,
            display_name="Demo Advisor",
            role=UserRole.advisor,
        )

        all_holdings: list[_Holding] = []
        for acct_name, holdings in _CLIENT_HOLDINGS.items():
            acct = await _ensure_account(
                session,
                user_id=client.id,
                name=acct_name,
                kind=_CLIENT_ACCOUNT_KINDS[acct_name],
            )
            for h in holdings:
                await _ensure_position(session, account_id=acct.id, h=h)
                all_holdings.append(h)

        for g in _CLIENT_GOALS:
            await _ensure_goal(session, user_id=client.id, goal=g)

        # Advisor sandbox account so portfolio queries also work for them.
        advisor_acct = await _ensure_account(
            session,
            user_id=advisor.id,
            name="Advisor Sandbox",
            kind=AccountKind.brokerage,
        )
        for h in _ADVISOR_HOLDINGS:
            await _ensure_position(session, account_id=advisor_acct.id, h=h)
            all_holdings.append(h)

        await _seed_prices(session, all_holdings)
        await session.commit()

        # Counts for the caller.
        n_acct = (
            await session.execute(
                select(Account).where(Account.user_id == client.id)
            )
        ).all()
        n_pos = (
            await session.execute(
                select(Position)
                .join(Account, Position.account_id == Account.id)
                .where(Account.user_id == client.id)
            )
        ).all()

        summary = {
            "client_id": str(client.id),
            "advisor_id": str(advisor.id),
            "client_accounts": len(n_acct),
            "client_positions": len(n_pos),
        }

    log.info("seed complete: %s", summary)
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    summary = asyncio.run(seed())
    print(summary)


if __name__ == "__main__":
    main()
