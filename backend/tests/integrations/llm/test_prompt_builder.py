import pytest
from datetime import datetime, timezone
from unittest.mock import patch

import app.integrations.llm.prompt_builder as pb_module
from app.domain.models.conversation import Conversation, ConversationStage
from app.domain.models.message import Message, MessageRole, MessageType
from app.integrations.llm.prompt_builder import PromptBuilder

KB_CONTENT = "# System Instructions\nBe helpful."


@pytest.fixture(autouse=True)
def mock_knowledge_base():
    with patch.object(pb_module, "_get_knowledge_base", return_value=KB_CONTENT):
        pb_module._knowledge_base = None
        yield
    pb_module._knowledge_base = None


def test_system_prompt_includes_knowledge_base():
    builder = PromptBuilder()
    conv = Conversation(phone_number="+5511999999999")
    prompt = builder.build_system_prompt(conv)
    assert "# System Instructions" in prompt
    assert "Be helpful." in prompt


def test_system_prompt_includes_conversation_state():
    builder = PromptBuilder()
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.QUALIFICATION,
        guests=4,
        checkin="2026-04-10",
    )
    prompt = builder.build_system_prompt(conv)
    assert "qualification" in prompt
    assert "4" in prompt
    assert "2026-04-10" in prompt


def test_build_messages_formats_roles():
    builder = PromptBuilder()
    msgs = [
        Message(
            phone_number="+5511",
            timestamp=datetime.now(timezone.utc),
            role=MessageRole.USER,
            message="Oi",
        ),
        Message(
            phone_number="+5511",
            timestamp=datetime.now(timezone.utc),
            role=MessageRole.ASSISTANT,
            message="Olá!",
        ),
    ]
    result = builder.build_messages(msgs)
    assert result[0] == {"role": "user", "content": "Oi"}
    assert result[1] == {"role": "assistant", "content": "Olá!"}


def test_system_prompt_includes_extra_context():
    builder = PromptBuilder()
    conv = Conversation(
        phone_number="+5511999999999",
        checkin="2026-04-10",
        checkout="2026-04-12",
    )
    prompt = builder.build_system_prompt(conv, extra_context={"dates_available": True})
    assert "dates_available" in prompt
    assert "true" in prompt.lower()


def test_system_prompt_extra_context_none_does_not_crash():
    builder = PromptBuilder()
    conv = Conversation(phone_number="+5511999999999")
    prompt = builder.build_system_prompt(conv, extra_context=None)
    assert "Current Conversation State" in prompt
