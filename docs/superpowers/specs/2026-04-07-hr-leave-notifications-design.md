# HR Leave Email Notifications + Supervisor RBAC

**Status:** Draft — pending user review
**Date:** 2026-04-07
**Author:** Claude Opus 4.6 (1M context)
**Reviewers:** Gemini 2.5 Pro (CLI), Codex CLI, DeepSeek-R1 32B (Ollama)

## 1. Context

Nuzantara HR module (`apps/backend-rag/backend/app/routers/hr.py` + `services/hr/hr_service.py`) currently:

- Accepts leave requests via `POST /api/hr/leave/request`
- Allows any HR admin (`HR_ADMIN_EMAILS` = Zero, antonellosiano, Asya, Ruslana) to approve/reject any request via `POST /api/hr/leave/{id}/approve` and `.../reject`
- **Does not send any email notification** when a leave request is created

This spec adds supervisor-aware email notifications and delegated approval rights, as instructed by the product owner (Zero, 2026-04-07).

## 2. Requirements

### 2.1 Routing rules (stable per org chart, 2026-04-07)

| Requester (email local-part@domain) | Approver (TO) | Zero CC | Asya CC |
|---|---|---|---|
| kadek.tax@balizero.com | tax@balizero.com (Veronika) | yes | yes |
| angel.tax@balizero.com | tax@balizero.com | yes | yes |
| dewa.ayu.tax@balizero.com | tax@balizero.com | yes | yes |
| faysha.tax@balizero.com | tax@balizero.com | yes | yes |
| dea@balizero.com | ruslana@balizero.com | yes | yes |
| rina@balizero.com | ruslana@balizero.com | yes | yes |
| tax@balizero.com (Veronika) | zero@balizero.com | — (already TO) | yes |
| everyone else (e.g. new hires) | zero@balizero.com | — (already TO) | yes |
| asya@balizero.com | zero@balizero.com | — (already TO) | — (already requester) |

**Invariant:** Zero is always CC'd (unless he is the TO); Asya is always CC'd (unless she is the requester).

### 2.2 RBAC delegation

A user can approve/reject a leave request if and only if:

```
(is_hr_admin(user) OR resolve_approver(request.requester_email) == user.email)
AND user.email != request.requester_email
```

**Self-approval is forbidden for everyone**, including HR admins (Zero, Asya, Ruslana). If Asya or Zero request leave, someone else must approve it.

**Rationale:** two out of three independent LLM reviewers flagged unrestricted admin self-approval as a governance concern; the product owner confirmed option (b) "forbid self-approval for all" on 2026-04-07.

### 2.3 Email content

- **Subject:** `Leave Request — {Requester Name} ({N} day[s])`
- **Body (HTML):**
  - Employee name + email
  - Leave type name (resolved from `hr_leave_types`)
  - Date range (single date if start = end, else `start → end`)
  - Total days
  - Reason (if provided)
  - Link to `https://kita.balizero.com/hr/leave`

### 2.4 Trigger + failure handling

- **Trigger:** on successful `request_leave()` insert only. No email on approve/reject (out of scope).
- **Failure mode:** fire-and-forget via `fastapi.BackgroundTasks`. Notifier catches all exceptions and logs a warning. **Leave request creation must not fail because of email errors.** Asya/Zero can always see pending requests in the dashboard as a fallback.

## 3. Architecture

### 3.1 New files

**`apps/backend-rag/backend/app/services/hr/hr_leave_routing.py`**

Pure routing logic, no I/O, unit-testable in isolation.

```python
"""HR leave request routing — hard-coded org chart rules.

When the org chart changes, update SUPERVISOR_MAP and add/update tests.
No DB column, no migration: 7 employees, rules stable.
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


def build_notification_recipients(requester_email: str) -> dict[str, list[str] | str]:
    """Return {to, cc[]} for the leave-request notification email.

    Rules:
    - TO: the approver from resolve_approver()
    - Zero always in CC unless he is already TO
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

**`apps/backend-rag/backend/app/services/hr/hr_leave_notifier.py`**

Fire-and-forget email sender. Copies the Brevo-via-HTTP pattern already used by `backend/services/crm/notifiers.py:24` and `crm_practices.py:172`. Uses `INTERNAL_EMAIL_API_URL` env var (default: `https://nuzantara-rag.fly.dev/api/notifications/send-email`) so local and staging can override.

