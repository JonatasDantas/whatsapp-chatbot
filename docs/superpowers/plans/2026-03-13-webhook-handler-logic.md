# Webhook Handler Logic Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement webhook handler logic to parse WhatsApp payloads, manage conversations, and persist messages to DynamoDB.

**Architecture:** Clean architecture with handler → use case → repository flow. Parsing happens at the handler level, use case receives typed data. DynamoDB repositories implement domain interfaces.

**Tech Stack:** Python 3.12, Pydantic, boto3, aws-lambda-powertools, pytest

**Spec:** `docs/superpowers/specs/2026-03-13-webhook-handler-logic-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/domain/models/conversation.py` | Add `name` field, `touch()` method |
| Modify | `backend/app/domain/models/message.py` | Add `message_type`, `media_id` fields |
| Create | `backend/app/integrations/whatsapp/message_parser.py` | WhatsApp payload Pydantic models + parser |
| Create | `backend/app/integrations/dynamodb/conversation_repo.py` | DynamoDB ConversationRepository impl |
| Create | `backend/app/integrations/dynamodb/message_repo.py` | DynamoDB MessageRepository impl |
| Create | `backend/app/use_cases/process_incoming_message.py` | Orchestrate message processing |
| Modify | `backend/app/handlers/webhook_handler.py` | Wire parsing → use case, error handling |
| Create | `backend/tests/integrations/whatsapp/test_message_parser.py` | Parser tests |
| Create | `backend/tests/use_cases/test_process_incoming_message.py` | Use case tests |
| Create | `backend/tests/integrations/dynamodb/test_conversation_repo.py` | Conversation repo tests |
| Create | `backend/tests/integrations/dynamodb/test_message_repo.py` | Message repo tests |
| Create | `backend/tests/handlers/test_webhook_handler.py` | Handler tests |

---

## Chunk 1: Domain Models + WhatsApp Parser

### Task 1: Update Domain Models

**Files:**
- Modify: `backend/app/domain/models/conversation.py`
- Modify: `backend/app/domain/models/message.py`
- Create: `backend/tests/domain/test_models.py`

- [ ] **Step 1: Write tests for Conversation model changes**

Create `backend/tests/domain/test_models.py`:

```python
from datetime import datetime, timezone

from app.domain.models.conversation import Conversation, ConversationStage


def test_conversation_has_name_field():
    conv = Conversation(phone_number="+5511999999999", name="Maria")
    assert conv.name == "Maria"


def test_conversation_name_defaults_to_none():
    conv = Conversation(phone_number="+5511999999999")
    assert conv.name is None


def test_conversation_touch_updates_timestamp():
    conv = Conversation(phone_number="+5511999999999")
    original = conv.updated_at
    conv.touch()
    assert conv.updated_at >= original
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/domain/test_models.py -v`
Expected: FAIL — `name` field and `touch()` not defined

- [ ] **Step 3: Update Conversation model**

In `backend/app/domain/models/conversation.py`, add `from datetime import datetime, timezone` import, `name` field after `stage`, and `touch()` method:

```python
from datetime import datetime, timezone

# ... (existing imports)

class Conversation(BaseModel):
    phone_number: str
    name: Optional[str] = None
    stage: ConversationStage = ConversationStage.GREETING
    checkin: Optional[str] = None
    checkout: Optional[str] = None
    guests: Optional[int] = None
    purpose: Optional[str] = None
    customer_profile: Optional[str] = None
    rules_accepted: bool = False
    price_estimate: Optional[float] = None
    lead_status: LeadStatus = LeadStatus.NEW
    owner_notified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
```

- [ ] **Step 4: Write tests for Message model changes**

Add to `backend/tests/domain/test_models.py`:

