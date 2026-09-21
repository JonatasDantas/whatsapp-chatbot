import pytest
import boto3
from moto import mock_aws
from app.integrations.dynamodb.calendar_repo import DynamoDBCalendarRepository


@pytest.fixture
def table():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        t = ddb.create_table(
            TableName="BlockedPeriods",
            KeySchema=[{"AttributeName": "period_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "period_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield t


def test_add_and_list_period(table):
    repo = DynamoDBCalendarRepository(table)
    period = repo.add_period("2026-04-10", "2026-04-13", "booked")
    assert period["period_id"]
    assert period["start_date"] == "2026-04-10"
    assert period["end_date"] == "2026-04-13"
    listed = repo.list_all()
    assert len(listed) == 1


def test_is_unavailable_when_dates_overlap(table):
    repo = DynamoDBCalendarRepository(table)
    repo.add_period("2026-04-10", "2026-04-13")
    assert repo.is_available("2026-04-10", "2026-04-12") is False


def test_is_available_when_no_overlap(table):
    repo = DynamoDBCalendarRepository(table)
    repo.add_period("2026-04-10", "2026-04-13")
    assert repo.is_available("2026-04-14", "2026-04-16") is True


def test_checkout_equals_existing_checkin_is_available(table):
    repo = DynamoDBCalendarRepository(table)
    repo.add_period("2026-04-10", "2026-04-13")
    assert repo.is_available("2026-04-08", "2026-04-10") is True


def test_delete_period(table):
    repo = DynamoDBCalendarRepository(table)
    period = repo.add_period("2026-04-10", "2026-04-13")
    deleted = repo.delete_period(period["period_id"])
    assert deleted is True
    assert repo.list_all() == []


def test_delete_nonexistent_period(table):
    repo = DynamoDBCalendarRepository(table)
    assert repo.delete_period("nonexistent-id") is False


def test_get_blocked_dates(table):
    repo = DynamoDBCalendarRepository(table)
    repo.add_period("2026-04-10", "2026-04-13")
    blocked = repo.get_blocked_dates()
    assert "2026-04-10" in blocked
    assert "2026-04-11" in blocked
    assert "2026-04-12" in blocked
    assert "2026-04-13" not in blocked
