"""Shared pytest fixtures for the backend test suite."""
import os
import pytest
import boto3
from moto import mock_aws


@pytest.fixture
def aws_credentials(monkeypatch):
    """Fake AWS credentials so moto doesn't try to use real ones."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def dynamodb_tables(aws_credentials):
    """Create all DynamoDB tables used by the application under moto."""
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