```python
from app.domain.models.message import Message, MessageRole, MessageType


def test_message_with_text_type():
    msg = Message(
        phone_number="+5511999999999",
        role=MessageRole.USER,
        message="Hello",
        message_type=MessageType.TEXT,
    )
    assert msg.message_type == MessageType.TEXT
    assert msg.media_id is None


def test_message_with_audio_type_and_media_id():
    msg = Message(
        phone_number="+5511999999999",
        role=MessageRole.USER,
        message="",
        message_type=MessageType.AUDIO,
        media_id="media_123",
    )
    assert msg.message_type == MessageType.AUDIO
    assert msg.media_id == "media_123"
```

- [ ] **Step 5: Update Message model**

In `backend/app/domain/models/message.py`, add `timezone` import, `MessageType` enum, `message_type` field, and `media_id` field:

```python
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageType(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    UNSUPPORTED = "unsupported"


class Message(BaseModel):
    phone_number: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    role: MessageRole
    message: str
    message_type: MessageType = MessageType.TEXT
    media_id: Optional[str] = None
```

- [ ] **Step 6: Run all model tests**

Run: `uv run pytest backend/tests/domain/test_models.py -v`
Expected: All PASS

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check backend/app/domain/models/ backend/tests/domain/
git add backend/app/domain/models/conversation.py backend/app/domain/models/message.py backend/tests/domain/test_models.py
git commit -m "feat: add name/touch to Conversation, message_type/media_id to Message"
```

---

### Task 2: WhatsApp Message Parser

**Files:**
- Create: `backend/app/integrations/whatsapp/message_parser.py`
- Create: `backend/tests/integrations/whatsapp/test_message_parser.py`

- [ ] **Step 1: Write parser tests**

Create `backend/tests/integrations/whatsapp/test_message_parser.py`:

```python
from app.integrations.whatsapp.message_parser import MessageParser, ParsedMessage


def _make_webhook_payload(
    messages=None, contacts=None, statuses=None
) -> dict:
    """Build a minimal valid WhatsApp webhook payload."""
    value = {"messaging_product": "whatsapp", "metadata": {
        "display_phone_number": "15550000000",
        "phone_number_id": "123456",
    }}
    if contacts is not None:
        value["contacts"] = contacts
    if messages is not None:
        value["messages"] = messages
    if statuses is not None:
        value["statuses"] = statuses
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "BIZ_ID", "changes": [{"value": value, "field": "messages"}]}],
    }


def test_parse_text_message():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "Maria"}, "wa_id": "5511999999999"}],
        messages=[{
            "from": "5511999999999",
            "id": "wamid.abc123",
            "timestamp": "1710280800",
            "type": "text",
            "text": {"body": "Hello"},
        }],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 1
    msg = result[0]
    assert msg.phone_number == "+5511999999999"
    assert msg.contact_name == "Maria"
    assert msg.message_type == "text"
    assert msg.content == "Hello"
    assert msg.media_id is None
    assert msg.whatsapp_message_id == "wamid.abc123"


def test_parse_audio_message():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "João"}, "wa_id": "5511888888888"}],
        messages=[{
            "from": "5511888888888",
            "id": "wamid.audio1",
            "timestamp": "1710280800",
            "type": "audio",
            "audio": {"id": "media_xyz", "mime_type": "audio/ogg"},
        }],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 1
    msg = result[0]
    assert msg.message_type == "audio"
    assert msg.media_id == "media_xyz"
    assert msg.content == ""


def test_parse_unsupported_message_type():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "Ana"}, "wa_id": "5511777777777"}],
        messages=[{
            "from": "5511777777777",
            "id": "wamid.img1",
            "timestamp": "1710280800",
            "type": "image",
            "image": {"id": "media_img"},
        }],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 1
    msg = result[0]
    assert msg.message_type == "unsupported"
    assert msg.content == "[unsupported: image]"


def test_parse_status_only_payload():
    payload = _make_webhook_payload(
        statuses=[{"id": "wamid.s1", "status": "delivered", "recipient_id": "5511999999999"}],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 0


def test_parse_phone_number_normalization():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "Test"}, "wa_id": "5511999999999"}],
        messages=[{
            "from": "5511999999999",
            "id": "wamid.norm1",
            "timestamp": "1710280800",
            "type": "text",
            "text": {"body": "Hi"},
        }],
    )
    result = MessageParser.parse(payload)
    assert result[0].phone_number == "+5511999999999"


