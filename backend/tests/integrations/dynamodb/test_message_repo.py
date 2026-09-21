import boto3
import pytest
from app.domain.models.message import Message, MessageRole, MessageType
from app.integrations.dynamodb.message_repo import DynamoDBMessageRepository
from moto import mock_aws


@pytest.fixture
def dynamodb_table():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="test-messages",
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
        yield boto3.resource("dynamodb", region_name="us-east-1").Table("test-messages")


def test_save_and_get_recent_messages(dynamodb_table):
    repo = DynamoDBMessageRepository(dynamodb_table)

    msg = Message(
        phone_number="+5511999999999",
        role=MessageRole.USER,
        message="Hello",
        message_type=MessageType.TEXT,
    )
    repo.save(msg)

    recent = repo.get_recent("+5511999999999", limit=10)
    assert len(recent) == 1
    assert recent[0].message == "Hello"
    assert recent[0].role == MessageRole.USER


def test_get_recent_returns_newest_first(dynamodb_table):
    repo = DynamoDBMessageRepository(dynamodb_table)

    from datetime import datetime, timezone

    for i in range(3):
        msg = Message(
            phone_number="+5511999999999",
            timestamp=datetime(2026, 3, 12, 21, 0, i, tzinfo=timezone.utc),
            role=MessageRole.USER,
            message=f"Message {i}",
            message_type=MessageType.TEXT,
        )
        repo.save(msg)

    recent = repo.get_recent("+5511999999999", limit=2)
    assert len(recent) == 2
    assert recent[0].message == "Message 2"
    assert recent[1].message == "Message 1"


def test_get_recent_empty(dynamodb_table):
    repo = DynamoDBMessageRepository(dynamodb_table)
    recent = repo.get_recent("+5511000000000")
    assert recent == []


def test_get_all_returns_chronological_order(dynamodb_table):
    from datetime import datetime, timezone

    repo = DynamoDBMessageRepository(dynamodb_table)

    timestamps = [
        datetime(2026, 3, 12, 21, 0, 2, tzinfo=timezone.utc),
        datetime(2026, 3, 12, 21, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 12, 21, 0, 1, tzinfo=timezone.utc),
    ]
    for ts in timestamps:
        repo.save(Message(
            phone_number="+5511999999999",
            timestamp=ts,
            role=MessageRole.USER,
            message=f"msg-{ts.second}",
            message_type=MessageType.TEXT,
        ))

    all_msgs = repo.get_all("+5511999999999")
    assert len(all_msgs) == 3
    assert all_msgs[0].message == "msg-0"
    assert all_msgs[1].message == "msg-1"
    assert all_msgs[2].message == "msg-2"


def test_get_all_empty(dynamodb_table):
    repo = DynamoDBMessageRepository(dynamodb_table)
    assert repo.get_all("+5511000000000") == []
