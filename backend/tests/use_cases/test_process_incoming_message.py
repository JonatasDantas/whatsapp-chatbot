from typing import Optional

from app.domain.models.conversation import Conversation, ConversationStage
from app.domain.models.message import Message, MessageType
from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.integrations.whatsapp.message_parser import ParsedMessage
from app.use_cases.process_incoming_message import ProcessIncomingMessage


class FakeConversationRepo(ConversationRepository):
    def __init__(self):
        self.conversations: dict[str, Conversation] = {}

    def load(self, phone_number: str) -> Optional[Conversation]:
        return self.conversations.get(phone_number)

    def save(self, conversation: Conversation) -> None:
        self.conversations[conversation.phone_number] = conversation


class FakeMessageRepo(MessageRepository):
    def __init__(self):
        self.messages: list[Message] = []

    def save(self, message: Message) -> None:
        self.messages.append(message)

    def get_recent(self, phone_number: str, limit: int = 10) -> list[Message]:
        return [m for m in self.messages if m.phone_number == phone_number][:limit]


def _make_parsed_message(**overrides) -> ParsedMessage:
    defaults = {
        "phone_number": "+5511999999999",
        "contact_name": "Maria",
        "message_type": "text",
        "content": "Hello",
        "media_id": None,
        "whatsapp_message_id": "wamid.abc",
        "timestamp": "1710280800",
    }
    defaults.update(overrides)
    return ParsedMessage(**defaults)


def test_creates_new_conversation():
    conv_repo = FakeConversationRepo()
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    use_case.execute([_make_parsed_message()])

    conv = conv_repo.conversations["+5511999999999"]
    assert conv.name == "Maria"
    assert conv.stage == ConversationStage.GREETING


def test_reuses_existing_conversation():
    conv_repo = FakeConversationRepo()
    existing = Conversation(
        phone_number="+5511999999999",
        name="Maria",
        stage=ConversationStage.AVAILABILITY,
    )
    conv_repo.conversations["+5511999999999"] = existing
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    use_case.execute([_make_parsed_message()])

    conv = conv_repo.conversations["+5511999999999"]
    assert conv.stage == ConversationStage.AVAILABILITY


def test_saves_user_message():
    conv_repo = FakeConversationRepo()
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    use_case.execute([_make_parsed_message(content="Is it available?")])

    assert len(msg_repo.messages) == 1
    assert msg_repo.messages[0].message == "Is it available?"
    assert msg_repo.messages[0].message_type == MessageType.TEXT


def test_saves_audio_message_with_media_id():
    conv_repo = FakeConversationRepo()
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    use_case.execute([_make_parsed_message(
        message_type="audio",
        content="",
        media_id="media_123",
    )])

    assert msg_repo.messages[0].message_type == MessageType.AUDIO
    assert msg_repo.messages[0].media_id == "media_123"


def test_processes_multiple_messages():
    conv_repo = FakeConversationRepo()
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    messages = [
        _make_parsed_message(content="Hi", whatsapp_message_id="wamid.1"),
        _make_parsed_message(content="Hello", whatsapp_message_id="wamid.2"),
    ]
    use_case.execute(messages)

    assert len(msg_repo.messages) == 2
