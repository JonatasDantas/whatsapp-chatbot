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

def test_calculates_price_when_stage_is_pricing():
    from app.domain.models.conversation import ConversationStage
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.PRICING,
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
    )
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("O preço é R$ 1600.", {})
    whatsapp_client = MagicMock()
    pricing_service = MagicMock()
    pricing_service.calculate.return_value = 1600.0
    availability_service = MagicMock()
    availability_service.check.return_value = True
    notify_owner = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        pricing_service=pricing_service,
        availability_service=availability_service,
        notify_owner=notify_owner,
    )
    use_case.execute(phone_number="+5511999999999")

    pricing_service.calculate.assert_called_once_with(
        checkin="2026-04-10", checkout="2026-04-12", guests=4
    )
    saved = conv_repo.save.call_args[0][0]
    assert saved.price_estimate == 1600.0


def test_notifies_owner_when_lead_becomes_qualified():
    from app.domain.models.conversation import ConversationStage
    conv = Conversation(phone_number="+5511999999999", stage=ConversationStage.PRICING)
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Perfeito!", {"lead_status": "qualified"})
    whatsapp_client = MagicMock()
    pricing_service = MagicMock()
    availability_service = MagicMock()
    notify_owner = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        pricing_service=pricing_service,
        availability_service=availability_service,
        notify_owner=notify_owner,
    )
    use_case.execute(phone_number="+5511999999999")

    notify_owner.execute.assert_called_once_with(phone_number="+5511999999999")


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


def test_pricing_failure_does_not_stop_flow():
    """If pricing calculation raises, the AI response is still sent."""
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.PRICING,
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
    )
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Deixa eu verificar.", {})
    whatsapp_client = MagicMock()
    pricing_service = MagicMock()
    pricing_service.calculate.side_effect = ValueError("invalid dates")

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        pricing_service=pricing_service,
    )
    use_case.execute(phone_number="+5511999999999")

    # Despite pricing failure, WhatsApp message is still sent
    whatsapp_client.send_text.assert_called_once()
    saved = conv_repo.save.call_args[0][0]
    assert saved.price_estimate is None


def test_skips_pricing_when_no_checkin_or_checkout():
    """Pricing is skipped if dates are not set."""
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.PRICING,
        guests=4,
        # checkin and checkout intentionally omitted
    )
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Qual a data?", {})
    whatsapp_client = MagicMock()
    pricing_service = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        pricing_service=pricing_service,
    )
    use_case.execute(phone_number="+5511999999999")

    pricing_service.calculate.assert_not_called()


def test_does_not_notify_owner_when_already_notified():
    """Owner is not re-notified if owner_notified is already True."""
    from app.domain.models.conversation import LeadStatus
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.PRICING,
        owner_notified=True,
        lead_status=LeadStatus.QUALIFIED,
    )
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Tudo certo!", {})
    whatsapp_client = MagicMock()
    notify_owner = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        notify_owner=notify_owner,
    )
    use_case.execute(phone_number="+5511999999999")

    notify_owner.execute.assert_not_called()


def test_availability_included_in_prompt_when_dates_known():
    """When checkin/checkout are set, availability check result is passed to prompt builder."""
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.AVAILABILITY,
        checkin="2026-04-10",
        checkout="2026-04-12",
    )
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Datas disponíveis!", {})
    whatsapp_client = MagicMock()
    availability_service = MagicMock()
    availability_service.check.return_value = True

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        availability_service=availability_service,
    )
    use_case.execute(phone_number="+5511999999999")

    availability_service.check.assert_called_once_with(
        checkin="2026-04-10", checkout="2026-04-12"
    )
    call_kwargs = prompt_builder.build_system_prompt.call_args[1]
    assert call_kwargs.get("extra_context") == {"dates_available": True}


def test_availability_not_checked_when_dates_missing():
    """When dates are not set, availability service is not called."""
    conv = Conversation(phone_number="+5511999999999")
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Olá!", {})
    whatsapp_client = MagicMock()
    availability_service = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        availability_service=availability_service,
    )
    use_case.execute(phone_number="+5511999999999")

    availability_service.check.assert_not_called()
    call_kwargs = prompt_builder.build_system_prompt.call_args[1]
    assert call_kwargs.get("extra_context") is None


def test_invalid_stage_from_llm_is_ignored():
    """An invalid stage value from the LLM should not crash and original stage is kept."""
    conv = Conversation(phone_number="+5511999999999", stage=ConversationStage.GREETING)
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Ok!", {"stage": "not_a_valid_stage"})
    whatsapp_client = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
    )
    use_case.execute(phone_number="+5511999999999")

    saved = conv_repo.save.call_args[0][0]
    assert saved.stage == ConversationStage.GREETING  # unchanged


def test_invalid_lead_status_from_llm_is_ignored():
    """An invalid lead_status from the LLM should not crash and original is kept."""
    from app.domain.models.conversation import LeadStatus
    conv = Conversation(phone_number="+5511999999999", lead_status=LeadStatus.NEW)
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Ok!", {"lead_status": "not_a_valid_status"})
    whatsapp_client = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
    )
    use_case.execute(phone_number="+5511999999999")

    saved = conv_repo.save.call_args[0][0]
    assert saved.lead_status == LeadStatus.NEW  # unchanged


def test_skips_pricing_when_price_already_set():
    """Pricing calculation is skipped if price_estimate is already populated."""
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.PRICING,
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
        price_estimate=1600.0,  # already set
    )
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("O valor é R$ 1600.", {})
    whatsapp_client = MagicMock()
    pricing_service = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        pricing_service=pricing_service,
    )
    use_case.execute(phone_number="+5511999999999")

    pricing_service.calculate.assert_not_called()
