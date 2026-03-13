## Project Overview

This project implements an AI-powered WhatsApp assistant for managing
vacation rental inquiries.

The assistant:

- Receives messages via WhatsApp Cloud API
- Uses an LLM to answer questions
- Sends property information and media
- Checks availability
- Calculates price estimates
- Qualifies potential guests
- Notifies the owner when a lead is ready
- Hands off the conversation to a human

The AI does NOT complete bookings automatically. It collects information
and escalates to the owner when necessary.

Infrastructure includes:

- AWS Lambda
- API Gateway
- DynamoDB
- S3
- CloudFront (frontend)

---

## Architecture Principles

This project follows a lightweight Clean Architecture.

Goals: - Keep business logic independent of infrastructure - Keep Lambda
handlers thin - Keep integrations isolated - Keep use cases focused and
testable

Architecture flow:

Handlers\
↓\
Use Cases\
↓\
Services\
↓\
Repositories (interfaces)\
↓\
Integrations / Repository Implementations

Rules: - Use cases must not depend on AWS or external APIs - Domain
models must not depend on infrastructure - Integrations must only
implement external communication - Handlers must only translate events
to use cases

---

## Project Structure

```
whatsapp-chatbot/
│
├── backend/
│   │
│   ├── app/
│   │   ├── domain/
│   │   │   ├── models/
│   │   │   │   ├── conversation.py
│   │   │   │   ├── message.py
│   │   │   │   └── reservation.py
│   │   │   │
│   │   │   └── repositories/
│   │   │       ├── conversation_repository.py
│   │   │       ├── message_repository.py
│   │   │       └── calendar_repository.py
│   │   │
│   │   ├── use_cases/
│   │   │   ├── process_incoming_message.py
│   │   │   ├── generate_ai_response.py
│   │   │   └── notify_owner.py
│   │   │
│   │   ├── services/
│   │   │   ├── conversation_service.py
│   │   │   ├── pricing_service.py
│   │   │   └── availability_service.py
│   │   │
│   │   ├── integrations/
│   │   │   ├── whatsapp/
│   │   │   │   ├── whatsapp_client.py
│   │   │   │   └── message_parser.py
│   │   │   │
│   │   │   ├── llm/
│   │   │   │   ├── openai_client.py
│   │   │   │   └── prompt_builder.py
│   │   │   │
│   │   │   └── speech/
│   │   │       └── whisper_client.py
│   │   │
│   │   ├── handlers/
│   │   │   └── webhook_handler.py
│   │   │
│   │   ├── config/
│   │   │   ├── settings.py
│   │   │   └── constants.py
│   │   │
│   │   └── utils/
│   │       ├── logger.py
│   │       └── time_utils.py
│   │
│   ├── lambdas/
│   │   └── webhook/
│   │       └── handler.py
│   │
│   ├── tests/
│   │
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│
├── infrastructure/
│   │
│   ├── app.py                 # CDK entrypoint
│   │
│   └── cdk/
│       ├── stacks/
│       │   ├── backend_stack.py
│       │   └── frontend_stack.py
│       │
│       └── constructs/
│           └── api_lambda.py
│
├── cdk.json                    # moved to repo root
│
├── AGENTS.md
├── README.md
└── .gitignore
```

---

## Data Model

The backend uses **Amazon DynamoDB** for persistence.\
The data model is designed around **conversation-driven workflows**.

The system stores three primary entities:

- Conversations
- Messages
- Reservations

The **Conversations table is the source of truth for chatbot context and
lead qualification state.**

Messages store the chat history.

Reservations store confirmed bookings.

---

## Conversations Table

The `Conversations` table stores the **structured state of a chat with a
guest**.

This acts as the **memory of the assistant** and allows the chatbot to
continue conversations without sending the entire message history to the
LLM.

### Primary Key

PK: phone_number

Example:

+551199999999

### Example Item

```json
{
  "phone_number": "+551199999999",
  "stage": "qualification",
  "checkin": "2026-04-10",
  "checkout": "2026-04-12",
  "guests": 6,
  "purpose": "birthday",
  "customer_profile": "family",
  "rules_accepted": true,
  "price_estimate": 1800,
  "lead_status": "qualified",
  "owner_notified": false,
  "created_at": "2026-03-12T21:00:00Z",
  "updated_at": "2026-03-12T21:05:00Z"
}
```

### Conversation Fields

Field Description

---

phone_number Unique conversation identifier
stage Current step in conversation flow
checkin Desired check-in date
checkout Desired check-out date
guests Number of guests
purpose Purpose of the stay
customer_profile Optional classification of guest
rules_accepted Whether guest accepted house rules
price_estimate Calculated price estimate
lead_status Status of lead
owner_notified Whether owner was alerted
created_at Conversation creation timestamp
updated_at Last update timestamp

### Conversation Stages

greeting\
availability\
qualification\
pricing\
owner_takeover

Stages control the chatbot behavior.

---

## Messages Table

The `Messages` table stores **chat history**.

This allows:

- debugging conversations
- retrieving recent messages for prompts
- auditing chatbot behavior

### Primary Key

PK: phone_number\
SK: timestamp

### Example Item

```json
{
  "phone_number": "+551199999999",
  "timestamp": "2026-03-12T21:00:00Z",
  "role": "user",
  "message": "Is the cottage available April 10?"
}
```

Example assistant message:

