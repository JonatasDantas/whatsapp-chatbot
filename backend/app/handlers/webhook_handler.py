import json
import os
import traceback

import boto3
from app.integrations.dynamodb.conversation_repo import DynamoDBConversationRepository
from app.integrations.dynamodb.message_repo import DynamoDBMessageRepository
from app.integrations.whatsapp.message_parser import MessageParser
from app.use_cases.process_incoming_message import ProcessIncomingMessage
from aws_lambda_powertools import Logger

logger = Logger(service="chacara-chatbot")

_verify_token: str | None = None
_dynamodb = None
_conversations_table = None
_messages_table = None


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def _get_verify_token() -> str:
    global _verify_token
    if _verify_token is None:
        param_name = os.environ.get("WHATSAPP_VERIFY_TOKEN_PARAM", "")
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
        _verify_token = response["Parameter"]["Value"]
    return _verify_token


def _get_conversations_table():
    global _conversations_table
    if _conversations_table is None:
        table_name = os.environ.get("CONVERSATIONS_TABLE", "Conversations")
        _conversations_table = _get_dynamodb().Table(table_name)
    return _conversations_table


def _get_messages_table():
    global _messages_table
    if _messages_table is None:
        table_name = os.environ.get("MESSAGES_TABLE", "Messages")
        _messages_table = _get_dynamodb().Table(table_name)
    return _messages_table


class WebhookHandler:
    def handle(self, event: dict, _context) -> dict:
        http_method = event.get("httpMethod", "")

        if http_method == "GET":
            return self._handle_verification(event)

        if http_method == "POST":
            return self._handle_incoming(event)

        return {"statusCode": 405, "body": "Method Not Allowed"}

    def _handle_verification(self, event: dict) -> dict:
        params = event.get("queryStringParameters") or {}
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        logger.info("webhook_verification_request", extra={
            "mode": mode,
            "has_token": bool(token),
            "has_challenge": bool(challenge),
        })

        verify_token = _get_verify_token()

        if mode == "subscribe" and token == verify_token:
            logger.info("webhook_verified")
            return {"statusCode": 200, "body": challenge}

        logger.warning("webhook_verification_failed", extra={"mode": mode})
        return {"statusCode": 403, "body": "Forbidden"}

    def _handle_incoming(self, event: dict) -> dict:
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            logger.error("webhook_invalid_json")
            return {"statusCode": 200, "body": json.dumps({"status": "invalid_json"})}

        parsed_messages = MessageParser.parse(body)

        logger.info("webhook_received", extra={
            "message_count": len(parsed_messages),
            "has_statuses": bool(
                body.get("entry", [{}])[0]
                .get("changes", [{}])[0]
                .get("value", {})
                .get("statuses")
            ) if body.get("entry") else False,
        })

        if not parsed_messages:
            logger.info("status_update_ignored")
            return {"statusCode": 200, "body": json.dumps({"status": "no_messages"})}

        try:
            conv_repo = DynamoDBConversationRepository(_get_conversations_table())
            msg_repo = DynamoDBMessageRepository(_get_messages_table())
            use_case = ProcessIncomingMessage(conv_repo, msg_repo)
            use_case.execute(parsed_messages)
        except Exception:
            logger.error("webhook_error", extra={
                "error": traceback.format_exc(),
                "phone_numbers": [m.phone_number for m in parsed_messages],
            })

        return {"statusCode": 200, "body": json.dumps({"status": "received"})}
