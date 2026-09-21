import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_vendor'))

from app.handlers.webhook_handler import WebhookHandler

_handler = WebhookHandler()


def handler(event, context):
    return _handler.handle(event, context)