```json
{
  "phone_number": "+551199999999",
  "timestamp": "2026-03-12T21:00:02Z",
  "role": "assistant",
  "message": "Yes, those dates are available."
}
```

### Fields

Field Description

---

phone_number Conversation identifier
timestamp Message timestamp
role `user` or `assistant`
message Text content

Messages should **never be used as the primary conversation context**.\
The structured context must always be read from the **Conversations
table**.

---

## Reservations Table

The `Reservations` table stores **confirmed bookings**.

Reservations are created only after the **owner confirms the booking
manually**.

### Primary Key

PK: reservation_id

### Example Item

```json
{
  "reservation_id": "res_123",
  "phone_number": "+551199999999",
  "guest_name": "Maria Silva",
  "checkin": "2026-04-10",
  "checkout": "2026-04-12",
  "guests": 6,
  "price": 1800,
  "status": "confirmed",
  "created_at": "2026-03-12T21:10:00Z"
}
```

## Fields

Field Description

---

reservation_id Unique reservation identifier
phone_number Phone number of guest
guest_name Guest name
checkin Check-in date
checkout Check-out date
guests Number of guests
price Final confirmed price
status Reservation status
created_at Creation timestamp

---

## Layer Responsibilities

### Domain

Contains business entities and repository interfaces.

Examples:

- Conversation
- Message
- Reservation

Domain models may contain business logic related to the entity.

Domain must NOT import:

- AWS SDK
- HTTP clients
- LLM SDKs

---

### Repositories

Repository interfaces define data access contracts.

Example:

```
class ConversationRepository:

    def load(self, phone: str):
        pass

    def save(self, conversation):
        pass
```

Repositories must not implement infrastructure logic.

---

### Use Cases

Use cases implement application workflows.

Examples:

- ProcessIncomingMessage
- GenerateAIResponse
- NotifyOwner

Use cases orchestrate:

- repositories
- services
- integrations

Use cases must remain framework-independent.

---

### Services

Services implement reusable domain logic.

Examples:

- pricing calculations
- availability logic
- conversation state logic

Services should not depend on infrastructure.

---

### Integrations

Integrations communicate with external systems.

Examples:

- WhatsApp API
- OpenAI API
- Whisper transcription
- external calendars

Integrations should:

- be small
- expose simple interfaces
- avoid business logic

---

### Handlers

Handlers translate external events into use case calls.

Example flow:
`Lambda event → webhook_handler → use_case`

Handlers must remain very thin.

---

## Lambda Entrypoints

Each Lambda lives in:

lambdas/

Example:

`lambdas/webhook/handler.py`

Example implementation:

```
from app.handlers.webhook_handler import WebhookHandler

def handler(event, context): return WebhookHandler().handle(event)
```

Lambda handlers must contain no business logic.

---

## LLM Design

Important rules:

- Do NOT send full conversation history
- Send only:
  - structured conversation state
  - last few messages

Prompt context includes:

- conversation stage
- known guest information
- missing information
- recent messages

Example state:

`{ "guests": 6, "checkin": "2026-04-10", "checkout": "2026-04-12", "purpose": "birthday" }`

LLM should never calculate business values like pricing.

Backend services should handle those.

---

## Conversation Flow

Incoming WhatsApp Message\
↓\
Webhook Handler\
↓\
ProcessIncomingMessage Use Case\
↓\
Load Conversation\
↓\
Extract Entities\
↓\
Generate AI Response\
↓\
Send Message via WhatsApp\
↓\
Update Conversation State

If booking intent is detected:

Notify Owner\
↓\
Conversation stage = owner_takeover

At this point the AI stops replying.

---

## Python Tooling

Recommended stack:

- Python 3.12
- uv (package manager)
- pydantic
- httpx
- openai
- boto3
- aws-lambda-powertools
- pendulum
- orjson

Development tools:

- pytest
- ruff
- mypy

---

## Dependency Management

Use uv.

Example:

uv init\
uv add openai\
uv add pydantic\
uv add httpx

Dependencies live in:

pyproject.toml

---

## Logging

Use structured logging.

Example:

`logger.info( "message_received", phone=phone, stage=stage )`

Avoid printing raw logs.

---

## Testing

Tests live in:

tests/

Structure mirrors application modules.

Example:

tests/use_cases/\
tests/services/\
tests/integrations/

Use pytest.

---

## Coding Guidelines

- prefer small functions
- avoid deep inheritance
- prefer composition
- keep classes focused
- keep handlers thin
- isolate infrastructure

Naming:

- classes: PascalCase
- functions: snake_case
- modules: snake_case

---

## Adding New Features

Steps:

1.  Update domain models if needed
2.  Add repository interface if storage is required
3.  Implement use case
4.  Add service if reusable logic appears
5.  Add integration if external API is needed
6.  Connect via handler

Never add business logic directly in handlers or integrations.

---

## AI Agent Guidance

When modifying the repository:

- respect the architecture
- avoid unnecessary frameworks
- prefer explicit code
- keep Lambda handlers minimal
- maintain low operational cost

Where logic belongs:

Business workflow → use_cases\
Reusable logic → services\
External API calls → integrations\
Data access → repositories

---

## Summary

This repository implements a clean backend architecture for an AI
WhatsApp assistant.

Key principles:

- separation of concerns
- minimal serverless runtime
- cost-efficient LLM usage
- maintainable Python code

Agents modifying this repository should prioritize clarity, simplicity,
and low operational cost.
