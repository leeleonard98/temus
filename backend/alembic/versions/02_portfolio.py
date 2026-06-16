"""02_portfolio: accounts, positions, prices, goals

Revision ID: 02_portfolio
Revises: cc68bfd490f2
Create Date: 2026-06-16 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02_portfolio"
down_revision: Union[str, None] = "cc68bfd490f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # accounts
    op.create_table(
        "accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "cash",
                "brokerage",
                "retirement",
                "crypto",
                name="account_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_accounts_user_id"), "accounts", ["user_id"], unique=False)

    # positions
    op.create_table(
        "positions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("avg_cost", sa.Numeric(20, 8), nullable=False),
        sa.Column(
            "asset_class",
            sa.Enum(
                "equity",
                "bond",
                "cash",
                "crypto",
                "alt",
                name="asset_class",
            ),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'USD'"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_positions_account_id"), "positions", ["account_id"], unique=False
    )

    # prices — composite PK (symbol, ts), idx for "latest by symbol"
    op.create_table(
        "prices",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "ts"),
    )
    op.create_index(
        "ix_prices_symbol_ts_desc",
        "prices",
        ["symbol", sa.text("ts DESC")],
        unique=False,
    )

    # goals
    op.create_table(
        "goals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("target_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column(
            "current_amount",
            sa.Numeric(20, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_goals_user_id"), "goals", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_goals_user_id"), table_name="goals")
    op.drop_table("goals")
    op.drop_index("ix_prices_symbol_ts_desc", table_name="prices")
    op.drop_table("prices")
    op.drop_index(op.f("ix_positions_account_id"), table_name="positions")
    op.drop_table("positions")
    op.drop_index(op.f("ix_accounts_user_id"), table_name="accounts")
    op.drop_table("accounts")
    # Drop SQL enum types — Alembic autogenerate doesn't emit these and they
    # otherwise persist between downgrade/upgrade cycles in the same DB.
    sa.Enum(name="asset_class").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="account_kind").drop(op.get_bind(), checkfirst=True)
