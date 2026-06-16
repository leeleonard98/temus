"""Unit tests for the deterministic risk-score calculator (AC5)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.db.models import AssetClass
from app.services.risk import PositionRow, compute_risk_score


def _row(asset_class: AssetClass, market_value: float, symbol: str = "X") -> PositionRow:
    return PositionRow(
        symbol=symbol, asset_class=asset_class, market_value=Decimal(str(market_value))
    )


def test_empty_positions_returns_zero_conservative() -> None:
    r = compute_risk_score([])
    assert r.score == 0
    assert r.label == "conservative"
    assert r.drivers == []


def test_all_cash_is_conservative() -> None:
    r = compute_risk_score([_row(AssetClass.cash, 1000)])
    assert r.score == 5
    assert r.label == "conservative"


def test_all_crypto_is_aggressive() -> None:
    r = compute_risk_score([_row(AssetClass.crypto, 1000)])
    assert r.score == 95
    assert r.label == "aggressive"


def test_balanced_60_40_equity_bond_is_moderate() -> None:
    # 60% equity (70) + 40% bond (20) = 42 + 8 = 50 → moderate
    rows = [
        _row(AssetClass.equity, 600, "VOO"),
        _row(AssetClass.bond, 400, "BND"),
    ]
    r = compute_risk_score(rows)
    assert r.score == 50
    assert r.label == "moderate"


def test_label_boundary_lt_34_conservative() -> None:
    # 80% bond (20) + 20% equity (70) = 16 + 14 = 30 → conservative
    rows = [
        _row(AssetClass.bond, 800),
        _row(AssetClass.equity, 200),
    ]
    r = compute_risk_score(rows)
    assert r.score == 30
    assert r.label == "conservative"


def test_label_boundary_gt_66_aggressive() -> None:
    # 95% equity (70) + 5% cash (5) = 66.5 + 0.25 = 66.75 → aggressive (>66)
    rows = [
        _row(AssetClass.equity, 950),
        _row(AssetClass.cash, 50),
    ]
    r = compute_risk_score(rows)
    assert r.score >= 67
    assert r.label == "aggressive"


def test_drivers_top_three_by_contribution() -> None:
    rows = [
        _row(AssetClass.equity, 600, "VOO"),    # 60% * 70 = 42
        _row(AssetClass.bond, 200, "BND"),       # 20% * 20 = 4
        _row(AssetClass.cash, 100, "USD"),       # 10% * 5 = 0.5
        _row(AssetClass.crypto, 100, "BTC"),     # 10% * 95 = 9.5
    ]
    r = compute_risk_score(rows)
    assert len(r.drivers) == 3
    # Top contributor first (equity), then crypto, then bond.
    assert "equity" in r.drivers[0].lower() or "VOO" in r.drivers[0]


def test_zero_market_value_positions_ignored() -> None:
    rows = [
        _row(AssetClass.equity, 0),
        _row(AssetClass.cash, 100),
    ]
    r = compute_risk_score(rows)
    assert r.score == 5  # treated as all-cash


def test_negative_market_value_clamped_to_zero() -> None:
    # Defensive: a short position shouldn't break the calc.
    rows = [
        _row(AssetClass.equity, -100),
        _row(AssetClass.cash, 100),
    ]
    r = compute_risk_score(rows)
    assert r.label in ("conservative", "moderate", "aggressive")
    assert 0 <= r.score <= 100


@pytest.mark.parametrize(
    "ac,expected_weight",
    [
        (AssetClass.cash, 5),
        (AssetClass.bond, 20),
        (AssetClass.equity, 70),
        (AssetClass.alt, 60),
        (AssetClass.crypto, 95),
    ],
)
def test_single_class_score_matches_weight(ac: AssetClass, expected_weight: int) -> None:
    r = compute_risk_score([_row(ac, 1000)])
    assert r.score == expected_weight
