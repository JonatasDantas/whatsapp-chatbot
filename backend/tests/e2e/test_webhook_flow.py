"""
End-to-end tests for the webhook Lambda handler.

These tests exercise the full flow from HTTP event → WebhookHandler → use cases
→ DynamoDB (mocked via moto) → WhatsApp send (mocked).

External dependencies mocked:
- DynamoDB: moto (real table operations, fake network)
- SSM / Settings: patched to return known values
- OpenAI: patched to return a fixed response
- WhatsApp send: patched to capture outbound messages
- S3 / PromptBuilder: patched to skip knowledge base fetch

This validates that the data flows correctly between layers.
"""
import json
import os
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

# ── helpers ──────────────────────────────────────────────────────────────────

def _text_message_event(phone: str, text: str, timestamp: str = "1710280800") -> dict:
    wa_id = phone.lstrip("+")
    return {
        "httpMethod": "POST",
        "body": json.dumps({
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "BIZ_ID",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550000000",
                            "phone_number_id": "123",
                        },
                        "contacts": [{"profile": {"name": "Maria Silva"}, "wa_id": wa_id}],
                        "messages": [{
                            "from": wa_id,
                            "id": "wamid.test1",
                            "timestamp": timestamp,
                            "type": "text",
                            "text": {"body": text},
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }),
    }


def _fake_settings():
    s = MagicMock()
    s.openai_api_key = "sk-test"
    s.openai_model = "gpt-4o-mini"
    s.whatsapp_access_token = "wa-token"
    s.whatsapp_phone_number_id = "123"
    s.knowledge_base_bucket = "kb-bucket"
    s.owner_phone = "+5511888888888"
    return s


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_all_singletons():
    """Reset module-level singletons so tests don't share state."""
    import app.config.settings as settings_mod
    import app.integrations.dynamodb.conversation_repo as conv_mod
    import app.integrations.dynamodb.message_repo as msg_mod
    import app.integrations.dynamodb.calendar_repo as cal_mod
    import app.integrations.dynamodb.reservation_repo as res_mod
    import app.integrations.llm.openai_client as openai_mod
    import app.integrations.llm.prompt_builder as pb_mod
    import app.integrations.whatsapp.whatsapp_client as wa_mod
    import app.handlers.webhook_handler as wh_mod

    settings_mod._settings = None
    conv_mod._repo = None
    conv_mod._table = None
    conv_mod._dynamodb = None
    msg_mod._repo = None
    msg_mod._table = None
    msg_mod._dynamodb = None
    cal_mod._repo = None
    cal_mod._table = None
    cal_mod._dynamodb = None
    res_mod._repo = None
    res_mod._table = None
    res_mod._dynamodb = None
    openai_mod._client = None
    openai_mod._openai_raw = None
    pb_mod._knowledge_base = None
    wa_mod._client = None
    wh_mod._ssm = None
    wh_mod._availability_service = None
    wh_mod._pricing_service = None

    yield

    # Reset again after test
    settings_mod._settings = None
    conv_mod._repo = None
    conv_mod._table = None
    conv_mod._dynamodb = None
    msg_mod._repo = None
    msg_mod._table = None
    msg_mod._dynamodb = None
    cal_mod._repo = None
    cal_mod._table = None
    cal_mod._dynamodb = None
    res_mod._repo = None
    res_mod._table = None
    res_mod._dynamodb = None
    openai_mod._client = None
    openai_mod._openai_raw = None
    pb_mod._knowledge_base = None
    wa_mod._client = None
    wh_mod._ssm = None
    wh_mod._availability_service = None
    wh_mod._pricing_service = None


@pytest.fixture
def tables(monkeypatch):
    """Set up real DynamoDB tables in moto and inject env vars."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("CONVERSATIONS_TABLE", "Conversations")
    monkeypatch.setenv("MESSAGES_TABLE", "Messages")
    monkeypatch.setenv("RESERVATIONS_TABLE", "Reservations")
    monkeypatch.setenv("BLOCKED_PERIODS_TABLE", "BlockedPeriods")
    monkeypatch.setenv("NIGHTLY_RATE", "800.0")

    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")

        conversations = ddb.create_table(
            TableName="Conversations",
            KeySchema=[{"AttributeName": "phone_number", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "phone_number", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        messages = ddb.create_table(
            TableName="Messages",
            KeySchema=[
                {"AttributeName": "phone_number", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "phone_number", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.create_table(
            TableName="Reservations",
            KeySchema=[{"AttributeName": "reservation_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "reservation_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.create_table(
            TableName="BlockedPeriods",
            KeySchema=[{"AttributeName": "period_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "period_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        yield {"conversations": conversations, "messages": messages}


# ── tests ────────────────────────────────────────────────────────────────────

def test_incoming_message_creates_conversation_and_sends_reply(tables, monkeypatch):
    """
    Full flow: WhatsApp POST → conversation created → LLM called → reply sent.
    """
    import app.config.settings as settings_mod
    monkeypatch.setattr(settings_mod, "_settings", _fake_settings())

    llm_response = json.dumps({"response": "Olá, Maria! Como posso ajudar?", "updates": {}})

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=llm_response))]
    )

    with patch("app.integrations.llm.openai_client._get_openai_raw", return_value=fake_openai), \
         patch("app.integrations.llm.prompt_builder._get_knowledge_base", return_value="## Property Info\nTest property."), \
         patch("httpx.post") as mock_wa_send, \
         patch("app.handlers.webhook_handler._get_verify_token", return_value="token"):

        mock_wa_send.return_value = MagicMock(raise_for_status=MagicMock())

        from app.handlers.webhook_handler import WebhookHandler
        handler = WebhookHandler()
        event = _text_message_event("+5511999999999", "Olá, quero informações sobre a chácara")
        response = handler.handle(event, None)

    assert response["statusCode"] == 200

    # Verify conversation was persisted in DynamoDB
    item = tables["conversations"].get_item(Key={"phone_number": "+5511999999999"}).get("Item")
    assert item is not None
    assert item["phone_number"] == "+5511999999999"
    assert item["name"] == "Maria Silva"

    # Verify message was persisted
    msgs = tables["messages"].scan().get("Items", [])
    user_msgs = [m for m in msgs if m["role"] == "user"]
    assistant_msgs = [m for m in msgs if m["role"] == "assistant"]
    assert len(user_msgs) == 1
    assert "chácara" in user_msgs[0]["message"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["message"] == "Olá, Maria! Como posso ajudar?"

    # Verify WhatsApp reply was sent
    mock_wa_send.assert_called_once()
    payload = mock_wa_send.call_args.kwargs["json"]
    assert payload["to"] == "+5511999999999"
    assert payload["text"]["body"] == "Olá, Maria! Como posso ajudar?"


def test_incoming_message_updates_conversation_stage(tables, monkeypatch):
    """LLM-returned updates are applied to the conversation state."""
    import app.config.settings as settings_mod
    monkeypatch.setattr(settings_mod, "_settings", _fake_settings())

    llm_response = json.dumps({
        "response": "Ótimo! Checkin em 10 de abril.",
        "updates": {"stage": "availability", "checkin": "2026-04-10", "guests": 4},
    })

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=llm_response))]
    )

    with patch("app.integrations.llm.openai_client._get_openai_raw", return_value=fake_openai), \
         patch("app.integrations.llm.prompt_builder._get_knowledge_base", return_value="## KB\nTest."), \
         patch("httpx.post") as mock_wa_send, \
         patch("app.handlers.webhook_handler._get_verify_token", return_value="token"):

        mock_wa_send.return_value = MagicMock(raise_for_status=MagicMock())

        from app.handlers.webhook_handler import WebhookHandler
        handler = WebhookHandler()
        response = handler.handle(_text_message_event("+5511999999999", "Quero o dia 10 de abril"), None)

    assert response["statusCode"] == 200

    item = tables["conversations"].get_item(Key={"phone_number": "+5511999999999"}).get("Item")
    assert item["stage"] == "availability"
    assert item["checkin"] == "2026-04-10"
    assert item["guests"] == 4


def test_second_message_continues_existing_conversation(tables, monkeypatch):
    """Second message from same phone reuses existing conversation."""
    import app.config.settings as settings_mod
    monkeypatch.setattr(settings_mod, "_settings", _fake_settings())

    # Insert existing conversation directly
    tables["conversations"].put_item(Item={
        "phone_number": "+5511999999999",
        "name": "Maria Silva",
        "stage": "availability",
        "checkin": "2026-04-10",
        "checkout": None,
        "guests": None,
        "purpose": None,
        "customer_profile": None,
        "rules_accepted": False,
        "price_estimate": None,
        "lead_status": "new",
        "owner_notified": False,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
    })

    llm_response = json.dumps({"response": "Perfeito, temos disponibilidade!", "updates": {}})
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=llm_response))]
    )

    with patch("app.integrations.llm.openai_client._get_openai_raw", return_value=fake_openai), \
         patch("app.integrations.llm.prompt_builder._get_knowledge_base", return_value="## KB\nTest."), \
         patch("httpx.post") as mock_wa_send, \
         patch("app.handlers.webhook_handler._get_verify_token", return_value="token"):

        mock_wa_send.return_value = MagicMock(raise_for_status=MagicMock())

        from app.handlers.webhook_handler import WebhookHandler
        handler = WebhookHandler()
        handler.handle(_text_message_event("+5511999999999", "E no final de semana?"), None)

    # Stage should still be availability (LLM didn't change it)
    item = tables["conversations"].get_item(Key={"phone_number": "+5511999999999"}).get("Item")
    assert item["stage"] == "availability"
    assert item["checkin"] == "2026-04-10"  # Preserved from pre-existing conversation


def test_owner_takeover_stops_ai_response(tables, monkeypatch):
    """When stage is owner_takeover, the AI must not reply."""
    import app.config.settings as settings_mod
    monkeypatch.setattr(settings_mod, "_settings", _fake_settings())

    tables["conversations"].put_item(Item={
        "phone_number": "+5511999999999",
        "name": "Maria",
        "stage": "owner_takeover",
        "checkout": None,
        "checkin": None,
        "guests": None,
        "purpose": None,
        "customer_profile": None,
        "rules_accepted": False,
        "price_estimate": None,
        "lead_status": "qualified",
        "owner_notified": True,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
    })

    fake_openai = MagicMock()

    with patch("app.integrations.llm.openai_client._get_openai_raw", return_value=fake_openai), \
         patch("app.integrations.llm.prompt_builder._get_knowledge_base", return_value="## KB"), \
         patch("httpx.post") as mock_wa_send, \
         patch("app.handlers.webhook_handler._get_verify_token", return_value="token"):

        mock_wa_send.return_value = MagicMock(raise_for_status=MagicMock())

        from app.handlers.webhook_handler import WebhookHandler
        handler = WebhookHandler()
        response = handler.handle(_text_message_event("+5511999999999", "Oi, alguma novidade?"), None)

    assert response["statusCode"] == 200

    # OpenAI must NOT have been called
    fake_openai.chat.completions.create.assert_not_called()
    # WhatsApp send must NOT have been called (user message is saved but no reply)
    mock_wa_send.assert_not_called()


def test_status_update_webhook_returns_200(tables, monkeypatch):
    """WhatsApp status delivery updates (not messages) must return 200 without errors."""
    import app.config.settings as settings_mod
    monkeypatch.setattr(settings_mod, "_settings", _fake_settings())
    event = {
        "httpMethod": "POST",
        "body": json.dumps({
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "BIZ_ID",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {},
                        "statuses": [{"id": "wamid.s1", "status": "delivered", "recipient_id": "123"}],
                    },
                    "field": "messages",
                }],
            }],
        }),
    }

    with patch("app.integrations.llm.prompt_builder._get_knowledge_base", return_value="## KB"), \
         patch("app.handlers.webhook_handler._get_verify_token", return_value="token"):
        from app.handlers.webhook_handler import WebhookHandler
        handler = WebhookHandler()
        response = handler.handle(event, None)

    assert response["statusCode"] == 200
    # No messages should be saved (no user message in payload)
    msgs = tables["messages"].scan().get("Items", [])
    assert len(msgs) == 0


def test_webhook_verification_get_request():
    """WhatsApp GET verification must return the challenge when token matches."""
    with patch("app.handlers.webhook_handler._get_verify_token", return_value="secret-token"):
        from app.handlers.webhook_handler import WebhookHandler
        handler = WebhookHandler()
        event = {
            "httpMethod": "GET",
            "queryStringParameters": {
                "hub.mode": "subscribe",
                "hub.verify_token": "secret-token",
                "hub.challenge": "challenge_xyz",
            },
        }
        response = handler.handle(event, None)

    assert response["statusCode"] == 200
    assert response["body"] == "challenge_xyz"


def test_qualified_lead_notifies_owner(tables, monkeypatch):
    """
    When LLM sets lead_status=qualified, the owner receives a WhatsApp notification.
    Two WhatsApp calls should happen: one reply to the guest, one to the owner.
    """
    import app.config.settings as settings_mod
    monkeypatch.setattr(settings_mod, "_settings", _fake_settings())

    tables["conversations"].put_item(Item={
        "phone_number": "+5511999999999",
        "name": "Carlos",
        "stage": "pricing",
        "checkin": "2026-04-10",
        "checkout": "2026-04-12",
        "guests": 4,
        "purpose": "birthday",
        "customer_profile": None,
        "rules_accepted": True,
        "price_estimate": Decimal("1600.0"),
        "lead_status": "new",
        "owner_notified": False,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
    })

    llm_response = json.dumps({
        "response": "Ótimo! Vou encaminhar para o proprietário.",
        "updates": {"lead_status": "qualified", "stage": "owner_takeover"},
    })
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=llm_response))]
    )

    with patch("app.integrations.llm.openai_client._get_openai_raw", return_value=fake_openai), \
         patch("app.integrations.llm.prompt_builder._get_knowledge_base", return_value="## KB\nTest."), \
         patch("httpx.post") as mock_wa_send, \
         patch("app.handlers.webhook_handler._get_verify_token", return_value="token"):

        mock_wa_send.return_value = MagicMock(raise_for_status=MagicMock())

        from app.handlers.webhook_handler import WebhookHandler
        handler = WebhookHandler()
        response = handler.handle(
            _text_message_event("+5511999999999", "Perfeito, pode confirmar!"), None
        )

    assert response["statusCode"] == 200

    # Owner should be notified
    item = tables["conversations"].get_item(Key={"phone_number": "+5511999999999"}).get("Item")
    assert item["lead_status"] == "qualified"
    assert item["owner_notified"] is True

    # Two WhatsApp sends: one to guest, one to owner
    assert mock_wa_send.call_count == 2
    sent_to = [call.kwargs["json"]["to"] for call in mock_wa_send.call_args_list]
    assert "+5511999999999" in sent_to
    assert "+5511888888888" in sent_to


def test_pricing_calculated_and_persisted(tables, monkeypatch):
    """
    When stage is pricing and checkin/checkout are set, price_estimate is calculated
    and stored in DynamoDB before the LLM call.
    """
    import app.config.settings as settings_mod
    monkeypatch.setenv("NIGHTLY_RATE", "800.0")
    monkeypatch.setattr(settings_mod, "_settings", _fake_settings())

    tables["conversations"].put_item(Item={
        "phone_number": "+5511999999999",
        "name": "Ana",
        "stage": "pricing",
        "checkin": "2026-05-01",
        "checkout": "2026-05-03",
        "guests": 6,
        "purpose": "anniversary",
        "customer_profile": None,
        "rules_accepted": True,
        "price_estimate": None,  # not yet calculated
        "lead_status": "new",
        "owner_notified": False,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
    })

    llm_response = json.dumps({
        "response": "O valor estimado é R$ 1600. Confirma?",
        "updates": {},
    })
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=llm_response))]
    )

    with patch("app.integrations.llm.openai_client._get_openai_raw", return_value=fake_openai), \
         patch("app.integrations.llm.prompt_builder._get_knowledge_base", return_value="## KB\nTest."), \
         patch("httpx.post") as mock_wa_send, \
         patch("app.handlers.webhook_handler._get_verify_token", return_value="token"):

        mock_wa_send.return_value = MagicMock(raise_for_status=MagicMock())

        from app.handlers.webhook_handler import WebhookHandler
        handler = WebhookHandler()
        handler.handle(_text_message_event("+5511999999999", "Qual o preço?"), None)

    # price_estimate should now be stored (2 nights × R$800)
    item = tables["conversations"].get_item(Key={"phone_number": "+5511999999999"}).get("Item")
    from decimal import Decimal
    assert item.get("price_estimate") == Decimal("1600.0")
