import os
from typing import Any

import boto3

from app.domain.models.reservation import Reservation
from app.domain.repositories.reservation_repository import ReservationRepository
from app.utils.dynamodb import to_dynamodb_item

_dynamodb = None
_table = None
_repo = None


def _get_table():
    global _dynamodb, _table
    if _table is None:
        if _dynamodb is None:
            _dynamodb = boto3.resource("dynamodb")
        _table = _dynamodb.Table(os.environ["RESERVATIONS_TABLE"])
    return _table


def get_reservation_repo() -> "DynamoDBReservationRepository":
    global _repo
    if _repo is None:
        _repo = DynamoDBReservationRepository(_get_table())
    return _repo


class DynamoDBReservationRepository(ReservationRepository):
    def __init__(self, table: Any) -> None:
        self._table = table

    def save(self, reservation: Reservation) -> None:
        item = to_dynamodb_item(reservation.model_dump(mode="json"))
        self._table.put_item(Item=item)

    def get(self, reservation_id: str) -> Reservation | None:
        response = self._table.get_item(Key={"reservation_id": reservation_id})
        item = response.get("Item")
        if not item:
            return None
        return Reservation.model_validate(item)

    def list_all(self) -> list[Reservation]:
        response = self._table.scan()
        items = response.get("Items", [])
        reservations = [Reservation.model_validate(item) for item in items]
        return sorted(reservations, key=lambda r: r.checkin)
