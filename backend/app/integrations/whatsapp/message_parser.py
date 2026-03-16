from typing import Optional

from aws_lambda_powertools import Logger
from pydantic import BaseModel, ConfigDict, Field

logger = Logger()


class ParsedMessage(BaseModel):
    phone_number: str
    contact_name: str
    message_type: str  # text, audio, unsupported
    content: str
    media_id: Optional[str] = None
    whatsapp_message_id: str
    timestamp: str


class ContactProfile(BaseModel):
    name: str


class Contact(BaseModel):
    profile: ContactProfile
    wa_id: str


class TextContent(BaseModel):
    body: str


class AudioContent(BaseModel):
    id: str
    mime_type: Optional[str] = None


class WhatsAppMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    text: Optional[TextContent] = None
    audio: Optional[AudioContent] = None


class Metadata(BaseModel):
    display_phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None


class Value(BaseModel):
    messaging_product: Optional[str] = None
    metadata: Optional[Metadata] = None
    contacts: Optional[list[Contact]] = None
    messages: Optional[list[WhatsAppMessage]] = None
    statuses: Optional[list[dict]] = None


class Change(BaseModel):
    value: Value
    field: str


class Entry(BaseModel):
    id: str
    changes: list[Change]


class WhatsAppWebhook(BaseModel):
    object: str
    entry: list[Entry]


def _normalize_phone(phone: str) -> str:
    if not phone.startswith("+"):
        return f"+{phone}"
    return phone


class MessageParser:
    @staticmethod
    def parse(payload: dict) -> list[ParsedMessage]:
        try:
            webhook = WhatsAppWebhook.model_validate(payload)
        except Exception:
            logger.warning("webhook_parse_failed")
            return []

        if webhook.object != "whatsapp_business_account":
            logger.warning("unexpected_webhook_object", object=webhook.object)
            return []

        parsed: list[ParsedMessage] = []

        for entry in webhook.entry:
            for change in entry.changes:
                value = change.value

                if not value.messages:
                    if value.statuses:
                        logger.info("webhook_status_update_skipped", count=len(value.statuses))
                    continue

                contacts_map: dict[str, str] = {}
                if value.contacts:
                    for contact in value.contacts:
                        contacts_map[contact.wa_id] = contact.profile.name

                for msg in value.messages:
                    phone = _normalize_phone(msg.from_)
                    contact_name = contacts_map.get(msg.from_, "Unknown")

                    if msg.type == "text" and msg.text:
                        content = msg.text.body
                        media_id = None
                        message_type = "text"
                    elif msg.type == "audio" and msg.audio:
                        content = ""
                        media_id = msg.audio.id
                        message_type = "audio"
                    else:
                        content = f"[unsupported: {msg.type}]"
                        media_id = None
                        message_type = "unsupported"
                        logger.warning("unsupported_message_type", type=msg.type, phone=phone)

                    logger.info("message_parsed", phone=phone, message_type=message_type)
                    parsed.append(ParsedMessage(
                        phone_number=phone,
                        contact_name=contact_name,
                        message_type=message_type,
                        content=content,
                        media_id=media_id,
                        whatsapp_message_id=msg.id,
                        timestamp=msg.timestamp,
                    ))

        return parsed
