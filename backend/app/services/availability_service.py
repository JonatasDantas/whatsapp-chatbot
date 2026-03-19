from app.domain.repositories.calendar_repository import CalendarRepository


class AvailabilityService:
    def __init__(self, calendar_repo: CalendarRepository):
        self._calendar_repo = calendar_repo

    def check(self, checkin: str, checkout: str) -> bool:
        return self._calendar_repo.is_available(checkin, checkout)
