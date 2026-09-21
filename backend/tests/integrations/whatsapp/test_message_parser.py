import base64

from app.integrations.whatsapp.message_parser import MessageParser


def _make_payload(phone: str, message_type: str, message: dict, from_me: bool = False, push_name: str = "Test") -> dict:
    number = phone.lstrip("+")
    return {
        "event": "messages.upsert",
        "instance": "chacara",
        "data": {
            "key": {
                "remoteJid": f"{number}@s.whatsapp.net",
                "fromMe": from_me,
                "id": "wamid.abc123",
            },
            "pushName": push_name,
            "message": message,
            "messageType": message_type,
            "messageTimestamp": 1710280800,
        },
    }


def test_parse_text_message():
    payload = _make_payload("+5511999999999", "conversation", {"conversation": "Hello"}, push_name="Maria")
    result = MessageParser.parse(payload)
    assert len(result) == 1
    msg = result[0]
    assert msg.phone_number == "+5511999999999"
    assert msg.contact_name == "Maria"
    assert msg.message_type == "text"
    assert msg.content == "Hello"
    assert msg.audio_data is None
    assert msg.whatsapp_message_id == "wamid.abc123"


def test_parse_audio_message():
    audio_bytes = b"fake-audio-data"
    b64 = base64.b64encode(audio_bytes).decode()
    payload = _make_payload("+5511888888888", "audioMessage", {"base64": b64}, push_name="João")
    result = MessageParser.parse(payload)
    assert len(result) == 1
    msg = result[0]
    assert msg.message_type == "audio"
    assert msg.audio_data == audio_bytes
    assert msg.content == ""


def test_parse_audio_missing_base64_returns_empty_bytes():
    payload = _make_payload("+5511888888888", "audioMessage", {})
    result = MessageParser.parse(payload)
    assert len(result) == 1
    assert result[0].audio_data == b""


def test_parse_audio_corrupt_base64_returns_empty_bytes():
    """If the base64 field is present but contains invalid data, fall back to empty bytes."""
    payload = _make_payload("+5511888888888", "audioMessage", {"base64": "!!!not-valid-base64!!!"})
    result = MessageParser.parse(payload)
    assert len(result) == 1
    assert result[0].audio_data == b""


def test_parse_unsupported_message_type_is_skipped():
    payload = _make_payload("+5511777777777", "imageMessage", {"imageMessage": {}})
    result = MessageParser.parse(payload)
    assert result == []


def test_parse_non_upsert_event_returns_empty():
    payload = {"event": "connection.update", "data": {"state": "open"}}
    result = MessageParser.parse(payload)
    assert result == []


def test_parse_from_me_true_returns_empty():
    payload = _make_payload("+5511999999999", "conversation", {"conversation": "I replied"}, from_me=True)
    result = MessageParser.parse(payload)
    assert result == []


def test_parse_group_message_is_skipped():
    payload = {
        "event": "messages.upsert",
        "instance": "chacara",
        "data": {
            "key": {"remoteJid": "123456789@g.us", "fromMe": False, "id": "wamid.grp1"},
            "pushName": "Someone",
            "message": {"conversation": "Hi group"},
            "messageType": "conversation",
            "messageTimestamp": 1710280800,
        },
    }
    result = MessageParser.parse(payload)
    assert result == []


def test_parse_phone_number_normalization():
    payload = _make_payload("+5511999999999", "conversation", {"conversation": "Hi"})
    result = MessageParser.parse(payload)
    assert result[0].phone_number == "+5511999999999"


def test_parse_phone_without_plus_gets_normalized():
    number = "5511999999999"
    payload = {
        "event": "messages.upsert",
        "instance": "chacara",
        "data": {
            "key": {"remoteJid": f"{number}@s.whatsapp.net", "fromMe": False, "id": "wamid.x"},
            "pushName": "Test",
            "message": {"conversation": "Hi"},
            "messageType": "conversation",
            "messageTimestamp": 1710280800,
        },
    }
    result = MessageParser.parse(payload)
    assert result[0].phone_number == "+5511999999999"


def test_parse_timestamp_is_string():
    payload = _make_payload("+5511999999999", "conversation", {"conversation": "Hi"})
    result = MessageParser.parse(payload)
    assert isinstance(result[0].timestamp, str)
    assert result[0].timestamp == "1710280800"
