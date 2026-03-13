from app.domain.models.conversation import Conversation
from app.domain.models.message import Message, MessageRole, MessageType


def test_conversation_has_name_field():
    conv = Conversation(phone_number="+5511999999999", name="Maria")
    assert conv.name == "Maria"


def test_conversation_name_defaults_to_none():
    conv = Conversation(phone_number="+5511999999999")
    assert conv.name is None


def test_conversation_touch_updates_timestamp():
    conv = Conversation(phone_number="+5511999999999")
    original = conv.updated_at
    conv.touch()
    assert conv.updated_at >= original


def test_message_with_text_type():
    msg = Message(
        phone_number="+5511999999999",
        role=MessageRole.USER,
        message="Hello",
        message_type=MessageType.TEXT,
    )
    assert msg.message_type == MessageType.TEXT
    assert msg.media_id is None


def test_message_with_audio_type_and_media_id():
    msg = Message(
        phone_number="+5511999999999",
        role=MessageRole.USER,
        message="",
        message_type=MessageType.AUDIO,
        media_id="media_123",
    )
    assert msg.message_type == MessageType.AUDIO
    assert msg.media_id == "media_123"
