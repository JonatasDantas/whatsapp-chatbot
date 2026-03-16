import json, pytest
from unittest.mock import MagicMock
from app.integrations.llm.openai_client import OpenAIClient

def _make_mock_openai(response_text: str):
    mock = MagicMock()
    choice = MagicMock()
    choice.message.content = response_text
    mock.chat.completions.create.return_value = MagicMock(choices=[choice])
    return mock

def test_chat_returns_text_and_updates():
    payload = json.dumps({
        "response": "Olá! Que datas você tem em mente?",
        "updates": {"stage": "availability", "name": "João"}
    })
    mock_openai = _make_mock_openai(payload)
    client = OpenAIClient(openai_client=mock_openai, model="gpt-4o-mini")

    text, updates = client.chat(
        system="You are a helpful assistant.",
        messages=[{"role": "user", "content": "Oi"}],
    )
    assert text == "Olá! Que datas você tem em mente?"
    assert updates["stage"] == "availability"
    assert updates["name"] == "João"

def test_chat_handles_missing_updates():
    payload = json.dumps({"response": "Olá!"})
    mock_openai = _make_mock_openai(payload)
    client = OpenAIClient(openai_client=mock_openai, model="gpt-4o-mini")
    text, updates = client.chat(system="sys", messages=[])
    assert text == "Olá!"
    assert updates == {}

def test_chat_handles_malformed_json():
    mock_openai = _make_mock_openai("Não entendi.")
    client = OpenAIClient(openai_client=mock_openai, model="gpt-4o-mini")
    text, updates = client.chat(system="sys", messages=[])
    assert text == "Não entendi."
    assert updates == {}
