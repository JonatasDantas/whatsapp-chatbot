from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class ReservationStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Reservation(BaseModel):
    reservation_id: str
    phone_number: str
    guest_name: str
    checkin: str
    checkout: str
    guests: int
    price: float
    status: ReservationStatus = ReservationStatus.CONFIRMED
    created_at: datetime = Field(default_factory=_now_utc)