def test_parse_multiple_messages():
    payload = _make_webhook_payload(
        contacts=[{"profile": {"name": "Maria"}, "wa_id": "5511999999999"}],
        messages=[
            {"from": "5511999999999", "id": "wamid.m1", "timestamp": "1710280800", "type": "text", "text": {"body": "Hi"}},
            {"from": "5511999999999", "id": "wamid.m2", "timestamp": "1710280801", "type": "text", "text": {"body": "Hello"}},
        ],
    )
    result = MessageParser.parse(payload)
    assert len(result) == 2


def test_parse_invalid_payload_returns_empty():
    result = MessageParser.parse({"object": "something_else"})
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/integrations/whatsapp/test_message_parser.py -v`
Expected: FAIL — `MessageParser` not defined

- [ ] **Step 3: Implement the parser**

Create `backend/app/integrations/whatsapp/message_parser.py`:

```python
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field as PydanticField


class ParsedMessage(BaseModel):
    phone_number: str
    contact_name: str
    message_type: str  # text, audio, unsupported
    content: str
    media_id: Optional[str] = None
    whatsapp_message_id: str
    timestamp: str


class ContactProfile(BaseModel):
    name: str


class Contact(BaseModel):
    profile: ContactProfile
    wa_id: str


class TextContent(BaseModel):
    body: str


class AudioContent(BaseModel):
    id: str
    mime_type: Optional[str] = None


class WhatsAppMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = PydanticField(alias="from")
    id: str
    timestamp: str
    type: str
    text: Optional[TextContent] = None
    audio: Optional[AudioContent] = None


class Metadata(BaseModel):
    display_phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None


class Value(BaseModel):
    messaging_product: Optional[str] = None
    metadata: Optional[Metadata] = None
    contacts: Optional[list[Contact]] = None
    messages: Optional[list[WhatsAppMessage]] = None
    statuses: Optional[list[dict]] = None


class Change(BaseModel):
    value: Value
    field: str


class Entry(BaseModel):
    id: str
    changes: list[Change]


class WhatsAppWebhook(BaseModel):
    object: str
    entry: list[Entry]


SUPPORTED_TYPES = {"text", "audio"}


def _normalize_phone(phone: str) -> str:
    if not phone.startswith("+"):
        return f"+{phone}"
    return phone


class MessageParser:
    @staticmethod
    def parse(payload: dict) -> list[ParsedMessage]:
        try:
            webhook = WhatsAppWebhook.model_validate(payload)
        except Exception:
            return []

        if webhook.object != "whatsapp_business_account":
            return []

        parsed: list[ParsedMessage] = []

        for entry in webhook.entry:
            for change in entry.changes:
                value = change.value

                if not value.messages:
                    continue

                contacts_map: dict[str, str] = {}
                if value.contacts:
                    for contact in value.contacts:
                        contacts_map[contact.wa_id] = contact.profile.name

                for msg in value.messages:
                    phone = _normalize_phone(msg.from_)
                    contact_name = contacts_map.get(msg.from_, "Unknown")

                    if msg.type == "text" and msg.text:
                        content = msg.text.body
                        media_id = None
                        message_type = "text"
                    elif msg.type == "audio" and msg.audio:
                        content = ""
                        media_id = msg.audio.id
                        message_type = "audio"
                    else:
                        content = f"[unsupported: {msg.type}]"
                        media_id = None
                        message_type = "unsupported"

                    parsed.append(ParsedMessage(
                        phone_number=phone,
                        contact_name=contact_name,
                        message_type=message_type,
                        content=content,
                        media_id=media_id,
                        whatsapp_message_id=msg.id,
                        timestamp=msg.timestamp,
                    ))

        return parsed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/integrations/whatsapp/test_message_parser.py -v`
Expected: All PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check backend/app/integrations/whatsapp/ backend/tests/integrations/whatsapp/
git add backend/app/integrations/whatsapp/message_parser.py backend/tests/integrations/whatsapp/test_message_parser.py
git commit -m "feat: add WhatsApp message parser with payload validation"
```

