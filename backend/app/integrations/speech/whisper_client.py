import io

from openai import OpenAI
from aws_lambda_powertools import Logger

from app.integrations.llm.openai_client import _get_openai_raw

logger = Logger()

_client = None


def get_whisper_client() -> "WhisperClient":
    global _client
    if _client is None:
        _client = WhisperClient(openai_client=_get_openai_raw())
    return _client


class WhisperClient:
    def __init__(self, openai_client: OpenAI):
        self._client = openai_client

    def transcribe(self, audio_data: bytes, filename: str = "audio.ogg") -> str:
        audio_file = io.BytesIO(audio_data)
        audio_file.name = filename
        result = self._client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="pt",
        )
        logger.info("audio_transcribed", length_chars=len(result.text))
        return result.text
