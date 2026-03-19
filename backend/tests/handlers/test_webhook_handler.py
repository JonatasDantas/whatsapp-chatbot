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
    wa_id = phone.lstrip("+")
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "BIZ_ID", "changes": [{"value": {
            "messaging_product": "whatsapp",
            "metadata": {
                "display_phone_number": "15550000000",
                "phone_number_id": "123",
            },
            "contacts": [{"profile": {"name": "Test"}, "wa_id": wa_id}],
            "messages": [{
                "from": wa_id,
                "id": "wamid.test1",
                "timestamp": "1710280800",
                "type": "text",
                "text": {"body": text},
            }],
        }, "field": "messages"}]}],
    }


def _make_text_webhook_payload() -> dict:
    return _text_message_payload("+5511999999999", "Hello")


def _reset_handler_globals():
    handler_module._ssm = None
    handler_module._availability_service = None
    handler_module._pricing_service = None


@pytest.fixture(autouse=False)
def mock_repos():
    """Reset handler globals and mock repo/client factories."""
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
    """Return a list of patches for all external integrations used in POST handling."""
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


def test_post_status_only_returns_200():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "BIZ_ID", "changes": [{"value": {
            "messaging_product": "whatsapp",
            "metadata": {},
            "statuses": [
                {"id": "wamid.s1", "status": "delivered", "recipient_id": "123"},
            ],
        }, "field": "messages"}]}],
    }
    patches = _patch_all_integrations()
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], patches[9]:
        handler = WebhookHandler()
        response = handler.handle(_make_post_event(payload), None)
        assert response["statusCode"] == 200


def test_post_invalid_payload_returns_200():
    patches = _patch_all_integrations()
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], patches[9]:
        handler = WebhookHandler()
        response = handler.handle(_make_post_event({"invalid": "payload"}), None)
        assert response["statusCode"] == 200


def test_post_malformed_json_returns_200():
    handler = WebhookHandler()
    event = {"httpMethod": "POST", "body": "not json"}
    response = handler.handle(event, None)
    assert response["statusCode"] == 200


def test_get_valid_token_returns_200_with_challenge():
    with patch("app.handlers.webhook_handler._get_verify_token", return_value="my-token"):
        handler = WebhookHandler()
        event = {
            "httpMethod": "GET",
            "queryStringParameters": {
                "hub.mode": "subscribe",
                "hub.verify_token": "my-token",
                "hub.challenge": "challenge_abc",
            },
        }
        response = handler.handle(event, None)
        assert response["statusCode"] == 200
        assert response["body"] == "challenge_abc"


def test_get_invalid_token_returns_403():
    with patch("app.handlers.webhook_handler._get_verify_token", return_value="my-token"):
        handler = WebhookHandler()
        event = {
            "httpMethod": "GET",
            "queryStringParameters": {
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "challenge_abc",
            },
        }
        response = handler.handle(event, None)
        assert response["statusCode"] == 403


def test_get_missing_params_returns_403():
    with patch("app.handlers.webhook_handler._get_verify_token", return_value="my-token"):
        handler = WebhookHandler()
        event = {
            "httpMethod": "GET",
            "queryStringParameters": {},
        }
        response = handler.handle(event, None)
        assert response["statusCode"] == 403


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
