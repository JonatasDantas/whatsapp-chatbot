import json
import os

import boto3
from aws_lambda_powertools import Logger

from app.config.settings import _get_settings
from app.integrations.dynamodb.calendar_repo import get_calendar_repo
from app.integrations.dynamodb.conversation_repo import get_conversation_repo
from app.integrations.dynamodb.message_repo import get_message_repo
from app.integrations.llm.openai_client import get_openai_client
from app.integrations.llm.prompt_builder import PromptBuilder
from app.integrations.speech.whisper_client import get_whisper_client
from app.integrations.whatsapp.message_parser import MessageParser
from app.integrations.whatsapp.whatsapp_client import get_whatsapp_client
from app.services.availability_service import AvailabilityService
from app.services.pricing_service import PricingService
from app.use_cases.generate_ai_response import GenerateAIResponse
from app.use_cases.notify_owner import NotifyOwner
from app.use_cases.process_incoming_message import ProcessIncomingMessage

_NIGHTLY_RATE = float(os.environ.get("NIGHTLY_RATE", "800.0"))

_availability_service = None
_pricing_service = None


def _get_availability_service() -> AvailabilityService:
    global _availability_service
    if _availability_service is None:
        _availability_service = AvailabilityService(calendar_repo=get_calendar_repo())
    return _availability_service


def _get_pricing_service() -> PricingService:
    global _pricing_service
    if _pricing_service is None:
        _pricing_service = PricingService(nightly_rate=_NIGHTLY_RATE)
    return _pricing_service

logger = Logger()

_ssm = None


def _get_ssm():
    global _ssm
    if _ssm is None:
        _ssm = boto3.client("ssm")
    return _ssm


def _get_verify_token() -> str:
    param = _get_ssm().get_parameter(
        Name="/chacara-chatbot/whatsapp/verify-token", WithDecryption=True
    )
    return param["Parameter"]["Value"]


class WebhookHandler:
    def handle(self, event: dict, context) -> dict:
        method = event.get("httpMethod", "POST")
        if method == "GET":
            return self._handle_verification(event)
        return self._handle_incoming(event)

    def _handle_verification(self, event: dict) -> dict:
        logger.info("webhook_verification_attempt")
        params = event.get("queryStringParameters") or {}
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        if mode == "subscribe" and token == _get_verify_token():
            logger.info("webhook_verification_success")
            return {"statusCode": 200, "body": challenge}
        logger.warning("webhook_verification_failed", mode=mode)
        return {"statusCode": 403, "body": "Forbidden"}

    def _handle_incoming(self, event: dict) -> dict:
        logger.info("incoming_webhook_received")
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            logger.warning("invalid_json_body")
            return {"statusCode": 200, "body": "OK"}

        parsed_messages = MessageParser.parse(body)

        process_use_case = ProcessIncomingMessage(
            conversation_repo=get_conversation_repo(),
            message_repo=get_message_repo(),
            whatsapp_client=get_whatsapp_client(),
            whisper_client=get_whisper_client(),
        )
        process_use_case.execute(parsed_messages)

        settings = _get_settings()
        notify_owner_use_case = NotifyOwner(
            conversation_repo=get_conversation_repo(),
            whatsapp_client=get_whatsapp_client(),
            owner_phone=settings.owner_phone,
        )

        generate_use_case = GenerateAIResponse(
            conversation_repo=get_conversation_repo(),
            message_repo=get_message_repo(),
            openai_client=get_openai_client(),
            prompt_builder=PromptBuilder(),
            whatsapp_client=get_whatsapp_client(),
            pricing_service=_get_pricing_service(),
            availability_service=_get_availability_service(),
            notify_owner=notify_owner_use_case,
        )

        seen_phones = set()
        for parsed in parsed_messages:
            if parsed.phone_number not in seen_phones:
                seen_phones.add(parsed.phone_number)
                try:
                    generate_use_case.execute(phone_number=parsed.phone_number)
                except Exception:
                    logger.exception("error_generating_response", phone=parsed.phone_number)

        return {"statusCode": 200, "body": "OK"}
