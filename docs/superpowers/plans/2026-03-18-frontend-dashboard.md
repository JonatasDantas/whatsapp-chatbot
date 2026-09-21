# Frontend Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an owner-facing web dashboard (Next.js + TypeScript) for monitoring WhatsApp conversations, reading message history, taking over conversations, and viewing upcoming reservations on a calendar — deployed to AWS CloudFront.

**Architecture:** New Admin API Lambda handles all frontend data requests with Cognito JWT auth; Next.js app is statically exported to S3 and served via CloudFront; a new CDK FrontendStack provisions all frontend infrastructure alongside the existing BackendStack.

**Tech Stack:** Python 3.12, AWS CDK (Python), Next.js 14, TypeScript, Tailwind CSS, SWR, AWS Cognito, DynamoDB, S3, CloudFront, API Gateway, Lambda, pytest, Vitest, React Testing Library

---

## File Map

### Backend (new files)
- `backend/app/handlers/admin_handler.py` — HTTP router and handler methods for the admin REST API
- `backend/app/integrations/dynamodb/reservation_repo.py` — DynamoDB CRUD for Reservations table
- `backend/lambdas/admin/handler.py` — Lambda entrypoint for the admin API
- `backend/tests/handlers/test_admin_handler.py` — tests for admin handler

### Infrastructure (new files)
- `infrastructure/cdk/stacks/frontend_stack.py` — CDK stack: Cognito, Admin API, S3, CloudFront
- `infrastructure/cdk/constructs/admin_api.py` — CDK construct: Lambda + API Gateway + Cognito authorizer
- `infrastructure/cdk/constructs/frontend_hosting.py` — CDK construct: S3 bucket + CloudFront distribution

### Infrastructure (modified files)
- `infrastructure/app.py` — add `FrontendStack` instantiation

### Frontend (new files)
- `frontend/package.json` — Next.js 14, TypeScript, Tailwind, SWR, aws-amplify
- `frontend/tsconfig.json`
- `frontend/next.config.ts` — static export config
- `frontend/tailwind.config.ts`
- `frontend/src/app/layout.tsx` — root layout with auth provider
- `frontend/src/app/page.tsx` — dashboard page (conversation list + summary cards)
- `frontend/src/app/conversations/[phone]/page.tsx` — chat view page
- `frontend/src/app/calendar/page.tsx` — calendar page with reservations
- `frontend/src/components/ConversationsTable.tsx` — sortable table of conversations
- `frontend/src/components/ChatView.tsx` — message timeline component
- `frontend/src/components/CalendarView.tsx` — monthly calendar with reservation events
- `frontend/src/components/TakeoverButton.tsx` — confirm + POST takeover action
- `frontend/src/lib/api.ts` — typed API client (fetches via SWR)
- `frontend/src/lib/auth.ts` — Cognito auth helpers (sign in, get token, sign out)
- `frontend/src/lib/types.ts` — shared TypeScript types
- `frontend/src/middleware.ts` — redirect unauthenticated users to /login
- `frontend/src/app/login/page.tsx` — login form
- `frontend/tests/components/ConversationsTable.test.tsx`
- `frontend/tests/components/ChatView.test.tsx`
- `frontend/tests/components/TakeoverButton.test.tsx`
- `frontend/vitest.config.ts`

---

## Phase 1: Backend Admin API

### Task 1: Reservation DynamoDB repository

**Files:**
- Create: `backend/app/integrations/dynamodb/reservation_repo.py`
- Test: `backend/tests/integrations/dynamodb/test_reservation_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integrations/dynamodb/test_reservation_repo.py
from unittest.mock import MagicMock
from datetime import datetime

from app.domain.models.reservation import Reservation, ReservationStatus
from app.integrations.dynamodb.reservation_repo import DynamoDBReservationRepository


def _make_reservation(**kwargs) -> Reservation:
    defaults = dict(
        reservation_id="res_001",
        phone_number="+5511999999999",
        guest_name="Ana Lima",
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
        price=1200.0,
        status=ReservationStatus.CONFIRMED,
        created_at=datetime(2026, 3, 1),
    )
    defaults.update(kwargs)
    return Reservation(**defaults)


def test_save_and_load_reservation():
    table = MagicMock()
    repo = DynamoDBReservationRepository(table)
    res = _make_reservation()
    repo.save(res)
    table.put_item.assert_called_once()
    item = table.put_item.call_args[1]["Item"]
    assert item["reservation_id"] == "res_001"


def test_list_all_returns_sorted_by_checkin():
    table = MagicMock()
    table.scan.return_value = {
        "Items": [
            {"reservation_id": "res_002", "phone_number": "+5511999999998",
             "guest_name": "B", "checkin": "2026-05-01", "checkout": "2026-05-03",
             "guests": 2, "price": 800.0, "status": "confirmed",
             "created_at": "2026-03-01T00:00:00"},
            {"reservation_id": "res_001", "phone_number": "+5511999999999",
             "guest_name": "A", "checkin": "2026-04-10", "checkout": "2026-04-12",
             "guests": 4, "price": 1200.0, "status": "confirmed",
             "created_at": "2026-03-01T00:00:00"},
        ]
    }
    repo = DynamoDBReservationRepository(table)
    results = repo.list_all()
    assert len(results) == 2
    assert results[0].checkin == "2026-04-10"
    assert results[1].checkin == "2026-05-01"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot
uv run pytest backend/tests/integrations/dynamodb/test_reservation_repo.py -v
```
Expected: ImportError — `reservation_repo` does not exist yet.

- [ ] **Step 3: Implement `DynamoDBReservationRepository`**

```python
# backend/app/integrations/dynamodb/reservation_repo.py
import os
from typing import Any

import boto3

from app.domain.models.reservation import Reservation

_dynamodb = None
_table = None
_repo = None


def _get_table():
    global _dynamodb, _table
    if _table is None:
        if _dynamodb is None:
            _dynamodb = boto3.resource("dynamodb")
        _table = _dynamodb.Table(os.environ["RESERVATIONS_TABLE"])
    return _table


def get_reservation_repo() -> "DynamoDBReservationRepository":
    global _repo
    if _repo is None:
        _repo = DynamoDBReservationRepository(_get_table())
    return _repo


class DynamoDBReservationRepository:
    def __init__(self, table: Any) -> None:
        self._table = table

    def save(self, reservation: Reservation) -> None:
        item = reservation.model_dump(mode="json")
        self._table.put_item(Item=item)

    def get(self, reservation_id: str) -> Reservation | None:
        response = self._table.get_item(Key={"reservation_id": reservation_id})
        item = response.get("Item")
        if not item:
            return None
        return Reservation.model_validate(item)

    def list_all(self) -> list[Reservation]:
        response = self._table.scan()
        items = response.get("Items", [])
        reservations = [Reservation.model_validate(item) for item in items]
        return sorted(reservations, key=lambda r: r.checkin)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest backend/tests/integrations/dynamodb/test_reservation_repo.py -v
```
Expected: 2 PASSED

