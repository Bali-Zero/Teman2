---
date: 2026-06-04
domain: operations
client_case: false
study: doc-intake-unified FASE 1
sources:
  - apps/backend-rag/backend/services/crm/drive_poll_service.py
  - apps/backend-rag/backend/services/misc/autonomous_scheduler.py
  - apps/backend-rag/backend/services/integrations/zoho_email_service.py
  - ~/scripts/openclaw-cron/drive-poll.sh (Pro + Mini crontab)
---

# 01b — Document-Intake Sources: Google Drive + Zoho Email

Mapping of how documents enter Nuzantara via **Google Drive** and **Zoho Mail**,
existing hooks, and gaps for a unified automated document-intake.

---

## 1. GOOGLE DRIVE — status: **ACTIVE (event-driven pull, currently driven by Mini cron)**

Drive is NOT passive storage. There is a real new-file detection + OCR ingest pipeline.

### 1.1 Detection mechanism
- `backend/services/crm/drive_poll_service.py:206 poll_drive_changes()` →
  `:241 _do_poll_drive_changes()`.
  Uses the **Drive Changes API** with an incremental `page_token`:
  - `:261` reads `drive_poll_page_token` from `system_settings`.
  - `:267` first run seeds via `drive_service.get_start_page_token()`.
  - `:277` `drive_service.list_changes_since(page_token)` → list of changes.
  - `:285` persists `new_page_token` even on no-change.
  Wrapped in a `DriveCircuitBreaker` (`:34`) that opens after consecutive
  failures and sends a Telegram alert (`:102 _send_telegram_alert`).

### 1.2 Folder → client/company routing + OCR dispatch
- Builds 3 lookup maps from Postgres:
  - `client_drive_subfolders` (top-level + nested subfolders) → `:295`
  - `clients.google_drive_folder_id` (client root) → `:304`
  - `companies.google_drive_folder_id` / `tax_dept_folder_id` → `:315`
- For each new (non-folder, non-trashed) file:
  - parent in a **known client subfolder** → dispatches OCR via
    `crm_enhanced._dispatch_ocr_by_folder` (`crm_enhanced.py:861`), which
    delegates to `services/documents/ocr_dispatcher_service.dispatch_ocr_by_folder`.
  - parent in a **client/company root** → does NOT insert a document, but
    enqueues a **CRM-Guardian** semantic-summary refresh
    (`_enqueue_guardian_client` `:149`, `_enqueue_guardian_company_folder` `:178`).
  - **unknown parent** → resolves via `drive_service.get_file_metadata`, and if
    the grandparent is a known subfolder it **auto-registers** the nested folder
    into `client_drive_subfolders` for future polls (self-healing folder map).

### 1.3 Relevant client folders (canonical structure)
`google_drive_service.py:632 STANDARD_SUBFOLDERS`:
`00_Profile, 01_Immigration, 02_Company(+AKTA/NIB/NPWP/Profile Perseroan),
03_Tax(+SPT company/SPT personal/LKPM reports/NPWP personal), 04_Family, 99_Misc`.
Parent roots: `gdrive_individuals_folder_id` / `gdrive_companies_folder_id`
(`config.py:870`, env `GDRIVE_COMPANIES_FOLDER_ID`).
NOTE: `service_account_drive_service.py:84` records this constant pointed at a
**phantom (404) folder Feb–May 2026** — known prior scar, now resolved.

### 1.4 Scheduling — the load-bearing gotcha
- In-process scheduler task is **DISABLED**:
  `autonomous_scheduler.py:783 enabled=False` — comment: "DISABLED 2026-03-22:
  moved to Air cron (curl POST /api/admin/drive/poll every 5min). Fly.io
  auto_stop incompatible with internal polling."
- The actual trigger is the cron script
  `~/scripts/openclaw-cron/drive-poll.sh:27` → `POST {API_URL}/api/admin/drive/poll`
  (handled by `admin_drive_health.py:210` → `poll_drive_changes()`).