---

## Chunk 2: DynamoDB Repositories

### Task 3: DynamoDB Conversation Repository

**Files:**
- Create: `backend/app/integrations/dynamodb/conversation_repo.py`
- Create: `backend/tests/integrations/dynamodb/test_conversation_repo.py`

Note: These tests use moto to mock DynamoDB. We need to add it as a dev dependency first.

- [ ] **Step 1: Add moto dev dependency and commit**

```bash
uv add --dev "moto[dynamodb]>=5.0.0"
git add pyproject.toml uv.lock
git commit -m "chore: add moto for DynamoDB testing"
```

- [ ] **Step 2: Write repository tests**

Create `backend/tests/integrations/dynamodb/test_conversation_repo.py`:

```python
import os

import boto3
import pytest
from moto import mock_aws

from app.domain.models.conversation import Conversation, ConversationStage
from app.integrations.dynamodb.conversation_repo import DynamoDBConversationRepository


@pytest.fixture
def dynamodb_table():
    with mock_aws():
        os.environ["CONVERSATIONS_TABLE"] = "test-conversations"
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="test-conversations",
            KeySchema=[{"AttributeName": "phone_number", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "phone_number", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield boto3.resource("dynamodb", region_name="us-east-1").Table("test-conversations")


def test_save_and_load_conversation(dynamodb_table):
    repo = DynamoDBConversationRepository(dynamodb_table)
    conv = Conversation(phone_number="+5511999999999", name="Maria")
    repo.save(conv)

    loaded = repo.load("+5511999999999")
    assert loaded is not None
    assert loaded.phone_number == "+5511999999999"
    assert loaded.name == "Maria"
    assert loaded.stage == ConversationStage.GREETING


def test_load_nonexistent_returns_none(dynamodb_table):
    repo = DynamoDBConversationRepository(dynamodb_table)
    result = repo.load("+5511000000000")
    assert result is None


def test_save_updates_existing_conversation(dynamodb_table):
    repo = DynamoDBConversationRepository(dynamodb_table)
    conv = Conversation(phone_number="+5511999999999", name="Maria")
    repo.save(conv)

    conv.stage = ConversationStage.AVAILABILITY
    conv.touch()
    repo.save(conv)

    loaded = repo.load("+5511999999999")
    assert loaded.stage == ConversationStage.AVAILABILITY
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest backend/tests/integrations/dynamodb/test_conversation_repo.py -v`
Expected: FAIL — `DynamoDBConversationRepository` not found

- [ ] **Step 4: Implement conversation repository**

Create `backend/app/integrations/dynamodb/conversation_repo.py`:

```python
from typing import Optional

from app.domain.models.conversation import Conversation
from app.domain.repositories.conversation_repository import ConversationRepository


class DynamoDBConversationRepository(ConversationRepository):
    def __init__(self, table) -> None:
        self._table = table

    def load(self, phone_number: str) -> Optional[Conversation]:
        response = self._table.get_item(Key={"phone_number": phone_number})
        item = response.get("Item")
        if not item:
            return None
        return Conversation.model_validate(item)

    def save(self, conversation: Conversation) -> None:
        item = conversation.model_dump(mode="json")
        self._table.put_item(Item=item)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest backend/tests/integrations/dynamodb/test_conversation_repo.py -v`
