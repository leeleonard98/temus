"""Price — append-only tick log keyed by (symbol, ts).

Populated by:
  * the seed script (one row per symbol at "now")
  * the simulated `/prices/stream` endpoint (every Nth tick is persisted)

Read by the portfolio endpoint to compute `last_price` per holding.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Price(Base):
    """A point-in-time price tick. Composite PK (symbol, ts)."""

    __tablename__ = "prices"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    __table_args__ = (
        # Recent-first lookups: "give me the latest price for AAPL" is `ORDER BY ts DESC LIMIT 1`.
        Index("ix_prices_symbol_ts_desc", "symbol", ts.desc()),
    )