---

### Task 2: Admin handler — list and detail endpoints

**Files:**
- Create: `backend/app/handlers/admin_handler.py`
- Create: `backend/tests/handlers/test_admin_handler.py`

- [ ] **Step 1: Write the failing tests for list/detail**

```python
# backend/tests/handlers/test_admin_handler.py
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.domain.models.conversation import Conversation, ConversationStage, LeadStatus
from app.domain.models.message import Message, MessageRole, MessageType
from app.handlers.admin_handler import AdminHandler


def _make_conversation(**kwargs) -> Conversation:
    defaults = dict(
        phone_number="+5511999999999",
        stage=ConversationStage.QUALIFICATION,
        lead_status=LeadStatus.QUALIFIED,
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return Conversation(**defaults)


def _event(method: str, path: str, path_params: dict | None = None, body: dict | None = None) -> dict:
    return {
        "httpMethod": method,
        "resource": path,
        "pathParameters": path_params or {},
        "body": json.dumps(body) if body else None,
        "headers": {},
    }


def test_list_conversations_returns_200():
    conv_repo = MagicMock()
    msg_repo = MagicMock()
    res_repo = MagicMock()
    whatsapp = MagicMock()
    conv_repo.list_all.return_value = [_make_conversation()]

    handler = AdminHandler(conv_repo, msg_repo, res_repo, whatsapp)
    event = _event("GET", "/api/conversations")
    result = handler.handle(event)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["conversations"]) == 1
    assert body["conversations"][0]["phone_number"] == "+5511999999999"


def test_get_conversation_messages_returns_200():
    conv_repo = MagicMock()
    msg_repo = MagicMock()
    res_repo = MagicMock()
    whatsapp = MagicMock()
    conv_repo.load.return_value = _make_conversation()
    msg_repo.get_all.return_value = [
        Message(
            phone_number="+5511999999999",
            role=MessageRole.USER,
            message="Olá, tem disponibilidade?",
            message_type=MessageType.TEXT,
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    ]

    handler = AdminHandler(conv_repo, msg_repo, res_repo, whatsapp)
    event = _event("GET", "/api/conversations/{phone}/messages",
                   path_params={"phone": "%2B5511999999999"})
    result = handler.handle(event)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["messages"]) == 1


def test_list_reservations_returns_200():
    conv_repo = MagicMock()
    msg_repo = MagicMock()
    res_repo = MagicMock()
    whatsapp = MagicMock()
    res_repo.list_all.return_value = []

    handler = AdminHandler(conv_repo, msg_repo, res_repo, whatsapp)
    event = _event("GET", "/api/reservations")
    result = handler.handle(event)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["reservations"] == []


def test_unknown_route_returns_404():
    handler = AdminHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    event = _event("GET", "/api/unknown")
    result = handler.handle(event)
    assert result["statusCode"] == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/handlers/test_admin_handler.py -v
```
Expected: ImportError — `admin_handler` does not exist yet.

- [ ] **Step 3: Add `get_all` to message repository**

The existing `DynamoDBMessageRepository.get_recent()` only returns recent messages. We need `get_all()` for the admin chat view. Add to `backend/app/integrations/dynamodb/message_repo.py`:

```python
def get_all(self, phone_number: str) -> list[Message]:
    response = self._table.query(
        KeyConditionExpression=Key("phone_number").eq(phone_number),
        ScanIndexForward=True,
    )
    items = response.get("Items", [])
    return [Message.model_validate(item) for item in items]
```

Also add `list_all()` to `DynamoDBConversationRepository` in `backend/app/integrations/dynamodb/conversation_repo.py`:

```python
def list_all(self) -> list[Conversation]:
    response = self._table.scan()
    items = response.get("Items", [])
    conversations = [Conversation.model_validate(item) for item in items]
    return sorted(conversations, key=lambda c: c.updated_at, reverse=True)
```

- [ ] **Step 4: Implement `AdminHandler`**

