import boto3
import pytest
from app.domain.models.conversation import Conversation, ConversationStage
from app.integrations.dynamodb.conversation_repo import DynamoDBConversationRepository
from moto import mock_aws


@pytest.fixture
def dynamodb_table():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="test-conversations",
            KeySchema=[{"AttributeName": "phone_number", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "phone_number", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        yield resource.Table("test-conversations")


def test_save_and_load_conversation(dynamodb_table):
    repo = DynamoDBConversationRepository(dynamodb_table)
    conv = Conversation(phone_number="+5511999999999", name="Maria")
    repo.save(conv)

    loaded = repo.load("+5511999999999")
    assert loaded is not None
    assert loaded.phone_number == "+5511999999999"
    assert loaded.name == "Maria"
    assert loaded.stage == ConversationStage.GREETING


def test_load_nonexistent_returns_none(dynamodb_table):
    repo = DynamoDBConversationRepository(dynamodb_table)
    result = repo.load("+5511000000000")
    assert result is None


def test_save_updates_existing_conversation(dynamodb_table):
    repo = DynamoDBConversationRepository(dynamodb_table)
    conv = Conversation(phone_number="+5511999999999", name="Maria")
    repo.save(conv)

    conv.stage = ConversationStage.AVAILABILITY
    conv.touch()
    repo.save(conv)

    loaded = repo.load("+5511999999999")
    assert loaded.stage == ConversationStage.AVAILABILITY


def test_list_all_returns_sorted_by_updated_at_desc(dynamodb_table):
    from datetime import datetime, timezone, timedelta
    repo = DynamoDBConversationRepository(dynamodb_table)

    older = Conversation(
        phone_number="+5511111111111",
        name="Older",
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    newer = Conversation(
        phone_number="+5511222222222",
        name="Newer",
        updated_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
    )
    repo.save(older)
    repo.save(newer)

    results = repo.list_all()
    assert len(results) == 2
    assert results[0].phone_number == "+5511222222222"  # newest first
    assert results[1].phone_number == "+5511111111111"


def test_list_all_empty(dynamodb_table):
    repo = DynamoDBConversationRepository(dynamodb_table)
    assert repo.list_all() == []