Expected: All PASS

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check backend/app/integrations/dynamodb/ backend/tests/integrations/dynamodb/
git add backend/app/integrations/dynamodb/conversation_repo.py backend/tests/integrations/dynamodb/test_conversation_repo.py
git commit -m "feat: add DynamoDB conversation repository"
```

---

### Task 4: DynamoDB Message Repository

**Files:**
- Create: `backend/app/integrations/dynamodb/message_repo.py`
- Create: `backend/tests/integrations/dynamodb/test_message_repo.py`

- [ ] **Step 1: Write repository tests**

Create `backend/tests/integrations/dynamodb/test_message_repo.py`:

```python
import os

import boto3
import pytest
from moto import mock_aws

from app.domain.models.message import Message, MessageRole, MessageType
from app.integrations.dynamodb.message_repo import DynamoDBMessageRepository


@pytest.fixture
def dynamodb_table():
    with mock_aws():
        os.environ["MESSAGES_TABLE"] = "test-messages"
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="test-messages",
            KeySchema=[
                {"AttributeName": "phone_number", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "phone_number", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield boto3.resource("dynamodb", region_name="us-east-1").Table("test-messages")


def test_save_and_get_recent_messages(dynamodb_table):
    repo = DynamoDBMessageRepository(dynamodb_table)

    msg = Message(
        phone_number="+5511999999999",
        role=MessageRole.USER,
        message="Hello",
        message_type=MessageType.TEXT,
    )
    repo.save(msg)

    recent = repo.get_recent("+5511999999999", limit=10)
    assert len(recent) == 1
    assert recent[0].message == "Hello"
    assert recent[0].role == MessageRole.USER


def test_get_recent_returns_newest_first(dynamodb_table):
    repo = DynamoDBMessageRepository(dynamodb_table)

    from datetime import datetime, timezone

    for i in range(3):
        msg = Message(
            phone_number="+5511999999999",
            timestamp=datetime(2026, 3, 12, 21, 0, i, tzinfo=timezone.utc),
            role=MessageRole.USER,
            message=f"Message {i}",
            message_type=MessageType.TEXT,
        )
        repo.save(msg)

    recent = repo.get_recent("+5511999999999", limit=2)
    assert len(recent) == 2
    assert recent[0].message == "Message 2"
    assert recent[1].message == "Message 1"


def test_get_recent_empty(dynamodb_table):
    repo = DynamoDBMessageRepository(dynamodb_table)
    recent = repo.get_recent("+5511000000000")
    assert recent == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/integrations/dynamodb/test_message_repo.py -v`
Expected: FAIL — `DynamoDBMessageRepository` not found

- [ ] **Step 3: Implement message repository**

Create `backend/app/integrations/dynamodb/message_repo.py`:

```python
from boto3.dynamodb.conditions import Key

from app.domain.models.message import Message
from app.domain.repositories.message_repository import MessageRepository


class DynamoDBMessageRepository(MessageRepository):
    def __init__(self, table) -> None:
        self._table = table

    def save(self, message: Message) -> None:
        item = message.model_dump(mode="json")
        self._table.put_item(Item=item)

    def get_recent(self, phone_number: str, limit: int = 10) -> list[Message]:
        response = self._table.query(
            KeyConditionExpression=Key("phone_number").eq(phone_number),
            ScanIndexForward=False,
            Limit=limit,
        )
        items = response.get("Items", [])
        return [Message.model_validate(item) for item in items]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/integrations/dynamodb/test_message_repo.py -v`
Expected: All PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check backend/app/integrations/dynamodb/ backend/tests/integrations/dynamodb/
git add backend/app/integrations/dynamodb/message_repo.py backend/tests/integrations/dynamodb/test_message_repo.py
git commit -m "feat: add DynamoDB message repository"
```

---

## Chunk 3: Use Case + Handler Wiring

### Task 5: ProcessIncomingMessage Use Case

**Files:**
- Create: `backend/app/use_cases/process_incoming_message.py`
- Create: `backend/tests/use_cases/test_process_incoming_message.py`

- [ ] **Step 1: Write use case tests**

Create `backend/tests/use_cases/test_process_incoming_message.py`:

```python
from typing import Optional
from datetime import datetime, timezone

from app.domain.models.conversation import Conversation, ConversationStage
from app.domain.models.message import Message, MessageType
from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.integrations.whatsapp.message_parser import ParsedMessage
from app.use_cases.process_incoming_message import ProcessIncomingMessage


class FakeConversationRepo(ConversationRepository):
    def __init__(self):
        self.conversations: dict[str, Conversation] = {}

    def load(self, phone_number: str) -> Optional[Conversation]:
        return self.conversations.get(phone_number)

    def save(self, conversation: Conversation) -> None:
        self.conversations[conversation.phone_number] = conversation


class FakeMessageRepo(MessageRepository):
    def __init__(self):
        self.messages: list[Message] = []

    def save(self, message: Message) -> None:
        self.messages.append(message)

    def get_recent(self, phone_number: str, limit: int = 10) -> list[Message]:
        return [m for m in self.messages if m.phone_number == phone_number][:limit]


def _make_parsed_message(**overrides) -> ParsedMessage:
    defaults = {
        "phone_number": "+5511999999999",
        "contact_name": "Maria",
        "message_type": "text",
        "content": "Hello",
        "media_id": None,
        "whatsapp_message_id": "wamid.abc",
        "timestamp": "1710280800",
    }
    defaults.update(overrides)
    return ParsedMessage(**defaults)


def test_creates_new_conversation():
    conv_repo = FakeConversationRepo()
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    use_case.execute([_make_parsed_message()])

    conv = conv_repo.conversations["+5511999999999"]
    assert conv.name == "Maria"
    assert conv.stage == ConversationStage.GREETING


def test_reuses_existing_conversation():
    conv_repo = FakeConversationRepo()
    existing = Conversation(
        phone_number="+5511999999999",
        name="Maria",
        stage=ConversationStage.AVAILABILITY,
    )
    conv_repo.conversations["+5511999999999"] = existing
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    use_case.execute([_make_parsed_message()])

    conv = conv_repo.conversations["+5511999999999"]
    assert conv.stage == ConversationStage.AVAILABILITY


def test_saves_user_message():
    conv_repo = FakeConversationRepo()
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    use_case.execute([_make_parsed_message(content="Is it available?")])

    assert len(msg_repo.messages) == 1
    assert msg_repo.messages[0].message == "Is it available?"
    assert msg_repo.messages[0].message_type == MessageType.TEXT


def test_saves_audio_message_with_media_id():
    conv_repo = FakeConversationRepo()
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    use_case.execute([_make_parsed_message(
        message_type="audio",
        content="",
        media_id="media_123",
    )])

    assert msg_repo.messages[0].message_type == MessageType.AUDIO
    assert msg_repo.messages[0].media_id == "media_123"


def test_processes_multiple_messages():
    conv_repo = FakeConversationRepo()
    msg_repo = FakeMessageRepo()
    use_case = ProcessIncomingMessage(conv_repo, msg_repo)

    messages = [
        _make_parsed_message(content="Hi", whatsapp_message_id="wamid.1"),
        _make_parsed_message(content="Hello", whatsapp_message_id="wamid.2"),
    ]
    use_case.execute(messages)

    assert len(msg_repo.messages) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/use_cases/test_process_incoming_message.py -v`
Expected: FAIL — `ProcessIncomingMessage` not found

- [ ] **Step 3: Implement use case**

Create `backend/app/use_cases/process_incoming_message.py`:

```python
from datetime import datetime, timezone

from aws_lambda_powertools import Logger

from app.domain.models.conversation import Conversation
from app.domain.models.message import Message, MessageRole, MessageType
from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.integrations.whatsapp.message_parser import ParsedMessage

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
                "name": parsed.contact_name,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/use_cases/test_process_incoming_message.py -v`
Expected: All PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check backend/app/use_cases/ backend/tests/use_cases/
git add backend/app/use_cases/process_incoming_message.py backend/tests/use_cases/test_process_incoming_message.py
git commit -m "feat: add ProcessIncomingMessage use case"
```

---

### Task 6: Wire Handler to Use Case

**Files:**
- Modify: `backend/app/handlers/webhook_handler.py`
- Create: `backend/tests/handlers/test_webhook_handler.py`

- [ ] **Step 1: Write handler tests**

Create `backend/tests/handlers/test_webhook_handler.py`:

```python
import json
from unittest.mock import patch, MagicMock

from app.handlers.webhook_handler import WebhookHandler


def _make_post_event(body: dict) -> dict:
    return {
        "httpMethod": "POST",
        "body": json.dumps(body),
    }


def _make_text_webhook_payload() -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "BIZ_ID", "changes": [{"value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "15550000000", "phone_number_id": "123"},
            "contacts": [{"profile": {"name": "Maria"}, "wa_id": "5511999999999"}],
            "messages": [{
                "from": "5511999999999",
                "id": "wamid.test1",
                "timestamp": "1710280800",
                "type": "text",
                "text": {"body": "Hello"},
            }],
        }, "field": "messages"}]}],
    }


