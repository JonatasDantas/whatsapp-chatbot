import pytest
from unittest.mock import patch, MagicMock
from app.config.settings import Settings

PARAM_NAMES = {
    "OPENAI_API_KEY_PARAM": "/chacara-chatbot/openai-api-key",
    "EVOLUTION_API_URL_PARAM": "/chacara-chatbot/evolution-api-url",
    "EVOLUTION_API_KEY_PARAM": "/chacara-chatbot/evolution-api-key",
    "EVOLUTION_INSTANCE_NAME_PARAM": "/chacara-chatbot/evolution-instance-name",
    "KNOWLEDGE_BASE_BUCKET_PARAM": "/chacara-chatbot/knowledge-base-bucket",
}

SSM_RESPONSE = {
    "Parameters": [
        {"Name": "/chacara-chatbot/openai-api-key", "Value": "sk-test"},
        {"Name": "/chacara-chatbot/evolution-api-url", "Value": "https://evolution.example.com"},
        {"Name": "/chacara-chatbot/evolution-api-key", "Value": "evo-key"},
        {"Name": "/chacara-chatbot/evolution-instance-name", "Value": "chacara"},
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
    assert s.evolution_api_url == "https://evolution.example.com"
    assert s.evolution_api_key == "evo-key"
    assert s.evolution_instance_name == "chacara"
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
            # evolution-api-url intentionally missing
            {"Name": "/chacara-chatbot/evolution-api-key", "Value": "evo-key"},
            {"Name": "/chacara-chatbot/evolution-instance-name", "Value": "chacara"},
            {"Name": "/chacara-chatbot/knowledge-base-bucket", "Value": "my-bucket"},
        ],
        "InvalidParameters": ["/chacara-chatbot/evolution-api-url"],
    }

    with patch("app.config.settings.boto3.client", return_value=_mock_ssm(response_missing_one)):
        with pytest.raises(ValueError, match="/chacara-chatbot/evolution-api-url"):
            Settings()


def test_get_settings_singleton_returns_same_instance(monkeypatch):
    """_get_settings() caches the instance and returns the same object on repeated calls."""
    import app.config.settings as settings_mod
    _set_param_envs(monkeypatch)
    monkeypatch.setattr(settings_mod, "_settings", None)

    with patch("app.config.settings.boto3.client", return_value=_mock_ssm()):
        s1 = settings_mod._get_settings()
        s2 = settings_mod._get_settings()

    assert s1 is s2
    monkeypatch.setattr(settings_mod, "_settings", None)


def test_settings_with_no_param_env_vars_skips_ssm(monkeypatch):
    """When no *_PARAM env vars are set, Settings initialises without calling SSM."""
    for key in PARAM_NAMES:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("OWNER_PHONE_PARAM", raising=False)

    with patch("app.config.settings.boto3.client") as mock_boto:
        s = Settings()

    mock_boto.assert_not_called()
    assert s.openai_api_key == ""
    assert s.evolution_api_url == ""
