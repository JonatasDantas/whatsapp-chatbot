import httpx
from aws_lambda_powertools import Logger

from app.config.settings import _get_settings

logger = Logger()

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"

_client = None


def get_whatsapp_client() -> "WhatsAppClient":
    global _client
    if _client is None:
        settings = _get_settings()
        _client = WhatsAppClient(
            access_token=settings.whatsapp_access_token,
            phone_number_id=settings.whatsapp_phone_number_id,
        )
    return _client


class WhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str):
        self._access_token = access_token
        self._phone_number_id = phone_number_id

    def send_text(self, to: str, text: str) -> None:
        url = f"{WHATSAPP_API_URL}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        response = httpx.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info("whatsapp_message_sent", to=to)

    def get_media_url(self, media_id: str) -> str:
        url = f"{WHATSAPP_API_URL}/{media_id}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        return response.json()["url"]

    def download_media(self, media_url: str) -> bytes:
        headers = {"Authorization": f"Bearer {self._access_token}"}
        response = httpx.get(media_url, headers=headers)
        response.raise_for_status()
        return response.content
