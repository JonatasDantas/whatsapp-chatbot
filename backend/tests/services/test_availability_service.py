from unittest.mock import MagicMock
from app.services.availability_service import AvailabilityService


def test_delegates_to_calendar_repo():
    repo = MagicMock()
    repo.is_available.return_value = True
    svc = AvailabilityService(calendar_repo=repo)
    result = svc.check("2026-04-10", "2026-04-12")
    assert result is True
    repo.is_available.assert_called_once_with("2026-04-10", "2026-04-12")


def test_returns_false_when_unavailable():
    repo = MagicMock()
    repo.is_available.return_value = False
    svc = AvailabilityService(calendar_repo=repo)
    assert svc.check("2026-04-10", "2026-04-12") is False
