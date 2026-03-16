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
        whatsapp_client=None,
        whisper_client=None,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._whatsapp_client = whatsapp_client
        self._whisper_client = whisper_client

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

        content = parsed.content
        if (
            parsed.message_type == MessageType.AUDIO
            and parsed.media_id
            and self._whatsapp_client
            and self._whisper_client
        ):
            content = self._transcribe_audio(parsed.media_id)

        message = Message(
            phone_number=parsed.phone_number,
            timestamp=datetime.fromtimestamp(int(parsed.timestamp), tz=timezone.utc),
            role=MessageRole.USER,
            message=content,
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

    def _transcribe_audio(self, media_id: str) -> str:
        logger.info("audio_transcription_started", media_id=media_id)
        media_url = self._whatsapp_client.get_media_url(media_id)
        audio_data = self._whatsapp_client.download_media(media_url)
        transcript = self._whisper_client.transcribe(audio_data=audio_data)
        logger.info("audio_transcription_completed", media_id=media_id)
        return transcript
