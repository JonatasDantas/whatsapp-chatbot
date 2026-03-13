import json
from unittest.mock import MagicMock, patch

from app.handlers.webhook_handler import WebhookHandler


def _make_post_event(body: dict) -> dict:
    return {
        "httpMethod": "POST",
        "body": json.dumps(body),
    }


def _make_text_webhook_payload() -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "BIZ_ID", "changes": [{"value": {
            "messaging_product": "whatsapp",
            "metadata": {
                "display_phone_number": "15550000000",
                "phone_number_id": "123",
            },
            "contacts": [{"profile": {"name": "Maria"}, "wa_id": "5511999999999"}],
            "messages": [{
                "from": "5511999999999",
                "id": "wamid.test1",
                "timestamp": "1710280800",
                "type": "text",
                "text": {"body": "Hello"},
            }],
        }, "field": "messages"}]}],
    }


@patch("app.handlers.webhook_handler._get_messages_table")
@patch("app.handlers.webhook_handler._get_conversations_table")
def test_post_returns_200(mock_conv_table, mock_msg_table):
    mock_conv_table.return_value = MagicMock()
    mock_msg_table.return_value = MagicMock()

    # Mock the DynamoDB table's get_item to return no existing conversation
    mock_conv_table.return_value.get_item.return_value = {}
    # Mock put_item to do nothing
    mock_conv_table.return_value.put_item.return_value = {}
    mock_msg_table.return_value.put_item.return_value = {}

    handler = WebhookHandler()
    event = _make_post_event(_make_text_webhook_payload())
    response = handler.handle(event, None)
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
    handler = WebhookHandler()
    event = _make_post_event(payload)
    response = handler.handle(event, None)
    assert response["statusCode"] == 200


def test_post_invalid_payload_returns_200():
    handler = WebhookHandler()
    event = _make_post_event({"invalid": "payload"})
    response = handler.handle(event, None)
    assert response["statusCode"] == 200


def test_post_malformed_json_returns_200():
    handler = WebhookHandler()
    event = {"httpMethod": "POST", "body": "not json"}
    response = handler.handle(event, None)
    assert response["statusCode"] == 200


def test_get_valid_token_returns_200_with_challenge():
    with patch(
        "app.handlers.webhook_handler._get_verify_token", return_value="my-token"
    ):
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
    with patch(
        "app.handlers.webhook_handler._get_verify_token", return_value="my-token"
    ):
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
    with patch(
        "app.handlers.webhook_handler._get_verify_token", return_value="my-token"
    ):
        handler = WebhookHandler()
        event = {
            "httpMethod": "GET",
            "queryStringParameters": {},
        }
        response = handler.handle(event, None)
        assert response["statusCode"] == 403
