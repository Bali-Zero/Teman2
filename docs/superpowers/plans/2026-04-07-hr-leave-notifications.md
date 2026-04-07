# HR Leave Notifications + Supervisor RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add supervisor-aware email notifications and delegated approval rights to the HR leave module, so Veronika approves tax team requests, Ruslana approves Dea/Rina, and everyone else routes to Zero, with Zero/Asya in CC per the rules in `docs/superpowers/specs/2026-04-07-hr-leave-notifications-design.md`.

**Architecture:** Two new pure modules (`hr_leave_routing.py` for mapping, `hr_leave_notifier.py` for Brevo HTTP notification), two small additions to `hr_service.py`, four router changes in `hr.py`, three unit test files. No migrations, no frontend. Fire-and-forget via FastAPI `BackgroundTasks`. Self-approval blocked for everyone including HR admins.

**Tech Stack:** FastAPI, asyncpg (Postgres), httpx, pytest, pydantic v2. Python 3.11. Deploy target: `fly deploy --app nuzantara-rag --strategy rolling`.

**Spec reference:** `docs/superpowers/specs/2026-04-07-hr-leave-notifications-design.md`

---

## File Structure

**New files:**
- `apps/backend-rag/backend/app/services/hr/hr_leave_routing.py` — pure routing functions, no I/O
- `apps/backend-rag/backend/app/services/hr/hr_leave_notifier.py` — async Brevo HTTP notifier, fire-and-forget
- `apps/backend-rag/backend/tests/unit/services/hr/__init__.py` — marker
- `apps/backend-rag/backend/tests/unit/services/hr/test_hr_leave_routing.py` — parametrized routing tests
- `apps/backend-rag/backend/tests/unit/services/hr/test_hr_leave_notifier.py` — httpx mock tests
- `apps/backend-rag/backend/tests/unit/app/routers/test_hr_leave_rbac.py` — RBAC delegation tests

**Modified files:**
- `apps/backend-rag/backend/app/services/hr/hr_service.py` — add `get_leave_request(id)` and `get_leave_type_name(id)` methods
- `apps/backend-rag/backend/app/routers/hr.py` — add `BackgroundTasks` param, notifier scheduling, `_require_can_review_leave` helper, update `approve_leave`/`reject_leave`

---

## Task 1: Create `hr_leave_routing.py` module (TDD)

**Files:**
- Create: `apps/backend-rag/backend/tests/unit/services/hr/__init__.py`
- Create: `apps/backend-rag/backend/tests/unit/services/hr/test_hr_leave_routing.py`
- Create: `apps/backend-rag/backend/app/services/hr/hr_leave_routing.py`

- [ ] **Step 1: Create the test directory marker**

Create `apps/backend-rag/backend/tests/unit/services/hr/__init__.py` as empty file.

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
mkdir -p backend/tests/unit/services/hr
touch backend/tests/unit/services/hr/__init__.py
```

- [ ] **Step 2: Write failing tests for `resolve_approver`**

Create `apps/backend-rag/backend/tests/unit/services/hr/test_hr_leave_routing.py`:

```python
"""Tests for HR leave routing logic (pure functions, no I/O)."""

import pytest

from backend.app.services.hr.hr_leave_routing import (
    ASYA_EMAIL,
    ZERO_EMAIL,
    build_notification_recipients,
    resolve_approver,
)


class TestResolveApprover:
    @pytest.mark.parametrize("requester,expected", [
        ("kadek.tax@balizero.com",    "tax@balizero.com"),
        ("angel.tax@balizero.com",    "tax@balizero.com"),
        ("dewa.ayu.tax@balizero.com", "tax@balizero.com"),
        ("faysha.tax@balizero.com",   "tax@balizero.com"),
        ("dea@balizero.com",          "ruslana@balizero.com"),
        ("rina@balizero.com",         "ruslana@balizero.com"),
        ("tax@balizero.com",          ZERO_EMAIL),   # Veronika → Zero
        ("asya@balizero.com",         ZERO_EMAIL),
        ("ruslana@balizero.com",      ZERO_EMAIL),
        ("zero@balizero.com",         ZERO_EMAIL),
        ("random@balizero.com",       ZERO_EMAIL),   # unknown → Zero
    ])
    def test_routing_rules(self, requester: str, expected: str) -> None:
        assert resolve_approver(requester) == expected

    def test_case_insensitive(self) -> None:
        assert resolve_approver("KADEK.TAX@BALIZERO.COM") == "tax@balizero.com"

    def test_whitespace_stripped(self) -> None:
        assert resolve_approver("  kadek.tax@balizero.com  ") == "tax@balizero.com"


class TestBuildNotificationRecipients:
    def test_tax_team_kadek(self) -> None:
        result = build_notification_recipients("kadek.tax@balizero.com")
        assert result == {"to": "tax@balizero.com", "cc": [ZERO_EMAIL, ASYA_EMAIL]}

    def test_dea_routes_to_ruslana(self) -> None:
        result = build_notification_recipients("dea@balizero.com")
        assert result == {"to": "ruslana@balizero.com", "cc": [ZERO_EMAIL, ASYA_EMAIL]}

    def test_zero_is_own_approver_no_duplicate_cc(self) -> None:
        result = build_notification_recipients("zero@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": [ASYA_EMAIL]}

    def test_asya_as_requester_not_in_cc(self) -> None:
        result = build_notification_recipients("asya@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": []}

    def test_veronika_as_requester(self) -> None:
        result = build_notification_recipients("tax@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": [ASYA_EMAIL]}

    def test_ruslana_as_requester(self) -> None:
        result = build_notification_recipients("ruslana@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": [ASYA_EMAIL]}

    def test_unknown_user_fallback(self) -> None:
        result = build_notification_recipients("newhire@balizero.com")
        assert result == {"to": ZERO_EMAIL, "cc": [ASYA_EMAIL]}
