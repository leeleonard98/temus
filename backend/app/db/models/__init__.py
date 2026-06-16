"""ORM models. Add new models here so Alembic autogenerate sees them."""
from app.db.models.account import Account, AccountKind
from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.chat_session import ChatSession
from app.db.models.goal import Goal
from app.db.models.position import AssetClass, Position
from app.db.models.price import Price
from app.db.models.user import User, UserRole

__all__ = [
    "Account",
    "AccountKind",
    "AssetClass",
    "ChatMessage",
    "ChatSession",
    "Goal",
    "MessageRole",
    "Position",
    "Price",
    "User",
    "UserRole",
]
