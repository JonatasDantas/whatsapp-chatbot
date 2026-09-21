from unittest.mock import MagicMock
from app.domain.models.conversation import Conversation, ConversationStage, LeadStatus
from app.use_cases.notify_owner import NotifyOwner


def _make_qualified_conv():
    return Conversation(
        phone_number="+5511999999999",
        name="Maria",
        stage=ConversationStage.PRICING,
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=6,
        purpose="birthday",
        lead_status=LeadStatus.QUALIFIED,
    )


def test_sends_whatsapp_to_owner():
    conv = _make_qualified_conv()
    conv_repo = MagicMock()
    conv_repo.load.return_value = conv
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    whatsapp.send_text.assert_called_once()
    call_args = whatsapp.send_text.call_args
    assert call_args[1]["to"] == "+5511888888888"
    assert "+5511999999999" in call_args[1]["text"]


def test_marks_owner_notified():
    conv = _make_qualified_conv()
    conv_repo = MagicMock()
    conv_repo.load.return_value = conv
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    conv_repo.save.assert_called_once()
    saved = conv_repo.save.call_args[0][0]
    assert saved.owner_notified is True


def test_skips_if_already_notified():
    conv = _make_qualified_conv()
    conv.owner_notified = True
    conv_repo = MagicMock()
    conv_repo.load.return_value = conv
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    whatsapp.send_text.assert_not_called()
    conv_repo.save.assert_not_called()


def test_skips_if_conversation_not_found():
    conv_repo = MagicMock()
    conv_repo.load.return_value = None
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    whatsapp.send_text.assert_not_called()


def test_skips_if_lead_not_qualified():
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.GREETING,
        lead_status=LeadStatus.NEW,
    )
    conv_repo = MagicMock()
    conv_repo.load.return_value = conv
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    whatsapp.send_text.assert_not_called()
    conv_repo.save.assert_not_called()
