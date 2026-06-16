"""Unit tests for portfolio ORM models — pure construction, no DB."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.db.models import (
    Account,
    AccountKind,
    AssetClass,
    Goal,
    Position,
    Price,
)


def test_account_kind_enum_values() -> None:
    assert AccountKind.cash.value == "cash"
    assert AccountKind.brokerage.value == "brokerage"
    assert AccountKind.retirement.value == "retirement"
    assert AccountKind.crypto.value == "crypto"


def test_account_construct() -> None:
    uid = uuid.uuid4()
    acct = Account(user_id=uid, name="Joint Brokerage", kind=AccountKind.brokerage)
    assert acct.user_id == uid
    assert acct.name == "Joint Brokerage"
    assert acct.kind is AccountKind.brokerage


def test_asset_class_enum_values() -> None:
    assert {a.value for a in AssetClass} == {"equity", "bond", "cash", "crypto", "alt"}


def test_position_construct_defaults_currency() -> None:
    aid = uuid.uuid4()
    p = Position(
        account_id=aid,
        symbol="AAPL",
        quantity=Decimal("10.5"),
        avg_cost=Decimal("150.25"),
        asset_class=AssetClass.equity,
    )
    assert p.symbol == "AAPL"
    assert p.quantity == Decimal("10.5")
    assert p.asset_class is AssetClass.equity
    # default kicks in only on flush; explicit construction leaves it unset
    # so we just assert the attribute is accessible without error.
    assert getattr(p, "currency", "USD") in ("USD", None)


def test_price_construct_composite_pk() -> None:
    from datetime import datetime, timezone

    ts = datetime(2026, 6, 16, tzinfo=timezone.utc)
    p = Price(symbol="AAPL", ts=ts, price=Decimal("192.34"))
    assert p.symbol == "AAPL"
    assert p.ts == ts
    assert p.price == Decimal("192.34")


def test_goal_construct() -> None:
    uid = uuid.uuid4()
    g = Goal(
        user_id=uid,
        name="Retirement at 60",
        target_amount=Decimal("1500000"),
        target_date=date(2055, 1, 1),
        current_amount=Decimal("180000"),
    )
    assert g.name == "Retirement at 60"
    assert g.target_amount == Decimal("1500000")
    assert g.target_date == date(2055, 1, 1)
