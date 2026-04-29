# Backend Missing Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the missing backend features to make the WhatsApp chatbot fully operational: WhatsApp reply, iCal availability checking, pricing calculation, and owner notification.

**Architecture:** The system follows Clean Architecture — use cases orchestrate services and integrations; services contain reusable business logic; integrations handle external APIs. New features add a `PricingService`, `AvailabilityService`, iCal `CalendarRepository` implementation, and a `NotifyOwner` use case wired into the existing `GenerateAIResponse` flow.

**Tech Stack:** Python 3.12, Pydantic v2, httpx (for iCal fetching), pendulum (for date math), boto3/SSM (for secrets), WhatsApp Cloud API, OpenAI

---

## File Map

**Create:**
- `backend/app/services/pricing_service.py` — nightly rate × nights calculation
- `backend/app/services/availability_service.py` — wraps CalendarRepository, checks date overlap
- `backend/app/integrations/ical/__init__.py` — empty package marker
- `backend/app/integrations/ical/ical_calendar_repo.py` — fetches + parses .ics URL to implement CalendarRepository
- `backend/app/use_cases/notify_owner.py` — sends WhatsApp summary to owner, marks owner_notified
- `backend/tests/services/test_pricing_service.py`
- `backend/tests/services/test_availability_service.py`
- `backend/tests/integrations/ical/test_ical_calendar_repo.py`
- `backend/tests/use_cases/test_notify_owner.py`

**Modify:**
- `backend/app/config/settings.py` — add `owner_phone`, `ical_url` from SSM
- `backend/app/use_cases/generate_ai_response.py` — uncomment WhatsApp send; inject PricingService, AvailabilityService, NotifyOwner; wire in pre-LLM pricing/availability and post-LLM notifications
- `backend/app/handlers/webhook_handler.py` — inject new dependencies
- `backend/lambdas/webhook/handler.py` — wire new integrations at Lambda entry point
- `backend/tests/use_cases/test_generate_ai_response.py` — update for new constructor + behaviors
- `backend/tests/config/test_settings.py` — add new setting params

---

## Task 1: Fix — Enable WhatsApp Reply

The bot currently receives messages but never replies. Line 66 in `generate_ai_response.py` is commented out.

**Files:**
- Modify: `backend/app/use_cases/generate_ai_response.py:66`
- Test: `backend/tests/use_cases/test_generate_ai_response.py`

- [ ] **Step 1: Run the existing test to verify the current (broken) behavior**

```bash
cd /path/to/chacara-chatbot/backend
python -m pytest tests/use_cases/test_generate_ai_response.py::test_saves_assistant_message_and_sends_whatsapp -v
```
Expected: FAIL — `whatsapp_client.send_text.assert_called_once_with(...)` fails because send is commented out.

- [ ] **Step 2: Uncomment the WhatsApp send line**

In `backend/app/use_cases/generate_ai_response.py`, change line 66:
```python
# self._whatsapp_client.send_text(to=phone_number, text=response_text)
```
to:
```python
self._whatsapp_client.send_text(to=phone_number, text=response_text)
```

- [ ] **Step 3: Run the test to verify it passes**

```bash
python -m pytest tests/use_cases/test_generate_ai_response.py -v
```
Expected: all 3 tests PASS.

---

## Task 2: Add owner_phone and ical_url to Settings

Two new configuration values are needed: the owner's WhatsApp number (for notifications) and the iCal URL (for availability checking). Both are sourced from SSM Parameter Store via environment variable names.

**Files:**
- Modify: `backend/app/config/settings.py`
- Test: `backend/tests/config/test_settings.py`

- [ ] **Step 1: Read the existing settings test**

```bash
cat backend/tests/config/test_settings.py
```

- [ ] **Step 2: Add failing tests for new settings**

In `backend/tests/config/test_settings.py`, add at the end. Note: use `patch("app.config.settings.boto3.client")` (matching existing test pattern) and call `_set_param_envs` to set the required existing env vars, then also set the new param env var, and include the new param in SSM response:

