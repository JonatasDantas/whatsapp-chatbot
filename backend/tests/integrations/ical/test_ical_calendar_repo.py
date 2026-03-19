from unittest.mock import patch, MagicMock
from app.integrations.ical.ical_calendar_repo import ICalCalendarRepository

SAMPLE_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260410
DTEND;VALUE=DATE:20260413
SUMMARY:Booked
END:VEVENT
END:VCALENDAR
"""


def _make_repo(ics_content: str) -> ICalCalendarRepository:
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = ics_content
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        repo = ICalCalendarRepository(url="https://example.com/cal.ics")
        repo._refresh()
    return repo


def test_is_unavailable_when_dates_overlap():
    repo = _make_repo(SAMPLE_ICS)
    assert repo.is_available("2026-04-10", "2026-04-12") is False


def test_is_available_when_dates_do_not_overlap():
    repo = _make_repo(SAMPLE_ICS)
    assert repo.is_available("2026-04-14", "2026-04-16") is True


def test_is_available_when_checkout_equals_existing_checkin():
    # guest checks out on same day existing booking starts — no overlap
    repo = _make_repo(SAMPLE_ICS)
    assert repo.is_available("2026-04-08", "2026-04-10") is True


def test_get_blocked_dates_returns_date_strings():
    repo = _make_repo(SAMPLE_ICS)
    blocked = repo.get_blocked_dates()
    assert "2026-04-10" in blocked
    assert "2026-04-11" in blocked
    assert "2026-04-12" in blocked
    assert "2026-04-13" not in blocked  # checkout day is exclusive


def test_empty_calendar_is_always_available():
    empty_ics = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"
    repo = _make_repo(empty_ics)
    assert repo.is_available("2026-04-10", "2026-04-12") is True