```python
# backend/app/handlers/admin_handler.py
import json
from urllib.parse import unquote

from aws_lambda_powertools import Logger

from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.integrations.dynamodb.reservation_repo import DynamoDBReservationRepository
from app.integrations.whatsapp.whatsapp_client import WhatsAppClient

logger = Logger()

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Authorization,Content-Type",
}

TAKEOVER_MESSAGE = (
    "Olá! O proprietário da chácara entrará em contato com você em breve. "
    "Obrigado pela paciência!"
)


def _ok(body: dict) -> dict:
    return {"statusCode": 200, "headers": CORS_HEADERS, "body": json.dumps(body, default=str)}


def _not_found(msg: str = "Not found") -> dict:
    return {"statusCode": 404, "headers": CORS_HEADERS, "body": json.dumps({"error": msg})}


def _error(msg: str, code: int = 500) -> dict:
    return {"statusCode": code, "headers": CORS_HEADERS, "body": json.dumps({"error": msg})}


class AdminHandler:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        reservation_repo: DynamoDBReservationRepository,
        whatsapp_client: WhatsAppClient,
    ) -> None:
        self._conv_repo = conversation_repo
        self._msg_repo = message_repo
        self._res_repo = reservation_repo
        self._whatsapp = whatsapp_client

    def handle(self, event: dict) -> dict:
        method = event.get("httpMethod", "GET")
        resource = event.get("resource", "")
        params = event.get("pathParameters") or {}

        logger.info("admin_request", method=method, resource=resource)

        if method == "OPTIONS":
            return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

        if resource == "/api/conversations" and method == "GET":
            return self._list_conversations()

        if resource == "/api/conversations/{phone}" and method == "GET":
            phone = unquote(params.get("phone", ""))
            return self._get_conversation(phone)

        if resource == "/api/conversations/{phone}/messages" and method == "GET":
            phone = unquote(params.get("phone", ""))
            return self._get_messages(phone)

        if resource == "/api/conversations/{phone}/takeover" and method == "POST":
            phone = unquote(params.get("phone", ""))
            return self._takeover(phone)

        if resource == "/api/reservations" and method == "GET":
            return self._list_reservations()

        return _not_found()

    def _list_conversations(self) -> dict:
        conversations = self._conv_repo.list_all()
        return _ok({"conversations": [c.model_dump(mode="json") for c in conversations]})

    def _get_conversation(self, phone: str) -> dict:
        conv = self._conv_repo.load(phone)
        if not conv:
            return _not_found(f"Conversation not found: {phone}")
        return _ok({"conversation": conv.model_dump(mode="json")})

    def _get_messages(self, phone: str) -> dict:
        messages = self._msg_repo.get_all(phone)
        return _ok({"messages": [m.model_dump(mode="json") for m in messages]})

    def _takeover(self, phone: str) -> dict:
        from app.domain.models.conversation import ConversationStage
        conv = self._conv_repo.load(phone)
        if not conv:
            return _not_found(f"Conversation not found: {phone}")
        conv.stage = ConversationStage.OWNER_TAKEOVER
        conv.owner_notified = True
        conv.touch()
        self._conv_repo.save(conv)
        try:
            self._whatsapp.send_text(phone, TAKEOVER_MESSAGE)
        except Exception:
            logger.exception("failed_to_send_takeover_message", phone=phone)
        return _ok({"conversation": conv.model_dump(mode="json")})

    def _list_reservations(self) -> dict:
        reservations = self._res_repo.list_all()
        return _ok({"reservations": [r.model_dump(mode="json") for r in reservations]})
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest backend/tests/handlers/test_admin_handler.py -v
```
Expected: 4 PASSED

---

### Task 3: Takeover test

**Files:**
- Modify: `backend/tests/handlers/test_admin_handler.py`

- [ ] **Step 1: Add takeover test**

Append to `backend/tests/handlers/test_admin_handler.py`:

```python
def test_takeover_sets_stage_and_sends_message():
    conv_repo = MagicMock()
    msg_repo = MagicMock()
    res_repo = MagicMock()
    whatsapp = MagicMock()
    conv_repo.load.return_value = _make_conversation()

    handler = AdminHandler(conv_repo, msg_repo, res_repo, whatsapp)
    event = _event("POST", "/api/conversations/{phone}/takeover",
                   path_params={"phone": "%2B5511999999999"})
    result = handler.handle(event)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["conversation"]["stage"] == "owner_takeover"
    assert body["conversation"]["owner_notified"] is True
    whatsapp.send_text.assert_called_once_with(
        "+5511999999999",
        "Olá! O proprietário da chácara entrará em contato com você em breve. "
        "Obrigado pela paciência!",
    )
    conv_repo.save.assert_called_once()


def test_takeover_not_found_returns_404():
    conv_repo = MagicMock()
    conv_repo.load.return_value = None
    handler = AdminHandler(conv_repo, MagicMock(), MagicMock(), MagicMock())
    event = _event("POST", "/api/conversations/{phone}/takeover",
                   path_params={"phone": "unknown"})
    result = handler.handle(event)
    assert result["statusCode"] == 404
```

- [ ] **Step 2: Run all admin handler tests**

```bash
uv run pytest backend/tests/handlers/test_admin_handler.py -v
```
Expected: 6 PASSED

---

### Task 4: Admin Lambda entrypoint

**Files:**
- Create: `backend/lambdas/admin/__init__.py` (empty)
- Create: `backend/lambdas/admin/handler.py`

- [ ] **Step 1: Create Lambda entrypoint**

```python
# backend/lambdas/admin/handler.py
from app.handlers.admin_handler import AdminHandler
from app.integrations.dynamodb.conversation_repo import get_conversation_repo
from app.integrations.dynamodb.message_repo import get_message_repo
from app.integrations.dynamodb.reservation_repo import get_reservation_repo
from app.integrations.whatsapp.whatsapp_client import get_whatsapp_client

_handler = AdminHandler(
    conversation_repo=get_conversation_repo(),
    message_repo=get_message_repo(),
    reservation_repo=get_reservation_repo(),
    whatsapp_client=get_whatsapp_client(),
)


def handler(event, context):
    return _handler.handle(event)
```

Also create empty `backend/lambdas/admin/__init__.py`.

- [ ] **Step 2: Verify full backend test suite passes**

```bash
uv run pytest backend/tests/ -v
```
Expected: All tests PASSED (no regressions)

---

## Phase 2: CDK Infrastructure

### Task 5: CDK Admin API construct

**Files:**
- Create: `infrastructure/cdk/constructs/admin_api.py`

- [ ] **Step 1: Create the `AdminApiConstruct`**

```python
# infrastructure/cdk/constructs/admin_api.py
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class AdminApiConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        conversations_table: dynamodb.Table,
        messages_table: dynamodb.Table,
        reservations_table: dynamodb.Table,
        whatsapp_token_param: ssm.IStringParameter,
        whatsapp_phone_param: ssm.IStringParameter,
        user_pool: cognito.UserPool,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        powertools_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:aws:lambda:{scope.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:7",
        )

        function = _lambda.Function(
            self,
            "AdminFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas.admin.handler.handler",
            code=_lambda.Code.from_asset("backend"),
            layers=[powertools_layer],
            environment={
                "CONVERSATIONS_TABLE": conversations_table.table_name,
                "MESSAGES_TABLE": messages_table.table_name,
                "RESERVATIONS_TABLE": reservations_table.table_name,
                "WHATSAPP_ACCESS_TOKEN_PARAM": whatsapp_token_param.parameter_name,
                "WHATSAPP_PHONE_NUMBER_ID_PARAM": whatsapp_phone_param.parameter_name,
            },
        )

        conversations_table.grant_read_write_data(function)
        messages_table.grant_read_data(function)
        reservations_table.grant_read_data(function)

        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameters"],
                resources=[
                    whatsapp_token_param.parameter_arn,
                    whatsapp_phone_param.parameter_arn,
                ],
            )
        )
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt"],
                resources=[f"arn:aws:kms:{scope.region}:{scope.account}:alias/aws/ssm"],
            )
        )

        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "AdminAuthorizer",
            cognito_user_pools=[user_pool],
        )

        api = apigw.RestApi(
            self,
            "AdminApi",
            rest_api_name="ChacaraAdminApi",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Authorization", "Content-Type"],
            ),
        )

        api_root = api.root.add_resource("api")

        # /api/conversations
        conversations = api_root.add_resource("conversations")
        conversations.add_method(
            "GET",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        # /api/conversations/{phone}
        phone_resource = conversations.add_resource("{phone}")
        phone_resource.add_method(
            "GET",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        # /api/conversations/{phone}/messages
        messages_resource = phone_resource.add_resource("messages")
        messages_resource.add_method(
            "GET",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        # /api/conversations/{phone}/takeover
        takeover_resource = phone_resource.add_resource("takeover")
        takeover_resource.add_method(
            "POST",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        # /api/reservations
        reservations = api_root.add_resource("reservations")
        reservations.add_method(
            "GET",
            apigw.LambdaIntegration(function),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        self.api_url = api.url
```

