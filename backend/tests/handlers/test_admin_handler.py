import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.domain.models.conversation import Conversation, ConversationStage, LeadStatus
from app.domain.models.message import Message, MessageRole, MessageType
from app.handlers.admin_handler import AdminHandler


def _make_conversation(**kwargs) -> Conversation:
    defaults = dict(
        phone_number="+5511999999999",
        stage=ConversationStage.QUALIFICATION,
        lead_status=LeadStatus.QUALIFIED,
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return Conversation(**defaults)


def _event(method: str, path: str, path_params: dict | None = None, body: dict | None = None) -> dict:
    return {
        "httpMethod": method,
        "resource": path,
        "pathParameters": path_params or {},
        "body": json.dumps(body) if body else None,
        "headers": {},
    }


def test_list_conversations_returns_200():
    conv_repo = MagicMock()
    msg_repo = MagicMock()
    res_repo = MagicMock()
    whatsapp = MagicMock()
    conv_repo.list_all.return_value = [_make_conversation()]

    handler = AdminHandler(conv_repo, msg_repo, res_repo, whatsapp)
    event = _event("GET", "/api/conversations")
    result = handler.handle(event)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["conversations"]) == 1
    assert body["conversations"][0]["phone_number"] == "+5511999999999"


def test_get_conversation_messages_returns_200():
    conv_repo = MagicMock()
    msg_repo = MagicMock()
    res_repo = MagicMock()
    whatsapp = MagicMock()
    conv_repo.load.return_value = _make_conversation()
    msg_repo.get_all.return_value = [
        Message(
            phone_number="+5511999999999",
            role=MessageRole.USER,
            message="Olá, tem disponibilidade?",
            message_type=MessageType.TEXT,
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    ]

    handler = AdminHandler(conv_repo, msg_repo, res_repo, whatsapp)
    event = _event("GET", "/api/conversations/{phone}/messages",
                   path_params={"phone": "%2B5511999999999"})
    result = handler.handle(event)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["messages"]) == 1


def test_list_reservations_returns_200():
    conv_repo = MagicMock()
    msg_repo = MagicMock()
    res_repo = MagicMock()
    whatsapp = MagicMock()
    res_repo.list_all.return_value = []

    handler = AdminHandler(conv_repo, msg_repo, res_repo, whatsapp)
    event = _event("GET", "/api/reservations")
    result = handler.handle(event)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["reservations"] == []


def test_unknown_route_returns_404():
    handler = AdminHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    event = _event("GET", "/api/unknown")
    result = handler.handle(event)
    assert result["statusCode"] == 404


def test_takeover_sets_stage_and_sends_message():
    conv_repo = MagicMock()
    msg_repo = MagicMock()
    res_repo = MagicMock()
    whatsapp = MagicMock()
    conv_repo.load.return_value = _make_conversation()

    handler = AdminHandler(conv_repo, msg_repo, res_repo, whatsapp)
    event = _event("POST", "/api/conversations/{phone}/takeover",
                   path_params={"phone": "%2B5511999999999"})
    result = handler.handle(event)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["conversation"]["stage"] == "owner_takeover"
    assert body["conversation"]["owner_notified"] is True
    whatsapp.send_text.assert_called_once_with(
        "+5511999999999",
        "Olá! O proprietário da chácara entrará em contato com você em breve. "
        "Obrigado pela paciência!",
    )
    conv_repo.save.assert_called_once()


def test_takeover_not_found_returns_404():
    conv_repo = MagicMock()
    conv_repo.load.return_value = None
    handler = AdminHandler(conv_repo, MagicMock(), MagicMock(), MagicMock())
    event = _event("POST", "/api/conversations/{phone}/takeover",
                   path_params={"phone": "unknown"})
    result = handler.handle(event)
    assert result["statusCode"] == 404
