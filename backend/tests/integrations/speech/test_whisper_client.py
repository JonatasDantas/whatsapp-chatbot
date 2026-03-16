from unittest.mock import MagicMock, patch
from app.integrations.speech.whisper_client import WhisperClient

def test_transcribe_calls_whisper_api():
    mock_openai = MagicMock()
    mock_openai.audio.transcriptions.create.return_value = MagicMock(text="Olá, tudo bem?")

    client = WhisperClient(openai_client=mock_openai)
    result = client.transcribe(audio_data=b"fake-audio-bytes", filename="audio.ogg")

    assert result == "Olá, tudo bem?"
    mock_openai.audio.transcriptions.create.assert_called_once()
    call_kwargs = mock_openai.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["model"] == "whisper-1"
    assert call_kwargs["language"] == "pt"
