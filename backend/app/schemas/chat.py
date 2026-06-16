"""Pydantic schemas for the chat router."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UserRoleLiteral = Literal["client", "advisor"]
MessageRoleLiteral = Literal["user", "assistant", "system"]


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r".+@.+")
    display_name: str = Field(min_length=1, max_length=255)
    role: UserRoleLiteral


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str
    role: UserRoleLiteral


class SessionCreate(BaseModel):
    user_id: uuid.UUID
    title: str | None = Field(default=None, max_length=255)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    session_id: uuid.UUID
    role: MessageRoleLiteral
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    content: str = Field(min_length=1)
    # AC4: arbitrary JSON describing what the client is currently looking at
    # (portfolio totals, visible positions, etc.). Echoed into the system
    # prompt and persisted on the user-message row for traceability.
    ui_context: dict | None = None
