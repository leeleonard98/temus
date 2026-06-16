"""Account model — a brokerage / cash / retirement / crypto bucket owned by a User."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccountKind(str, enum.Enum):
    """Account container type — drives default asset_class assumptions and UI grouping."""

    cash = "cash"
    brokerage = "brokerage"
    retirement = "retirement"
    crypto = "crypto"


class Account(Base):
    """A logical account bucket (e.g. "Joint Brokerage", "Roth IRA")."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[AccountKind] = mapped_column(
        Enum(
            AccountKind,
            name="account_kind",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