---

### Task 6: CDK Frontend hosting construct

**Files:**
- Create: `infrastructure/cdk/constructs/frontend_hosting.py`

- [ ] **Step 1: Create `FrontendHostingConstruct`**

```python
# infrastructure/cdk/constructs/frontend_hosting.py
from aws_cdk import RemovalPolicy
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct


class FrontendHostingConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "FrontendBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        oac = cloudfront.S3OriginAccessControl(self, "FrontendOAC")

        distribution = cloudfront.Distribution(
            self,
            "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    bucket, origin_access_control=oac
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        s3deploy.BucketDeployment(
            self,
            "FrontendDeployment",
            sources=[s3deploy.Source.asset("frontend/out")],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        self.distribution_url = f"https://{distribution.distribution_domain_name}"
        self.bucket = bucket
        self.distribution = distribution
```

---

### Task 7: CDK FrontendStack

**Files:**
- Create: `infrastructure/cdk/stacks/frontend_stack.py`
- Modify: `infrastructure/app.py`

- [ ] **Step 1: Create `FrontendStack`**

```python
# infrastructure/cdk/stacks/frontend_stack.py
from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from cdk.constructs.admin_api import AdminApiConstruct
from cdk.constructs.frontend_hosting import FrontendHostingConstruct
from cdk.stacks.backend_stack import BackendStack


class FrontendStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        backend: BackendStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        user_pool = cognito.UserPool(
            self,
            "OwnerUserPool",
            user_pool_name="chacara-owner-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            removal_policy=RemovalPolicy.DESTROY,
        )

        user_pool_client = cognito.UserPoolClient(
            self,
            "OwnerAppClient",
            user_pool=user_pool,
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(implicit_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL],
            ),
        )

        whatsapp_token_param = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "WhatsappAccessTokenParam",
            parameter_name="/chacara-chatbot/whatsapp-access-token",
        )
        whatsapp_phone_param = ssm.StringParameter.from_string_parameter_name(
            self,
            "WhatsappPhoneParam",
            "/chacara-chatbot/whatsapp-phone-number-id",
        )

        admin_api = AdminApiConstruct(
            self,
            "AdminApi",
            conversations_table=backend.conversations_table,
            messages_table=backend.messages_table,
            reservations_table=backend.reservations_table,
            whatsapp_token_param=whatsapp_token_param,
            whatsapp_phone_param=whatsapp_phone_param,
            user_pool=user_pool,
        )

        hosting = FrontendHostingConstruct(self, "FrontendHosting")

        CfnOutput(self, "AdminApiUrl", value=admin_api.api_url)
        CfnOutput(self, "FrontendUrl", value=hosting.distribution_url)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
```

- [ ] **Step 2: Expose table properties in BackendStack**

In `infrastructure/cdk/stacks/backend_stack.py`, save the tables as instance attributes so FrontendStack can reference them. At the end of `__init__`, after creating the tables:

```python
# Add these lines at the end of BackendStack.__init__, after table creation:
self.conversations_table = conversations_table
self.messages_table = messages_table
self.reservations_table = reservations_table
```

- [ ] **Step 3: Update `infrastructure/app.py`**

```python
#!/usr/bin/env python3
import aws_cdk as cdk
from cdk.stacks.backend_stack import BackendStack
from cdk.stacks.frontend_stack import FrontendStack

app = cdk.App()
backend = BackendStack(app, "ChacaraChatbotStack")
FrontendStack(app, "ChacaraFrontendStack", backend=backend)
app.synth()
```

- [ ] **Step 4: Verify CDK synth runs without errors**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot
source .venv/bin/activate
cd infrastructure && cdk synth 2>&1 | tail -20
```
Expected: Synthesized output with both stacks, no errors.

---

## Phase 3: Next.js Frontend

### Task 8: Next.js project scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "chacara-dashboard",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "next": "14.2.3",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "swr": "^2.2.5",
    "aws-amplify": "^6.4.0",
    "@aws-amplify/ui-react": "^6.1.14"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "typescript": "^5",
    "tailwindcss": "^3.4.1",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.38",
    "vitest": "^1.5.0",
    "@vitejs/plugin-react": "^4.2.1",
    "@testing-library/react": "^15.0.0",
    "@testing-library/jest-dom": "^6.4.2",
    "@testing-library/user-event": "^14.5.2",
    "jsdom": "^24.0.0"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `frontend/next.config.ts`**

```typescript
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
}

export default nextConfig
```

- [ ] **Step 4: Create `frontend/tailwind.config.ts`**

```typescript
import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: { extend: {} },
  plugins: [],
}

export default config
```

- [ ] **Step 5: Create `frontend/postcss.config.js`**

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 6: Create `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
})
```

- [ ] **Step 7: Create `frontend/tests/setup.ts`**

```typescript
import '@testing-library/jest-dom'
```

- [ ] **Step 8: Install dependencies**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot/frontend
npm install
```

---

### Task 9: Types and API client

**Files:**
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create `frontend/src/lib/types.ts`**

