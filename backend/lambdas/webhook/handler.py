from app.handlers.webhook_handler import WebhookHandler

_handler = WebhookHandler()


def handler(event, context):
    return _handler.handle(event, context)
