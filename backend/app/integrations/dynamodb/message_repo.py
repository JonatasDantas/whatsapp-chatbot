from typing import Any

from app.domain.models.message import Message
from app.domain.repositories.message_repository import MessageRepository
from boto3.dynamodb.conditions import Key


class DynamoDBMessageRepository(MessageRepository):
    def __init__(self, table: Any) -> None:  # boto3 DynamoDB Table resource
        self._table = table

    def save(self, message: Message) -> None:
        item = message.model_dump(mode="json")
        self._table.put_item(Item=item)

    def get_recent(self, phone_number: str, limit: int = 10) -> list[Message]:
        response = self._table.query(
            KeyConditionExpression=Key("phone_number").eq(phone_number),
            ScanIndexForward=False,
            Limit=limit,
        )
        items = response.get("Items", [])
        return [Message.model_validate(item) for item in items]
