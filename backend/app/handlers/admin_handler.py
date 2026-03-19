import json
import os
from urllib.parse import unquote

from aws_lambda_powertools import Logger

from app.domain.models.conversation import ConversationStage
from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.domain.repositories.reservation_repository import ReservationRepository
from app.integrations.whatsapp.whatsapp_client import WhatsAppClient

logger = Logger()

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
    "Access-Control-Allow-Headers": "Authorization,Content-Type",
}

TAKEOVER_MESSAGE = (
    "Olá! O proprietário da chácara entrará em contato com você em breve. "
    "Obrigado pela paciência!"
)


def _ok(body: dict) -> dict:
    return {"statusCode": 200, "headers": CORS_HEADERS, "body": json.dumps(body, default=str)}


def _not_found(msg: str = "Not found") -> dict:
    return {"statusCode": 404, "headers": CORS_HEADERS, "body": json.dumps({"error": msg})}


def _error(msg: str, code: int = 500) -> dict:
    return {"statusCode": code, "headers": CORS_HEADERS, "body": json.dumps({"error": msg})}


class AdminHandler:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        reservation_repo: ReservationRepository,
        whatsapp_client: WhatsAppClient,
    ) -> None:
        self._conv_repo = conversation_repo
        self._msg_repo = message_repo
        self._res_repo = reservation_repo
        self._whatsapp = whatsapp_client

    def handle(self, event: dict) -> dict:
        method = event.get("httpMethod", "GET")
        resource = event.get("resource", "")
        params = event.get("pathParameters") or {}

        logger.info("admin_request", method=method, resource=resource)

        if method == "OPTIONS":
            return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

        if resource == "/api/conversations" and method == "GET":
            return self._list_conversations()

        if resource == "/api/conversations/{phone}" and method == "GET":
            phone = unquote(params.get("phone", ""))
            return self._get_conversation(phone)

        if resource == "/api/conversations/{phone}/messages" and method == "GET":
            phone = unquote(params.get("phone", ""))
            return self._get_messages(phone)

        if resource == "/api/conversations/{phone}/takeover" and method == "POST":
            phone = unquote(params.get("phone", ""))
            return self._takeover(phone)

        if resource == "/api/reservations" and method == "GET":
            return self._list_reservations()

        return _not_found()

    def _list_conversations(self) -> dict:
        conversations = self._conv_repo.list_all()
        return _ok({"conversations": [c.model_dump(mode="json") for c in conversations]})

    def _get_conversation(self, phone: str) -> dict:
        conv = self._conv_repo.load(phone)
        if not conv:
            return _not_found(f"Conversation not found: {phone}")
        return _ok({"conversation": conv.model_dump(mode="json")})

    def _get_messages(self, phone: str) -> dict:
        messages = self._msg_repo.get_all(phone)
        return _ok({"messages": [m.model_dump(mode="json") for m in messages]})

    def _takeover(self, phone: str) -> dict:
        conv = self._conv_repo.load(phone)
        if not conv:
            return _not_found(f"Conversation not found: {phone}")
        conv.stage = ConversationStage.OWNER_TAKEOVER
        conv.owner_notified = True
        conv.touch()
        self._conv_repo.save(conv)
        try:
            self._whatsapp.send_text(phone, TAKEOVER_MESSAGE)
        except Exception:
            logger.exception("failed_to_send_takeover_message", phone=phone)
        return _ok({"conversation": conv.model_dump(mode="json")})

    def _list_reservations(self) -> dict:
        reservations = self._res_repo.list_all()
        return _ok({"reservations": [r.model_dump(mode="json") for r in reservations]})