```typescript
export type ConversationStage =
  | 'greeting'
  | 'availability'
  | 'qualification'
  | 'pricing'
  | 'owner_takeover'

export type LeadStatus = 'new' | 'qualified' | 'unqualified'

export interface Conversation {
  phone_number: string
  name: string | null
  stage: ConversationStage
  checkin: string | null
  checkout: string | null
  guests: number | null
  purpose: string | null
  customer_profile: string | null
  rules_accepted: boolean
  price_estimate: number | null
  lead_status: LeadStatus
  owner_notified: boolean
  created_at: string
  updated_at: string
}

export type MessageRole = 'user' | 'assistant'

export interface Message {
  phone_number: string
  timestamp: string
  role: MessageRole
  message: string
  message_type: string
}

export type ReservationStatus = 'confirmed' | 'cancelled'

export interface Reservation {
  reservation_id: string
  phone_number: string
  guest_name: string
  checkin: string
  checkout: string
  guests: number
  price: number
  status: ReservationStatus
  created_at: string
}
```

- [ ] **Step 2: Create `frontend/src/lib/api.ts`**

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? ''

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  // Get token from Amplify session
  const { fetchAuthSession } = await import('aws-amplify/auth')
  const session = await fetchAuthSession()
  const token = session.tokens?.idToken?.toString() ?? ''

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: token,
      ...(options?.headers ?? {}),
    },
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API error ${res.status}: ${err}`)
  }

  return res.json() as Promise<T>
}

export const fetcher = (url: string) => apiFetch(url)

export async function takeoverConversation(phone: string): Promise<void> {
  await apiFetch(`/api/conversations/${encodeURIComponent(phone)}/takeover`, {
    method: 'POST',
  })
}
```

---

### Task 10: Auth setup (Cognito + Amplify)

**Files:**
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/app/login/page.tsx`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/middleware.ts`
- Create: `frontend/src/app/globals.css`

- [ ] **Step 1: Create `frontend/src/lib/auth.ts`**

```typescript
import { Amplify } from 'aws-amplify'

export function configureAmplify() {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: process.env.NEXT_PUBLIC_USER_POOL_ID!,
        userPoolClientId: process.env.NEXT_PUBLIC_USER_POOL_CLIENT_ID!,
      },
    },
  })
}
```

- [ ] **Step 2: Create `frontend/src/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: Create `frontend/src/app/layout.tsx`**

```typescript
'use client'
import './globals.css'
import { configureAmplify } from '@/lib/auth'

configureAmplify()

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="bg-gray-50 text-gray-900 min-h-screen">
        {children}
      </body>
    </html>
  )
}
```

- [ ] **Step 4: Create `frontend/src/app/login/page.tsx`**

```typescript
'use client'
import { useState } from 'react'
import { signIn } from 'aws-amplify/auth'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await signIn({ username: email, password })
      router.push('/')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-8 w-full max-w-sm space-y-4">
        <h1 className="text-2xl font-bold text-center">Chácara Dashboard</h1>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <div>
          <label className="block text-sm font-medium mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Senha</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white py-2 rounded font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 5: Create `frontend/src/middleware.ts`**

```typescript
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Middleware runs on the edge; Amplify session is client-side.
// We protect routes client-side in components instead.
// This file exports a no-op matcher to satisfy Next.js.
export function middleware(_request: NextRequest) {
  return NextResponse.next()
}

export const config = {
  matcher: [],
}
```

---

### Task 11: Conversations Table component

**Files:**
- Create: `frontend/src/components/ConversationsTable.tsx`
- Create: `frontend/tests/components/ConversationsTable.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/components/ConversationsTable.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ConversationsTable from '@/components/ConversationsTable'
import type { Conversation } from '@/lib/types'

const mockConversations: Conversation[] = [
  {
    phone_number: '+5511999999999',
    name: 'Ana Lima',
    stage: 'qualification',
    checkin: '2026-04-10',
    checkout: '2026-04-12',
    guests: 4,
    purpose: 'anniversary',
    customer_profile: null,
    rules_accepted: true,
    price_estimate: 1200,
    lead_status: 'qualified',
    owner_notified: false,
    created_at: '2026-03-01T00:00:00Z',
    updated_at: '2026-03-02T00:00:00Z',
  },
]

describe('ConversationsTable', () => {
  it('renders conversation phone number', () => {
    render(<ConversationsTable conversations={mockConversations} />)
    expect(screen.getByText('+5511999999999')).toBeDefined()
  })

  it('renders stage badge', () => {
    render(<ConversationsTable conversations={mockConversations} />)
    expect(screen.getByText('qualification')).toBeDefined()
  })

  it('renders lead status', () => {
    render(<ConversationsTable conversations={mockConversations} />)
    expect(screen.getByText('qualified')).toBeDefined()
  })

  it('renders empty state when no conversations', () => {
    render(<ConversationsTable conversations={[]} />)
    expect(screen.getByText(/no conversations/i)).toBeDefined()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot/frontend
npm test -- --reporter verbose 2>&1 | tail -20
```
Expected: FAIL — ConversationsTable not found

- [ ] **Step 3: Implement `ConversationsTable`**

```typescript
// frontend/src/components/ConversationsTable.tsx
import Link from 'next/link'
import type { Conversation } from '@/lib/types'

const STAGE_COLORS: Record<string, string> = {
  greeting: 'bg-gray-100 text-gray-700',
  availability: 'bg-blue-100 text-blue-700',
  qualification: 'bg-yellow-100 text-yellow-700',
  pricing: 'bg-orange-100 text-orange-700',
  owner_takeover: 'bg-red-100 text-red-700',
}

const LEAD_COLORS: Record<string, string> = {
  new: 'bg-gray-100 text-gray-600',
  qualified: 'bg-green-100 text-green-700',
  unqualified: 'bg-red-100 text-red-600',
}

interface Props {
  conversations: Conversation[]
}

export default function ConversationsTable({ conversations }: Props) {
  if (conversations.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No conversations found.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 bg-white rounded-lg shadow">
        <thead className="bg-gray-50">
          <tr>
            {['Phone', 'Name', 'Stage', 'Lead', 'Check-in', 'Check-out', 'Guests', 'Updated'].map(h => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {h}
              </th>
            ))}
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {conversations.map(c => (
            <tr key={c.phone_number} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 text-sm font-mono">{c.phone_number}</td>
              <td className="px-4 py-3 text-sm">{c.name ?? '—'}</td>
              <td className="px-4 py-3">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${STAGE_COLORS[c.stage] ?? 'bg-gray-100'}`}>
                  {c.stage}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${LEAD_COLORS[c.lead_status] ?? 'bg-gray-100'}`}>
                  {c.lead_status}
                </span>
              </td>
              <td className="px-4 py-3 text-sm">{c.checkin ?? '—'}</td>
              <td className="px-4 py-3 text-sm">{c.checkout ?? '—'}</td>
              <td className="px-4 py-3 text-sm text-center">{c.guests ?? '—'}</td>
              <td className="px-4 py-3 text-xs text-gray-400">
                {new Date(c.updated_at).toLocaleString('pt-BR')}
              </td>
              <td className="px-4 py-3">
                <Link
                  href={`/conversations/${encodeURIComponent(c.phone_number)}`}
                  className="text-blue-600 hover:underline text-sm"
                >
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot/frontend
npm test
```
Expected: 4 PASSED

