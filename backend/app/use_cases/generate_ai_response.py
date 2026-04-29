from datetime import datetime, timezone

from aws_lambda_powertools import Logger

from app.domain.models.conversation import Conversation, ConversationStage, LeadStatus
from app.domain.models.message import Message, MessageRole, MessageType
from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.integrations.llm.openai_client import OpenAIClient
from app.integrations.llm.prompt_builder import PromptBuilder
from app.integrations.whatsapp.whatsapp_client import WhatsAppClient
from app.services.availability_service import AvailabilityService
from app.services.pricing_service import PricingService
from app.use_cases.notify_owner import NotifyOwner

logger = Logger()

_ALLOWED_UPDATES = {"stage", "checkin", "checkout", "guests", "purpose", "name", "rules_accepted", "customer_profile", "lead_status"}


class GenerateAIResponse:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        openai_client: OpenAIClient,
        prompt_builder: PromptBuilder,
        whatsapp_client: WhatsAppClient,
        pricing_service: PricingService | None = None,
        availability_service: AvailabilityService | None = None,
        notify_owner: NotifyOwner | None = None,
    ):
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._openai_client = openai_client
        self._prompt_builder = prompt_builder
        self._whatsapp_client = whatsapp_client
        self._pricing_service = pricing_service
        self._availability_service = availability_service
        self._notify_owner = notify_owner

    def execute(self, phone_number: str) -> None:
        conversation = self._conversation_repo.load(phone_number)
        if conversation is None:
            conversation = Conversation(phone_number=phone_number)

        if conversation.stage == ConversationStage.OWNER_TAKEOVER:
            logger.info("owner_takeover_skip_ai", phone=phone_number)
            return

        self._enrich_conversation(conversation)

        recent_messages = self._message_repo.get_recent(phone_number, limit=10)
        extra_context = self._build_extra_context(conversation)
        system_prompt = self._prompt_builder.build_system_prompt(conversation, extra_context=extra_context)
        messages = self._prompt_builder.build_messages(recent_messages)

        logger.info("llm_request_started", phone=phone_number, stage=conversation.stage, recent_messages_count=len(recent_messages))
        response_text, updates = self._openai_client.chat(
            system=system_prompt,
            messages=messages,
        )
        logger.info("llm_response_received", phone=phone_number, updates=updates)

        self._apply_updates(conversation, updates)
        conversation.touch()
        self._conversation_repo.save(conversation)
        logger.info("conversation_state_updated", phone=phone_number, stage=conversation.stage)

        assistant_message = Message(
            phone_number=phone_number,
            timestamp=datetime.now(timezone.utc),
            role=MessageRole.ASSISTANT,
            message=response_text,
            message_type=MessageType.TEXT,
        )
        self._message_repo.save(assistant_message)
        # self._whatsapp_client.send_text(to=phone_number, text=response_text)
        logger.info("ai_response_sent", phone=phone_number)

        if (
            conversation.lead_status == LeadStatus.QUALIFIED
            and not conversation.owner_notified
            and self._notify_owner
        ):
            try:
                self._notify_owner.execute(phone_number=phone_number)
            except Exception:
                logger.exception("failed_to_notify_owner", phone=phone_number)

    def _build_extra_context(self, conversation: Conversation) -> dict | None:
        if (
            self._availability_service
            and conversation.checkin
            and conversation.checkout
        ):
            try:
                available = self._availability_service.check(
                    checkin=conversation.checkin,
                    checkout=conversation.checkout,
                )
                return {"dates_available": available}
            except Exception:
                logger.exception("availability_check_failed")
        return None

    def _enrich_conversation(self, conversation: Conversation) -> None:
        if (
            self._pricing_service
            and conversation.stage == ConversationStage.PRICING
            and conversation.checkin
            and conversation.checkout
            and conversation.guests
            and conversation.price_estimate is None
        ):
            try:
                price = self._pricing_service.calculate(
                    checkin=conversation.checkin,
                    checkout=conversation.checkout,
                    guests=conversation.guests,
                )
                conversation.price_estimate = price
                logger.info("price_calculated", price=price)
            except Exception:
                logger.exception("pricing_calculation_failed")

    def _apply_updates(self, conversation: Conversation, updates: dict) -> None:
        for key, value in updates.items():
            if key not in _ALLOWED_UPDATES:
                continue
            if key == "stage":
                try:
                    conversation.stage = ConversationStage(value)
                except ValueError:
                    logger.warning("invalid_stage_from_llm", stage=value)
            elif key == "lead_status":
                try:
                    conversation.lead_status = LeadStatus(value)
                except ValueError:
                    logger.warning("invalid_lead_status_from_llm", lead_status=value)
            else:
                setattr(conversation, key, value)
