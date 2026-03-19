from app.domain.models.message import Message


class MessageRepository:
    def save(self, message: Message) -> None:
        raise NotImplementedError

    def get_recent(self, phone_number: str, limit: int = 10) -> list[Message]:
        raise NotImplementedError

    def get_all(self, phone_number: str) -> list[Message]:
        raise NotImplementedError
