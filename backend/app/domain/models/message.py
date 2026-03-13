from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    phone_number: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    role: MessageRole
    message: str
