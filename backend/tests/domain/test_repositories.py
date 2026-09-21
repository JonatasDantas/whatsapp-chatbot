"""
Tests that the abstract repository base classes raise NotImplementedError.
These serve as a contract: subclasses must override all methods.
"""
import pytest

from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.domain.repositories.reservation_repository import ReservationRepository
from app.domain.repositories.calendar_repository import CalendarRepository


def test_conversation_repo_load_raises():
    with pytest.raises(NotImplementedError):
        ConversationRepository().load("+55")


def test_conversation_repo_save_raises():
    with pytest.raises(NotImplementedError):
        ConversationRepository().save(None)


def test_conversation_repo_list_all_raises():
    with pytest.raises(NotImplementedError):
        ConversationRepository().list_all()


def test_message_repo_save_raises():
    with pytest.raises(NotImplementedError):
        MessageRepository().save(None)


def test_message_repo_get_recent_raises():
    with pytest.raises(NotImplementedError):
        MessageRepository().get_recent("+55")


def test_message_repo_get_all_raises():
    with pytest.raises(NotImplementedError):
        MessageRepository().get_all("+55")


def test_reservation_repo_save_raises():
    with pytest.raises(NotImplementedError):
        ReservationRepository().save(None)


def test_reservation_repo_get_raises():
    with pytest.raises(NotImplementedError):
        ReservationRepository().get("id")


def test_reservation_repo_list_all_raises():
    with pytest.raises(NotImplementedError):
        ReservationRepository().list_all()


def test_calendar_repo_is_available_raises():
    with pytest.raises(NotImplementedError):
        CalendarRepository().is_available("2026-04-10", "2026-04-12")


def test_calendar_repo_get_blocked_dates_raises():
    with pytest.raises(NotImplementedError):
        CalendarRepository().get_blocked_dates()
