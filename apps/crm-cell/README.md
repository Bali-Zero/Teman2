# crm-cell

Sprint 3 W2 — light cell wrapping the existing CRM modules
(`apps/backend-rag/backend/services/crm/*`) without rewriting them.

The 14 CRM automations (W1.1 inventory) keep their current code. This cell
adds:

1. **Genome scar registry** — accumulate "what went wrong" across runs.
2. **HGT publisher** — broadcast structural patterns (not client PII) on
   confidence ≥ 0.7.
3. **ObservedShellBus event bridge** — durable run trace via `crm_welcome_runs`
   (mig 153 outbox pattern).
4. **Cell descriptor** (`cell.yaml`) validated by AdmissionTest.

## Runtime

`runtime: fastapi-inproc + pro-cron-suborganelle` — the cell IS the existing
FastAPI request cycle for the in-process modules
(`practice_status_listener`, `welcome_practice_service`, `enrichment.py`)
plus two Pro-only sub-organelles:

- **`drive_poll`** — every 5 min via Pro crontab
  (`scripts/drive_poll_cron.sh`). Pro-only because Fly auto_stop loses the
  Drive `page_token`.
- **`nightly_engine`** — daily 07:00 WITA via Pro crontab
  (`scripts/crm_automation_engine.py`).

## Events

**Outbound** (new): `crm_welcome_completed` (mig 153). Fires only when a
welcome flow completes ALL 4 sub-steps. Partial-failure rows are persisted
to `crm_welcome_runs` for audit but do NOT broadcast.

**Inbound**: existing `practice_changed`, `client_changed`,
`compliance_alert` channels.

## Symbiosis Law alignment

- Law 1 (single brain): CRM uses Gemini 3 Flash via existing GenAI client
  (no new LLM endpoints).
- Law 2 (data sovereignty): client_data_access=true. UU PDP scope. PII
  never crosses HGT publication boundary.
- Law 3 (event-driven): outbound via PG NOTIFY + outbox; consumes inbound
  channels via `practice_status_listener`.
- Law 4 (graceful degradation): 5 fallback modes (postgres_down,
  drive_unreachable, brevo_down, whatsapp_down, telegram_down).
- Law 5 (kill-switch): comment crontab + `CRM_LISTENER_DISABLED=1`.

See `cell.yaml` for the full 7 Leggi declaration.

## C2 (rule registry) — REJECTED, NEVER

Twenty CRM has a DB-backed workflow registry because it's multi-tenant
SaaS. We are not. Internally-authored automations belong in code/git,
never runtime-mutable DB config. Revisit only on SaaS pivot.

See `docs/sprint3/crm-cell-design.md` § "C2" and
`docs/sprint3/review-synthesis-2026-05-04.md` for full reasoning.