def test_post_returns_200():
    handler = WebhookHandler()
    event = _make_post_event(_make_text_webhook_payload())
    response = handler.handle(event, None)
    assert response["statusCode"] == 200


def test_post_status_only_returns_200():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "BIZ_ID", "changes": [{"value": {
            "messaging_product": "whatsapp",
            "metadata": {},
            "statuses": [{"id": "wamid.s1", "status": "delivered", "recipient_id": "123"}],
        }, "field": "messages"}]}],
    }
    handler = WebhookHandler()
    event = _make_post_event(payload)
    response = handler.handle(event, None)
    assert response["statusCode"] == 200


def test_post_invalid_payload_returns_200():
    handler = WebhookHandler()
    event = _make_post_event({"invalid": "payload"})
    response = handler.handle(event, None)
    assert response["statusCode"] == 200


def test_post_malformed_json_returns_200():
    handler = WebhookHandler()
    event = {"httpMethod": "POST", "body": "not json"}
    response = handler.handle(event, None)
    assert response["statusCode"] == 200
```

- [ ] **Step 2: Run tests to verify current behavior**

Run: `uv run pytest backend/tests/handlers/test_webhook_handler.py -v`
Expected: Some tests may pass (200 is already returned), but we need to verify handler wiring works

- [ ] **Step 3: Update webhook handler**

Replace `backend/app/handlers/webhook_handler.py` with:

```python
import json
import os
import traceback

