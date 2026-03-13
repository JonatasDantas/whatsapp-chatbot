from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageType(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    UNSUPPORTED = "unsupported"


class Message(BaseModel):
    phone_number: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    role: MessageRole
    message: str
    message_type: MessageType = MessageType.TEXT
    media_id: Optional[str] = None
