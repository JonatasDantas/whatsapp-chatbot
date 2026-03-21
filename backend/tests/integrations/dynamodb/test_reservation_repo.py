from unittest.mock import MagicMock
from datetime import datetime

from app.domain.models.reservation import Reservation, ReservationStatus
from app.integrations.dynamodb.reservation_repo import DynamoDBReservationRepository


def _make_reservation(**kwargs) -> Reservation:
    defaults = dict(
        reservation_id="res_001",
        phone_number="+5511999999999",
        guest_name="Ana Lima",
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
        price=1200.0,
        status=ReservationStatus.CONFIRMED,
        created_at=datetime(2026, 3, 1),
    )
    defaults.update(kwargs)
    return Reservation(**defaults)


def test_save_and_load_reservation():
    table = MagicMock()
    repo = DynamoDBReservationRepository(table)
    res = _make_reservation()
    repo.save(res)
    table.put_item.assert_called_once()
    item = table.put_item.call_args[1]["Item"]
    assert item["reservation_id"] == "res_001"


def test_list_all_returns_sorted_by_checkin():
    table = MagicMock()
    table.scan.return_value = {
        "Items": [
            {"reservation_id": "res_002", "phone_number": "+5511999999998",
             "guest_name": "B", "checkin": "2026-05-01", "checkout": "2026-05-03",
             "guests": 2, "price": 800.0, "status": "confirmed",
             "created_at": "2026-03-01T00:00:00"},
            {"reservation_id": "res_001", "phone_number": "+5511999999999",
             "guest_name": "A", "checkin": "2026-04-10", "checkout": "2026-04-12",
             "guests": 4, "price": 1200.0, "status": "confirmed",
             "created_at": "2026-03-01T00:00:00"},
        ]
    }
    repo = DynamoDBReservationRepository(table)
    results = repo.list_all()
    assert len(results) == 2
    assert results[0].checkin == "2026-04-10"
    assert results[1].checkin == "2026-05-01"


def test_get_returns_reservation_by_id():
    table = MagicMock()
    table.get_item.return_value = {
        "Item": {
            "reservation_id": "res_001",
            "phone_number": "+5511999999999",
            "guest_name": "Ana Lima",
            "checkin": "2026-04-10",
            "checkout": "2026-04-12",
            "guests": 4,
            "price": 1200.0,
            "status": "confirmed",
            "created_at": "2026-03-01T00:00:00",
        }
    }
    repo = DynamoDBReservationRepository(table)
    result = repo.get("res_001")
    assert result is not None
    assert result.reservation_id == "res_001"
    assert result.guest_name == "Ana Lima"
    table.get_item.assert_called_once_with(Key={"reservation_id": "res_001"})


def test_get_returns_none_when_not_found():
    table = MagicMock()
    table.get_item.return_value = {}
    repo = DynamoDBReservationRepository(table)
    result = repo.get("missing_id")
    assert result is None
