import httpx
from aws_lambda_powertools import Logger

from app.config.settings import _get_settings

logger = Logger()

_client = None


def get_whatsapp_client() -> "WhatsAppClient":
    global _client
    if _client is None:
        settings = _get_settings()
        _client = WhatsAppClient(
            api_url=settings.evolution_api_url,
            api_key=settings.evolution_api_key,
            instance_name=settings.evolution_instance_name,
        )
    return _client


class WhatsAppClient:
    def __init__(self, api_url: str, api_key: str, instance_name: str):
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._instance_name = instance_name

    def send_text(self, to: str, text: str) -> None:
        url = f"{self._api_url}/message/sendText/{self._instance_name}"
        headers = {"apikey": self._api_key}
        payload = {"number": to, "text": text}
        response = httpx.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info("whatsapp_message_sent", to=to)
