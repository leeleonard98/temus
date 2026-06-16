"""Deterministic risk-score calculation (AC5).

Inputs: positions with their current market values + asset classes.
Output: a 0-100 risk score, a label, and the top contributing positions.

The numbers are pinned in `_RISK_WEIGHTS`. They reflect a simple
"how volatile is this asset class" heuristic — not a real risk model.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.db.models import AssetClass

# Per-asset-class risk contribution. Bigger = more volatile.
_RISK_WEIGHTS: dict[AssetClass, int] = {
    AssetClass.cash: 5,
    AssetClass.bond: 20,
    AssetClass.equity: 70,
    AssetClass.crypto: 95,
    AssetClass.alt: 60,
}

# Label thresholds — match the spec ("<34 conservative, 34-66 moderate, >66 aggressive").
_CONSERVATIVE_MAX = 34
_MODERATE_MAX = 66


@dataclass(frozen=True)
class PositionRow:
    """Minimal projection of a Position for risk math."""

    symbol: str
    asset_class: AssetClass
    market_value: Decimal


@dataclass(frozen=True)
class RiskAssessment:
    """Result of `compute_risk_score`."""

    score: int  # 0..100
    label: str  # "conservative" | "moderate" | "aggressive"
    drivers: list[str]  # top-3 contributors as human-readable strings


def _label_for(score: int) -> str:
    if score < _CONSERVATIVE_MAX:
        return "conservative"
    if score <= _MODERATE_MAX:
        return "moderate"
    return "aggressive"


def compute_risk_score(positions: list[PositionRow]) -> RiskAssessment:
    """Weighted-by-market-value risk score across the positions.

    Edge cases:
      * Empty list → score=0, label=conservative, drivers=[].
      * Negative or zero market values are clamped to 0 (a short shouldn't
        push the score down through "fake" weight).
    """
    if not positions:
        return RiskAssessment(score=0, label="conservative", drivers=[])

    weighted = []  # (PositionRow, contribution_to_total)
    total_mv = Decimal("0")
    for p in positions:
        mv = p.market_value if p.market_value > 0 else Decimal("0")
        total_mv += mv

    if total_mv == 0:
        return RiskAssessment(score=0, label="conservative", drivers=[])

    score_acc = Decimal("0")
    for p in positions:
        mv = p.market_value if p.market_value > 0 else Decimal("0")
        if mv == 0:
            continue
        weight = _RISK_WEIGHTS.get(p.asset_class, 50)
        contribution = (mv / total_mv) * Decimal(weight)
        score_acc += contribution
        weighted.append((p, contribution))

    score = int(round(score_acc))
    score = max(0, min(100, score))
    label = _label_for(score)

    weighted.sort(key=lambda t: t[1], reverse=True)
    drivers = [
        f"{p.symbol} ({p.asset_class.value}) — {float(c):.1f} pts"
        for p, c in weighted[:3]
    ]

    return RiskAssessment(score=score, label=label, drivers=drivers)