import boto3
from aws_lambda_powertools import Logger

from app.integrations.whatsapp.message_parser import MessageParser
from app.integrations.dynamodb.conversation_repo import DynamoDBConversationRepository
from app.integrations.dynamodb.message_repo import DynamoDBMessageRepository
from app.use_cases.process_incoming_message import ProcessIncomingMessage

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
```

- [ ] **Step 4: Run handler tests**

Run: `uv run pytest backend/tests/handlers/test_webhook_handler.py -v`
Expected: All PASS

- [ ] **Step 5: Run all tests**

Run: `uv run pytest backend/tests/ -v`
Expected: All PASS

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check backend/
git add backend/app/handlers/webhook_handler.py backend/tests/handlers/test_webhook_handler.py
git commit -m "feat: wire webhook handler to use case with error handling and logging"
```

---

## Chunk 4: Final Verification

### Task 7: Full Test Suite + Deploy

- [ ] **Step 1: Run full test suite with coverage**

Run: `uv run pytest backend/tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 2: Lint entire backend**

Run: `uv run ruff check backend/`
Expected: No errors

- [ ] **Step 3: CDK synth**

Run: `uv run cdk synth > /dev/null && echo "OK"`
Expected: OK

- [ ] **Step 4: Deploy**

Run: `uv run cdk deploy --require-approval never`
Expected: Stack updates successfully

- [ ] **Step 5: Final commit if any remaining changes**

```bash
git status
# Only stage specific changed files if any remain
```