```python
def test_loads_owner_phone_from_ssm(monkeypatch):
    _set_param_envs(monkeypatch)
    monkeypatch.setenv("OWNER_PHONE_PARAM", "/chacara/owner-phone")
    full_response = {
        "Parameters": SSM_RESPONSE["Parameters"] + [
            {"Name": "/chacara/owner-phone", "Value": "+5511888888888"}
        ],
        "InvalidParameters": [],
    }
    with patch("app.config.settings.boto3.client", return_value=_mock_ssm(full_response)):
        s = Settings()
    assert s.owner_phone == "+5511888888888"


def test_loads_ical_url_from_ssm(monkeypatch):
    _set_param_envs(monkeypatch)
    monkeypatch.setenv("ICAL_URL_PARAM", "/chacara/ical-url")
    full_response = {
        "Parameters": SSM_RESPONSE["Parameters"] + [
            {"Name": "/chacara/ical-url", "Value": "https://example.com/calendar.ics"}
        ],
        "InvalidParameters": [],
    }
    with patch("app.config.settings.boto3.client", return_value=_mock_ssm(full_response)):
        s = Settings()
    assert s.ical_url == "https://example.com/calendar.ics"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/config/test_settings.py -v -k "owner_phone or ical_url"
```
Expected: FAIL — `Settings` has no `owner_phone` or `ical_url` attribute.

- [ ] **Step 4: Update settings.py**

Replace the `param_names` dict in `backend/app/config/settings.py` to include the two new params:

```python
class Settings:
    def __init__(self):
        self.openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.owner_phone: str = ""
        self.ical_url: str = ""

        param_names = {
            attr: os.environ[env_var]
            for attr, env_var in {
                "openai_api_key": "OPENAI_API_KEY_PARAM",
                "whatsapp_access_token": "WHATSAPP_ACCESS_TOKEN_PARAM",
                "whatsapp_phone_number_id": "WHATSAPP_PHONE_NUMBER_ID_PARAM",
                "knowledge_base_bucket": "KNOWLEDGE_BASE_BUCKET_PARAM",
                "owner_phone": "OWNER_PHONE_PARAM",
                "ical_url": "ICAL_URL_PARAM",
            }.items()
            if env_var in os.environ
        }
        # ... rest unchanged
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/config/test_settings.py -v
```
Expected: all tests PASS.

---

## Task 3: iCal Calendar Repository Implementation

Fetches an `.ics` URL via httpx and parses VEVENT date ranges to check availability. Uses only stdlib + httpx (already vendored). No new dependencies needed.

**Files:**
- Create: `backend/app/integrations/ical/__init__.py`
- Create: `backend/app/integrations/ical/ical_calendar_repo.py`
- Create: `backend/tests/integrations/ical/__init__.py`
- Create: `backend/tests/integrations/ical/test_ical_calendar_repo.py`

- [ ] **Step 1: Create the test file with a minimal .ics fixture**

Create `backend/tests/integrations/ical/test_ical_calendar_repo.py`:

```python
from unittest.mock import patch, MagicMock
from app.integrations.ical.ical_calendar_repo import ICalCalendarRepository

SAMPLE_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260410
DTEND;VALUE=DATE:20260413
SUMMARY:Booked
END:VEVENT
END:VCALENDAR
"""

def _make_repo(ics_content: str) -> ICalCalendarRepository:
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = ics_content
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        repo = ICalCalendarRepository(url="https://example.com/cal.ics")
        repo._refresh()
    return repo


def test_is_unavailable_when_dates_overlap():
    repo = _make_repo(SAMPLE_ICS)
    assert repo.is_available("2026-04-10", "2026-04-12") is False


def test_is_available_when_dates_do_not_overlap():
    repo = _make_repo(SAMPLE_ICS)
    assert repo.is_available("2026-04-14", "2026-04-16") is True


def test_is_available_when_checkout_equals_existing_checkin():
    # guest checks out on same day existing booking starts — no overlap
    repo = _make_repo(SAMPLE_ICS)
    assert repo.is_available("2026-04-08", "2026-04-10") is True


def test_get_blocked_dates_returns_date_strings():
    repo = _make_repo(SAMPLE_ICS)
    blocked = repo.get_blocked_dates()
    assert "2026-04-10" in blocked
    assert "2026-04-11" in blocked
    assert "2026-04-12" in blocked
    assert "2026-04-13" not in blocked  # checkout day is exclusive


def test_empty_calendar_is_always_available():
    empty_ics = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"
    repo = _make_repo(empty_ics)
    assert repo.is_available("2026-04-10", "2026-04-12") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/integrations/ical/ -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Create package files**

Create `backend/app/integrations/ical/__init__.py` (empty).
Create `backend/tests/integrations/ical/__init__.py` (empty).

- [ ] **Step 4: Implement ICalCalendarRepository**

Create `backend/app/integrations/ical/ical_calendar_repo.py`:

```python
import re
from datetime import date, timedelta