```

- [ ] **Step 3: Run tests to verify they fail with ImportError**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/hr/test_hr_leave_routing.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.app.services.hr.hr_leave_routing'`

- [ ] **Step 4: Implement `hr_leave_routing.py`**

Create `apps/backend-rag/backend/app/services/hr/hr_leave_routing.py`:

```python
"""HR leave request routing — hard-coded org chart rules.

Tax team (*.tax@) → Veronika (tax@balizero.com)
Dea, Rina → Ruslana
Everyone else (including Veronika herself) → Zero

When the org chart changes, update SUPERVISOR_MAP and add tests.
No DB column, no migration: 7 employees, rules stable per Zero (2026-04-07).
"""
from __future__ import annotations

SUPERVISOR_MAP: dict[str, str] = {
    "kadek.tax@balizero.com":    "tax@balizero.com",  # Veronika
    "angel.tax@balizero.com":    "tax@balizero.com",
    "dewa.ayu.tax@balizero.com": "tax@balizero.com",
    "faysha.tax@balizero.com":   "tax@balizero.com",
    "dea@balizero.com":          "ruslana@balizero.com",
    "rina@balizero.com":         "ruslana@balizero.com",
}

ZERO_EMAIL = "zero@balizero.com"
ASYA_EMAIL = "asya@balizero.com"


def _normalize(email: str) -> str:
    return email.lower().strip()


def resolve_approver(requester_email: str) -> str:
    """Return the email of the user who should approve this leave request.

    Falls back to Zero when the requester has no specific supervisor
    configured (e.g. Veronika, Asya, Ruslana, and anyone not in the map).
    """
    return SUPERVISOR_MAP.get(_normalize(requester_email), ZERO_EMAIL)


def build_notification_recipients(
    requester_email: str,
) -> dict[str, str | list[str]]:
    """Return {to, cc[]} for the leave-request notification email.

    Rules:
    - TO: the approver from resolve_approver()
    - Zero always in CC unless he is already the TO
    - Asya always in CC unless she is the requester
    """
    requester = _normalize(requester_email)
    approver = resolve_approver(requester)
    cc: list[str] = []
    if approver != ZERO_EMAIL:
        cc.append(ZERO_EMAIL)
    if requester != ASYA_EMAIL:
        cc.append(ASYA_EMAIL)
    return {"to": approver, "cc": cc}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/hr/test_hr_leave_routing.py -v
```

Expected: 18 tests PASS (11 parametrized + 2 normalization + 5 build_notification + 7 = 18). All green.

- [ ] **Step 6: Run ruff and type check**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
ruff check backend/app/services/hr/hr_leave_routing.py backend/tests/unit/services/hr/test_hr_leave_routing.py
python -m py_compile backend/app/services/hr/hr_leave_routing.py
```

Expected: `All checks passed!` and no compile errors.

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/services/hr/hr_leave_routing.py \
        apps/backend-rag/backend/tests/unit/services/hr/__init__.py \
        apps/backend-rag/backend/tests/unit/services/hr/test_hr_leave_routing.py
git commit -m "feat(hr): add leave routing module with supervisor map

Pure functions for resolving approver + building notification recipients
per the org chart rules (tax team → Veronika, Dea/Rina → Ruslana, default
→ Zero; Zero/Asya in CC with dedup rules).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Add `get_leave_request` and `get_leave_type_name` to `HRService`

**Files:**
- Modify: `apps/backend-rag/backend/app/services/hr/hr_service.py` (add 2 methods)

- [ ] **Step 1: Read current LEAVE section to find insertion point**

```bash
cd ~/Desktop/nuzantara
grep -n "async def get_leave_balance\|async def list_leave_requests" \
  apps/backend-rag/backend/app/services/hr/hr_service.py
```

Expected: Two line numbers. Insert new methods BEFORE `get_leave_balance` (just after `reject_leave`).

- [ ] **Step 2: Add the two new methods to `HRService`**

Open `apps/backend-rag/backend/app/services/hr/hr_service.py`. Find the line `async def get_leave_balance(` and insert the following methods immediately BEFORE that line:

```python
    async def get_leave_request(
        self, request_id: int,
    ) -> dict[str, Any] | None:
        """Fetch a single leave request with requester email + leave type.

        Returns None if the request does not exist. Used by the router to
        perform delegated RBAC checks before approve/reject.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT lr.*,
                       tm.email AS requester_email,
                       tm.full_name AS requester_name,
                       lt.name AS leave_type_name
                FROM hr_leave_requests lr
                JOIN hr_employees e ON e.id = lr.employee_id
                JOIN team_members tm ON tm.id = e.team_member_id
                JOIN hr_leave_types lt ON lt.id = lr.leave_type_id
                WHERE lr.id = $1
            """, request_id)
        return dict(row) if row else None

    async def get_leave_type_name(self, type_id: int) -> str:
        """Return the human-readable name of a leave type.

        Falls back to "Leave type #N" if the id is not found (defensive:
        should not happen given FK constraints, but keeps the notifier
        independent of strict row presence).
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name FROM hr_leave_types WHERE id = $1", type_id,
            )
        return row["name"] if row else f"Leave type #{type_id}"
```

- [ ] **Step 3: Verify file compiles and imports**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
python -m py_compile backend/app/services/hr/hr_service.py
python -c "from backend.app.services.hr.hr_service import HRService; print('import OK')"
ruff check backend/app/services/hr/hr_service.py
```

Expected: `import OK` + `All checks passed!`.

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/services/hr/hr_service.py
git commit -m "feat(hr): add get_leave_request + get_leave_type_name helpers

Two small service methods needed by the delegated-RBAC helper in the
router and by the email notifier to display the leave type name.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Create `hr_leave_notifier.py` module (TDD)

> **⚠️ POST-EXECUTION NOTE (2026-04-07):** the original code blocks below
> reproduce two bugs that were caught in code review and fixed in commit
> `3dffb6e6e`. **If you re-execute this task from scratch, apply these
> deltas BEFORE committing:**
>
> 1. **CRIT — `cc` must be a comma-joined string, not `list[str]`.** The
>    receiving Pydantic model `SendEmailRequest`
>    (`backend/app/modules/notifications/router.py:68`) declares
>    `cc: str | None`. Sending a list raises 422 in production. Build the
>    payload conditionally: `if recipients["cc"]: payload["cc"] = ", ".join(recipients["cc"])`
>    and omit the key entirely when the list is empty. Same scar as
>    commit `08c4df17c` in `attendance_monitor.py`.
>
> 2. **IMP — Escape user-controlled HTML.** `requester_name`, `requester_email`,
>    `leave_type_name`, and especially `reason` (free-text TEXT column) must
>    pass through `html.escape()` from stdlib before being interpolated into
>    the body. The subject also uses the escaped name.
>
> Tests must be updated to (a) assert `payload["cc"]` is a string, and
> (b) include a regression test that validates the payload against the
> real `SendEmailRequest` model and a regression test for HTML injection
> in `reason`. See `apps/backend-rag/backend/app/services/hr/hr_leave_notifier.py`
> and `tests/unit/services/hr/test_hr_leave_notifier.py` at HEAD for the
> corrected implementation.

**Files:**
- Create: `apps/backend-rag/backend/tests/unit/services/hr/test_hr_leave_notifier.py`
- Create: `apps/backend-rag/backend/app/services/hr/hr_leave_notifier.py`

- [ ] **Step 1: Write failing tests**

Create `apps/backend-rag/backend/tests/unit/services/hr/test_hr_leave_notifier.py`:

```python
"""Tests for HR leave notifier — Brevo HTTP, fire-and-forget semantics."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.services.hr.hr_leave_notifier import (
    notify_leave_request_pending,
)


