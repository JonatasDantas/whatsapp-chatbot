# Webhook Handler Logic — Design Spec

## Goal

Implement the initial webhook handler logic for processing incoming WhatsApp messages. Parse and validate payloads, manage conversations, and persist messages.

## Components

### WhatsApp Payload Schema (`integrations/whatsapp/message_parser.py`)

Pydantic models that validate the WhatsApp Cloud API webhook payload structure:

```
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "<BUSINESS_ID>",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": { "display_phone_number": "...", "phone_number_id": "..." },
        "contacts": [{ "profile": { "name": "Guest Name" }, "wa_id": "551199999999" }],
        "messages": [{
          "from": "551199999999",
          "id": "wamid.xxx",
          "timestamp": "1234567890",
          "type": "text",
          "text": { "body": "message content" }
        }],
        "statuses": [...]
      },
      "field": "messages"
    }]
  }]
}
```

Both `contacts` and `messages` are optional lists under `value` — status-only payloads omit `messages`, and some payloads omit `contacts`. Pydantic models use `Optional[list[...]]` for both.

Models: `WhatsAppWebhook`, `Entry`, `Change`, `Value`, `Contact`, `ContactProfile`, `WhatsAppMessage`, `TextContent`, `AudioContent`.

`ParsedMessage` is a Pydantic model defined in `message_parser.py` (it's parser output, not a domain model). Fields: phone_number, contact_name, message_type (text/audio/unsupported), content (text body, or `"[unsupported: <type>]"` for unsupported types), media_id (for audio), whatsapp_message_id (the `wamid` for future deduplication).

**Phone number normalization:** WhatsApp sends numbers without `+` prefix (e.g., `551199999999`). The parser normalizes to `+<number>` format to match the Conversations table key format defined in CLAUDE.md.

**Timestamp conversion:** WhatsApp sends Unix epoch as a string. The parser converts to ISO-8601 `datetime` for the domain models. Messages use ISO-8601 with millisecond precision as the DynamoDB sort key (e.g., `2026-03-12T21:00:00.123Z`) to avoid collisions when multiple messages arrive in the same payload.

### Domain Model Changes

**Conversation** — Add `name: Optional[str] = None` field for the WhatsApp contact display name.

**Message** — Add `message_type: MessageType` field with enum values: `text`, `audio`, `unsupported`. Add optional `media_id: Optional[str]` for audio messages (future Whisper integration).

### DynamoDB Repository Implementations

New directory: `integrations/dynamodb/` (addition to project structure).

**`integrations/dynamodb/conversation_repo.py`** — Implements `ConversationRepository`. Uses boto3 `get_item` / `put_item` against the Conversations table. Serializes/deserializes Conversation model to/from DynamoDB items.

**`integrations/dynamodb/message_repo.py`** — Implements `MessageRepository`. Uses `put_item` for save, `query` with ScanIndexForward=False + Limit for get_recent.

Table names are read from environment variables (`CONVERSATIONS_TABLE`, `MESSAGES_TABLE`) already defined in the CDK stack. Boto3 DynamoDB resource is created at module level (outside the class) for Lambda cold start performance, consistent with the existing `ssm_client` pattern.

### Use Case: ProcessIncomingMessage (`use_cases/process_incoming_message.py`)

Constructor receives `ConversationRepository` and `MessageRepository` via dependency injection.

The use case receives `list[ParsedMessage]` — parsing happens in the handler, not the use case. This keeps the use case independent of WhatsApp payload structure.

No service layer is needed at this stage — the use case calls repositories directly. Services will be introduced when reusable business logic emerges (pricing, availability).

Flow:
1. For each parsed message:
   a. Load conversation by phone_number
   b. If not found, create new Conversation (phone_number, name, stage=greeting) — object construction only, no separate save
   c. Create Message record (phone_number, timestamp, role=user, content, message_type, media_id)
   d. Save message
   e. Update conversation `updated_at` via `conversation.touch()`
   f. Save conversation (covers both new and existing conversations in a single put_item)
2. Return list of parsed messages (for future use by response generation)

### Webhook Handler Changes (`handlers/webhook_handler.py`)

The `_handle_incoming` method:
1. Parses the raw API Gateway event body (json.loads)
2. Calls MessageParser to parse WhatsApp payload into `list[ParsedMessage]`
3. If no messages (status-only payload), logs and returns 200
4. Instantiates repositories and use case
5. Calls use case with parsed messages
6. Wraps everything in try/except — always returns 200 to WhatsApp
7. Logs errors with full context

### Error Handling Pattern

- Webhook handler always returns 200 to avoid WhatsApp retries
- Errors are caught at the handler level, logged with full context (phone, payload summary, traceback)
- Individual message processing errors don't block other messages in the same payload
- Repository errors (DynamoDB failures) are logged and re-raised to the handler catch

### Logging Strategy

Structured JSON logs via aws-lambda-powertools Logger at each stage:

| Event | Fields |
|-------|--------|
| `webhook_received` | message_count, has_statuses |
| `status_update_ignored` | phone_number, status |
| `message_parsed` | phone_number, name, message_type |
| `conversation_created` | phone_number, name, stage |
| `conversation_loaded` | phone_number, stage |
| `message_saved` | phone_number, message_type, role |
| `webhook_error` | phone_number, error, traceback |

### Lambda Entrypoint (`lambdas/webhook/handler.py`)

Remains thin — unchanged.

## Data Flow

```
POST /webhook (API Gateway)
  → Lambda handler (thin)
    → WebhookHandler._handle_incoming()
      → MessageParser.parse(raw_body)  # handler-level, not use case
        → Returns list[ParsedMessage] or empty (for status-only payloads)
      → ProcessIncomingMessage.execute(parsed_messages)
        → For each ParsedMessage:
          → ConversationRepository.load(phone_number)
          → If None: create new Conversation
          → MessageRepository.save(message)
          → ConversationRepository.save(conversation)
      → Return 200
```

## Out of Scope

- AI response generation (future step)
- Audio transcription via Whisper (ground prepared with media_id, not integrated)
- Image/video/document processing (message_type=unsupported, LLM will handle reply)
- Outbound messaging via WhatsApp API
- Message deduplication via wamid (field stored for future use)