import httpx
from aws_lambda_powertools import Logger

from app.domain.repositories.calendar_repository import CalendarRepository

logger = Logger()

_DTSTART_RE = re.compile(r"DTSTART[^:]*:(\d{8})")
_DTEND_RE = re.compile(r"DTEND[^:]*:(\d{8})")

_repo = None


def get_ical_calendar_repo() -> "ICalCalendarRepository":
    global _repo
    if _repo is None:
        from app.config.settings import _get_settings
        settings = _get_settings()
        _repo = ICalCalendarRepository(url=settings.ical_url)
        _repo._refresh()
    return _repo


def _parse_date(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _date_range(start: date, end: date) -> list[date]:
    """Returns all dates from start up to (not including) end."""
    result = []
    current = start
    while current < end:
        result.append(current)
        current += timedelta(days=1)
    return result


class ICalCalendarRepository(CalendarRepository):
    def __init__(self, url: str):
        self._url = url
        self._blocked: set[date] = set()

    def _refresh(self) -> None:
        response = httpx.get(self._url, timeout=10)
        response.raise_for_status()
        self._blocked = set()
        for event_block in response.text.split("BEGIN:VEVENT")[1:]:
            start_match = _DTSTART_RE.search(event_block)
            end_match = _DTEND_RE.search(event_block)
            if start_match and end_match:
                start = _parse_date(start_match.group(1))
                end = _parse_date(end_match.group(1))
                self._blocked.update(_date_range(start, end))
        logger.info("ical_refreshed", blocked_count=len(self._blocked))

    def is_available(self, checkin: str, checkout: str) -> bool:
        start = date.fromisoformat(checkin)
        end = date.fromisoformat(checkout)
        requested = set(_date_range(start, end))
        return requested.isdisjoint(self._blocked)

    def get_blocked_dates(self) -> list[str]:
        return sorted(d.isoformat() for d in self._blocked)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/integrations/ical/ -v
```
Expected: all 5 tests PASS.

---

## Task 4: PricingService

Calculates a price estimate based on number of nights and guests. Rate is a constant for now (can be made configurable later via SSM).

**Files:**
- Create: `backend/app/services/pricing_service.py`
- Create: `backend/tests/services/__init__.py`
- Create: `backend/tests/services/test_pricing_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/__init__.py` (empty).

Create `backend/tests/services/test_pricing_service.py`:

```python
import pytest
from app.services.pricing_service import PricingService


def test_two_nights_returns_correct_total():
    svc = PricingService(nightly_rate=800.0)
    price = svc.calculate(checkin="2026-04-10", checkout="2026-04-12", guests=4)
    assert price == 1600.0


def test_one_night():
    svc = PricingService(nightly_rate=800.0)
    price = svc.calculate(checkin="2026-04-10", checkout="2026-04-11", guests=2)
    assert price == 800.0


def test_invalid_dates_raises():
    svc = PricingService(nightly_rate=800.0)
    with pytest.raises(ValueError):
        svc.calculate(checkin="2026-04-12", checkout="2026-04-10", guests=2)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/services/test_pricing_service.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement PricingService**

Create `backend/app/services/__init__.py` (empty, if not exists).

Create `backend/app/services/pricing_service.py`:

```python
from datetime import date


class PricingService:
    def __init__(self, nightly_rate: float):
        self._rate = nightly_rate

    def calculate(self, checkin: str, checkout: str, guests: int) -> float:
        start = date.fromisoformat(checkin)
        end = date.fromisoformat(checkout)
        nights = (end - start).days
        if nights <= 0:
            raise ValueError(f"checkout must be after checkin: {checkin} -> {checkout}")
        return float(self._rate * nights)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/services/test_pricing_service.py -v
```
Expected: all 3 tests PASS.

---

## Task 5: AvailabilityService

Wraps `CalendarRepository` to provide a clean service interface for use cases.

**Files:**
- Create: `backend/app/services/availability_service.py`
- Test: `backend/tests/services/test_availability_service.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/services/test_availability_service.py`:

```python
from unittest.mock import MagicMock
from app.services.availability_service import AvailabilityService


def test_delegates_to_calendar_repo():
    repo = MagicMock()
    repo.is_available.return_value = True
    svc = AvailabilityService(calendar_repo=repo)
    result = svc.check("2026-04-10", "2026-04-12")
    assert result is True
    repo.is_available.assert_called_once_with("2026-04-10", "2026-04-12")


def test_returns_false_when_unavailable():
    repo = MagicMock()
    repo.is_available.return_value = False
    svc = AvailabilityService(calendar_repo=repo)
    assert svc.check("2026-04-10", "2026-04-12") is False
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/services/test_availability_service.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement AvailabilityService**

Create `backend/app/services/availability_service.py`:

```python
from app.domain.repositories.calendar_repository import CalendarRepository


class AvailabilityService:
    def __init__(self, calendar_repo: CalendarRepository):
        self._calendar_repo = calendar_repo

    def check(self, checkin: str, checkout: str) -> bool:
        return self._calendar_repo.is_available(checkin, checkout)
```

- [ ] **Step 4: Run to verify tests pass**

```bash
python -m pytest tests/services/ -v
```
Expected: all tests PASS.

---

## Task 6: NotifyOwner Use Case

Sends a summary WhatsApp message to the owner when a lead is qualified and hasn't been notified yet. Marks `owner_notified = True` on the conversation.

**Files:**
- Create: `backend/app/use_cases/notify_owner.py`
- Create: `backend/tests/use_cases/test_notify_owner.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/use_cases/test_notify_owner.py`:

```python
from unittest.mock import MagicMock
from app.domain.models.conversation import Conversation, ConversationStage, LeadStatus
from app.use_cases.notify_owner import NotifyOwner


def _make_qualified_conv():
    return Conversation(
        phone_number="+5511999999999",
        name="Maria",
        stage=ConversationStage.PRICING,
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=6,
        purpose="birthday",
        lead_status=LeadStatus.QUALIFIED,
    )


def test_sends_whatsapp_to_owner():
    conv = _make_qualified_conv()
    conv_repo = MagicMock()
    conv_repo.load.return_value = conv
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    whatsapp.send_text.assert_called_once()
    call_args = whatsapp.send_text.call_args
    assert call_args[1]["to"] == "+5511888888888"
    assert "+5511999999999" in call_args[1]["text"]


def test_marks_owner_notified():
    conv = _make_qualified_conv()
    conv_repo = MagicMock()
    conv_repo.load.return_value = conv
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    conv_repo.save.assert_called_once()
    saved = conv_repo.save.call_args[0][0]
    assert saved.owner_notified is True


def test_skips_if_already_notified():
    conv = _make_qualified_conv()
    conv.owner_notified = True
    conv_repo = MagicMock()
    conv_repo.load.return_value = conv
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    whatsapp.send_text.assert_not_called()
    conv_repo.save.assert_not_called()


def test_skips_if_conversation_not_found():
    conv_repo = MagicMock()
    conv_repo.load.return_value = None
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    whatsapp.send_text.assert_not_called()


def test_skips_if_lead_not_qualified():
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.GREETING,
        lead_status=LeadStatus.NEW,
    )
    conv_repo = MagicMock()
    conv_repo.load.return_value = conv
    whatsapp = MagicMock()
    use_case = NotifyOwner(conversation_repo=conv_repo, whatsapp_client=whatsapp, owner_phone="+5511888888888")
    use_case.execute(phone_number="+5511999999999")
    whatsapp.send_text.assert_not_called()
    conv_repo.save.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/use_cases/test_notify_owner.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement NotifyOwner**

