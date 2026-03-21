import httpx, pytest
from unittest.mock import MagicMock, patch
from app.integrations.whatsapp.whatsapp_client import WhatsAppClient

def test_send_text_calls_correct_endpoint():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_response) as mock_post:
        client = WhatsAppClient(access_token="tok", phone_number_id="999")
        client.send_text(to="+5511999999999", text="Olá!")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "999" in args[0]
        assert kwargs["json"]["to"] == "+5511999999999"
        assert kwargs["json"]["text"]["body"] == "Olá!"
        assert kwargs["headers"]["Authorization"] == "Bearer tok"


def test_get_media_url_returns_url():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"url": "https://cdn.whatsapp.net/audio/123.ogg"}

    with patch("httpx.get", return_value=mock_response) as mock_get:
        client = WhatsAppClient(access_token="tok", phone_number_id="999")
        url = client.get_media_url(media_id="media-abc")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "media-abc" in args[0]
        assert kwargs["headers"]["Authorization"] == "Bearer tok"
        assert url == "https://cdn.whatsapp.net/audio/123.ogg"


def test_download_media_returns_bytes():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"fake-audio-bytes"

    with patch("httpx.get", return_value=mock_response) as mock_get:
        client = WhatsAppClient(access_token="tok", phone_number_id="999")
        data = client.download_media("https://cdn.whatsapp.net/audio/123.ogg")

        mock_get.assert_called_once()
        call_headers = mock_get.call_args.kwargs["headers"]
        assert call_headers["Authorization"] == "Bearer tok"
        assert data == b"fake-audio-bytes"
