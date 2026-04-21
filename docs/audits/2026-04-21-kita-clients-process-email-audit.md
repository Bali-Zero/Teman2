# Audit kita.balizero.com/clients & /process — Email Flow

**Date:** 2026-04-21
**Author:** Claude Opus 4.7 max effort
**Scope:** apps/backend-rag backend code handling the 5-state practice lifecycle
(inquiry → waiting_documents → sending_invoice → on_process → completed) plus
welcome email, HR bonus notification, and all 7 cron notifier endpoints.

---

## Critical infrastructure discoveries (contextual)

### Two parallel migration systems — only v2 is active

- `backend/migrations/migration_*.py` (fino a 118) — **LEGACY, not discovered**
- `backend/db/migrations_v2/*.sql` (up to 125) — canonical (migration_manager
  scans only this directory, see `migration_manager.py:233`)
- Consequence: the new `email_send_log` migration MUST be a `.sql` file in
  `migrations_v2/`. Next free sequential number: **126**.

### notification_log has three conflicting schemas coexisting

1. `backend/migrations/migration_111_notification_log.py` (legacy, inert):
   `user_id UUID, channel, ref, sent_at`
2. `backend/app/modules/notifications/migrations/001_create_notification_tables.sql`
   (standalone module, run-once on its own): `client_id, action, created_at`
3. `alert_dispatcher.py:294` + `compliance_alerts.sql:9` reference variant #1.

Because only migrations*v2 is discovered by the central manager, **whichever
notification_log exists in prod depends on whether the notifications module's
own migration ran**. This is a \_latent bug unrelated to this audit* — logged
for follow-up, NOT fixed here.

### HTTP 207 for cron partial_failure — deferred

Air SSH unreachable from current Pro session; cron wrapper behavior on 207
cannot be verified. **Decision:** keep HTTP 200 and add
`{"status": "partial_failure", "errors": [...]}` to the response body.
Monitoring can evolve to read body later without causing a regression today.

---

## 8 bugs — verification and impact

### Bug 1 ✅ CONFIRMED — internal_email.py swallows all exceptions

**File:** `backend/app/services/internal_email.py:98-105`
**Signature:** `async def send_internal_email(...) -> None:` with default
`raise_on_failure=False`. All exceptions are caught and logged as warning.

**Impact:** Every critical email path (HR bonus, invoice notifications,
welcome, compliance alerts) uses this function. Brevo 4xx/5xx, network
errors, timeouts all silently become "best-effort dropped". The only
current signal is a `logger.warning` line — no DB trace, no Telegram alert,
no retry.

**Scope of use:** 23 files grep'd as callers including

- `crm_practices._notify_hr_bonus_pending` (HR bonus → Asya)
- `services/crm/welcome/welcome_practice_service.py` (practice-to-practice welcome)
- `services/analytics/attendance_monitor.py`
- `services/compliance/lkpm_deadline_notifier.py`
- `services/compliance/visa_expiry_team_notifier.py`
- `services/crm/birthday_notifier_service.py`
- Cron notifier chains

### Bug 2 ⚠️ PARTIALLY CONFIRMED — welcome_email_service idempotency

**File:** `backend/services/crm/welcome/welcome_email_service.py:244-270`

Actual behavior (re-read fresh):

- Line 244-249: raw httpx POST
- Line 251: `if resp.status_code == 200:` → only then inserts
  notification_alerts idempotency marker
- Line 264-270: else branch → logger.error, **no marker inserted**

**Verdict:** The idempotency marker IS only written on 200. The mapped bug
was incorrectly stated. However there are three real issues:

1. The httpx POST is **not wrapped in try/except**. An exception
   (connection refused, timeout) propagates up to `process_pending_welcome_emails`
   line 141-143 which counts it as `failed`. The welcome row was already
   DELETEd on line 130-133, so the email is lost — no retry, no alert.
2. No Telegram/DB alert fires on welcome failure.
3. Exception swallowed silently if brochure attachment URL is down
   (line 224 else branch logs warning but proceeds with payload _without_
   attachment). Client receives a technically-ok email missing the brochure,
   never learns.

### Bug 3 ✅ CONFIRMED — cron notifiers return 200 on partial failure

**File:** `backend/app/routers/cron_notifiers.py:236-292` (`/all` endpoint)

Every sub-notifier in `/all` is wrapped in individual try/except that sets
`results["<name>"] = {"error": str(e)}` and continues. The outer endpoint
returns the merged dict with HTTP 200 unconditionally. External monitor
that only checks status code sees green.

The **individual** endpoints (visa-expiry, unpaid-invoices, stale-practices,
lkpm-deadlines, welcome-pending, birthday) have no outer try/except at all:
if the sub-service's `check_and_notify()` raises, FastAPI returns 500. But
internal failures within `check_and_notify()` (per-recipient email failures)
are swallowed by internal_email.py (Bug 1 chain).

### Bug 4 ✅ CONFIRMED — portal_notification_service silent insert failure

