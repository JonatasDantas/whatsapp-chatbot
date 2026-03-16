import os
from typing import Any, Optional

import boto3

from app.domain.models.conversation import Conversation
from app.domain.repositories.conversation_repository import ConversationRepository

_dynamodb = None
_table = None
_repo = None


def _get_table():
    global _dynamodb, _table
    if _table is None:
        if _dynamodb is None:
            _dynamodb = boto3.resource("dynamodb")
        _table = _dynamodb.Table(os.environ["CONVERSATIONS_TABLE"])
    return _table


def get_conversation_repo() -> "DynamoDBConversationRepository":
    global _repo
    if _repo is None:
        _repo = DynamoDBConversationRepository(_get_table())
    return _repo


class DynamoDBConversationRepository(ConversationRepository):
    def __init__(self, table: Any) -> None:
        self._table = table

    def load(self, phone_number: str) -> Optional[Conversation]:
        response = self._table.get_item(Key={"phone_number": phone_number})
        item = response.get("Item")
        if not item:
            return None
        return Conversation.model_validate(item)

    def save(self, conversation: Conversation) -> None:
        item = conversation.model_dump(mode="json")
        self._table.put_item(Item=item)
