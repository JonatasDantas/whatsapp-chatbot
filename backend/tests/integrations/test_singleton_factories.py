"""
Tests for singleton factory functions across all integrations.
Each factory has two branches: _x is None (init) and _x is already set (return cached).
These are kept in a single file to avoid cluttering individual test files.
"""
import os
import boto3
import pytest
from moto import mock_aws
from unittest.mock import MagicMock, patch


def _create_conversations_table(ddb):
    return ddb.create_table(
        TableName="Conversations",
        KeySchema=[{"AttributeName": "phone_number", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "phone_number", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


def _create_messages_table(ddb):
    return ddb.create_table(
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


def _create_blocked_periods_table(ddb):
    return ddb.create_table(
        TableName="BlockedPeriods",
        KeySchema=[{"AttributeName": "period_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "period_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


def _aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


# ── conversation repo ─────────────────────────────────────────────────────────

def test_conversation_repo_singleton(monkeypatch):
    import app.integrations.dynamodb.conversation_repo as mod
    monkeypatch.setenv("CONVERSATIONS_TABLE", "Conversations")
    _aws_env(monkeypatch)
    mod._repo = None
    mod._table = None
    mod._dynamodb = None

    with mock_aws():
        _create_conversations_table(boto3.resource("dynamodb", region_name="us-east-1"))
        r1 = mod.get_conversation_repo()
        r2 = mod.get_conversation_repo()
    assert r1 is r2

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


def test_conversation_table_reuses_dynamodb_resource(monkeypatch):
    """When _dynamodb is already set but _table is None, skip creating the resource."""
    import app.integrations.dynamodb.conversation_repo as mod
    monkeypatch.setenv("CONVERSATIONS_TABLE", "Conversations")
    _aws_env(monkeypatch)

    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_conversations_table(ddb)
        mod._repo = None
        mod._table = None
        mod._dynamodb = ddb  # pre-set resource

        mod.get_conversation_repo()
        assert mod._table is not None

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


# ── message repo ──────────────────────────────────────────────────────────────

def test_message_repo_singleton(monkeypatch):
    import app.integrations.dynamodb.message_repo as mod
    monkeypatch.setenv("MESSAGES_TABLE", "Messages")
    _aws_env(monkeypatch)
    mod._repo = None
    mod._table = None
    mod._dynamodb = None

    with mock_aws():
        _create_messages_table(boto3.resource("dynamodb", region_name="us-east-1"))
        r1 = mod.get_message_repo()
        r2 = mod.get_message_repo()
    assert r1 is r2

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


def test_message_table_reuses_dynamodb_resource(monkeypatch):
    import app.integrations.dynamodb.message_repo as mod
    monkeypatch.setenv("MESSAGES_TABLE", "Messages")
    _aws_env(monkeypatch)

    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_messages_table(ddb)
        mod._repo = None
        mod._table = None
        mod._dynamodb = ddb

        mod.get_message_repo()
        assert mod._table is not None

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


# ── calendar repo ─────────────────────────────────────────────────────────────

def test_calendar_repo_singleton(monkeypatch):
    import app.integrations.dynamodb.calendar_repo as mod
    monkeypatch.setenv("BLOCKED_PERIODS_TABLE", "BlockedPeriods")
    _aws_env(monkeypatch)
    mod._repo = None
    mod._table = None
    mod._dynamodb = None

    with mock_aws():
        _create_blocked_periods_table(boto3.resource("dynamodb", region_name="us-east-1"))
        r1 = mod.get_calendar_repo()
        r2 = mod.get_calendar_repo()
    assert r1 is r2

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


def test_calendar_table_reuses_dynamodb_resource(monkeypatch):
    import app.integrations.dynamodb.calendar_repo as mod
    monkeypatch.setenv("BLOCKED_PERIODS_TABLE", "BlockedPeriods")
    _aws_env(monkeypatch)

    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_blocked_periods_table(ddb)
        mod._repo = None
        mod._table = None
        mod._dynamodb = ddb

        mod.get_calendar_repo()
        assert mod._table is not None

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


# ── openai client ─────────────────────────────────────────────────────────────

def test_openai_client_singleton(monkeypatch):
    """get_openai_client() returns the same instance on repeated calls."""
    import app.integrations.llm.openai_client as mod

    fake_settings = MagicMock()
    fake_settings.openai_api_key = "sk-test"
    fake_settings.openai_model = "gpt-4o-mini"

    mod._client = None
    mod._openai_raw = None

    with patch("app.integrations.llm.openai_client._get_settings", return_value=fake_settings), \
         patch("app.integrations.llm.openai_client.OpenAI", return_value=MagicMock()):
        c1 = mod.get_openai_client()
        c2 = mod.get_openai_client()

    assert c1 is c2

    mod._client = None
    mod._openai_raw = None


def test_openai_raw_client_singleton(monkeypatch):
    """_get_openai_raw() returns the same OpenAI instance on repeated calls."""
    import app.integrations.llm.openai_client as mod

    fake_settings = MagicMock()
    fake_settings.openai_api_key = "sk-test"

    mod._openai_raw = None

    with patch("app.integrations.llm.openai_client._get_settings", return_value=fake_settings), \
         patch("app.integrations.llm.openai_client.OpenAI", return_value=MagicMock()) as mock_openai:
        r1 = mod._get_openai_raw()
        r2 = mod._get_openai_raw()

    assert r1 is r2
    mock_openai.assert_called_once()

    mod._openai_raw = None


# ── reservation repo (table-already-set branches) ────────────────────────────

def test_reservation_repo_singleton(monkeypatch):
    import app.integrations.dynamodb.reservation_repo as mod
    monkeypatch.setenv("RESERVATIONS_TABLE", "Reservations")
    _aws_env(monkeypatch)
    mod._repo = None
    mod._table = None
    mod._dynamodb = None

    with mock_aws():
        boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="Reservations",
            KeySchema=[{"AttributeName": "reservation_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "reservation_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        r1 = mod.get_reservation_repo()
        r2 = mod.get_reservation_repo()
    assert r1 is r2

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


def test_reservation_table_reuses_dynamodb_resource(monkeypatch):
    """When _dynamodb is pre-set, _get_table() skips creating a new resource."""
    import app.integrations.dynamodb.reservation_repo as mod
    monkeypatch.setenv("RESERVATIONS_TABLE", "Reservations")
    _aws_env(monkeypatch)

    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="Reservations",
            KeySchema=[{"AttributeName": "reservation_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "reservation_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        mod._repo = None
        mod._table = None
        mod._dynamodb = ddb

        mod.get_reservation_repo()
        assert mod._table is not None

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


# ── "table already set" branches (short-circuit on second call) ───────────────

def test_conversation_table_already_set_is_returned_directly(monkeypatch):
    """When _table is already set, _get_table() returns it without touching DynamoDB."""
    import app.integrations.dynamodb.conversation_repo as mod
    monkeypatch.setenv("CONVERSATIONS_TABLE", "Conversations")
    _aws_env(monkeypatch)

    fake_table = MagicMock()
    mod._table = fake_table
    mod._repo = None

    result = mod.get_conversation_repo()
    assert mod._table is fake_table

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


def test_message_table_already_set_is_returned_directly(monkeypatch):
    import app.integrations.dynamodb.message_repo as mod
    monkeypatch.setenv("MESSAGES_TABLE", "Messages")
    _aws_env(monkeypatch)

    fake_table = MagicMock()
    mod._table = fake_table
    mod._repo = None

    mod.get_message_repo()
    assert mod._table is fake_table

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


def test_calendar_table_already_set_is_returned_directly(monkeypatch):
    import app.integrations.dynamodb.calendar_repo as mod
    monkeypatch.setenv("BLOCKED_PERIODS_TABLE", "BlockedPeriods")
    _aws_env(monkeypatch)

    fake_table = MagicMock()
    mod._table = fake_table
    mod._repo = None

    mod.get_calendar_repo()
    assert mod._table is fake_table

    mod._repo = None
    mod._table = None
    mod._dynamodb = None


def test_reservation_table_already_set_is_returned_directly(monkeypatch):
    """When _table is already set in reservation_repo, _get_table() skips creation."""
    import app.integrations.dynamodb.reservation_repo as mod
    monkeypatch.setenv("RESERVATIONS_TABLE", "Reservations")
    _aws_env(monkeypatch)

    fake_table = MagicMock()
    mod._table = fake_table
    mod._repo = None

    mod.get_reservation_repo()
    assert mod._table is fake_table

    mod._repo = None
    mod._table = None
    mod._dynamodb = None
