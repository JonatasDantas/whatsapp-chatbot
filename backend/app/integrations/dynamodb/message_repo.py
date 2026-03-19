import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from app.domain.models.message import Message
from app.domain.repositories.message_repository import MessageRepository

_dynamodb = None
_table = None
_repo = None


def _get_table():
    global _dynamodb, _table
    if _table is None:
        if _dynamodb is None:
            _dynamodb = boto3.resource("dynamodb")
        _table = _dynamodb.Table(os.environ["MESSAGES_TABLE"])
    return _table


def get_message_repo() -> "DynamoDBMessageRepository":
    global _repo
    if _repo is None:
        _repo = DynamoDBMessageRepository(_get_table())
    return _repo


class DynamoDBMessageRepository(MessageRepository):
    def __init__(self, table: Any) -> None:
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

    def get_all(self, phone_number: str) -> list[Message]:
        response = self._table.query(
            KeyConditionExpression=Key("phone_number").eq(phone_number),
            ScanIndexForward=True,
        )
        items = response.get("Items", [])
        return [Message.model_validate(item) for item in items]
