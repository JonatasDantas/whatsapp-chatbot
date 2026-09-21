from app.domain.models.conversation import Conversation, ConversationStage, LeadStatus
from app.domain.models.message import Message, MessageRole, MessageType
from app.domain.models.reservation import Reservation, ReservationStatus


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


def test_conversation_stage_values():
    assert ConversationStage.GREETING == "greeting"
    assert ConversationStage.AVAILABILITY == "availability"
    assert ConversationStage.QUALIFICATION == "qualification"
    assert ConversationStage.PRICING == "pricing"
    assert ConversationStage.OWNER_TAKEOVER == "owner_takeover"


def test_lead_status_values():
    assert LeadStatus.NEW == "new"
    assert LeadStatus.QUALIFIED == "qualified"
    assert LeadStatus.UNQUALIFIED == "unqualified"


def test_conversation_defaults():
    conv = Conversation(phone_number="+5511999999999")
    assert conv.stage == ConversationStage.GREETING
    assert conv.lead_status == LeadStatus.NEW
    assert conv.owner_notified is False
    assert conv.rules_accepted is False
    assert conv.checkin is None
    assert conv.checkout is None
    assert conv.guests is None
    assert conv.price_estimate is None


def test_reservation_default_status():
    from datetime import datetime
    res = Reservation(
        reservation_id="r1",
        phone_number="+5511999999999",
        guest_name="João",
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
        price=800.0,
    )
    assert res.status == ReservationStatus.CONFIRMED


def test_reservation_status_values():
    assert ReservationStatus.CONFIRMED == "confirmed"
    assert ReservationStatus.CANCELLED == "cancelled"


def test_reservation_serialization():
    from datetime import datetime
    res = Reservation(
        reservation_id="r1",
        phone_number="+5511999999999",
        guest_name="João",
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
        price=800.0,
        status=ReservationStatus.CANCELLED,
    )
    data = res.model_dump(mode="json")
    assert data["status"] == "cancelled"
    assert data["reservation_id"] == "r1"