---

### Task 12: TakeoverButton component

**Files:**
- Create: `frontend/src/components/TakeoverButton.tsx`
- Create: `frontend/tests/components/TakeoverButton.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/components/TakeoverButton.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import TakeoverButton from '@/components/TakeoverButton'

vi.mock('@/lib/api', () => ({
  takeoverConversation: vi.fn().mockResolvedValue(undefined),
}))

describe('TakeoverButton', () => {
  it('renders button when not in takeover stage', () => {
    render(<TakeoverButton phone="+5511999999999" stage="qualification" onSuccess={() => {}} />)
    expect(screen.getByRole('button', { name: /assume/i })).toBeDefined()
  })

  it('shows disabled state when already in owner_takeover', () => {
    render(<TakeoverButton phone="+5511999999999" stage="owner_takeover" onSuccess={() => {}} />)
    const btn = screen.getByRole('button')
    expect(btn.hasAttribute('disabled') || btn.getAttribute('aria-disabled') === 'true').toBe(true)
  })

  it('calls onSuccess after confirmation', async () => {
    const onSuccess = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<TakeoverButton phone="+5511999999999" stage="qualification" onSuccess={onSuccess} />)
    fireEvent.click(screen.getByRole('button', { name: /assume/i }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce())
  })

  it('does nothing if user cancels confirmation', async () => {
    const onSuccess = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<TakeoverButton phone="+5511999999999" stage="qualification" onSuccess={onSuccess} />)
    fireEvent.click(screen.getByRole('button', { name: /assume/i }))
    await waitFor(() => expect(onSuccess).not.toHaveBeenCalled())
  })
})
```

- [ ] **Step 2: Implement `TakeoverButton`**

```typescript
// frontend/src/components/TakeoverButton.tsx
'use client'
import { useState } from 'react'
import { takeoverConversation } from '@/lib/api'
import type { ConversationStage } from '@/lib/types'

interface Props {
  phone: string
  stage: ConversationStage
  onSuccess: () => void
}

export default function TakeoverButton({ phone, stage, onSuccess }: Props) {
  const [loading, setLoading] = useState(false)
  const isTakenOver = stage === 'owner_takeover'

  async function handleClick() {
    if (!confirm('Assume this conversation? The AI will stop responding and the guest will be notified.')) return
    setLoading(true)
    try {
      await takeoverConversation(phone)
      onSuccess()
    } catch (err) {
      alert('Failed to take over conversation. Please try again.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={isTakenOver || loading}
      aria-disabled={isTakenOver || loading}
      className={`px-4 py-2 rounded font-medium text-sm transition-colors ${
        isTakenOver
          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
          : 'bg-amber-500 hover:bg-amber-600 text-white'
      }`}
    >
      {isTakenOver ? 'Owner Assumed' : loading ? 'Assuming...' : 'Assume Conversation'}
    </button>
  )
}
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot/frontend
npm test
```
Expected: All tests PASSED

---

### Task 13: ChatView component

**Files:**
- Create: `frontend/src/components/ChatView.tsx`
- Create: `frontend/tests/components/ChatView.test.tsx`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/tests/components/ChatView.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ChatView from '@/components/ChatView'
import type { Message } from '@/lib/types'

const messages: Message[] = [
  {
    phone_number: '+5511999999999',
    timestamp: '2026-03-01T10:00:00Z',
    role: 'user',
    message: 'Olá, tem disponibilidade?',
    message_type: 'text',
  },
  {
    phone_number: '+5511999999999',
    timestamp: '2026-03-01T10:00:05Z',
    role: 'assistant',
    message: 'Sim, temos disponibilidade!',
    message_type: 'text',
  },
]

describe('ChatView', () => {
  it('renders user message', () => {
    render(<ChatView messages={messages} />)
    expect(screen.getByText('Olá, tem disponibilidade?')).toBeDefined()
  })

  it('renders assistant message', () => {
    render(<ChatView messages={messages} />)
    expect(screen.getByText('Sim, temos disponibilidade!')).toBeDefined()
  })

  it('renders empty state for no messages', () => {
    render(<ChatView messages={[]} />)
    expect(screen.getByText(/no messages/i)).toBeDefined()
  })
})
```

- [ ] **Step 2: Implement `ChatView`**

```typescript
// frontend/src/components/ChatView.tsx
import type { Message } from '@/lib/types'

interface Props {
  messages: Message[]
}

