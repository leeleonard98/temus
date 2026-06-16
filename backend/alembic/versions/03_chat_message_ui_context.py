"""03_chat_message_ui_context: add ui_context jsonb on chat_messages

Revision ID: 03_chat_message_ui_context
Revises: 02_portfolio
Create Date: 2026-06-16 14:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "03_chat_message_ui_context"
down_revision: Union[str, None] = "02_portfolio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # AC4: persist the UI state JSON the client sent with the chat turn so
    # we can later trace what the model "saw" and reproduce a turn exactly.
    op.add_column(
        "chat_messages",
        sa.Column("ui_context", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "ui_context")