Create `backend/app/use_cases/notify_owner.py`:

```python
from aws_lambda_powertools import Logger

from app.domain.models.conversation import LeadStatus
from app.domain.repositories.conversation_repository import ConversationRepository
from app.integrations.whatsapp.whatsapp_client import WhatsAppClient

logger = Logger()


class NotifyOwner:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        whatsapp_client: WhatsAppClient,
        owner_phone: str,
    ):
        self._conversation_repo = conversation_repo
        self._whatsapp_client = whatsapp_client
        self._owner_phone = owner_phone

    def execute(self, phone_number: str) -> None:
        conversation = self._conversation_repo.load(phone_number)
        if conversation is None:
            logger.warning("notify_owner_no_conversation", phone=phone_number)
            return

        if conversation.lead_status != LeadStatus.QUALIFIED:
            logger.info("owner_notify_skipped_not_qualified", phone=phone_number, lead_status=conversation.lead_status)
            return

        if conversation.owner_notified:
            logger.info("owner_already_notified", phone=phone_number)
            return

        lines = [
            f"📲 Novo lead qualificado!",
            f"Telefone: {phone_number}",
        ]
        if conversation.name:
            lines.append(f"Nome: {conversation.name}")
        if conversation.checkin:
            lines.append(f"Check-in: {conversation.checkin}")
        if conversation.checkout:
            lines.append(f"Check-out: {conversation.checkout}")
        if conversation.guests:
            lines.append(f"Hóspedes: {conversation.guests}")
        if conversation.purpose:
            lines.append(f"Motivo: {conversation.purpose}")
        if conversation.price_estimate:
            lines.append(f"Estimativa: R$ {conversation.price_estimate:.2f}")

        message = "\n".join(lines)
        self._whatsapp_client.send_text(to=self._owner_phone, text=message)
        logger.info("owner_notified", phone=phone_number)

        conversation.owner_notified = True
        conversation.touch()
        self._conversation_repo.save(conversation)
```

