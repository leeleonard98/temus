"""ORM models. Add new models here so Alembic autogenerate sees them."""
from app.db.models.account import Account, AccountKind
from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.chat_session import ChatSession
from app.db.models.chunk import Chunk
from app.db.models.document import Document
from app.db.models.goal import Goal
from app.db.models.media_asset import MediaAsset
from app.db.models.position import AssetClass, Position
from app.db.models.price import Price
from app.db.models.user import User, UserRole

__all__ = [
    "Account",
    "AccountKind",
    "AssetClass",
    "ChatMessage",
    "ChatSession",
    "Chunk",
    "Document",
    "Goal",
    "MediaAsset",
    "MessageRole",
    "Position",
    "Price",
    "User",
    "UserRole",
]
