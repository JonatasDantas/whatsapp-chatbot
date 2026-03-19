import json
import os
from urllib.parse import unquote

from aws_lambda_powertools import Logger

from app.domain.models.conversation import ConversationStage
from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.domain.repositories.reservation_repository import ReservationRepository
from app.integrations.dynamodb.calendar_repo import DynamoDBCalendarRepository
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
        calendar_repo: DynamoDBCalendarRepository | None = None,
    ) -> None:
        self._conv_repo = conversation_repo
        self._msg_repo = message_repo
        self._res_repo = reservation_repo
        self._whatsapp = whatsapp_client
        self._calendar_repo = calendar_repo

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

        if resource == "/api/blocked-periods" and method == "GET":
            return self._list_blocked_periods()

        if resource == "/api/blocked-periods" and method == "POST":
            body = json.loads(event.get("body") or "{}")
            return self._add_blocked_period(body)

        if resource == "/api/blocked-periods/{period_id}" and method == "DELETE":
            period_id = unquote(params.get("period_id", ""))
            return self._delete_blocked_period(period_id)

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

    def _list_blocked_periods(self) -> dict:
        if not self._calendar_repo:
            return _error("Calendar not configured", 503)
        return _ok({"blocked_periods": self._calendar_repo.list_all()})

    def _add_blocked_period(self, body: dict) -> dict:
        if not self._calendar_repo:
            return _error("Calendar not configured", 503)
        start_date = body.get("start_date", "")
        end_date = body.get("end_date", "")
        if not start_date or not end_date:
            return _error("start_date and end_date are required", 400)
        reason = body.get("reason", "")
        period = self._calendar_repo.add_period(start_date, end_date, reason)
        return _ok({"blocked_period": period})

    def _delete_blocked_period(self, period_id: str) -> dict:
        if not self._calendar_repo:
            return _error("Calendar not configured", 503)
        if not period_id:
            return _error("period_id is required", 400)
        found = self._calendar_repo.delete_period(period_id)
        if not found:
            return _not_found(f"Blocked period not found: {period_id}")
        return _ok({"deleted": True})
