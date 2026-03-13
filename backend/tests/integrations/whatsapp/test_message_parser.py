from app.integrations.whatsapp.message_parser import MessageParser


def _make_webhook_payload(
    messages=None, contacts=None, statuses=None
) -> dict:
    """Build a minimal valid WhatsApp webhook payload."""
    value = {"messaging_product": "whatsapp", "metadata": {
        "display_phone_number": "15550000000",
        "phone_number_id": "123456",
    }}
    if contacts is not None:
        value["contacts"] = contacts
    if messages is not None:
        value["messages"] = messages
    if statuses is not None:
        value["statuses"] = statuses
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "BIZ_ID", "changes": [{"value": value, "field": "messages"}]}],
    }


def test_parse_text_message():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "Maria"}, "wa_id": "5511999999999"}],
        messages=[{
            "from": "5511999999999",
            "id": "wamid.abc123",
            "timestamp": "1710280800",
            "type": "text",
            "text": {"body": "Hello"},
        }],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 1
    msg = result[0]
    assert msg.phone_number == "+5511999999999"
    assert msg.contact_name == "Maria"
    assert msg.message_type == "text"
    assert msg.content == "Hello"
    assert msg.media_id is None
    assert msg.whatsapp_message_id == "wamid.abc123"


def test_parse_audio_message():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "João"}, "wa_id": "5511888888888"}],
        messages=[{
            "from": "5511888888888",
            "id": "wamid.audio1",
            "timestamp": "1710280800",
            "type": "audio",
            "audio": {"id": "media_xyz", "mime_type": "audio/ogg"},
        }],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 1
    msg = result[0]
    assert msg.message_type == "audio"
    assert msg.media_id == "media_xyz"
    assert msg.content == ""


def test_parse_unsupported_message_type():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "Ana"}, "wa_id": "5511777777777"}],
        messages=[{
            "from": "5511777777777",
            "id": "wamid.img1",
            "timestamp": "1710280800",
            "type": "image",
            "image": {"id": "media_img"},
        }],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 1
    msg = result[0]
    assert msg.message_type == "unsupported"
    assert msg.content == "[unsupported: image]"


def test_parse_status_only_payload():
    payload = _make_webhook_payload(
        statuses=[{
            "id": "wamid.s1",
            "status": "delivered",
            "recipient_id": "5511999999999",
        }],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 0


def test_parse_phone_number_normalization():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "Test"}, "wa_id": "5511999999999"}],
        messages=[{
            "from": "5511999999999",
            "id": "wamid.norm1",
            "timestamp": "1710280800",
            "type": "text",
            "text": {"body": "Hi"},
        }],
    )
    result = MessageParser.parse(payload)
    assert result[0].phone_number == "+5511999999999"


def test_parse_multiple_messages():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "Maria"}, "wa_id": "5511999999999"}],
        messages=[
            {
                "from": "5511999999999", "id": "wamid.m1",
                "timestamp": "1710280800", "type": "text",
                "text": {"body": "Hi"},
            },
            {
                "from": "5511999999999", "id": "wamid.m2",
                "timestamp": "1710280801", "type": "text",
                "text": {"body": "Hello"},
            },
        ],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 2


def test_parse_invalid_payload_returns_empty():
    result = MessageParser.parse({"object": "something_else"})
    assert result == []
