"""
End-to-end tests for the admin API handler.

These tests exercise the full flow from HTTP event → AdminHandler → DynamoDB (moto).
The WhatsApp client is mocked to capture outbound messages.
"""
import json

import boto3
import pytest
from moto import mock_aws
from unittest.mock import MagicMock

from app.handlers.admin_handler import AdminHandler
from app.integrations.dynamodb.calendar_repo import DynamoDBCalendarRepository
from app.integrations.dynamodb.conversation_repo import DynamoDBConversationRepository
from app.integrations.dynamodb.message_repo import DynamoDBMessageRepository
from app.integrations.dynamodb.reservation_repo import DynamoDBReservationRepository
from app.utils.dynamodb import to_dynamodb_item


def _event(method: str, path: str, path_params=None, body=None) -> dict:
    return {
        "httpMethod": method,
        "resource": path,
        "pathParameters": path_params or {},
        "body": json.dumps(body) if body else None,
        "headers": {},
    }


def _conv_item(**overrides) -> dict:
    base = {
        "phone_number": "+5511999999999",
        "name": "Maria",
        "stage": "greeting",
        "checkin": None,
        "checkout": None,
        "guests": None,
        "purpose": None,
        "customer_profile": None,
        "rules_accepted": False,
        "price_estimate": None,
        "lead_status": "new",
        "owner_notified": False,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


@pytest.fixture
def ddb_tables():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")

        conversations = ddb.create_table(
            TableName="Conversations",
            KeySchema=[{"AttributeName": "phone_number", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "phone_number", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        messages = ddb.create_table(
            TableName="Messages",
            KeySchema=[
                {"AttributeName": "phone_number", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "phone_number", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        reservations = ddb.create_table(
            TableName="Reservations",
            KeySchema=[{"AttributeName": "reservation_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "reservation_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        blocked_periods = ddb.create_table(
            TableName="BlockedPeriods",
            KeySchema=[{"AttributeName": "period_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "period_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        yield {
            "conversations": conversations,
            "messages": messages,
            "reservations": reservations,
            "blocked_periods": blocked_periods,
        }


@pytest.fixture
def admin(ddb_tables):
    whatsapp = MagicMock()
    handler = AdminHandler(
        conversation_repo=DynamoDBConversationRepository(ddb_tables["conversations"]),
        message_repo=DynamoDBMessageRepository(ddb_tables["messages"]),
        reservation_repo=DynamoDBReservationRepository(ddb_tables["reservations"]),
        whatsapp_client=whatsapp,
        calendar_repo=DynamoDBCalendarRepository(ddb_tables["blocked_periods"]),
    )
    return handler, whatsapp, ddb_tables


def test_list_conversations_returns_empty_when_none(admin):
    handler, _, _ = admin
    result = handler.handle(_event("GET", "/api/conversations"))
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["conversations"] == []


def test_list_conversations_returns_stored_conversation(admin):
    handler, _, tables = admin
    tables["conversations"].put_item(Item=to_dynamodb_item(_conv_item()))

    result = handler.handle(_event("GET", "/api/conversations"))
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["conversations"]) == 1
    assert body["conversations"][0]["phone_number"] == "+5511999999999"
    assert body["conversations"][0]["name"] == "Maria"


def test_get_single_conversation_reads_from_dynamodb(admin):
    handler, _, tables = admin
    tables["conversations"].put_item(Item=to_dynamodb_item(_conv_item()))

    result = handler.handle(_event(
        "GET", "/api/conversations/{phone}",
        path_params={"phone": "%2B5511999999999"},
    ))
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["conversation"]["stage"] == "greeting"


def test_takeover_updates_dynamodb_and_notifies_guest(admin):
    handler, whatsapp, tables = admin
    tables["conversations"].put_item(Item=to_dynamodb_item(_conv_item(
        stage="pricing",
        lead_status="qualified",
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
    )))

    result = handler.handle(_event(
        "POST", "/api/conversations/{phone}/takeover",
        path_params={"phone": "%2B5511999999999"},
    ))
    assert result["statusCode"] == 200

    # Verify DynamoDB was updated
    item = tables["conversations"].get_item(Key={"phone_number": "+5511999999999"}).get("Item")
    assert item["stage"] == "owner_takeover"
    assert item["owner_notified"] is True

    # Verify WhatsApp notification was sent to the guest
    whatsapp.send_text.assert_called_once()
    call_args = whatsapp.send_text.call_args
    assert call_args[0][0] == "+5511999999999"


def test_blocked_periods_full_crud(admin):
    handler, _, tables = admin

    # Add a blocked period
    add_result = handler.handle(_event(
        "POST", "/api/blocked-periods",
        body={"start_date": "2026-04-10", "end_date": "2026-04-13", "reason": "booked"},
    ))
    assert add_result["statusCode"] == 200
    period_id = json.loads(add_result["body"])["blocked_period"]["period_id"]

    # List should show it
    list_result = handler.handle(_event("GET", "/api/blocked-periods"))
    assert list_result["statusCode"] == 200
    periods = json.loads(list_result["body"])["blocked_periods"]
    assert len(periods) == 1
    assert periods[0]["start_date"] == "2026-04-10"

    # Delete it
    delete_result = handler.handle(_event(
        "DELETE", "/api/blocked-periods/{period_id}",
        path_params={"period_id": period_id},
    ))
    assert delete_result["statusCode"] == 200

    # List should be empty now
    list_result2 = handler.handle(_event("GET", "/api/blocked-periods"))
    assert json.loads(list_result2["body"])["blocked_periods"] == []


def test_get_messages_for_conversation(admin):
    from datetime import datetime, timezone
    from app.domain.models.message import Message, MessageRole, MessageType

    handler, _, tables = admin
    tables["conversations"].put_item(Item=to_dynamodb_item(_conv_item()))

    # Save a message via the repo
    msg_repo = DynamoDBMessageRepository(tables["messages"])
    msg_repo.save(Message(
        phone_number="+5511999999999",
        role=MessageRole.USER,
        message="Olá, tem disponibilidade?",
        message_type=MessageType.TEXT,
        timestamp=datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
    ))

    result = handler.handle(_event(
        "GET", "/api/conversations/{phone}/messages",
        path_params={"phone": "%2B5511999999999"},
    ))
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["messages"]) == 1
    assert body["messages"][0]["message"] == "Olá, tem disponibilidade?"