- [ ] **Step 4: Run to verify tests pass**

```bash
python -m pytest tests/use_cases/test_notify_owner.py -v
```
Expected: all 5 tests PASS.

---

## Task 7: Wire Pricing + Availability + NotifyOwner into GenerateAIResponse

Before calling the LLM, compute availability (if dates are known) and price estimate (if stage is PRICING). After LLM updates, trigger owner notification if lead becomes QUALIFIED.

**Files:**
- Modify: `backend/app/use_cases/generate_ai_response.py`
- Modify: `backend/tests/use_cases/test_generate_ai_response.py`

- [ ] **Step 1: Add new failing tests**

Add to `backend/tests/use_cases/test_generate_ai_response.py`:

```python
def test_calculates_price_when_stage_is_pricing():
    from app.domain.models.conversation import ConversationStage
    conv = Conversation(
        phone_number="+5511999999999",
        stage=ConversationStage.PRICING,
        checkin="2026-04-10",
        checkout="2026-04-12",
        guests=4,
    )
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("O preço é R$ 1600.", {})
    whatsapp_client = MagicMock()
    pricing_service = MagicMock()
    pricing_service.calculate.return_value = 1600.0
    availability_service = MagicMock()
    availability_service.check.return_value = True
    notify_owner = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        pricing_service=pricing_service,
        availability_service=availability_service,
        notify_owner=notify_owner,
    )
    use_case.execute(phone_number="+5511999999999")

    pricing_service.calculate.assert_called_once_with(
        checkin="2026-04-10", checkout="2026-04-12", guests=4
    )
    saved = conv_repo.save.call_args[0][0]
    assert saved.price_estimate == 1600.0


def test_notifies_owner_when_lead_becomes_qualified():
    from app.domain.models.conversation import ConversationStage, LeadStatus
    conv = Conversation(phone_number="+5511999999999", stage=ConversationStage.PRICING)
    conv_repo, msg_repo = _make_fake_repos(conversation=conv)
    prompt_builder = MagicMock()
    prompt_builder.build_system_prompt.return_value = "system"
    prompt_builder.build_messages.return_value = []
    openai_client = MagicMock()
    openai_client.chat.return_value = ("Perfeito!", {"lead_status": "qualified"})
    whatsapp_client = MagicMock()
    pricing_service = MagicMock()
    pricing_service.calculate.return_value = None
    availability_service = MagicMock()
    availability_service.check.return_value = True
    notify_owner = MagicMock()

    use_case = GenerateAIResponse(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        openai_client=openai_client,
        prompt_builder=prompt_builder,
        whatsapp_client=whatsapp_client,
        pricing_service=pricing_service,
        availability_service=availability_service,
        notify_owner=notify_owner,
    )
    use_case.execute(phone_number="+5511999999999")

    notify_owner.execute.assert_called_once_with(phone_number="+5511999999999")
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/use_cases/test_generate_ai_response.py -v
```
Expected: FAIL — `GenerateAIResponse.__init__` doesn't accept new params.