```python
"""HR leave request email notifier — Brevo via internal HTTP endpoint.

Consistent with backend/services/crm/notifiers.py pattern: posts to the
internal notifications/send-email endpoint which routes to Brevo.
"""
from __future__ import annotations

import logging
import os
from datetime import date

import httpx

from backend.app.services.hr.hr_leave_routing import build_notification_recipients

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

    Fire-and-forget: logs warning on failure, never raises. Invoked via
    FastAPI BackgroundTasks so the request handler returns immediately.
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
            f'<p><a href="https://kita.balizero.com/hr/leave">Review in HR Dashboard</a></p>'
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={
                    "to": recipients["to"],
                    "cc": recipients["cc"],
                    "subject": f"Leave Request — {requester_name} ({total_days} {day_label})",
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
        logger.warning("Leave notification failed for request %s: %s", request_id, e)
```

### 3.2 Modified files

**`apps/backend-rag/backend/app/services/hr/hr_service.py`** — adds two small methods:

```python
async def get_leave_request(self, request_id: int) -> dict[str, Any] | None:
    """Fetch a single leave request with requester email, or None."""
    async with self.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT lr.*, tm.email AS requester_email,
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
    """Return the human-readable name of a leave type, or a fallback."""
    async with self.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name FROM hr_leave_types WHERE id = $1", type_id,
        )
    return row["name"] if row else f"Leave type #{type_id}"
```

**`apps/backend-rag/backend/app/routers/hr.py`** — four changes:

1. Import `BackgroundTasks` and the routing helpers.
2. `request_leave()` accepts `background_tasks: BackgroundTasks`, fetches leave type name, schedules the notifier via `background_tasks.add_task(...)`.
3. New helper `_require_can_review_leave(service, user, request_id)`:
   - Calls `service.get_leave_request(request_id)` → 404 if missing
   - Normalizes `user.email` with `.lower().strip()`
   - Allows the review iff `(is_hr_admin(user) OR resolve_approver(req["requester_email"]) == user_email) AND user_email != normalize(req["requester_email"])`
   - Raises `HTTPException(403)` otherwise
   - Returns the fetched request dict so the handler can reuse it
4. `approve_leave()` and `reject_leave()` replace `_require_hr_admin(current_user)` with `await _require_can_review_leave(service, current_user, request_id)`.

## 4. Data flow

```
┌─────────────────────┐
│ POST /leave/request │
│ (Kadek as requester)│
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────┐
│ router.request_leave()   │
│  - service.request_leave │──────► INSERT hr_leave_requests (atomic txn, unchanged)
│  - get_leave_type_name() │
│  - background_tasks.add_task(notify_leave_request_pending)
└──────────┬───────────────┘
           │
           ▼
 200 OK returned to client (no email latency)
           │
           │ (background)
           ▼
┌─────────────────────────────────┐
│ notify_leave_request_pending    │
│  build_notification_recipients  │──► {to: tax@, cc: [zero@, asya@]}
│  POST INTERNAL_EMAIL_API_URL    │──► Brevo sends email
│  swallow errors, log warning    │
└─────────────────────────────────┘


┌─────────────────────────────┐
│ POST /leave/{id}/approve    │
│ (Veronika as reviewer)      │
└──────────┬──────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ _require_can_review_leave        │
│  service.get_leave_request(id)   │──► fetch requester_email
│  check is_hr_admin OR approver   │
│  check user != requester         │──► 403 if fail
└──────────┬───────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│ service.approve_leave(id, ...) │──► UPDATE ... WHERE id=$1 AND status='pending'
│                                │   (atomic, ValueError→400 if stale)
└────────────────────────────────┘
```

## 5. Testing

### 5.1 `tests/unit/services/hr/test_hr_leave_routing.py` (new, pure function tests)

Parametrized cases for `resolve_approver`:

| requester_email | expected_approver |
|---|---|
| kadek.tax@balizero.com | tax@balizero.com |
| angel.tax@balizero.com | tax@balizero.com |
| dewa.ayu.tax@balizero.com | tax@balizero.com |
| faysha.tax@balizero.com | tax@balizero.com |
| dea@balizero.com | ruslana@balizero.com |
| rina@balizero.com | ruslana@balizero.com |
| tax@balizero.com (Veronika) | zero@balizero.com |
| asya@balizero.com | zero@balizero.com |
| ruslana@balizero.com | zero@balizero.com |
| zero@balizero.com | zero@balizero.com |
| unknown@balizero.com | zero@balizero.com |
| `  KADEK.TAX@BALIZERO.COM  ` (case+whitespace) | tax@balizero.com |

Explicit cases for `build_notification_recipients`:

| Scenario | Requester | Expected result |
|---|---|---|
| Tax team (Kadek) | kadek.tax@ | `{to: tax@, cc: [zero@, asya@]}` |
| Dea | dea@ | `{to: ruslana@, cc: [zero@, asya@]}` |
| Zero (default route, Zero is TO) | zero@ | `{to: zero@, cc: [asya@]}` |
| Asya (default route, Asya excluded) | asya@ | `{to: zero@, cc: []}` |
| Veronika (default route, Asya still in CC) | tax@ | `{to: zero@, cc: [asya@]}` |
| Ruslana | ruslana@ | `{to: zero@, cc: [asya@]}` |
| Unknown user | random@ | `{to: zero@, cc: [asya@]}` |

