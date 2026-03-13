import json
import logging

from aws_lambda_powertools.utilities.typing import LambdaContext

logger = logging.getLogger(__name__)


class WebhookHandler:
    def handle(self, event: dict, context: LambdaContext) -> dict:
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

        verify_token = self._get_verify_token()

        if mode == "subscribe" and token == verify_token:
            logger.info("webhook_verified")
            return {"statusCode": 200, "body": challenge}

        logger.warning("webhook_verification_failed", extra={"mode": mode})
        return {"statusCode": 403, "body": "Forbidden"}

    def _handle_incoming(self, event: dict) -> dict:
        body = json.loads(event.get("body", "{}"))
        logger.info("webhook_received", extra={"body": body})
        return {"statusCode": 200, "body": json.dumps({"status": "received"})}

    def _get_verify_token(self) -> str:
        import os

        return os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
