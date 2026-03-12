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
backend/
│
├── app/
│
│ ├── domain/
│ │ ├── models/
│ │ │ ├── conversation.py
│ │ │ ├── message.py
│ │ │ ├── lead.py
│ │ │ └── reservation.py
│ │ │
│ │ └── repositories/
│ │ ├── conversation_repository.py
│ │ ├── message_repository.py
│ │ ├── lead_repository.py
│ │ └── calendar_repository.py
│
│ ├── use_cases/
│ │ ├── process_incoming_message.py
│ │ ├── generate_ai_response.py
│ │ └── notify_owner.py
│
│ ├── services/
│ │ ├── conversation_service.py
│ │ ├── pricing_service.py
│ │ └── availability_service.py
│
│ ├── integrations/
│ │ ├── whatsapp/
│ │ │ ├── whatsapp_client.py
│ │ │ └── message_parser.py
│ │ │
│ │ ├── llm/
│ │ │ ├── openai_client.py
│ │ │ └── prompt_builder.py
│ │ │
│ │ └── speech/
│ │ └── whisper_client.py
│
│ ├── handlers/
│ │ └── webhook_handler.py
│
│ ├── config/
│ │ ├── settings.py
│ │ └── constants.py
│
│ └── utils/
│ ├── logger.py
│ └── time_utils.py
│
├── lambdas/
│ └── webhook/
│ └── handler.py
│
├── tests/
├── requirements.txt
└── cdk/
```

---

## Layer Responsibilities

### Domain

Contains business entities and repository interfaces.

Examples:

- Conversation
- Message
- Lead
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

Create Lead\
↓\
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