@pytest.fixture
def sample_call_args() -> dict:
    return dict(
        request_id=42,
        requester_email="kadek.tax@balizero.com",
        requester_name="Kadek",
        leave_type_name="Annual Leave",
        start_date=date(2026, 12, 15),
        end_date=date(2026, 12, 19),
        total_days=5,
        reason="Family visit",
    )


class TestNotifyLeaveRequestPending:
    @pytest.mark.asyncio
    async def test_happy_path_posts_with_correct_recipients(
        self, sample_call_args: dict,
    ) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await notify_leave_request_pending(**sample_call_args)

        assert mock_client.post.call_count == 1
        call_kwargs = mock_client.post.call_args.kwargs
        payload = call_kwargs["json"]
        assert payload["to"] == "tax@balizero.com"
        assert payload["cc"] == ["zero@balizero.com", "asya@balizero.com"]
        assert "Kadek" in payload["subject"]
        assert "5 days" in payload["subject"]
        assert "Annual Leave" in payload["body"]
        assert "2026-12-15 → 2026-12-19" in payload["body"]
        assert "Family visit" in payload["body"]

    @pytest.mark.asyncio
    async def test_single_day_range_uses_singular_day(
        self, sample_call_args: dict,
    ) -> None:
        sample_call_args["total_days"] = 1
        sample_call_args["start_date"] = date(2026, 12, 15)
        sample_call_args["end_date"] = date(2026, 12, 15)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await notify_leave_request_pending(**sample_call_args)

        payload = mock_client.post.call_args.kwargs["json"]
        assert "1 day" in payload["subject"]
        assert "1 days" not in payload["subject"]
        # Single date means no arrow
        assert "2026-12-15" in payload["body"]
        assert "→" not in payload["body"]

    @pytest.mark.asyncio
    async def test_reason_none_omits_reason_block(
        self, sample_call_args: dict,
    ) -> None:
        sample_call_args["reason"] = None

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await notify_leave_request_pending(**sample_call_args)

        payload = mock_client.post.call_args.kwargs["json"]
        assert "Reason:" not in payload["body"]

    @pytest.mark.asyncio
    async def test_http_error_is_swallowed(self, sample_call_args: dict) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
        )
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            # Must not raise
            await notify_leave_request_pending(**sample_call_args)

    @pytest.mark.asyncio
    async def test_network_error_is_swallowed(
        self, sample_call_args: dict,
    ) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("connection refused"),
        )

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            # Must not raise
            await notify_leave_request_pending(**sample_call_args)
```

- [ ] **Step 2: Run tests to verify they fail with ImportError**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/hr/test_hr_leave_notifier.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.app.services.hr.hr_leave_notifier'`

- [ ] **Step 3: Implement `hr_leave_notifier.py`**

Create `apps/backend-rag/backend/app/services/hr/hr_leave_notifier.py`:

```python
"""HR leave request email notifier — Brevo via internal HTTP endpoint.

Consistent with backend/services/crm/notifiers.py pattern: posts to the
internal notifications/send-email endpoint which routes to Brevo. The URL
can be overridden with the INTERNAL_EMAIL_API_URL env var for local/staging.

Fire-and-forget semantics: all exceptions are caught and logged as warnings.
The caller (router) schedules this via fastapi.BackgroundTasks so the
HTTP request handler returns immediately without waiting for the email.
"""
from __future__ import annotations

import logging
import os
from datetime import date

import httpx

from backend.app.services.hr.hr_leave_routing import (
    build_notification_recipients,
)

logger = logging.getLogger(__name__)

_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")


async def notify_leave_request_pending(
    *,
    request_id: int,
    requester_email: str,
    requester_name: str,
    leave_type_name: str,
    start_date: date,
    end_date: date,
    total_days: int,
    reason: str | None,
) -> None:
    """Send an email to the supervisor when a leave request is created.

    Fire-and-forget: logs warning on failure, never raises. Expected to be
    scheduled via fastapi.BackgroundTasks so the client does not pay the
    email network latency.
    """
    try:
        recipients = build_notification_recipients(requester_email)
        date_range = (
            start_date.isoformat()
            if start_date == end_date
            else f"{start_date.isoformat()} → {end_date.isoformat()}"
        )
        day_label = "day" if total_days == 1 else "days"
        reason_block = (
            f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""
        )

        html_body = (
            f"<p>A leave request needs your review.</p>"
            f"<p><strong>Employee:</strong> {requester_name} ({requester_email})<br>"
            f"<strong>Type:</strong> {leave_type_name}<br>"
            f"<strong>Dates:</strong> {date_range}<br>"
            f"<strong>Duration:</strong> {total_days} {day_label}</p>"
            f"{reason_block}"
            f'<p><a href="https://kita.balizero.com/hr/leave">'
            f"Review in HR Dashboard</a></p>"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={
                    "to": recipients["to"],
                    "cc": recipients["cc"],
                    "subject": (
                        f"Leave Request — {requester_name} "
                        f"({total_days} {day_label})"
                    ),
                    "body": html_body,
                },
            )
            response.raise_for_status()

        logger.info(
            "Leave notification sent: req=%s to=%s cc=%s",
            request_id,
            recipients["to"],
            ",".join(recipients["cc"]),
        )
    except Exception as e:
        logger.warning(
            "Leave notification failed for request %s: %s", request_id, e,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/hr/test_hr_leave_notifier.py -v
```

