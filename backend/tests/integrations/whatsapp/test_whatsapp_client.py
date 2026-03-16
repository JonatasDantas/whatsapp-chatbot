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
