import json
from unittest.mock import MagicMock, patch

import pytest

import app.handlers.webhook_handler as handler_module
from app.handlers.webhook_handler import WebhookHandler


def _make_post_event(body: dict) -> dict:
    return {
        "httpMethod": "POST",
        "body": json.dumps(body),
    }


def _text_message_payload(phone: str, text: str) -> dict:
    number = phone.lstrip("+")
    return {
        "event": "messages.upsert",
        "instance": "chacara",
        "data": {
            "key": {
                "remoteJid": f"{number}@s.whatsapp.net",
                "fromMe": False,
                "id": "wamid.test1",
            },
            "pushName": "Test",
            "message": {"conversation": text},
            "messageType": "conversation",
            "messageTimestamp": 1710280800,
        },
    }


def _make_text_webhook_payload() -> dict:
    return _text_message_payload("+5511999999999", "Hello")


def _reset_handler_globals():
    handler_module._availability_service = None
    handler_module._pricing_service = None


@pytest.fixture(autouse=False)
def mock_repos():
    _reset_handler_globals()

    mock_conv_repo = MagicMock()
    mock_msg_repo = MagicMock()
    mock_conv_repo.load.return_value = None
    mock_msg_repo.get_recent.return_value = []

    with patch("app.handlers.webhook_handler.get_conversation_repo", return_value=mock_conv_repo), \
         patch("app.handlers.webhook_handler.get_message_repo", return_value=mock_msg_repo):
        yield mock_conv_repo, mock_msg_repo

    _reset_handler_globals()


def _patch_all_integrations():
    return [
        patch("app.handlers.webhook_handler.get_conversation_repo"),
        patch("app.handlers.webhook_handler.get_message_repo"),
        patch("app.handlers.webhook_handler.get_openai_client"),
        patch("app.handlers.webhook_handler.get_whatsapp_client"),
        patch("app.handlers.webhook_handler.get_whisper_client"),
        patch("app.handlers.webhook_handler.PromptBuilder"),
        patch("app.handlers.webhook_handler.GenerateAIResponse"),
        patch("app.handlers.webhook_handler._get_settings"),
        patch("app.handlers.webhook_handler._get_availability_service"),
        patch("app.handlers.webhook_handler._get_pricing_service"),
    ]


def test_post_returns_200():
    patches = _patch_all_integrations()
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6] as MockGenerate, patches[7], patches[8], patches[9]:
        MockGenerate.return_value = MagicMock()
        handler = WebhookHandler()
        response = handler.handle(_make_post_event(_make_text_webhook_payload()), None)
        assert response["statusCode"] == 200


def test_post_malformed_json_returns_200():
    handler = WebhookHandler()
    event = {"httpMethod": "POST", "body": "not json"}
    response = handler.handle(event, None)
    assert response["statusCode"] == 200


def test_null_body_returns_200():
    """API Gateway can send body=None; the handler must not crash."""
    handler = WebhookHandler()
    event = {"httpMethod": "POST", "body": None}
    response = handler.handle(event, None)
    assert response["statusCode"] == 200


def test_duplicate_phone_in_batch_generates_response_only_once(mock_repos):
    """Two parsed messages from the same phone must trigger exactly one AI response."""
    from app.integrations.whatsapp.message_parser import ParsedMessage

    parsed1 = ParsedMessage(
        phone_number="+5511999999999",
        contact_name="Maria",
        message_type="text",
        content="hi",
        whatsapp_message_id="wamid.1",
        timestamp="1710280800",
    )
    parsed2 = ParsedMessage(
        phone_number="+5511999999999",
        contact_name="Maria",
        message_type="text",
        content="again",
        whatsapp_message_id="wamid.2",
        timestamp="1710280801",
    )

    with patch("app.handlers.webhook_handler.GenerateAIResponse") as MockGenerate, \
         patch("app.handlers.webhook_handler.get_openai_client"), \
         patch("app.handlers.webhook_handler.get_whatsapp_client"), \
         patch("app.handlers.webhook_handler.get_whisper_client"), \
         patch("app.handlers.webhook_handler.PromptBuilder"), \
         patch("app.handlers.webhook_handler._get_settings"), \
         patch("app.handlers.webhook_handler._get_availability_service"), \
         patch("app.handlers.webhook_handler._get_pricing_service"), \
         patch("app.handlers.webhook_handler.MessageParser") as MockParser, \
         patch("app.handlers.webhook_handler.ProcessIncomingMessage"):

        MockParser.parse.return_value = [parsed1, parsed2]
        mock_instance = MagicMock()
        MockGenerate.return_value = mock_instance

        import json
        handler = WebhookHandler()
        handler.handle({"httpMethod": "POST", "body": json.dumps({})}, None)

    mock_instance.execute.assert_called_once_with(phone_number="+5511999999999")


