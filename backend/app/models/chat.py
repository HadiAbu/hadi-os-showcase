"""Chat schemas (REQ-15, REQ-16)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ConversationOut(BaseModel):
    id: str
    title: str
    archived: bool
    created_at: str
    last_message_at: str | None


class NewConversation(BaseModel):
    id: str


class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    created_at: str


class NewMessage(BaseModel):
    text: str = Field(min_length=1)
