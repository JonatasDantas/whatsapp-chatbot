import json

from openai import OpenAI
from aws_lambda_powertools import Logger

from app.config.settings import _get_settings

logger = Logger()

_openai_raw = None
_client = None


def _get_openai_raw() -> OpenAI:
    global _openai_raw
    if _openai_raw is None:
        _openai_raw = OpenAI(api_key=_get_settings().openai_api_key)
    return _openai_raw


def get_openai_client() -> "OpenAIClient":
    global _client
    if _client is None:
        settings = _get_settings()
        _client = OpenAIClient(openai_client=_get_openai_raw(), model=settings.openai_model)
    return _client


class OpenAIClient:
    def __init__(self, openai_client: OpenAI, model: str):
        self._client = openai_client
        self._model = model

    def chat(
        self,
        system: str,
        messages: list[dict],
    ) -> tuple[str, dict]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}] + messages,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        try:
            parsed = json.loads(raw)
            text = parsed.get("response", raw)
            updates = parsed.get("updates", {})
        except (json.JSONDecodeError, AttributeError):
            text = raw
            updates = {}

        logger.info("llm_response_received", updates_keys=list(updates.keys()))
        return text, updates
