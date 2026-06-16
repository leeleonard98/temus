"""Pydantic schemas for the portfolio / goals / risk / clients endpoints."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    symbol: str
    quantity: Decimal
    avg_cost: Decimal
    last_price: Decimal
    market_value: Decimal
    asset_class: Literal["equity", "bond", "cash", "crypto", "alt"]


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    kind: Literal["cash", "brokerage", "retirement", "crypto"]
    positions: list[PositionOut]


class PortfolioTotals(BaseModel):
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pl: Decimal
    unrealized_pl_pct: float


class AllocationSlice(BaseModel):
    asset_class: Literal["equity", "bond", "cash", "crypto", "alt"]
    weight: float


class PortfolioOut(BaseModel):
    user_id: uuid.UUID
    accounts: list[AccountOut]
    totals: PortfolioTotals
    allocation: list[AllocationSlice]


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    target_amount: Decimal
    target_date: date
    current_amount: Decimal
    created_at: datetime


class RiskOut(BaseModel):
    user_id: uuid.UUID
    score: int
    label: Literal["conservative", "moderate", "aggressive"]
    drivers: list[str]


class ClientSummary(BaseModel):
    """One-line summary of a client for the advisor dashboard."""

    id: uuid.UUID
    email: str
    display_name: str
    market_value: Decimal
    account_count: int
