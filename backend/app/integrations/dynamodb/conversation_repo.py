from typing import Any, Optional

from app.domain.models.conversation import Conversation
from app.domain.repositories.conversation_repository import ConversationRepository


class DynamoDBConversationRepository(ConversationRepository):
    def __init__(self, table: Any) -> None:  # boto3 DynamoDB Table resource
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
