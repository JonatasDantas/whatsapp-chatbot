import pytest
from unittest.mock import patch, MagicMock
from app.config.settings import Settings

PARAM_NAMES = {
    "OPENAI_API_KEY_PARAM": "/chacara-chatbot/openai-api-key",
    "WHATSAPP_ACCESS_TOKEN_PARAM": "/chacara-chatbot/whatsapp-access-token",
    "WHATSAPP_PHONE_NUMBER_ID_PARAM": "/chacara-chatbot/whatsapp-phone-number-id",
    "KNOWLEDGE_BASE_BUCKET_PARAM": "/chacara-chatbot/knowledge-base-bucket",
}

SSM_RESPONSE = {
    "Parameters": [
        {"Name": "/chacara-chatbot/openai-api-key", "Value": "sk-test"},
        {"Name": "/chacara-chatbot/whatsapp-access-token", "Value": "wa-token"},
        {"Name": "/chacara-chatbot/whatsapp-phone-number-id", "Value": "12345"},
        {"Name": "/chacara-chatbot/knowledge-base-bucket", "Value": "my-bucket"},
    ],
    "InvalidParameters": [],
}


def _mock_ssm(response=SSM_RESPONSE):
    mock_client = MagicMock()
    mock_client.get_parameters.return_value = response
    return mock_client


def _set_param_envs(monkeypatch):
    for key, value in PARAM_NAMES.items():
        monkeypatch.setenv(key, value)


def test_settings_reads_from_ssm(monkeypatch):
    _set_param_envs(monkeypatch)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    with patch("app.config.settings.boto3.client", return_value=_mock_ssm()):
        s = Settings()

    assert s.openai_api_key == "sk-test"
    assert s.openai_model == "gpt-4o"
    assert s.whatsapp_access_token == "wa-token"
    assert s.whatsapp_phone_number_id == "12345"
    assert s.knowledge_base_bucket == "my-bucket"


def test_settings_default_model(monkeypatch):
    _set_param_envs(monkeypatch)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with patch("app.config.settings.boto3.client", return_value=_mock_ssm()):
        s = Settings()

    assert s.openai_model == "gpt-4o-mini"


def test_loads_owner_phone_from_ssm(monkeypatch):
    _set_param_envs(monkeypatch)
    monkeypatch.setenv("OWNER_PHONE_PARAM", "/chacara/owner-phone")
    full_response = {
        "Parameters": SSM_RESPONSE["Parameters"] + [
            {"Name": "/chacara/owner-phone", "Value": "+5511888888888"}
        ],
        "InvalidParameters": [],
    }
    with patch("app.config.settings.boto3.client", return_value=_mock_ssm(full_response)):
        s = Settings()
    assert s.owner_phone == "+5511888888888"



def test_settings_raises_on_missing_parameter(monkeypatch):
    _set_param_envs(monkeypatch)
    response_missing_one = {
        "Parameters": [
            {"Name": "/chacara-chatbot/openai-api-key", "Value": "sk-test"},
            # whatsapp-access-token intentionally missing
            {"Name": "/chacara-chatbot/whatsapp-phone-number-id", "Value": "12345"},
            {"Name": "/chacara-chatbot/knowledge-base-bucket", "Value": "my-bucket"},
        ],
        "InvalidParameters": ["/chacara-chatbot/whatsapp-access-token"],
    }

    with patch("app.config.settings.boto3.client", return_value=_mock_ssm(response_missing_one)):
        with pytest.raises(ValueError, match="/chacara-chatbot/whatsapp-access-token"):
            Settings()
