class CalendarRepository:
    def is_available(self, checkin: str, checkout: str) -> bool:
        raise NotImplementedError

    def get_blocked_dates(self) -> list[str]:
        raise NotImplementedError
