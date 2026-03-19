import re
from datetime import date, timedelta

import httpx
from aws_lambda_powertools import Logger

from app.domain.repositories.calendar_repository import CalendarRepository

logger = Logger()

_DTSTART_RE = re.compile(r"DTSTART[^:]*:(\d{8})")
_DTEND_RE = re.compile(r"DTEND[^:]*:(\d{8})")

_repo = None


def get_ical_calendar_repo() -> "ICalCalendarRepository":
    global _repo
    if _repo is None:
        from app.config.settings import _get_settings
        settings = _get_settings()
        _repo = ICalCalendarRepository(url=settings.ical_url)
        _repo._refresh()
    return _repo


def _parse_date(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _date_range(start: date, end: date) -> list[date]:
    """Returns all dates from start up to (not including) end."""
    result = []
    current = start
    while current < end:
        result.append(current)
        current += timedelta(days=1)
    return result


class ICalCalendarRepository(CalendarRepository):
    def __init__(self, url: str):
        self._url = url
        self._blocked: set[date] = set()

    def _refresh(self) -> None:
        response = httpx.get(self._url, timeout=10)
        response.raise_for_status()
        self._blocked = set()
        for event_block in response.text.split("BEGIN:VEVENT")[1:]:
            start_match = _DTSTART_RE.search(event_block)
            end_match = _DTEND_RE.search(event_block)
            if start_match and end_match:
                start = _parse_date(start_match.group(1))
                end = _parse_date(end_match.group(1))
                self._blocked.update(_date_range(start, end))
        logger.info("ical_refreshed", blocked_count=len(self._blocked))

    def is_available(self, checkin: str, checkout: str) -> bool:
        start = date.fromisoformat(checkin)
        end = date.fromisoformat(checkout)
        requested = set(_date_range(start, end))
        return requested.isdisjoint(self._blocked)

    def get_blocked_dates(self) -> list[str]:
        return sorted(d.isoformat() for d in self._blocked)