- [ ] **Step 3: Update GenerateAIResponse**

Replace `backend/app/use_cases/generate_ai_response.py` with:

```python
from datetime import datetime, timezone

from aws_lambda_powertools import Logger

from app.domain.models.conversation import Conversation, ConversationStage, LeadStatus
from app.domain.models.message import Message, MessageRole, MessageType
from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.message_repository import MessageRepository
from app.integrations.llm.openai_client import OpenAIClient
from app.integrations.llm.prompt_builder import PromptBuilder
from app.integrations.whatsapp.whatsapp_client import WhatsAppClient
from app.services.availability_service import AvailabilityService
from app.services.pricing_service import PricingService
from app.use_cases.notify_owner import NotifyOwner

logger = Logger()

_ALLOWED_UPDATES = {"stage", "checkin", "checkout", "guests", "purpose", "name", "rules_accepted", "customer_profile", "lead_status"}


class GenerateAIResponse:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        openai_client: OpenAIClient,
        prompt_builder: PromptBuilder,
        whatsapp_client: WhatsAppClient,
        pricing_service: PricingService | None = None,
        availability_service: AvailabilityService | None = None,
        notify_owner: NotifyOwner | None = None,
    ):
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._openai_client = openai_client
        self._prompt_builder = prompt_builder
        self._whatsapp_client = whatsapp_client
        self._pricing_service = pricing_service
        self._availability_service = availability_service
        self._notify_owner = notify_owner

    def execute(self, phone_number: str) -> None:
        conversation = self._conversation_repo.load(phone_number)
        if conversation is None:
            conversation = Conversation(phone_number=phone_number)

        if conversation.stage == ConversationStage.OWNER_TAKEOVER:
            logger.info("owner_takeover_skip_ai", phone=phone_number)
            return

        self._enrich_conversation(conversation)

        recent_messages = self._message_repo.get_recent(phone_number, limit=10)
        system_prompt = self._prompt_builder.build_system_prompt(conversation)
        messages = self._prompt_builder.build_messages(recent_messages)

        logger.info("llm_request_started", phone=phone_number, stage=conversation.stage, recent_messages_count=len(recent_messages))
        response_text, updates = self._openai_client.chat(
            system=system_prompt,
            messages=messages,
        )
        logger.info("llm_response_received", phone=phone_number, updates=updates)

        self._apply_updates(conversation, updates)
        conversation.touch()
        self._conversation_repo.save(conversation)
        logger.info("conversation_state_updated", phone=phone_number, stage=conversation.stage)

        assistant_message = Message(
            phone_number=phone_number,
            timestamp=datetime.now(timezone.utc),
            role=MessageRole.ASSISTANT,
            message=response_text,
            message_type=MessageType.TEXT,
        )
        self._message_repo.save(assistant_message)
        self._whatsapp_client.send_text(to=phone_number, text=response_text)
        logger.info("ai_response_sent", phone=phone_number)

        if (
            conversation.lead_status == LeadStatus.QUALIFIED
            and not conversation.owner_notified
            and self._notify_owner
        ):
            try:
                self._notify_owner.execute(phone_number=phone_number)
            except Exception:
                logger.exception("failed_to_notify_owner", phone=phone_number)

    def _enrich_conversation(self, conversation: Conversation) -> None:
        if (
            self._pricing_service
            and conversation.stage == ConversationStage.PRICING
            and conversation.checkin
            and conversation.checkout
            and conversation.guests
            and conversation.price_estimate is None
        ):
            try:
                price = self._pricing_service.calculate(
                    checkin=conversation.checkin,
                    checkout=conversation.checkout,
                    guests=conversation.guests,
                )
                conversation.price_estimate = price
                logger.info("price_calculated", price=price)
            except Exception:
                logger.exception("pricing_calculation_failed")

    def _apply_updates(self, conversation: Conversation, updates: dict) -> None:
        for key, value in updates.items():
            if key not in _ALLOWED_UPDATES:
                continue
            if key == "stage":
                try:
                    conversation.stage = ConversationStage(value)
                except ValueError:
                    logger.warning("invalid_stage_from_llm", stage=value)
            elif key == "lead_status":
                try:
                    conversation.lead_status = LeadStatus(value)
                except ValueError:
                    logger.warning("invalid_lead_status_from_llm", lead_status=value)
            else:
                setattr(conversation, key, value)
```