Expected: 5 tests PASS (happy path, single day, no reason, http error swallow, network error swallow).

- [ ] **Step 5: Run ruff and py_compile**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
ruff check backend/app/services/hr/hr_leave_notifier.py \
           backend/tests/unit/services/hr/test_hr_leave_notifier.py
python -m py_compile backend/app/services/hr/hr_leave_notifier.py
```

Expected: `All checks passed!` + no errors.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/services/hr/hr_leave_notifier.py \
        apps/backend-rag/backend/tests/unit/services/hr/test_hr_leave_notifier.py
git commit -m "feat(hr): add leave request email notifier (Brevo, fire-and-forget)

Posts to INTERNAL_EMAIL_API_URL (default: internal Brevo adapter) with
recipients resolved by hr_leave_routing. All exceptions caught and logged
as warnings — leave creation must never fail because of email problems.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Add `_require_can_review_leave` helper to router + RBAC tests

**Files:**
- Create: `apps/backend-rag/backend/tests/unit/app/routers/test_hr_leave_rbac.py`
- Modify: `apps/backend-rag/backend/app/routers/hr.py` (add helper, update approve/reject endpoints)

- [ ] **Step 1: Write failing RBAC tests**

Create `apps/backend-rag/backend/tests/unit/app/routers/test_hr_leave_rbac.py`:

```python
"""Tests for HR leave RBAC helper — supervisor delegation + self-approval ban."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.app.routers.hr import _require_can_review_leave


def _mock_service_returning_request(requester_email: str) -> Any:
    service = AsyncMock()
    service.get_leave_request = AsyncMock(return_value={
        "id": 1,
        "requester_email": requester_email,
        "requester_name": "Test Employee",
        "status": "pending",
    })
    return service


class TestRequireCanReviewLeave:
    # ─── HR admins (universal access) ────────────────────────────────
    @pytest.mark.asyncio
    async def test_zero_approves_anyone(self) -> None:
        service = _mock_service_returning_request("kadek.tax@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "zero@balizero.com", "role": "member"},
            1,
        )
        assert req["id"] == 1

    @pytest.mark.asyncio
    async def test_asya_approves_anyone(self) -> None:
        service = _mock_service_returning_request("kadek.tax@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "asya@balizero.com", "role": "member"},
            1,
        )
        assert req["id"] == 1

    @pytest.mark.asyncio
    async def test_ruslana_approves_dea(self) -> None:
        service = _mock_service_returning_request("dea@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "ruslana@balizero.com", "role": "member"},
            1,
        )
        assert req["id"] == 1

    # ─── Supervisor delegation ───────────────────────────────────────
    @pytest.mark.asyncio
    async def test_veronika_approves_kadek(self) -> None:
        service = _mock_service_returning_request("kadek.tax@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "tax@balizero.com", "role": "member"},
            1,
        )
        assert req["id"] == 1

    @pytest.mark.asyncio
    async def test_veronika_cannot_approve_dea(self) -> None:
        service = _mock_service_returning_request("dea@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "tax@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_kadek_cannot_approve_angel(self) -> None:
        service = _mock_service_returning_request("angel.tax@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "kadek.tax@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    # ─── Self-approval forbidden (even for HR admins) ────────────────
    @pytest.mark.asyncio
    async def test_asya_cannot_self_approve(self) -> None:
        service = _mock_service_returning_request("asya@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "asya@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_zero_cannot_self_approve(self) -> None:
        service = _mock_service_returning_request("zero@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "zero@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_ruslana_cannot_self_approve(self) -> None:
        service = _mock_service_returning_request("ruslana@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "ruslana@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_veronika_cannot_self_approve(self) -> None:
        service = _mock_service_returning_request("tax@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "tax@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    # ─── Not found ───────────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_not_found_returns_404(self) -> None:
        service = AsyncMock()
        service.get_leave_request = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "zero@balizero.com"},
                999,
            )
        assert exc.value.status_code == 404

    # ─── Email normalization ─────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_user_email_case_insensitive(self) -> None:
        service = _mock_service_returning_request("kadek.tax@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "  TAX@BALIZERO.COM  ", "role": "member"},
            1,
        )
        assert req["id"] == 1
```

- [ ] **Step 2: Run tests to verify they fail (helper not yet exported)**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_hr_leave_rbac.py -v
```

Expected: `ImportError: cannot import name '_require_can_review_leave' from 'backend.app.routers.hr'`

- [ ] **Step 3: Add the helper to `hr.py`**

Open `apps/backend-rag/backend/app/routers/hr.py`. Find the line with `def _require_hr_admin(user: dict[str, Any]) -> None:` and add the following AFTER the existing `_require_hr_admin` function (still in the Helpers section):

```python
async def _require_can_review_leave(
    service: HRService,
    user: dict[str, Any],
    request_id: int,
) -> dict[str, Any]:
    """Return the leave request row if the user may approve/reject it.

    Policy:
    - HR admins (Zero, Asya, Ruslana, antonellosiano) can review anyone
      EXCEPT their own requests (self-approval is forbidden).
    - Delegated supervisors (resolved via hr_leave_routing.resolve_approver)
      can review their direct reports only.
    - Raises HTTPException 404 if the request does not exist.
    - Raises HTTPException 403 if the user lacks permission.
    """
    req = await service.get_leave_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")

    user_email = (user.get("email") or "").lower().strip()
    requester_email = (req.get("requester_email") or "").lower().strip()

    # Self-approval is forbidden even for HR admins.
    if user_email and user_email == requester_email:
        raise HTTPException(
            status_code=403,
            detail="You cannot approve or reject your own leave request",
        )

    if is_hr_admin(user):
        return req

    if resolve_approver(requester_email) == user_email:
        return req

    raise HTTPException(
        status_code=403,
        detail="You are not authorized to review this leave request",
    )
```

At the TOP of the file (in the imports section, near the existing `from backend.app.services.hr.hr_service import HRService` line), add:

```python
from backend.app.services.hr.hr_leave_routing import resolve_approver
```

- [ ] **Step 4: Run the RBAC tests to verify they pass**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_hr_leave_rbac.py -v
```

Expected: 12 tests PASS (3 HR admin access + 3 supervisor rules + 4 self-approval blocks + 1 not found + 1 case insensitive = 12).

- [ ] **Step 5: Verify the import chain still works**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.routers.hr import router, _require_can_review_leave; print('OK')"
ruff check backend/app/routers/hr.py backend/tests/unit/app/routers/test_hr_leave_rbac.py
```

Expected: `OK` + `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/hr.py \
        apps/backend-rag/backend/tests/unit/app/routers/test_hr_leave_rbac.py
git commit -m "feat(hr): add delegated-RBAC helper for leave review

_require_can_review_leave() implements: admin universal access, supervisor
delegation per hr_leave_routing, self-approval forbidden for everyone.
12 unit tests cover Veronika/Ruslana/Zero/Asya/Kadek scenarios + self-
approval bans + case-insensitive email matching.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Wire `approve_leave`/`reject_leave` to use the new helper

**Files:**
- Modify: `apps/backend-rag/backend/app/routers/hr.py` (update 2 endpoints)

- [ ] **Step 1: Update `approve_leave`**

Open `apps/backend-rag/backend/app/routers/hr.py`. Find:

```python
@router.post("/leave/{request_id}/approve")
async def approve_leave(
    request_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Approve a leave request."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    try:
        result = await service.approve_leave(request_id, _get_user_id(current_user))
        return {"success": True, "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

Replace with:

```python
@router.post("/leave/{request_id}/approve")
async def approve_leave(
    request_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Approve a leave request.

    Permission: HR admins (except self) OR the delegated supervisor of
    the requester. Self-approval is forbidden for everyone.
    """
    service = _get_hr_service(db_pool)
    await _require_can_review_leave(service, current_user, request_id)
    try:
        result = await service.approve_leave(
            request_id, _get_user_id(current_user),
        )
        return {"success": True, "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 2: Update `reject_leave`**

Find:

```python
@router.post("/leave/{request_id}/reject")
async def reject_leave(
    request_id: int,
    data: LeaveReviewRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Reject a leave request."""
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    try:
        result = await service.reject_leave(
            request_id, _get_user_id(current_user), data.reason or "",
        )
        return {"success": True, "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

Replace with:

```python
@router.post("/leave/{request_id}/reject")
async def reject_leave(
    request_id: int,
    data: LeaveReviewRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Reject a leave request.

    Permission: HR admins (except self) OR the delegated supervisor of
    the requester. Self-rejection is forbidden for everyone.
    """
    service = _get_hr_service(db_pool)
    await _require_can_review_leave(service, current_user, request_id)
    try:
        result = await service.reject_leave(
            request_id, _get_user_id(current_user), data.reason or "",
        )
        return {"success": True, "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 3: Verify import chain and lint**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.routers.hr import router; print('OK')"
ruff check backend/app/routers/hr.py
```

Expected: `OK` + `All checks passed!`

- [ ] **Step 4: Re-run the RBAC tests to confirm wiring**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_hr_leave_rbac.py -v
```

Expected: 12 tests still PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/hr.py
git commit -m "feat(hr): wire approve_leave/reject_leave to delegated RBAC

Replaces _require_hr_admin with _require_can_review_leave so supervisors
can review their direct reports and self-approval is blocked for everyone
including HR admins.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Wire `request_leave` to trigger the notifier via `BackgroundTasks`

**Files:**
- Modify: `apps/backend-rag/backend/app/routers/hr.py` (update 1 endpoint + imports)

- [ ] **Step 1: Add `BackgroundTasks` + notifier imports**

Open `apps/backend-rag/backend/app/routers/hr.py`. At the top, the existing FastAPI import line looks like:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
```

Change it to:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
```

Add the notifier import near the other HR service imports (below `from backend.app.services.hr.hr_leave_routing import resolve_approver` added in Task 4):

```python
from backend.app.services.hr.hr_leave_notifier import (
    notify_leave_request_pending,
)
```

- [ ] **Step 2: Update `request_leave` endpoint**

Find:

```python
@router.post("/leave/request")
async def request_leave(
    data: LeaveRequestCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Create a leave request."""
    service = _get_hr_service(db_pool)
    my_id = await _get_my_employee_id(service, current_user)
    try:
        result = await service.request_leave({
            "employee_id": my_id,
            **data.model_dump(),
        })
        return {"success": True, "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

Replace with:

```python
@router.post("/leave/request")
async def request_leave(
    data: LeaveRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Create a leave request.

    On success, schedules a fire-and-forget email notification to the
    supervisor (see hr_leave_routing.build_notification_recipients).
    Email failure does NOT fail the request; it is logged as a warning.
    """
    service = _get_hr_service(db_pool)
    my_id = await _get_my_employee_id(service, current_user)
    try:
        result = await service.request_leave({
            "employee_id": my_id,
            **data.model_dump(),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Schedule the supervisor notification email (fire-and-forget)
    leave_type_name = await service.get_leave_type_name(data.leave_type_id)
    background_tasks.add_task(
        notify_leave_request_pending,
        request_id=result["id"],
        requester_email=current_user.get("email", ""),
        requester_name=(
            current_user.get("full_name") or current_user.get("email", "")
        ),
        leave_type_name=leave_type_name,
        start_date=data.start_date,
        end_date=data.end_date,
        total_days=data.total_days,
        reason=data.reason,
    )

    return {"success": True, "request": result}
```

- [ ] **Step 3: Verify import chain + lint**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.routers.hr import router; print('OK')"
ruff check backend/app/routers/hr.py
python -m py_compile backend/app/routers/hr.py
```

Expected: `OK` + `All checks passed!` + no compile errors.

- [ ] **Step 4: Run the full HR test suite to catch regressions**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest \
  backend/tests/unit/services/hr/ \
  backend/tests/unit/app/routers/test_hr_leave_rbac.py \
  backend/tests/unit/utils/test_hr_utils.py \
  -v
```

Expected: all tests from Tasks 1, 3, 4 PASS + the existing `test_hr_utils` still PASS.

- [ ] **Step 5: Run the core RAG sanity tests (regression guard)**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest \
  backend/tests/services/rag/test_kg_langgraph.py \
  backend/tests/services/rag/test_kg_subgraphs.py \
  backend/tests/services/rag/test_confidence.py \
  -q
```

Expected: 85 tests PASS (same as the bug 10/11/12 baseline).

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/hr.py
git commit -m "feat(hr): trigger supervisor email on leave request creation

Wires request_leave to schedule notify_leave_request_pending via FastAPI
BackgroundTasks after the DB insert succeeds. Client does not pay email
latency; email failure never fails the leave request.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Stash unrelated pre-existing changes + push

**Files:**
- No code changes — pure git hygiene

- [ ] **Step 1: Inspect current working tree**

```bash
cd ~/Desktop/nuzantara
git status --short
```

Expected: a mix of HR-feature commits already staged (from Tasks 1-6) and the pre-existing 40+ modified files from other work (visa-oracle, llm/, evaluator JSONs, etc.).

- [ ] **Step 2: Stash all NON-HR pre-existing modifications**

Run this command (copy-paste verbatim — the file list is from the bundle 10/11/12 baseline and has NOT changed):

```bash
cd ~/Desktop/nuzantara
git stash push -m "WIP: pre-existing parked while deploying HR leave notifier" -- \
  apps/backend-rag/backend/app/routers/whatsapp_chat.py \
  apps/backend-rag/backend/app/setup/service_initializer.py \
  apps/backend-rag/backend/llm/config.py \
  apps/backend-rag/backend/llm/providers/gemini.py \
  apps/backend-rag/backend/llm/token_estimator.py \
  apps/backend-rag/backend/middleware/hybrid_auth.py \
  apps/backend-rag/backend/services/analytics/attendance_monitor.py \
  apps/backend-rag/backend/services/analytics/team_timesheet_service.py \
  apps/backend-rag/backend/services/llm_clients/gemini_service.py \
  apps/backend-rag/backend/services/llm_clients/pricing.py \
  apps/backend-rag/backend/services/rag/verification_service.py \
  apps/backend-rag/backend/services/visa_oracle/visa_oracle_service.py \
  apps/backend-rag/backend/tests/unit/core/test_redis_manager.py \
  apps/bali-intel-scraper/data/published_articles.json \
  apps/bali-intel-scraper/seo_metadata.json \
  apps/evaluator/nlm_deep_research/coverage_matrix.json \
  apps/evaluator/nlm_deep_research/gap_scanner_state.json \
  apps/evaluator/nlm_deep_research/t4_state.json \
  apps/evaluator/nlm_deep_research/yt_state.json \
  apps/evaluator/nlm_nb10_pipeline_state.json \
  apps/evaluator/nlm_nb10_sources.json \
  apps/evaluator/nlm_nb2_pipeline_state.json \
  apps/evaluator/nlm_nb2_sources.json \
  apps/evaluator/nlm_nb3_pipeline_state.json \
  apps/evaluator/nlm_nb3_sources.json \
  apps/evaluator/nlm_nb4_pipeline_state.json \
  apps/evaluator/nlm_nb4_sources.json \
  apps/evaluator/nlm_nb5_pipeline_state.json \
  apps/evaluator/nlm_nb5_sources.json \
  apps/evaluator/nlm_nb6_pipeline_state.json \
  apps/evaluator/nlm_nb6_sources.json \
  apps/evaluator/nlm_nb7_pipeline_state.json \
  apps/evaluator/nlm_nb7_sources.json \
  apps/evaluator/nlm_nb8_pipeline_state.json \
  apps/evaluator/nlm_nb8_sources.json \
  "apps/mouth/src/app/(visa-oracle)/visa-oracle/layout.tsx" \
  "apps/mouth/src/app/(visa-oracle)/visa-oracle/privacy/page.tsx" \
  "apps/mouth/src/app/(visa-oracle)/visa-oracle/result/page.tsx" \
  "apps/mouth/src/app/(visa-oracle)/visa-oracle/terms/page.tsx" \
  apps/mouth/src/lib/visa-oracle/nationalities.ts \
  package-lock.json 2>&1
```

**If a file in the list no longer has modifications (someone else committed it)**, git will print `error: pathspec ... did not match any file(s)`. That is OK — continue. The intent is: "stash everything that's modified from that list, ignore paths that are no longer modified."

- [ ] **Step 3: Verify only HR commits remain untouched on the branch**

```bash
cd ~/Desktop/nuzantara
git status --short | head -10
git log --oneline origin/main..HEAD
```

Expected: `git status` shows NO modified files (maybe untracked docs/plans, which is fine). `git log` shows the 6 commits from Tasks 1-6 ahead of origin/main.

- [ ] **Step 4: Push to origin/main**

```bash
cd ~/Desktop/nuzantara
git push origin main
```

Expected: push succeeds, 6 commits sent.

- [ ] **Step 5: No commit needed (git hygiene only)**

---

## Task 8: Deploy backend + restore stash

**Files:**
- No code changes — deployment

- [ ] **Step 1: Deploy backend to Fly.io (rolling strategy)**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
fly deploy --app nuzantara-rag --strategy rolling 2>&1 | tail -60
```

Expected: `✔ [N/N] Machine ... is now in a good state` for each machine; `Visit your newly deployed app at https://nuzantara-rag.fly.dev/`.

- [ ] **Step 2: Health check**

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://nuzantara-rag.fly.dev/health
curl -s https://nuzantara-rag.fly.dev/health | head -c 300
```

Expected: `HTTP 200` + `{"status":"healthy",...}`.

- [ ] **Step 3: Restore the stashed pre-existing changes**

```bash
cd ~/Desktop/nuzantara
git stash pop 2>&1 | tail -10
```

Expected: `Dropped refs/stash@{0} (...)` + the pre-existing 40 files are back as modified.

- [ ] **Step 4: Confirm stash restore did not touch HR files**

```bash
cd ~/Desktop/nuzantara
git status --short | grep -E "hr_leave|hr\.py|hr_service" || echo "no HR files modified (good)"
```

Expected: `no HR files modified (good)` — the HR feature is committed, nothing came back from the stash pointing at HR files.

- [ ] **Step 5: No commit needed**

---

## Task 9: E2E tests in production

**Files:**
- No code changes — prod verification

- [ ] **Step 1: Fetch JWT_SECRET from Fly env**

```bash
fly ssh console --app nuzantara-rag --command env 2>&1 | grep "^JWT_SECRET=" | head -1
```

Expected: `JWT_SECRET=<base64>` — copy the value for the next step.

- [ ] **Step 2: Generate a Kadek JWT (supervisor = Veronika)**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
python -c "
import jwt, time
secret = 'PASTE_JWT_SECRET_HERE'
payload = {
    'sub': 'kadek.tax@balizero.com',
    'email': 'kadek.tax@balizero.com',
    'exp': int(time.time()) + 600,
    'iat': int(time.time()),
}
print(jwt.encode(payload, secret, algorithm='HS256'))
"
```

Expected: a JWT string. Export it to a shell variable:

```bash
export KADEK_JWT="<paste_jwt_here>"
```

- [ ] **Step 3: Create a leave request as Kadek (happy path)**

```bash
curl -s -o /tmp/req.json -w "HTTP %{http_code}\n" \
  -X POST -H "Authorization: Bearer $KADEK_JWT" -H "Content-Type: application/json" \
  -d '{"leave_type_id":1,"start_date":"2026-12-29","end_date":"2026-12-29","total_days":1,"reason":"E2E HR notifier test"}' \
  https://nuzantara-rag.fly.dev/api/hr/leave/request
cat /tmp/req.json
```

Expected: `HTTP 200` + `{"success":true,"request":{"id":N,...}}`. Save the `id` for the next step.

- [ ] **Step 4: Check Fly logs for the "Leave notification sent" entry**

```bash
fly logs --app nuzantara-rag 2>&1 | grep -E "Leave notification" | tail -5
```

Expected: a line like `Leave notification sent: req=N to=tax@balizero.com cc=zero@balizero.com,asya@balizero.com`.

- [ ] **Step 5: Verify Veronika (tax@balizero.com) received the email**

Ask Zero to check `tax@balizero.com` inbox for a message with subject `Leave Request — Kadek (1 day)`. Verify `zero@balizero.com` and `asya@balizero.com` are in CC.

- [ ] **Step 6: Test supervisor RBAC — Veronika approves Kadek (should be 200)**

Generate a Veronika JWT (email `tax@balizero.com`) using the same Python snippet in Step 2. Export as `$VERONIKA_JWT`.

```bash
REQ_ID=$(cat /tmp/req.json | python -c "import json,sys; print(json.load(sys.stdin)['request']['id'])")
curl -s -o /tmp/approve.json -w "HTTP %{http_code}\n" \
  -X POST -H "Authorization: Bearer $VERONIKA_JWT" -H "Content-Type: application/json" \
  https://nuzantara-rag.fly.dev/api/hr/leave/$REQ_ID/approve
cat /tmp/approve.json
```

Expected: `HTTP 200` + `{"success":true,"request":{"id":...,"status":"approved",...}}`.

- [ ] **Step 7: Test supervisor RBAC — Veronika tries to approve a non-tax request (should be 403)**

Create another leave request, this time as `dea@balizero.com` (Dea). Generate `$DEA_JWT`, POST to `/leave/request` the same way. Save the new `id`.

Then try to approve it with Veronika's token:

```bash
DEA_REQ_ID=<id_from_dea_request>
curl -s -o /tmp/403.json -w "HTTP %{http_code}\n" \
  -X POST -H "Authorization: Bearer $VERONIKA_JWT" -H "Content-Type: application/json" \
  https://nuzantara-rag.fly.dev/api/hr/leave/$DEA_REQ_ID/approve
cat /tmp/403.json
```

Expected: `HTTP 403` + `{"detail":"You are not authorized to review this leave request",...}`.

- [ ] **Step 8: Test self-approval ban — Veronika requests leave, then tries to self-approve**

Use `$VERONIKA_JWT` to POST a leave request, save the id, then try to approve it with the same token:

```bash
curl -s -o /tmp/vreq.json -w "HTTP %{http_code}\n" \
  -X POST -H "Authorization: Bearer $VERONIKA_JWT" -H "Content-Type: application/json" \
  -d '{"leave_type_id":1,"start_date":"2026-12-30","end_date":"2026-12-30","total_days":1,"reason":"E2E self-approval test"}' \
  https://nuzantara-rag.fly.dev/api/hr/leave/request

VREQ_ID=$(cat /tmp/vreq.json | python -c "import json,sys; print(json.load(sys.stdin)['request']['id'])")

curl -s -o /tmp/self.json -w "HTTP %{http_code}\n" \
  -X POST -H "Authorization: Bearer $VERONIKA_JWT" -H "Content-Type: application/json" \
  https://nuzantara-rag.fly.dev/api/hr/leave/$VREQ_ID/approve
cat /tmp/self.json
```

Expected: the request creation is `HTTP 200`. The self-approval attempt is `HTTP 403` + `{"detail":"You cannot approve or reject your own leave request",...}`.

- [ ] **Step 9: Cleanup test rows in production DB**

```bash
PGPW=$(fly ssh console --app nuzantara-rag --command "env" 2>&1 | grep "^DATABASE_URL=" | sed 's|.*://[^:]*:||' | sed 's|@.*||')
fly proxy 15432:5432 --app nuzantara-postgres > /tmp/fly_proxy.log 2>&1 &
PROXY_PID=$!
sleep 3
PGPASSWORD="$PGPW" /opt/homebrew/opt/libpq/bin/psql -h localhost -p 15432 -U backend_rag_v2 -d nuzantara_rag -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
-- Inspect all rows that will be touched
SELECT id, employee_id, leave_type_id, status, reason
FROM hr_leave_requests
WHERE reason LIKE 'E2E HR notifier test%'
   OR reason LIKE 'E2E self-approval test%';
-- Delete them
DELETE FROM hr_leave_requests
WHERE reason LIKE 'E2E HR notifier test%'
   OR reason LIKE 'E2E self-approval test%'
RETURNING id, employee_id;
-- Restore any "used_days" / "pending_days" that were incremented.
-- For approved requests the service moved pending→used; for pending
-- requests only pending_days was incremented. Release whatever was
-- reserved for the Kadek, Dea, and Veronika rows touched by this test.
UPDATE hr_leave_balances
SET pending_days = 0, used_days = 0
WHERE balance_year = 2026
  AND employee_id IN (
      SELECT id FROM hr_employees WHERE team_member_id IN (
          SELECT id FROM team_members WHERE email IN (
              'kadek.tax@balizero.com',
              'dea@balizero.com',
              'tax@balizero.com'
          )
      )
  )
RETURNING employee_id, leave_type_id, pending_days, used_days;
COMMIT;
SQL
RC=$?
kill $PROXY_PID 2>/dev/null
wait 2>/dev/null
echo "psql exit: $RC"
```

**CAUTION:** before running this, verify with `BEGIN; ... ROLLBACK;` first to see what would be deleted/changed. Only convert to `COMMIT` once the dry-run looks correct.

Expected after COMMIT: `DELETE 2` or `DELETE 3`, pending/used days zeroed for the test rows.

- [ ] **Step 10: No commit needed (prod verification only)**

---

## Task 10: Save MOS memory + wrap-up

**Files:**
- No code changes — memory persistence

- [ ] **Step 1: Save MOS decision memory**

```bash
~/.claude/scripts/mem save decision "HR leave notifications + supervisor RBAC deployed 2026-04-07. New files: hr_leave_routing.py (6-entry SUPERVISOR_MAP), hr_leave_notifier.py (Brevo HTTP fire-and-forget via BackgroundTasks). hr.py: _require_can_review_leave helper bans self-approval even for HR admins. Routing: tax team → Veronika (tax@balizero.com), Dea/Rina → Ruslana, else → Zero. Asya always CC unless requester. E2E verified on prod: Kadek request → Veronika approves (200), Veronika tries Dea (403), Veronika self-approve (403). INTERNAL_EMAIL_API_URL env var controls Brevo endpoint. Tests: 18 routing + 5 notifier + 12 RBAC = 35 new unit tests. Co-authored by Gemini/Codex/DeepSeek review." 8
```

Expected: `✅ Saved: [decision] HR leave notifications ... (importance: 8)`.

- [ ] **Step 2: Final status check**

```bash
cd ~/Desktop/nuzantara
git log --oneline origin/main~7..origin/main
git status --short | head -5
```

Expected: 6 HR commits visible in the log (Tasks 1-6) + `git status` shows only the pre-existing stashed files (nothing HR-related).

- [ ] **Step 3: No commit needed**

---

## Global testing summary

After all 10 tasks, the backend should have:

| Test file | New tests | Purpose |
|---|---|---|
| `tests/unit/services/hr/test_hr_leave_routing.py` | 18 | `resolve_approver` + `build_notification_recipients` |
| `tests/unit/services/hr/test_hr_leave_notifier.py` | 5 | httpx mock, happy path, swallow errors |
| `tests/unit/app/routers/test_hr_leave_rbac.py` | 12 | delegated RBAC + self-approval ban + 404 |
| **Total new** | **35** | |
| `tests/unit/utils/test_hr_utils.py` | (existing) | regression baseline |
| `tests/services/rag/test_kg_*.py`, `test_confidence.py` | (existing 85) | regression baseline |

## Rollback plan

If anything goes wrong in prod:

```bash
cd ~/Desktop/nuzantara
git revert HEAD~5..HEAD  # revert Tasks 2-6 commits (keep Task 1 routing module if safe)
git push origin main
cd apps/backend-rag && fly deploy --app nuzantara-rag --strategy rolling
```

The notifier is fire-and-forget so a bad deploy does NOT corrupt data. The worst case is emails stop being sent — no data integrity impact.
