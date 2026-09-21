from unittest.mock import MagicMock, patch

from app.integrations.whatsapp.whatsapp_client import WhatsAppClient


def _make_client():
    return WhatsAppClient(
        api_url="https://evolution.example.com",
        api_key="test-key",
        instance_name="chacara",
    )


def test_send_text_calls_correct_endpoint():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_response) as mock_post:
        _make_client().send_text(to="+5511999999999", text="Olá!")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "chacara" in args[0]
        assert "sendText" in args[0]
        assert kwargs["json"]["number"] == "+5511999999999"
        assert kwargs["json"]["text"] == "Olá!"
        assert kwargs["headers"]["apikey"] == "test-key"


def test_send_text_uses_api_url():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_response) as mock_post:
        _make_client().send_text(to="+5511999999999", text="Hi")

        url = mock_post.call_args.args[0]
        assert url.startswith("https://evolution.example.com")


def test_send_text_strips_trailing_slash_from_url():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_response) as mock_post:
        client = WhatsAppClient(
            api_url="https://evolution.example.com/",
            api_key="key",
            instance_name="inst",
        )
        client.send_text(to="+55", text="Hi")

        url = mock_post.call_args.args[0]
        assert "//" not in url.replace("https://", "")


def test_send_text_raises_on_http_error():
    """Evolution API 4xx/5xx responses propagate via raise_for_status."""
    import httpx

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401 Unauthorized",
        request=MagicMock(),
        response=MagicMock(status_code=401),
    )

    with patch("httpx.post", return_value=mock_response):
        import pytest
        with pytest.raises(httpx.HTTPStatusError):
            _make_client().send_text(to="+55", text="Hi")
