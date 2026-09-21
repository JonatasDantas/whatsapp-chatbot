from aws_lambda_powertools import Logger

from app.domain.models.conversation import LeadStatus
from app.domain.repositories.conversation_repository import ConversationRepository
from app.integrations.whatsapp.whatsapp_client import WhatsAppClient

logger = Logger()


class NotifyOwner:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        whatsapp_client: WhatsAppClient,
        owner_phone: str,
    ):
        self._conversation_repo = conversation_repo
        self._whatsapp_client = whatsapp_client
        self._owner_phone = owner_phone

    def execute(self, phone_number: str) -> None:
        conversation = self._conversation_repo.load(phone_number)
        if conversation is None:
            logger.warning("notify_owner_no_conversation", phone=phone_number)
            return

        if conversation.lead_status != LeadStatus.QUALIFIED:
            logger.info("owner_notify_skipped_not_qualified", phone=phone_number, lead_status=conversation.lead_status)
            return

        if conversation.owner_notified:
            logger.info("owner_already_notified", phone=phone_number)
            return

        lines = [
            "📲 Novo lead qualificado!",
            f"Telefone: {phone_number}",
        ]
        if conversation.name:
            lines.append(f"Nome: {conversation.name}")
        if conversation.checkin:
            lines.append(f"Check-in: {conversation.checkin}")
        if conversation.checkout:
            lines.append(f"Check-out: {conversation.checkout}")
        if conversation.guests:
            lines.append(f"Hóspedes: {conversation.guests}")
        if conversation.purpose:
            lines.append(f"Motivo: {conversation.purpose}")
        if conversation.price_estimate:
            lines.append(f"Estimativa: R$ {conversation.price_estimate:.2f}")

        message = "\n".join(lines)
        self._whatsapp_client.send_text(to=self._owner_phone, text=message)
        logger.info("owner_notified", phone=phone_number)

        conversation.owner_notified = True
        conversation.touch()
        self._conversation_repo.save(conversation)
