# Frontend Dashboard Design

**Date:** 2026-03-18
**Status:** Approved (autonomous)

## Overview

Owner-facing web dashboard for the Chacara WhatsApp chatbot. Provides visibility into
active guest conversations, message history, ability to assume control of a conversation,
and a calendar view of upcoming reservations.

---

## Architecture

### Frontend

- **Framework**: Next.js 14 (TypeScript) with App Router
- **Deployment**: Static export (`next export`) → S3 → CloudFront
- **Auth**: Amazon Cognito (email/password). CloudFront configured with Cognito hosted UI
  via Lambda@Edge for token verification.
- **Data fetching**: SWR for polling-based real-time updates (5s interval)
- **Styling**: Tailwind CSS

### Backend API (new)

A new Lambda + API Gateway sits alongside the existing webhook API.
All endpoints require a valid Cognito JWT in the `Authorization` header.

**Endpoints:**

```
GET  /api/conversations          → list all conversations (sorted by updated_at desc)
GET  /api/conversations/{phone}  → single conversation detail
GET  /api/conversations/{phone}/messages → all messages for a conversation
POST /api/conversations/{phone}/takeover → owner takes control
GET  /api/reservations           → list all reservations (sorted by checkin asc)
```

### Takeover Flow

`POST /api/conversations/{phone}/takeover`:
1. Sets `conversation.stage = "owner_takeover"`
2. Sets `conversation.owner_notified = true`
3. Sends WhatsApp message: "Olá! O proprietário da chácara entrará em contato em breve."
4. Returns updated conversation

The AI webhook handler already stops responding when `stage == owner_takeover`.

---

## Pages / Views

### Dashboard (`/`)

- Summary cards: total active conversations, qualified leads, conversations pending takeover
- Table of all conversations with: phone, guest name, stage, lead_status, checkin/checkout,
  updated_at, action button

### Chat View (`/conversations/[phone]`)

- Left panel: conversation metadata (stage, guests, dates, purpose, price estimate)
- Right panel: scrollable chat timeline (user/assistant bubbles)
- "Assume Conversation" button → confirms, calls takeover endpoint, disables AI badge

### Calendar (`/calendar`)

- Monthly calendar grid
- Reservations shown as date range events (checkin→checkout)
- Click reservation → modal with guest details

---

## Infrastructure (CDK)

New `FrontendStack`:

- `S3Bucket` — private, static Next.js build
- `CloudFrontDistribution` — OAC for S3, HTTPS, SPA routing (404→200)
- `CognitoUserPool` — single owner user
- `CognitoUserPoolClient` — for the web app
- `ApiGateway` + Lambda — new `admin-api` Lambda for frontend data

New CDK constructs:
- `AdminApiConstruct` — Lambda + API Gateway + Cognito Authorizer
- `FrontendHostingConstruct` — S3 + CloudFront

---

## Data Flow

```
Browser → CloudFront → S3 (static assets)
Browser → API Gateway → Cognito Authorizer → Admin Lambda → DynamoDB
Browser → Cognito Hosted UI (login)
```

---

## Testing Strategy

- **Unit tests**: React components with Vitest + React Testing Library
- **API tests**: pytest for admin Lambda handlers (mocked DynamoDB)
- **E2E**: Playwright for critical paths (login → dashboard → chat → takeover)

---

## Files to Create / Modify

### New files

```
frontend/
  src/
    app/
      layout.tsx
      page.tsx                        ← Dashboard
      conversations/[phone]/page.tsx  ← Chat view
      calendar/page.tsx               ← Calendar
    components/
      ConversationsTable.tsx
      ChatView.tsx
      CalendarView.tsx
      TakeoverButton.tsx
    lib/
      api.ts                          ← API client
      auth.ts                         ← Cognito helpers
  package.json
  next.config.ts
  tailwind.config.ts
  tsconfig.json

backend/
  app/
    handlers/
      admin_handler.py               ← new admin API handler
  lambdas/
    admin/
      handler.py                     ← Lambda entrypoint

infrastructure/
  cdk/
    stacks/
      frontend_stack.py              ← new CDK stack
    constructs/
      admin_api.py
      frontend_hosting.py
```

### Modified files

```
infrastructure/app.py                ← add FrontendStack
```