- **Pro crontab: this `*/5` job is COMMENTED OUT** ("DISABLED 2026-04-29 02:42
  hotfix backend down: drive_poll satura PG").
- **Mini crontab: ACTIVE** → `*/5 * * * * .../drive-poll.sh`.
  ⇒ Drive intake is **live, but it depends entirely on the Mini H24 cron**.
  Since the comment still references the **decommissioned Air** (2026-05-05),
  the scheduling story is stale/fragile — single point of failure on Mini, no
  in-app fallback.
- Token health: `scripts/drive_token_watchdog.py` runs every 6h via Pro crontab
  (`drive-watchdog`), alerts 7d before the 90-day OAuth expiry
  (`google_drive_tokens` table, migration_034).

**Verdict Drive: ACTIVE event-driven intake (Changes API + OCR dispatch +
Guardian refresh), but trigger is an external Mini-only cron with a stale
Air-era comment and a disabled in-process fallback.**

---

## 2. ZOHO EMAIL — status: **read/write API integrated, but NO document-intake (no auto-ingest of attachments)**

Contrary to the "probably nothing for reception" hypothesis, Zoho IS integrated
for inbox read + attachment download — but only as an on-demand mailbox UI/API,
NOT as an ingestion source.

### 2.1 What exists
- `services/integrations/zoho_email_service.py` (1236 lines) — full Zoho **Mail
  REST API** client (OAuth, not IMAP/SMTP):
  - `:320 list_emails(folder_id="inbox", is_unread=...)` — lists inbox, exposes
    `has_attachments` (`:384`).
  - `:426 get_email()` — reads a message, parses attachments (`:500 _parse_attachments`).
  - `:959 get_attachment(user_id, message_id, attachment_id) -> bytes` —
    **downloads attachment content**.
  - `:1004 upload_attachment`, send/reply/forward, mark read/flag.
- OAuth: `zoho_oauth_service.py`, router `admin_zoho_auth.py`, migration_030.
- Routers `zoho_email.py`, `admin_email_health.py` (registered in
  router_manifest / router_registration).
- `zoho_invoice_service.py` — separate Zoho Invoice integration.

### 2.2 What is MISSING (the gap)
- **No scheduled Zoho poll**: zero refs to Zoho in `autonomous_scheduler.py`.
- **No Zoho cron**: nothing in Pro or Mini crontab (`grep -i zoho` empty).
- **No auto-ingest**: grep for zoho × (ocr|ingest|dispatch|document|intake)
  returns NOTHING. `get_attachment()` bytes are served to the frontend mailbox
  UI on demand — they are never routed into OCR / `client documents` / Drive.
- No webhook receiver for inbound Zoho mail.

NOTE on Brevo: Brevo is **send-only** (`zantara@balizero.com` via
`/api/notifications/send-email`) — confirmed not a reception path.

**Verdict Zoho: mailbox CRUD + attachment download EXIST, but there is NO
document-intake from email. Attachments are never auto-extracted, classified,
OCR'd, or filed to a client. For intake purposes Zoho is effectively absent.**

---

## 3. GAPS to wire an automated unified document-intake

### Drive
1. **Kill the Air-era fragility**: drive-poll trigger lives only on Mini cron with
   a stale comment. Options: (a) re-enable the in-process scheduler task guarded
   by a Fly-compatible flag, or (b) make the cron a first-class, monitored organ
   on both Pro+Mini with leader-election (avoid active-active double-OCR, cf.
   mata_garuda dup scar). Add liveness alerting on the `/api/admin/drive/poll`
   200-rate, not just token expiry.
2. **PG-saturation guard**: the 2026-04-29 disable reason ("drive_poll satura PG")
   is unresolved at root — any re-enable needs batching / rate-limit on OCR
   dispatch fan-out.

### Zoho
3. **Add an inbound poll service** mirroring `drive_poll_service`: scheduled
   `list_emails(inbox, is_unread=True)` → for each with `has_attachments`,
   `get_attachment()` → route bytes into the SAME OCR dispatcher
   (`ocr_dispatcher_service.dispatch_ocr_by_folder`) used by Drive, after
   resolving sender→client (CRM email match) and a target subfolder
   (e.g. `99_Misc` or doc-type classification). A read-cursor (Zoho message id /
   `received_unread`) is the email analogue of Drive's `page_token`.
4. **Sender→client resolution** is the hard part: map `from` address to a
   `clients` row (the CRM already reconciles client emails — migration 166
   `reconcile_client_email_duplicates`). Unmatched senders → quarantine queue.
5. **Idempotency**: dedupe by (message_id, attachment_id) so re-polls don't
   re-ingest; persist processed-attachment ledger.

### Unified
6. Both sources should converge on **one ingest entrypoint**
   (`dispatch_ocr_by_folder` + CRM-Guardian summary refresh) so Drive and Email
   produce identical downstream document records. The OCR dispatcher already
   exists and is source-agnostic — that is the natural unification point.

---

## Cited paths
- `apps/backend-rag/backend/services/crm/drive_poll_service.py:206,241,277,861-ref`
- `apps/backend-rag/backend/services/misc/autonomous_scheduler.py:767-786` (enabled=False)
- `apps/backend-rag/backend/app/routers/admin_drive_health.py:210`
- `apps/backend-rag/backend/services/integrations/google_drive_service.py:632`
- `apps/backend-rag/backend/app/core/config.py:870` (GDRIVE_COMPANIES_FOLDER_ID)
- `apps/backend-rag/backend/services/integrations/service_account_drive_service.py:84,100`
- `apps/backend-rag/backend/app/routers/crm_enhanced.py:861` (_dispatch_ocr_by_folder)
- `apps/backend-rag/backend/services/integrations/zoho_email_service.py:320,426,500,959,1004`
- `~/scripts/openclaw-cron/drive-poll.sh:27` ; Pro crontab (drive-poll DISABLED) ; Mini crontab (drive-poll `*/5` ACTIVE)
- `scripts/drive_token_watchdog.py` (Pro crontab, every 6h)