export default function ChatView({ messages }: Props) {
  if (messages.length === 0) {
    return <div className="text-center py-8 text-gray-400">No messages yet.</div>
  }

  return (
    <div className="flex flex-col gap-3 p-4 overflow-y-auto max-h-[60vh]">
      {messages.map((m, i) => (
        <div
          key={i}
          className={`flex ${m.role === 'user' ? 'justify-start' : 'justify-end'}`}
        >
          <div
            className={`max-w-xs lg:max-w-md px-4 py-2 rounded-2xl text-sm shadow-sm ${
              m.role === 'user'
                ? 'bg-white text-gray-900 border border-gray-200'
                : 'bg-blue-600 text-white'
            }`}
          >
            <p>{m.message}</p>
            <p className={`text-xs mt-1 ${m.role === 'user' ? 'text-gray-400' : 'text-blue-200'}`}>
              {new Date(m.timestamp).toLocaleTimeString('pt-BR')}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Run all frontend tests**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot/frontend
npm test
```
Expected: All tests PASSED

---

### Task 14: Dashboard page

**Files:**
- Create: `frontend/src/app/page.tsx`

- [ ] **Step 1: Create Dashboard page**

```typescript
// frontend/src/app/page.tsx
'use client'
import { useEffect, useState } from 'react'
import useSWR from 'swr'
import { useRouter } from 'next/navigation'
import { getCurrentUser, signOut } from 'aws-amplify/auth'
import ConversationsTable from '@/components/ConversationsTable'
import type { Conversation } from '@/lib/types'
import { fetcher } from '@/lib/api'

export default function DashboardPage() {
  const router = useRouter()
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    getCurrentUser()
      .then(() => setAuthChecked(true))
      .catch(() => router.push('/login'))
  }, [router])

  const { data, error, isLoading, mutate } = useSWR<{ conversations: Conversation[] }>(
    authChecked ? '/api/conversations' : null,
    fetcher,
    { refreshInterval: 5000 }
  )

  if (!authChecked || isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-gray-500">Loading...</div>
  }

  if (error) {
    return <div className="p-8 text-red-600">Error loading conversations.</div>
  }

  const conversations = data?.conversations ?? []
  const qualified = conversations.filter(c => c.lead_status === 'qualified').length
  const pendingTakeover = conversations.filter(c => c.stage !== 'owner_takeover' && c.lead_status === 'qualified').length

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-3 flex justify-between items-center shadow-sm">
        <h1 className="text-lg font-semibold">Chácara Dashboard</h1>
        <div className="flex gap-4 items-center">
          <a href="/calendar" className="text-sm text-blue-600 hover:underline">Calendar</a>
          <button onClick={() => signOut().then(() => router.push('/login'))} className="text-sm text-gray-500 hover:text-gray-700">
            Sign out
          </button>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: 'Total Conversations', value: conversations.length },
            { label: 'Qualified Leads', value: qualified },
            { label: 'Awaiting Takeover', value: pendingTakeover },
          ].map(card => (
            <div key={card.label} className="bg-white rounded-lg shadow p-5">
              <p className="text-sm text-gray-500">{card.label}</p>
              <p className="text-3xl font-bold mt-1">{card.value}</p>
            </div>
          ))}
        </div>

        <ConversationsTable conversations={conversations} />
      </main>
    </div>
  )
}
```

---

### Task 15: Chat view page

**Files:**
- Create: `frontend/src/app/conversations/[phone]/page.tsx`

- [ ] **Step 1: Create Chat view page**

```typescript
// frontend/src/app/conversations/[phone]/page.tsx
'use client'
import { useEffect, useState } from 'react'
import useSWR from 'swr'
import { useRouter, useParams } from 'next/navigation'
import { getCurrentUser } from 'aws-amplify/auth'
import ChatView from '@/components/ChatView'
import TakeoverButton from '@/components/TakeoverButton'
import type { Conversation, Message } from '@/lib/types'
import { fetcher } from '@/lib/api'

export default function ConversationPage() {
  const router = useRouter()
  const { phone } = useParams<{ phone: string }>()
  const decodedPhone = decodeURIComponent(phone)
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    getCurrentUser()
      .then(() => setAuthChecked(true))
      .catch(() => router.push('/login'))
  }, [router])

  const { data: convData, mutate: mutateConv } = useSWR<{ conversation: Conversation }>(
    authChecked ? `/api/conversations/${phone}` : null,
    fetcher,
    { refreshInterval: 5000 }
  )

  const { data: msgData } = useSWR<{ messages: Message[] }>(
    authChecked ? `/api/conversations/${phone}/messages` : null,
    fetcher,
    { refreshInterval: 5000 }
  )

  if (!authChecked) return null

  const conv = convData?.conversation
  const messages = msgData?.messages ?? []

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-3 flex items-center gap-4 shadow-sm">
        <button onClick={() => router.push('/')} className="text-sm text-blue-600 hover:underline">
          ← Back
        </button>
        <h1 className="text-lg font-semibold">{decodedPhone}</h1>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-6 grid grid-cols-3 gap-6">
        {/* Conversation metadata */}
        <aside className="col-span-1 bg-white rounded-lg shadow p-4 space-y-3 h-fit">
          <h2 className="font-semibold text-gray-700">Details</h2>
          {conv ? (
            <dl className="text-sm space-y-2">
              {[
                ['Stage', conv.stage],
                ['Lead', conv.lead_status],
                ['Check-in', conv.checkin],
                ['Check-out', conv.checkout],
                ['Guests', conv.guests],
                ['Purpose', conv.purpose],
                ['Price Est.', conv.price_estimate ? `R$ ${conv.price_estimate}` : '—'],
                ['Rules Accepted', conv.rules_accepted ? 'Yes' : 'No'],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-gray-400">{label}</dt>
                  <dd className="font-medium">{value ?? '—'}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-gray-400 text-sm">Loading...</p>
          )}

          {conv && (
            <div className="pt-2">
              <TakeoverButton
                phone={decodedPhone}
                stage={conv.stage}
                onSuccess={() => mutateConv()}
              />
            </div>
          )}
        </aside>

        {/* Chat messages */}
        <section className="col-span-2 bg-white rounded-lg shadow">
          <div className="border-b px-4 py-3">
            <h2 className="font-semibold text-gray-700">Messages ({messages.length})</h2>
          </div>
          <ChatView messages={messages} />
        </section>
      </main>
    </div>
  )
}
```

---

### Task 16: Calendar page

**Files:**
- Create: `frontend/src/components/CalendarView.tsx`
- Create: `frontend/src/app/calendar/page.tsx`

- [ ] **Step 1: Create `CalendarView` component**

```typescript
// frontend/src/components/CalendarView.tsx
import type { Reservation } from '@/lib/types'

interface Props {
  reservations: Reservation[]
  year: number
  month: number // 0-indexed
  onPrev: () => void
  onNext: () => void
}

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay()
}