**File:** `backend/services/portal/portal_notification_service.py:90-122`

`_insert_message` catches `Exception`, logs, returns `None`. Caller in
`crm_practices.py:1154-1175` uses `spawn(...)` with try/except wrapping
the coroutine creation (not the execution). Exception inside the awaited
coroutine is logged but does not propagate to status update endpoint.

**Impact:** Client portal loses status-change notification. Client
unaware that practice moved to `waiting_documents`, `sending_invoice`, etc.
Activity log still records "status changed" at practice level, so team side
appears successful. Only client portal is silent.

### Bug 5 ✅ CONFIRMED — waiting_documents Brevo→Zoho fallback silent

**File:** `backend/services/crm/waiting_documents_service.py:217-239`

Primary send block (line 221-231): try/except catches Brevo failure, logs
warning. Fallback to Zoho (line 235-239): `await self.zoho_email_service.send_email(...)`
is called **unwrapped**. If Zoho ALSO fails, exception propagates up to
outer try/except in `trigger_on_waiting_documents` line 89-90 (team leader
branch) or line 104-105 (client branch) which logs `logger.error("Failed to
notify ...")` and sets flag to False. `results` dict is returned with
`team_leader_notified=False` / `client_notified=False`, but **no alert is
raised anywhere**.

**Impact:** When both Brevo and Zoho are down (or email addresses rejected
by both), waiting-documents notifications are completely lost. Client never
learns documents are needed → practice stalls indefinitely.

### Bug 6 ✅ CONFIRMED — completed_process_service partial Drive upload

**File:** `backend/services/crm/completed_process_service.py:142-170`

Per-document `for` loop with per-iteration try/except at line 167-168.
On exception, logs `logger.error` and continues to next document. Successful
uploads added to `uploaded` list; failed ones silently missing from the list.

Line 184-187 builds `docs_section` from `uploaded` only. Client email line
202 includes "All your important documents are safely stored..." implying
completeness. Client has no indication that 1 of 3 expected documents
failed to upload.

**Impact:** Client celebrates completion but is missing authoritative
documents (passport scan, visa, certificate). Team leader notification
line 235-264 does not mention counts either.

### Bug 7 ✅ CONFIRMED — completed_process_service Brevo→Zoho fallback silent

**File:** `backend/services/crm/completed_process_service.py:266-290`

Identical pattern to Bug 5: Brevo try/except catches, logs warning, falls
through to Zoho. Zoho call is unwrapped. If both fail, the exception
propagates up to lines 91-92 (client) or 105-106 (team) where it's caught
and logged. `client_notified=False` / `team_notified=False` returned,
no alert.

### Bug 8 ✅ CONFIRMED — \_notify_hr_bonus_pending failure silent

**File:** `backend/app/routers/crm_practices.py:162-191`

Function `_notify_hr_bonus_pending` calls `send_internal_email(...)` at
line 186-191 with default `raise_on_failure=False`. Since `send_internal_email`
never raises, failure is swallowed at the `internal_email.py` layer.

`_create_hr_bonus_on_completed` (the caller, line 155-157) awaits but is
itself wrapped in try/except that only logs (line 158-159). The HR bonus
ledger row is successfully written, but Asya is never told. `hr_bonus_ledger`
row sits at `status='pending'` forever unless Asya polls.

---

## Additional bugs found (not in the original 8)

### Bug 9 ⚠️ LOW-PRIORITY — invoice_service HTTP errors on client email swallowed

**File:** `backend/services/invoicing/invoice_service.py:129-137`

Explicit try/except chain catches `httpx.HTTPStatusError`, `httpx.HTTPError`,
and bare `Exception`. `email_sent = False` is recorded in invoice_info and
persisted to `invoices` table. Asya gets a notification (Step 4) but if Step
3 failed, `email_sent_to_client=False` in DB — Asya has to know to check
this column. No proactive alert.

**Impact:** Client may not receive invoice but invoice row exists; client
gets no email; AR aging starts; collection chain is broken until Asya
manually spots `email_sent=false` during ledger review.

### Bug 10 ⚠️ LOW-PRIORITY — invoice_service Drive upload failure continues silently

**File:** `backend/services/invoicing/invoice_service.py:167-186`

Drive upload failure → continues. `drive_file_id` and `drive_web_link` are
None in invoice_info. The client email (already sent) has only the PDF
attached, no Drive link — this is actually fine. The team loses the backup
though: no Drive audit trail. Logger warning only.

### Bug 11 ⚠️ CONFIRMED — `portal_notification_service.notify_practice_status_changed`

practice_type fallback to "Practice"

**File:** `backend/app/routers/crm_practices.py:1160-1164`

```python
pt_row = await conn.fetchrow(
    "SELECT code FROM practice_types WHERE id = $1",
    updated_practice.get("practice_type_id"),
)
practice_type = (pt_row["code"] if pt_row else None) or "Practice"
```