def test_availability_and_pricing_services_are_singletons():
    """_get_availability_service and _get_pricing_service return the same instance on repeated calls."""
    import app.handlers.webhook_handler as wh_mod
    wh_mod._availability_service = None
    wh_mod._pricing_service = None

    with patch("app.handlers.webhook_handler.get_calendar_repo"), \
         patch("app.handlers.webhook_handler.AvailabilityService") as MockAvail, \
         patch("app.handlers.webhook_handler.PricingService") as MockPricing:

        MockAvail.return_value = MagicMock()
        MockPricing.return_value = MagicMock()

        a1 = wh_mod._get_availability_service()
        a2 = wh_mod._get_availability_service()
        p1 = wh_mod._get_pricing_service()
        p2 = wh_mod._get_pricing_service()

    assert a1 is a2
    assert p1 is p2
    MockAvail.assert_called_once()
    MockPricing.assert_called_once()

    wh_mod._availability_service = None
    wh_mod._pricing_service = None


def test_non_message_upsert_event_returns_200_without_processing():
    payload = {
        "event": "connection.update",
        "instance": "chacara",
        "data": {"state": "open"},
    }
    patches = _patch_all_integrations()
    with patches[0], patches[1], patches[2], patches[3] as mock_wa, \
         patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
        handler = WebhookHandler()
        response = handler.handle(_make_post_event(payload), None)

        assert response["statusCode"] == 200
        mock_wa.return_value.send_text.assert_not_called()


def test_from_me_message_is_skipped():
    payload = {
        "event": "messages.upsert",
        "instance": "chacara",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": True,
                "id": "wamid.self",
            },
            "pushName": "Bot",
            "message": {"conversation": "I replied"},
            "messageType": "conversation",
            "messageTimestamp": 1710280800,
        },
    }
    patches = _patch_all_integrations()
    with patches[0], patches[1], patches[2], patches[3] as mock_wa, \
         patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
        handler = WebhookHandler()
        response = handler.handle(_make_post_event(payload), None)

        assert response["statusCode"] == 200
        mock_wa.return_value.send_text.assert_not_called()


def test_post_calls_generate_ai_response(mock_repos):
    with patch("app.handlers.webhook_handler.GenerateAIResponse") as MockGenerate, \
         patch("app.handlers.webhook_handler.get_openai_client"), \
         patch("app.handlers.webhook_handler.get_whatsapp_client"), \
         patch("app.handlers.webhook_handler.get_whisper_client"), \
         patch("app.handlers.webhook_handler.PromptBuilder"), \
         patch("app.handlers.webhook_handler._get_settings"), \
         patch("app.handlers.webhook_handler._get_availability_service"), \
         patch("app.handlers.webhook_handler._get_pricing_service"):
        mock_instance = MagicMock()
        MockGenerate.return_value = mock_instance

        handler = WebhookHandler()
        event = {
            "httpMethod": "POST",
            "body": json.dumps(_text_message_payload("+5511999999999", "Oi")),
        }
        response = handler.handle(event, {})
        assert response["statusCode"] == 200
        mock_instance.execute.assert_called_once_with(phone_number="+5511999999999")
