from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class ConversationStage(StrEnum):
    GREETING = "greeting"
    AVAILABILITY = "availability"
    QUALIFICATION = "qualification"
    PRICING = "pricing"
    OWNER_TAKEOVER = "owner_takeover"


class LeadStatus(StrEnum):
    NEW = "new"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"


class Conversation(BaseModel):
    phone_number: str
    name: Optional[str] = None
    stage: ConversationStage = ConversationStage.GREETING
    checkin: Optional[str] = None
    checkout: Optional[str] = None
    guests: Optional[int] = None
    purpose: Optional[str] = None
    customer_profile: Optional[str] = None
    rules_accepted: bool = False
    price_estimate: Optional[float] = None
    lead_status: LeadStatus = LeadStatus.NEW
    owner_notified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