- [ ] **Step 4: Run all use case tests**

```bash
python -m pytest tests/use_cases/ -v
```
Expected: all tests PASS (old tests use optional params which default to None).

---

## Task 8: Wire New Dependencies into WebhookHandler

Update the webhook handler to construct and inject `ICalCalendarRepository`, `PricingService`, `AvailabilityService`, and `NotifyOwner`. All new symbols must be module-level imports (consistent with existing handler style). New service singletons use the same lazy-init factory pattern as existing integrations.

**Files:**
- Modify: `backend/app/handlers/webhook_handler.py`
- Modify: `backend/tests/handlers/test_webhook_handler.py`

- [ ] **Step 1: Update module-level imports in webhook_handler.py**

Add these imports at the top of `backend/app/handlers/webhook_handler.py` alongside the existing imports:

```python
import os

from app.config.settings import _get_settings
from app.integrations.ical.ical_calendar_repo import get_ical_calendar_repo
from app.services.availability_service import AvailabilityService
from app.services.pricing_service import PricingService
from app.use_cases.notify_owner import NotifyOwner

_NIGHTLY_RATE = float(os.environ.get("NIGHTLY_RATE", "800.0"))

_availability_service = None
_pricing_service = None


def _get_availability_service() -> AvailabilityService:
    global _availability_service
    if _availability_service is None:
        _availability_service = AvailabilityService(calendar_repo=get_ical_calendar_repo())
    return _availability_service


def _get_pricing_service() -> PricingService:
    global _pricing_service
    if _pricing_service is None:
        _pricing_service = PricingService(nightly_rate=_NIGHTLY_RATE)
    return _pricing_service
```

- [ ] **Step 2: Update _handle_incoming to use the new deps**

In `_handle_incoming`, replace the `generate_use_case` construction block with:

```python
        settings = _get_settings()
        notify_owner_use_case = NotifyOwner(
            conversation_repo=get_conversation_repo(),
            whatsapp_client=get_whatsapp_client(),
            owner_phone=settings.owner_phone,
        )

        generate_use_case = GenerateAIResponse(
            conversation_repo=get_conversation_repo(),
            message_repo=get_message_repo(),
            openai_client=get_openai_client(),
            prompt_builder=PromptBuilder(),
            whatsapp_client=get_whatsapp_client(),
            pricing_service=_get_pricing_service(),
            availability_service=_get_availability_service(),
            notify_owner=notify_owner_use_case,
        )
```

- [ ] **Step 3: Update _patch_all_integrations() in the test file**

The existing helper in `backend/tests/handlers/test_webhook_handler.py` patches 7 items. Add 4 more for the new module-level names. Replace the entire `_patch_all_integrations` function with:

```python
def _patch_all_integrations():
    """Return a list of patches for all external integrations used in POST handling."""
    return [
        patch("app.handlers.webhook_handler.get_conversation_repo"),
        patch("app.handlers.webhook_handler.get_message_repo"),
        patch("app.handlers.webhook_handler.get_openai_client"),
        patch("app.handlers.webhook_handler.get_whatsapp_client"),
        patch("app.handlers.webhook_handler.get_whisper_client"),
        patch("app.handlers.webhook_handler.PromptBuilder"),
        patch("app.handlers.webhook_handler.GenerateAIResponse"),
        patch("app.handlers.webhook_handler._get_settings"),
        patch("app.handlers.webhook_handler._get_availability_service"),
        patch("app.handlers.webhook_handler._get_pricing_service"),
    ]
```

Also update tests that unpack exactly 7 patches (`patches[0]` through `patches[6]`) to use `contextlib.ExitStack` for cleanliness, or simply expand the with-statement:

```python
def test_post_returns_200():
    patches = _patch_all_integrations()
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6] as MockGenerate, patches[7], patches[8], patches[9]:
        MockGenerate.return_value = MagicMock()
        handler = WebhookHandler()
        response = handler.handle(_make_post_event(_make_text_webhook_payload()), None)
        assert response["statusCode"] == 200
```

Apply the same expansion to `test_post_status_only_returns_200` and `test_post_invalid_payload_returns_200`. Also add the new patches to `test_post_calls_generate_ai_response`:

```python
def test_post_calls_generate_ai_response(mock_repos):
    with patch("app.handlers.webhook_handler.GenerateAIResponse") as MockGenerate, \
         patch("app.handlers.webhook_handler.get_openai_client"), \
         patch("app.handlers.webhook_handler.get_whatsapp_client"), \
         patch("app.handlers.webhook_handler.get_whisper_client"), \
         patch("app.handlers.webhook_handler.PromptBuilder"), \
         patch("app.handlers.webhook_handler._get_settings"), \
         patch("app.handlers.webhook_handler._get_availability_service"), \
         patch("app.handlers.webhook_handler._get_pricing_service"):
        mock_instance = MagicMock()
        MockGenerate.return_value = mock_instance

        handler = WebhookHandler()
        event = {
            "httpMethod": "POST",
            "body": json.dumps(_text_message_payload("+5511999999999", "Oi")),
        }
        response = handler.handle(event, {})
        assert response["statusCode"] == 200
        mock_instance.execute.assert_called_once_with(phone_number="+5511999999999")
```

Also add `_availability_service = None` and `_pricing_service = None` to the `_reset_handler_globals` function:

```python
def _reset_handler_globals():
    handler_module._ssm = None
    handler_module._availability_service = None
    handler_module._pricing_service = None
```

- [ ] **Step 4: Run handler tests**

```bash
python -m pytest tests/handlers/test_webhook_handler.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS.

---

## Task 9: Create Missing __init__ files

Ensure all new packages have `__init__.py` so imports work.

- [ ] **Step 1: Create any missing init files**

```bash
touch backend/app/services/__init__.py
touch backend/app/integrations/ical/__init__.py
touch backend/tests/services/__init__.py
touch backend/tests/integrations/ical/__init__.py
```

- [ ] **Step 2: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```
Expected: all tests PASS with no import errors.
