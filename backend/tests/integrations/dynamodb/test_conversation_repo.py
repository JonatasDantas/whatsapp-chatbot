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
