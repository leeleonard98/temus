"""Position — a holding of a single symbol within an Account."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetClass(str, enum.Enum):
    """Asset-class label — drives risk weighting (AC5) and allocation charts."""

    equity = "equity"
    bond = "bond"
    cash = "cash"
    crypto = "crypto"
    alt = "alt"


class Position(Base):
    """A holding: how much of `symbol` we own in this `account`."""

    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    asset_class: Mapped[AssetClass] = mapped_column(
        Enum(
            AssetClass,
            name="asset_class",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
