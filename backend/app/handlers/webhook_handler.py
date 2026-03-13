import json
import os

import boto3
from aws_lambda_powertools import Logger

logger = Logger(service="chacara-chatbot")

ssm_client = boto3.client("ssm")
_verify_token: str | None = None


def _get_verify_token() -> str:
    global _verify_token
    if _verify_token is None:
        param_name = os.environ.get("WHATSAPP_VERIFY_TOKEN_PARAM", "")
        response = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
        _verify_token = response["Parameter"]["Value"]
    return _verify_token


class WebhookHandler:
    def handle(self, event: dict, context) -> dict:
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
        body = json.loads(event.get("body", "{}"))
        logger.info("webhook_received", extra={"body": body})
        return {"statusCode": 200, "body": json.dumps({"status": "received"})}
