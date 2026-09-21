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


def test_chat_none_content_returns_empty():
    """If the LLM returns None content, the client should not crash."""
    mock = MagicMock()
    choice = MagicMock()
    choice.message.content = None
    mock.chat.completions.create.return_value = MagicMock(choices=[choice])
    client = OpenAIClient(openai_client=mock, model="gpt-4o-mini")
    text, updates = client.chat(system="sys", messages=[])
    assert updates == {}


def test_chat_passes_system_and_messages_correctly():
    """System prompt and user messages are combined correctly in the API call."""
    payload = json.dumps({"response": "Ok"})
    mock_openai = _make_mock_openai(payload)
    client = OpenAIClient(openai_client=mock_openai, model="gpt-4o-mini")
    user_msgs = [{"role": "user", "content": "Oi"}]
    client.chat(system="You are helpful.", messages=user_msgs)

    call_args = mock_openai.chat.completions.create.call_args
    messages_sent = call_args[1]["messages"]
    assert messages_sent[0] == {"role": "system", "content": "You are helpful."}
    assert messages_sent[1] == {"role": "user", "content": "Oi"}