function isDateInReservation(date: string, res: Reservation) {
  return date >= res.checkin && date <= res.checkout
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December']

export default function CalendarView({ reservations, year, month, onPrev, onNext }: Props) {
  const daysInMonth = getDaysInMonth(year, month)
  const firstDay = getFirstDayOfWeek(year, month)

  const cells: (number | null)[] = [...Array(firstDay).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <button onClick={onPrev} className="text-gray-500 hover:text-gray-900 px-2">‹</button>
        <h2 className="font-semibold text-lg">{MONTHS[month]} {year}</h2>
        <button onClick={onNext} className="text-gray-500 hover:text-gray-900 px-2">›</button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-gray-400 mb-2">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => <div key={d}>{d}</div>)}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, idx) => {
          if (!day) return <div key={idx} />
          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const activeReservations = reservations.filter(r => isDateInReservation(dateStr, r))
          const isToday = dateStr === new Date().toISOString().slice(0, 10)

          return (
            <div
              key={idx}
              title={activeReservations.map(r => `${r.guest_name} (${r.guests} guests)`).join('\n')}
              className={`rounded p-1 text-sm text-center min-h-[40px] flex flex-col items-center justify-start cursor-default
                ${isToday ? 'bg-blue-50 font-bold border border-blue-300' : ''}
                ${activeReservations.length > 0 ? 'bg-green-50 border border-green-200' : ''}
              `}
            >
              <span>{day}</span>
              {activeReservations.length > 0 && (
                <span className="text-xs text-green-700 truncate w-full text-center">
                  {activeReservations[0].guest_name}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create Calendar page**

```typescript
// frontend/src/app/calendar/page.tsx
'use client'
import { useEffect, useState } from 'react'
import useSWR from 'swr'
import { useRouter } from 'next/navigation'
import { getCurrentUser } from 'aws-amplify/auth'
import CalendarView from '@/components/CalendarView'
import type { Reservation } from '@/lib/types'
import { fetcher } from '@/lib/api'

export default function CalendarPage() {
  const router = useRouter()
  const [authChecked, setAuthChecked] = useState(false)
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth())

  useEffect(() => {
    getCurrentUser()
      .then(() => setAuthChecked(true))
      .catch(() => router.push('/login'))
  }, [router])

  const { data, isLoading } = useSWR<{ reservations: Reservation[] }>(
    authChecked ? '/api/reservations' : null,
    fetcher
  )

  function prevMonth() {
    if (month === 0) { setMonth(11); setYear(y => y - 1) }
    else setMonth(m => m - 1)
  }

  function nextMonth() {
    if (month === 11) { setMonth(0); setYear(y => y + 1) }
    else setMonth(m => m + 1)
  }

  if (!authChecked || isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-gray-500">Loading...</div>
  }

  const reservations = data?.reservations ?? []

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-3 flex items-center gap-4 shadow-sm">
        <a href="/" className="text-sm text-blue-600 hover:underline">← Dashboard</a>
        <h1 className="text-lg font-semibold">Calendar</h1>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <CalendarView
          reservations={reservations}
          year={year}
          month={month}
          onPrev={prevMonth}
          onNext={nextMonth}
        />

        <section className="mt-6 bg-white rounded-lg shadow p-4">
          <h2 className="font-semibold mb-3">Upcoming Reservations</h2>
          {reservations.length === 0 ? (
            <p className="text-gray-400 text-sm">No reservations.</p>
          ) : (
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 text-xs uppercase border-b">
                  <th className="pb-2 pr-4">Guest</th>
                  <th className="pb-2 pr-4">Check-in</th>
                  <th className="pb-2 pr-4">Check-out</th>
                  <th className="pb-2 pr-4">Guests</th>
                  <th className="pb-2">Price</th>
                </tr>
              </thead>
              <tbody>
                {reservations.map(r => (
                  <tr key={r.reservation_id} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-medium">{r.guest_name}</td>
                    <td className="py-2 pr-4">{r.checkin}</td>
                    <td className="py-2 pr-4">{r.checkout}</td>
                    <td className="py-2 pr-4">{r.guests}</td>
                    <td className="py-2">R$ {r.price.toLocaleString('pt-BR')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </div>
  )
}
```

---

### Task 17: Environment config

**Files:**
- Create: `frontend/.env.example`
- Create: `frontend/src/app/not-found.tsx`

- [ ] **Step 1: Create `.env.example`**

```bash
# frontend/.env.example
NEXT_PUBLIC_API_URL=https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod
NEXT_PUBLIC_USER_POOL_ID=us-east-1_XXXXXXXXX
NEXT_PUBLIC_USER_POOL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
```

Actual values come from `cdk deploy` outputs: `AdminApiUrl`, `UserPoolId`, `UserPoolClientId`.

Copy to `.env.local` and fill in CDK outputs before running `npm run build`.

- [ ] **Step 2: Create `frontend/src/app/not-found.tsx`**

```typescript
export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-300">404</h1>
        <p className="text-gray-500 mt-2">Page not found</p>
        <a href="/" className="text-blue-600 hover:underline mt-4 block">Go to Dashboard</a>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Run full frontend test suite**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot/frontend
npm test
```
Expected: All tests PASSED

---

## Phase 4: Integration Verification

### Task 18: Run all tests

- [ ] **Step 1: Run backend tests**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot
uv run pytest backend/tests/ -v
```
Expected: All PASSED

- [ ] **Step 2: Run frontend tests**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot/frontend
npm test
```
Expected: All PASSED

- [ ] **Step 3: Verify CDK synth**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot/infrastructure
source ../.venv/bin/activate
cdk synth 2>&1 | grep -E "(Stack|Error|Warning)"
```
Expected: `ChacaraChatbotStack` and `ChacaraFrontendStack` listed, no errors.

- [ ] **Step 4: Build frontend**

```bash
cd /Users/jowalmeida/dev/chacara-chatbot/frontend
cp .env.example .env.local
# Fill in placeholder values for build verification only
npm run build
```
Expected: Build succeeds, `out/` directory created.

---

## Deployment Instructions

After all tests pass:

1. **Deploy backend + frontend infrastructure:**
   ```bash
   cd /Users/jowalmeida/dev/chacara-chatbot/infrastructure
   cdk deploy --all
   ```

2. **Note CDK outputs** (`AdminApiUrl`, `UserPoolId`, `UserPoolClientId`, `FrontendUrl`)

3. **Create initial Cognito user:**
   ```bash
   aws cognito-idp admin-create-user \
     --user-pool-id <UserPoolId> \
     --username owner@example.com \
     --temporary-password TempPass123! \
     --message-action SUPPRESS
   ```

4. **Update frontend env and rebuild:**
   ```bash
   cd frontend
   # Edit .env.local with real values from CDK outputs
   npm run build
   ```

5. **Redeploy frontend (triggers S3 sync):**
   ```bash
   cd infrastructure
   cdk deploy ChacaraFrontendStack
   ```

6. **Access dashboard at CloudFront URL**
