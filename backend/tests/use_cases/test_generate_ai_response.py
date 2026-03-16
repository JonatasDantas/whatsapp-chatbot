import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from app.domain.models.conversation import Conversation, ConversationStage
from app.domain.models.message import Message, MessageRole, MessageType
from app.use_cases.generate_ai_response import GenerateAIResponse

def _make_fake_repos(conversation=None, messages=None):
    conv_repo = MagicMock()
    conv_repo.load.return_value = conversation or Conversation(phone_number="+5511999999999")
    msg_repo = MagicMock()
    msg_repo.get_recent.return_value = messages or []
    return conv_repo, msg_repo

def test_saves_assistant_message_and_sends_whatsapp():
    conv_repo, msg_repo = _make_fake_repos()
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Olá, bem-vindo!", {})
    whatsapp_client = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
    )
    use_case.execute(phone_number="+5511999999999")

    msg_repo.save.assert_called_once()
    saved_msg = msg_repo.save.call_args[0][0]
    assert saved_msg.role == MessageRole.ASSISTANT
    assert saved_msg.message == "Olá, bem-vindo!"
    whatsapp_client.send_text.assert_called_once_with(to="+5511999999999", text="Olá, bem-vindo!")

def test_updates_conversation_with_structured_data():
    conv = Conversation(phone_number="+5511999999999")
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Ok!", {"stage": "qualification", "guests": 4, "checkin": "2026-04-10"})
    whatsapp_client = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
    )
    use_case.execute(phone_number="+5511999999999")

    conv_repo.save.assert_called_once()
    saved_conv = conv_repo.save.call_args[0][0]
    assert saved_conv.stage == ConversationStage.QUALIFICATION
    assert saved_conv.guests == 4
    assert saved_conv.checkin == "2026-04-10"

def test_skips_ai_response_for_owner_takeover():
    conv = Conversation(phone_number="+5511999999999", stage=ConversationStage.OWNER_TAKEOVER)
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    openai_client = MagicMock()
    whatsapp_client = MagicMock()
    prompt_builder = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
    )
    use_case.execute(phone_number="+5511999999999")

    openai_client.chat.assert_not_called()
    whatsapp_client.send_text.assert_not_called()
