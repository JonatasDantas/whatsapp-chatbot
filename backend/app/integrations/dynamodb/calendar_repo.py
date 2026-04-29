import os
import uuid
from datetime import date, timedelta
from typing import Any

import boto3
from aws_lambda_powertools import Logger

from app.domain.repositories.calendar_repository import CalendarRepository

logger = Logger()

_dynamodb = None
_table = None
_repo = None


def _get_table():
    global _dynamodb, _table
    if _table is None:
        if _dynamodb is None:
            _dynamodb = boto3.resource("dynamodb")
        _table = _dynamodb.Table(os.environ["BLOCKED_PERIODS_TABLE"])
    return _table


def get_calendar_repo() -> "DynamoDBCalendarRepository":
    global _repo
    if _repo is None:
        _repo = DynamoDBCalendarRepository(_get_table())
    return _repo


def _date_range(start: date, end: date) -> list[date]:
    """Returns all dates from start up to (not including) end."""
    result = []
    current = start
    while current < end:
        result.append(current)
        current += timedelta(days=1)
    return result


class DynamoDBCalendarRepository(CalendarRepository):
    def __init__(self, table: Any) -> None:
        self._table = table

    def is_available(self, checkin: str, checkout: str) -> bool:
        periods = self.list_all()
        req_start = date.fromisoformat(checkin)
        req_end = date.fromisoformat(checkout)
        for period in periods:
            period_start = date.fromisoformat(period["start_date"])
            period_end = date.fromisoformat(period["end_date"])
            # Overlap: period starts before checkout AND ends after checkin
            if period_start < req_end and period_end > req_start:
                return False
        return True

    def get_blocked_dates(self) -> list[str]:
        periods = self.list_all()
        blocked: set[str] = set()
        for period in periods:
            start = date.fromisoformat(period["start_date"])
            end = date.fromisoformat(period["end_date"])
            for d in _date_range(start, end):
                blocked.add(d.isoformat())
        return sorted(blocked)

    def list_all(self) -> list[dict]:
        response = self._table.scan()
        items = response.get("Items", [])
        return sorted(items, key=lambda x: x["start_date"])

    def add_period(self, start_date: str, end_date: str, reason: str = "") -> dict:
        period = {
            "period_id": str(uuid.uuid4()),
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
        }
        self._table.put_item(Item=period)
        logger.info("blocked_period_added", start_date=start_date, end_date=end_date)
        return period

    def delete_period(self, period_id: str) -> bool:
        response = self._table.delete_item(
            Key={"period_id": period_id},
            ReturnValues="ALL_OLD",
        )
        deleted = bool(response.get("Attributes"))
        logger.info("blocked_period_deleted", period_id=period_id, found=deleted)
        return deleted
