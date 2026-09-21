import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_vendor'))

from app.handlers.admin_handler import AdminHandler
from app.integrations.dynamodb.calendar_repo import get_calendar_repo
from app.integrations.dynamodb.conversation_repo import get_conversation_repo
from app.integrations.dynamodb.message_repo import get_message_repo
from app.integrations.dynamodb.reservation_repo import get_reservation_repo
from app.integrations.whatsapp.whatsapp_client import get_whatsapp_client

_handler = AdminHandler(
    conversation_repo=get_conversation_repo(),
    message_repo=get_message_repo(),
    reservation_repo=get_reservation_repo(),
    whatsapp_client=get_whatsapp_client(),
    calendar_repo=get_calendar_repo(),
)


def handler(event, context):
    return _handler.handle(event)
