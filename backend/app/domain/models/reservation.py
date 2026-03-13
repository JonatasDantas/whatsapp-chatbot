from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ReservationStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Reservation(BaseModel):
    reservation_id: str
    phone_number: str
    guest_name: str
    checkin: str
    checkout: str
    guests: int
    price: float
    status: ReservationStatus = ReservationStatus.CONFIRMED
    created_at: datetime = Field(default_factory=datetime.utcnow)
