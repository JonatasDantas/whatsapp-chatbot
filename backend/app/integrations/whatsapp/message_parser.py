import base64
from typing import Optional

from aws_lambda_powertools import Logger
from pydantic import BaseModel

logger = Logger()


class ParsedMessage(BaseModel):
    phone_number: str
    contact_name: str
    message_type: str  # text, audio, unsupported
    content: str
    audio_data: Optional[bytes] = None
    whatsapp_message_id: str
    timestamp: str


def _extract_phone(remote_jid: str) -> str:
    number = remote_jid.split("@")[0]
    return number if number.startswith("+") else f"+{number}"


class MessageParser:
    @staticmethod
    def parse(payload: dict) -> list[ParsedMessage]:
        if payload.get("event") != "messages.upsert":
            logger.info("webhook_event_skipped", event=payload.get("event"))
            return []

        data = payload.get("data", {})
        key = data.get("key", {})

        if key.get("fromMe"):
            logger.info("self_message_skipped")
            return []

        remote_jid = key.get("remoteJid", "")
        if "@g.us" in remote_jid:
            logger.info("group_message_skipped", jid=remote_jid)
            return []

        phone = _extract_phone(remote_jid)
        contact_name = data.get("pushName") or "Unknown"
        message_id = key.get("id", "")
        timestamp = str(data.get("messageTimestamp", ""))
        message_type_raw = data.get("messageType", "")
        message = data.get("message", {})

        if message_type_raw == "conversation":
            content = message.get("conversation", "")
            logger.info("message_parsed", phone=phone, message_type="text")
            return [ParsedMessage(
                phone_number=phone,
                contact_name=contact_name,
                message_type="text",
                content=content,
                whatsapp_message_id=message_id,
                timestamp=timestamp,
            )]

        if message_type_raw == "audioMessage":
            raw_b64 = message.get("base64", "")
            try:
                audio_bytes = base64.b64decode(raw_b64) if raw_b64 else b""
            except Exception:
                logger.warning("audio_base64_decode_failed", phone=phone)
                audio_bytes = b""
            logger.info("message_parsed", phone=phone, message_type="audio")
            return [ParsedMessage(
                phone_number=phone,
                contact_name=contact_name,
                message_type="audio",
                content="",
                audio_data=audio_bytes,
                whatsapp_message_id=message_id,
                timestamp=timestamp,
            )]

        logger.warning("unsupported_message_type", type=message_type_raw, phone=phone)
        return []
