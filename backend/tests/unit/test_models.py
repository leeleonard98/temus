"""Smoke tests for ORM model registration & enum naming.

These tests don't hit the DB — they assert that:
1. Models are importable from the package.
2. They are registered on Base.metadata so Alembic autogenerate sees them.
3. Enum types have stable names (matters for migration determinism).
"""
from __future__ import annotations

import uuid


def test_user_model_registered_with_role_enum() -> None:
    from app.db.base import Base
    from app.db.models.user import User

    assert "users" in Base.metadata.tables
    table = Base.metadata.tables["users"]
    assert "id" in table.c
    assert "email" in table.c
    assert "display_name" in table.c
    assert "role" in table.c
    assert "created_at" in table.c
    # Email is unique.
    assert table.c.email.unique
    # Role enum has the expected name.
    role_type = table.c.role.type
    assert getattr(role_type, "name", None) == "user_role"
    # id is a uuid with a default callable.
    assert table.c.id.primary_key
    default = table.c.id.default
    assert default is not None
    # default.arg should be uuid.uuid4 (or callable returning uuid).
    val = default.arg(None) if callable(default.arg) else default.arg
    assert isinstance(val, uuid.UUID)
    # User instance carries role enum.
    u = User(email="x@y.z", display_name="X", role="client")
    assert u.email == "x@y.z"


def test_chat_session_model_registered() -> None:
    from app.db.base import Base
    from app.db.models.chat_session import ChatSession  # noqa: F401

    assert "chat_sessions" in Base.metadata.tables
    table = Base.metadata.tables["chat_sessions"]
    assert "user_id" in table.c
    assert "title" in table.c
    assert "created_at" in table.c
    assert "updated_at" in table.c
    # FK on user_id -> users.id
    fks = list(table.c.user_id.foreign_keys)
    assert any(fk.column.table.name == "users" for fk in fks)


def test_chat_message_model_registered_with_role_enum_and_index() -> None:
    from app.db.base import Base
    from app.db.models.chat_message import ChatMessage  # noqa: F401

    assert "chat_messages" in Base.metadata.tables
    table = Base.metadata.tables["chat_messages"]
    assert "session_id" in table.c
    assert "role" in table.c
    assert "content" in table.c
    assert "created_at" in table.c
    role_type = table.c.role.type
    assert getattr(role_type, "name", None) == "chat_message_role"
    # session_id indexed.
    assert table.c.session_id.index
    # FK -> chat_sessions.id
    fks = list(table.c.session_id.foreign_keys)
    assert any(fk.column.table.name == "chat_sessions" for fk in fks)


def test_models_package_imports_all_three() -> None:
    """`from app.db import models` must register all three models on Base."""
    from app.db import models  # noqa: F401
    from app.db.base import Base

    for tbl in ("users", "chat_sessions", "chat_messages"):
        assert tbl in Base.metadata.tables