If `practice_type_id` points to a deleted/missing practice_types row,
`practice_type` becomes the literal string "Practice", causing the client
to see: "Status update: Practice" / "Your Practice status has been updated
to Sending Invoice." Generic and confusing.

**Impact:** Client confusion; non-critical; low incidence (requires FK
violation).

### Bug 12 ⚠️ MEDIUM — welcome_email_service BCC admin even if admin == to

**File:** `backend/services/crm/welcome/welcome_email_service.py:200-205`

BCC is `settings.admin_notification_email` set unconditionally. If the
admin email equals `email` (client email) — unlikely but possible during
internal testing — duplicate delivery + disclosure. No guard.

### Bug 13 ⚠️ NOISE — welcome_email idempotency per (client_id, alert_type,

created_date) not per alert_type+client

**File:** `backend/services/crm/welcome/welcome_email_service.py:163-175` +
line 257

Idempotency check SELECTs `notification_alerts WHERE client_id=$1 AND alert_type=$2`
without a date bound (correct). But the INSERT uses `ON CONFLICT (client_id,
alert_type, created_date) DO NOTHING` — a composite involving created_date.
Two sends on different days to the same client won't collide. The SELECT
check catches this first (any date), so duplicates are only possible if
check-then-insert race happens across two cron workers. With
`welcome_email_queue` DELETE claim (line 130-133) serializing via row-level
DELETE-RETURNING, race is unlikely but not impossible if two workers
fetch 50-row batches that overlap and hit the queue before the first
DELETE commits.

**Verdict:** Theoretical race, low probability. Keep an eye on it.

---

## Non-bug verifications

### ✅ Welcome brochure URL exists (probable)

Cannot verify externally without a live fetch, but the URL is
`https://kita.balizero.com/static/brochure_balizero_en.pdf` and the
`/static/balizero-logo-clean.png` variant is referenced elsewhere and
known to resolve. 20s timeout is generous for a ~1-2MB PDF on Vercel CDN —
sufficient.

### ✅ funnel_email.py `/fire-due` cron coherent

Signed with `X-Internal-Key` header matching `INTERNAL_CRON_KEY` env.
Delegates to `fire_due(pool)` in `services/notifications/funnel_email/scheduler.py`
(not re-read, but call signature looks clean).

### ✅ InvoiceAutomationService does not use send_internal_email wrapper

Directly POSTs to `_EMAIL_API_URL`. Different exception handling surface
than Bug 1 chain; its failures ARE visible (HTTP error bubble up to
`email_sent=False` DB flag).

---

## Instrumentation strategy — single wrap in internal_email.py

Given 23 callers, wrapping each is expensive and risky. The strategy
adopted in Task 2:

1. Instrument `send_internal_email()` in `internal_email.py` to write
   pre/post records to `email_send_log` (new migration 126). A new
   `email_type` kwarg (default `"unknown"`) identifies the caller.
   Callers that handle critical emails (HR bonus, waiting_docs, completed,
   invoice, welcome) pass `email_type` explicitly.

2. Services that **do not** use `send_internal_email` (waiting_documents,
   completed_process, welcome, invoice — they all raw httpx POST) get a
   new tiny helper `log_email_attempt()` in
   `services/notifications/email_audit.py` so their retries and status
   propagate through the same `email_send_log` table.

3. Critical failure (non-zero `send_internal_email` exception path, or
   status != 200) sends Telegram alert to chat_id 1125336968 with a brief
   description.

4. `EmailHealthMonitor` (new file `services/email_health_monitor.py`)
   runs via cron `/api/cron/notifiers/email-health` every 30 min, retries
   `failed` + `retry_after<NOW()` rows, escalates stale, publishes daily
   report 08:00 WITA.

---

## Summary of bugs by status

| #   | Severity | File                                       | Status            |
| --- | -------- | ------------------------------------------ | ----------------- |
| 1   | HIGH     | internal_email.py                          | confirmed         |
| 2   | HIGH     | welcome_email_service.py                   | partial (revised) |
| 3   | HIGH     | cron_notifiers.py /all                     | confirmed         |
| 4   | HIGH     | portal_notification_service.py             | confirmed         |
| 5   | CRIT     | waiting_documents_service.py               | confirmed         |
| 6   | CRIT     | completed_process_service.py uploads       | confirmed         |
| 7   | CRIT     | completed_process_service.py emails        | confirmed         |
| 8   | HIGH     | \_notify_hr_bonus_pending                  | confirmed         |
| 9   | MED      | invoice_service client email               | new               |
| 10  | LOW      | invoice_service Drive                      | new               |
| 11  | LOW      | portal_notification practice_type fallback | new               |
| 12  | LOW      | welcome BCC no guard                       | new               |
| 13  | LOW      | welcome idempotency race                   | new (theoretical) |

Task 2 will fix 1, 3, 4, 5, 6, 7, 8, 9 (the operationally painful ones).
Bugs 10/11/12/13 left for a follow-up PR (noted in MEMORY).

---

**Next step:** Task 2 — apply minimal fixes, threading `email_type` through
callers.
