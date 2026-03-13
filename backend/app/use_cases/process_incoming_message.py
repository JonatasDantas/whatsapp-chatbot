from datetime import datetime, timezone

from app.domain.models.conversation import Conversation
from app.domain.models.message import Message, MessageRole, MessageType
from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.integrations.whatsapp.message_parser import ParsedMessage
from aws_lambda_powertools import Logger

logger = Logger(service="chacara-chatbot")


class ProcessIncomingMessage:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo

    def execute(self, parsed_messages: list[ParsedMessage]) -> list[ParsedMessage]:
        for parsed in parsed_messages:
            try:
                self._process_single(parsed)
            except Exception:
                logger.exception("message_processing_error", extra={
                    "phone_number": parsed.phone_number,
                    "whatsapp_message_id": parsed.whatsapp_message_id,
                })
        return parsed_messages

    def _process_single(self, parsed: ParsedMessage) -> None:
        conversation = self._conversation_repo.load(parsed.phone_number)

        if conversation is None:
            conversation = Conversation(
                phone_number=parsed.phone_number,
                name=parsed.contact_name,
            )
            logger.info("conversation_created", extra={
                "phone_number": parsed.phone_number,
                "contact_name": parsed.contact_name,
                "stage": conversation.stage,
            })
        else:
            logger.info("conversation_loaded", extra={
                "phone_number": parsed.phone_number,
                "stage": conversation.stage,
            })

        message = Message(
            phone_number=parsed.phone_number,
            timestamp=datetime.fromtimestamp(int(parsed.timestamp), tz=timezone.utc),
            role=MessageRole.USER,
            message=parsed.content,
            message_type=MessageType(parsed.message_type),
            media_id=parsed.media_id,
        )
        self._message_repo.save(message)

        logger.info("message_saved", extra={
            "phone_number": parsed.phone_number,
            "message_type": parsed.message_type,
            "role": "user",
        })

        conversation.touch()
        self._conversation_repo.save(conversation)
