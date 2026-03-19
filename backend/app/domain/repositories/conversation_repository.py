from typing import Optional

from app.domain.models.conversation import Conversation


class ConversationRepository:
    def load(self, phone_number: str) -> Optional[Conversation]:
        raise NotImplementedError

    def save(self, conversation: Conversation) -> None:
        raise NotImplementedError

    def list_all(self) -> list[Conversation]:
        raise NotImplementedError