### 5.2 `tests/unit/app/routers/test_hr_leave_rbac.py` (new, mocks service)

| Reviewer | Target requester | Expected status | Rationale |
|---|---|---|---|
| Veronika | Kadek | 200 | Supervisor of Kadek |
| Veronika | Dea | 403 | Not Dea's supervisor, not HR admin |
| Ruslana | Dea | 200 | HR admin + also Dea's supervisor |
| Zero | Kadek | 200 | HR admin |
| Asya | Kadek | 200 | HR admin |
| Kadek | Angel | 403 | Not admin, not supervisor |
| Asya | Asya (self-approve) | 403 | Self-approval forbidden even for admin |
| Zero | Zero (self-approve) | 403 | Self-approval forbidden even for Zero |

### 5.3 `tests/unit/services/hr/test_hr_leave_notifier.py` (new, mocks httpx)

- **Happy path:** mock `httpx.AsyncClient`, verify POST is called with correct `to`/`cc`/`subject`/`body`, no exception raised.
- **HTTP error:** mock `raise_for_status()` raising; assert `notify_leave_request_pending` returns cleanly (swallow).
- **Network error:** mock httpx raising `httpx.ConnectError`; same swallow behavior.

## 6. Risks + mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Email endpoint (Brevo) down | Medium | Low | Fire-and-forget + Asya/Zero see pending in dashboard |
| Supervisor inactive (Veronika on leave) | Low | Low | Out of scope; Zero (CC) and Asya (CC) can approve from dashboard manually |
| Self-approval attempt | Low | Medium | Hard-blocked in `_require_can_review_leave` + tested |
| Org chart changes | Low | Low | Hard-coded `SUPERVISOR_MAP` requires PR + deploy; rules stable at 7 employees |
| `INTERNAL_EMAIL_API_URL` unset in local/staging | High (dev) | None | Warning-only log + leave request still committed |
| Pending request modified between auth check and mutation (TOCTOU) | Zero | Zero | No code path modifies `employee_id` on an existing request; `approve_leave` UPDATE is already guarded by `WHERE status='pending'` (atomic) |

## 7. Explicit non-goals

- No DB column `supervisor_email` (hard-coded for now, per product owner)
- No notification to requester on approve/reject (deferred scope)
- No UI for supervisor management in `/hr/employees`
- No escalation on timeout (if supervisor doesn't respond in 48h, no auto-escalation)
- No email-thread reply-to-approve
- No migration, no frontend changes
- No change to `HR_ADMIN_EMAILS` (Veronika is NOT added as HR admin — she only has delegated review rights via the RBAC check)

## 8. File changes summary

| File | Type | Lines |
|---|---|---|
| `backend/app/services/hr/hr_leave_routing.py` | new | ~50 |
| `backend/app/services/hr/hr_leave_notifier.py` | new | ~90 |
| `backend/app/services/hr/hr_service.py` | modified | +30 |
| `backend/app/routers/hr.py` | modified | +40 |
| `backend/tests/unit/services/hr/test_hr_leave_routing.py` | new | ~70 |
| `backend/tests/unit/app/routers/test_hr_leave_rbac.py` | new | ~120 |
| `backend/tests/unit/services/hr/test_hr_leave_notifier.py` | new | ~90 |

Total: ~500 lines across 7 files. No migrations. No frontend changes.

## 9. Review history

Design reviewed in parallel by:

- **Gemini 2.5 Pro (CLI, plan mode)** — flagged BackgroundTasks, admin self-approval, API key requirement. Recommendation adopted for BackgroundTasks. Self-approval deferred to product owner → option (b) confirmed.
- **Codex CLI (read-only sandbox)** — flagged TOCTOU (rejected: no attack vector exists), BackgroundTasks (adopted), self-approval (adopted), URL env coupling (adopted via existing `INTERNAL_EMAIL_API_URL` env var), user-email normalization symmetry (adopted), also caught an ambiguous test-description wording (fixed).
- **DeepSeek-R1 32B (Ollama local)** — duplicated issues already caught by the other two; task-queue suggestion rejected as over-engineering.

Rejected suggestions (documented for future reference):
- Celery/Redis task queue (over-engineering for 10-20 requests/month)
- Service-level RBAC refactor to `review_leave(request_id, reviewer_email, action)` (breaks existing pattern, no real concurrency vulnerability to fix)
- Direct import of `ZohoEmailService` instead of Brevo HTTP hop (Brevo is the intentional primary provider; self-HTTP endpoint is a valid adapter pattern already used by `notifiers.py`)
