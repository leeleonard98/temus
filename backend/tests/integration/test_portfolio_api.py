"""Integration tests for /portfolio, /goals, /risk, /clients."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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

pytestmark = pytest.mark.asyncio


async def _make_demo_data(session: AsyncSession) -> tuple[User, User]:
    """Insert one client + one advisor with a small but realistic portfolio."""
    client = User(
        email="client@aura.test", display_name="Demo Client", role=UserRole.client
    )
    advisor = User(
        email="advisor@aura.test", display_name="Demo Advisor", role=UserRole.advisor
    )
    session.add_all([client, advisor])
    await session.flush()

    brokerage = Account(user_id=client.id, name="Brokerage", kind=AccountKind.brokerage)
    cash_acct = Account(user_id=client.id, name="Cash", kind=AccountKind.cash)
    session.add_all([brokerage, cash_acct])
    await session.flush()

    session.add_all(
        [
            Position(
                account_id=brokerage.id,
                symbol="AAPL",
                quantity=Decimal("10"),
                avg_cost=Decimal("100"),
                asset_class=AssetClass.equity,
            ),
            Position(
                account_id=brokerage.id,
                symbol="BND",
                quantity=Decimal("50"),
                avg_cost=Decimal("80"),
                asset_class=AssetClass.bond,
            ),
            Position(
                account_id=cash_acct.id,
                symbol="USD",
                quantity=Decimal("2000"),
                avg_cost=Decimal("1"),
                asset_class=AssetClass.cash,
            ),
        ]
    )

    now = datetime.now(tz=timezone.utc)
    session.add_all(
        [
            Price(symbol="AAPL", ts=now, price=Decimal("200")),
            Price(symbol="BND", ts=now, price=Decimal("70")),
            Price(symbol="USD", ts=now, price=Decimal("1")),
        ]
    )

    session.add(
        Goal(
            user_id=client.id,
            name="Retirement",
            target_amount=Decimal("1000000"),
            target_date=date(2055, 1, 1),
            current_amount=Decimal("12345.67"),
        )
    )
    await session.commit()
    return client, advisor


async def test_portfolio_returns_expected_shape(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    user, _ = await _make_demo_data(async_session)
    resp = await client.get(f"/api/v1/portfolio?user_id={user.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["user_id"] == str(user.id)
    assert len(body["accounts"]) == 2
    by_name = {a["name"]: a for a in body["accounts"]}
    assert "Brokerage" in by_name and "Cash" in by_name

    aapl = next(p for p in by_name["Brokerage"]["positions"] if p["symbol"] == "AAPL")
    # market_value = 10 * 200 = 2000
    assert Decimal(aapl["market_value"]) == Decimal("2000.00")
    assert Decimal(aapl["last_price"]) == Decimal("200")

    # totals: AAPL 2000 + BND 3500 + USD 2000 = 7500 mv; cost = 1000 + 4000 + 2000 = 7000
    totals = body["totals"]
    assert Decimal(totals["market_value"]) == Decimal("7500.00")
    assert Decimal(totals["cost_basis"]) == Decimal("7000.00")
    assert Decimal(totals["unrealized_pl"]) == Decimal("500.00")

    weights = {a["asset_class"]: a["weight"] for a in body["allocation"]}
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-3)
    assert weights.get("equity", 0) > 0


async def test_portfolio_unknown_user_404(client: AsyncClient) -> None:
    import uuid

    resp = await client.get(f"/api/v1/portfolio?user_id={uuid.uuid4()}")
    assert resp.status_code == 404


async def test_goals_returns_seeded_goal(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    user, _ = await _make_demo_data(async_session)
    resp = await client.get(f"/api/v1/goals?user_id={user.id}")
    assert resp.status_code == 200
    goals = resp.json()
    assert len(goals) == 1
    assert goals[0]["name"] == "Retirement"
    assert Decimal(goals[0]["current_amount"]) == Decimal("12345.67")


async def test_risk_returns_label_and_drivers(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    user, _ = await _make_demo_data(async_session)
    resp = await client.get(f"/api/v1/risk?user_id={user.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] in ("conservative", "moderate", "aggressive")
    assert isinstance(body["score"], int)
    assert 0 <= body["score"] <= 100
    assert len(body["drivers"]) <= 3


async def test_clients_advisor_view(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    user, _advisor = await _make_demo_data(async_session)
    resp = await client.get("/api/v1/clients")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1  # only the client user has role=client
    only = body[0]
    assert only["email"] == "client@aura.test"
    assert only["account_count"] == 2
    assert Decimal(only["market_value"]) == Decimal("7500.00")
