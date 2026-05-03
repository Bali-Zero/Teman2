# Sprint 3 W1.1 — CRM automation inventory

**Date:** 2026-05-03 · **Author:** Sprint 3 Air session (Claude Opus 4.7 1M)
**References:**
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md` § Sprint 3
- `apps/backend-rag/CLAUDE.md` § "Compliance alerts" (deprecation map)

## Why this doc

Sprint 3 plan calls for consolidating "13 CRM automations" into a single
`crm-cell` (L1). Step zero is a **factual inventory** — who they are, where
they live, how they're triggered, what events they emit. The 99b synthesis
doc names only the three biggest by example
(\`crm_automation_engine\` + \`practice_status_listener\` +
\`proactive_compliance_monitor\`); the actual count is closer to 14 once
you include the engine's 5 sub-modules + the partner stack + Drive watch.

Without this inventory the cell-boundary discussion (W1.2) is groundless.
With it, we can decide per-module: **in-cell** / **stays-in-monolith** /
**dismiss**.

## Tier 1: top-level orchestrators (3)

These are the ones the synthesis doc names. They run on Pro via cron or
launchd, not as part of the FastAPI process.

### 1. `crm_automation_engine` — nightly batch orchestrator

- **File:** `apps/backend-rag/scripts/crm_automation_engine.py` (~600 LOC)
- **Schedule:** daily 07:00 WITA (23:00 UTC) via Pro crontab
- **Run mode:** standalone Python entry point with `asyncpg.Pool`
- **Sub-modules invoked in sequence** (5 — each a top-level `async def`):
  1. `run_data_quality(pool, dry_run=…)` — email normalization, status
     cleanup, doc URL backfill (lines 197-253)
  2. `run_lead_assignment(pool, dry_run=…)` — round-robin assignment to
     `SETUP_TEAM` (lines 255-307)
  3. `run_doc_checklist_populate(pool, dry_run=…)` — fills missing required
     docs per practice type from `PRACTICE_REQUIRED_DOCS` table (lines 308-345)
  4. `run_renewal_alerts(pool, dry_run=…)` — 90/60/30/7-day expiry alerts
     (lines 347-405)
  5. `run_stale_detector(pool, dry_run=…)` — escalates practices stuck >N days
     (lines 407-451)
- **Output:** single Telegram digest via `send_telegram` (lines 170-195),
  log to `apps/backend-rag/logs/crm_automation.log`
- **Event emission:** none (writes directly to `practices` / `clients` /
  `notification_log`, relies on table triggers from migrations 075/112/146
  to fire `practice_changed` / `client_changed` events)
- **DB tables touched:** `clients`, `practices`, `practice_required_docs`,
  `notification_log`, `system_settings`
- **Shared by other automations:** `SETUP_TEAM`, `STATUS_MAP`,
  `PRACTICE_REQUIRED_DOCS` constants — single source of truth

### 2. `practice_status_listener` — long-running PG LISTEN consumer

- **File:** `apps/backend-rag/backend/services/crm/practice_status_listener.py`
  (468 LOC)
- **Schedule:** runs in-process inside FastAPI (not cron) — daemon registered
  in app lifespan
- **Run mode:** `class PracticeStatusListener` LISTEN on `practice_changed`
  channel; on event, generates a milestone notification body via
  `_milestone_content()` and writes to `notification_log` for downstream
  Brevo / Telegram delivery
- **Event emission:** none (consumer-only, writes to `notification_log`
  rows that downstream dispatchers read; no PG NOTIFY of its own)
- **DB tables touched:** `practices` (read), `notification_log` (write),
  `notification_prefs` (read for client opt-out)
- **Cell candidacy:** consumer-style, fits naturally inside the cell as the
  ear of `practice_changed`

### 3. `proactive_compliance_monitor` — DEPRECATED but still imported

- **File:** `apps/backend-rag/backend/services/misc/proactive_compliance_monitor.py`
  (512 LOC)
- **Status:** deprecated 2026-04-18 per `apps/backend-rag/CLAUDE.md`:
  > "5-line deprecation warning only, logic untouched (scope exception,
  > decision #10)"
- **Replaced by:** `backend.services.compliance.alerts_engine.AlertsEngine`
  (`generate_alerts(forecasts)`)
- **Schedule:** (whatever invoked it before deprecation — currently inert
  because the warning prevents fresh imports from running)
- **Cell candidacy:** **DO NOT migrate**. Cell-cell consolidation is the
  right time to actually delete the shim and any remaining call sites.

## Tier 2: in-process services that emit / consume CRM events (8)

These live in `backend/services/crm/` and run as part of the FastAPI request
cycle, not cron. They're not "automations" in the synthesis sense (cron-driven
batch jobs), but the cell-boundary debate has to include them because they're
the ones writing to the same tables that Tier 1 watches.

| # | File | LOC | Role |
|---|---|---|---|
| 4 | `practices.py` (impliciti via `client_service` + `welcome_practice_service`) | various | core CRUD |
| 5 | `client_service.py` | ~600 | client CRUD |
| 6 | `assignment.py` | ~200 | assignment logic shared with engine |
| 7 | `automation.py` | ~150 | (not the engine — re-export hub for legacy callers) |
| 8 | `enrichment.py` | ~250 | data enrichment from external sources |
| 9 | `notifiers.py` | ~300 | Telegram / Brevo dispatchers consumed by listener |
| 10 | `welcome/welcome_practice_service.py` | ~400 | new client welcome flow (creates practice + sends welcome WA + Drive folder) |
| 11 | `partners/service.py` + `partners/events.py` + `partners/emails.py` | ~600 | partner commission tracking — emits `partner.commission_changed` (NOT in PG_CHANNEL_MAP, dotted name fails validation) |

**Cell candidacy split (W1.2 will decide):**
- `practices.py` / `client_service.py` / `assignment.py` — likely STAY in
  monolith (HTTP-layer CRUD, called from many routers).
- `automation.py` — re-export hub, dismiss when crm-cell consolidates.
- `enrichment.py` / `welcome/*` — hybrid: some logic moves into cell, some
  stays per cell-boundary draft.
- `notifiers.py` — moves into cell as part of practice_status_listener
  ownership.
- `partners/*` — separate domain, not part of the 13. Defer to a later
  Sprint or leave in monolith.

## Tier 3: long-running listeners + watchers (3)

Cron- or daemon-driven, but separate from the engine.

### 12. `drive_poll_service` — Drive change watcher

- **File:** `apps/backend-rag/backend/services/crm/drive_poll_service.py` (502 LOC)
- **Schedule:** every 5 min via Pro crontab (`scripts/drive_poll_cron.sh`)
- **Note:** **NOT on Fly.io** — auto_stop loses page_token. Documented in
  CLAUDE.md § "Drive Polling (Air only)".
- **Status:** has its own scar (drive_poll_service called missing method on
  ServiceAccountDriveService 2026-04-29). Currently disabled in Pro crontab
  with `# DISABLED 2026-04-29 02:42` per the cicatrix antibody.
- **Event emission:** writes Drive change rows to `client_drive_changes`,
  fires `client_changed` via the table trigger
- **Cell candidacy:** **YES, in-cell**. Drive ownership is squarely CRM.

### 13. `enrichment` background sweep

- **File:** `apps/backend-rag/backend/services/crm/enrichment.py`
  (background tasks side, not the request-time enrichment)
- **Schedule:** triggered ad-hoc + by `enrichment_worker` invoked from the
  engine OR from FastAPI background tasks
- **Status:** in active use, no scars
- **Cell candidacy:** in-cell once consolidated

### 14. `birthday_notifier_service`

- **File:** `apps/backend-rag/backend/services/crm/birthday_notifier_service.py`
- **Schedule:** daily via the engine OR direct cron (TBD — not visible in
  the engine source; check Pro crontab)
- **Cell candidacy:** in-cell

## Why "13" is approximate

The synthesis doc says "13 CRM automations". Empirical count is **14**:
3 Tier 1 + 8 Tier 2 + 3 Tier 3. The mismatch is most likely because:

- `proactive_compliance_monitor` (#3) is deprecated — counted as 1 by
  whoever wrote the synthesis, will become 0 when we delete it in W1.2
- OR `partners/*` (#11) is excluded as a separate domain — bringing
  the count to 13

W1.2 (design) will pick a definitive set; the count drops out of that
decision. The number doesn't matter — the boundary does.

## Trigger inventory (events that flow IN/OUT today)

Cell-boundary work needs to know what events the cell will speak.

### Inbound events (cell-cell candidates as CONSUMERS)

- `practice_changed` (mig 075) — emitted by `practices` table trigger.
  Consumed by `practice_status_listener` today; will be consumed by
  the cell going forward.
- `client_changed` (mig 076) — emitted by `clients` table trigger.
  Consumed by cache invalidation handlers (in-process FastAPI).
- `compliance_alert` (mig 076) — emitted by `compliance_alerts` table.
  Consumed by `alert_dispatcher` (NOT crm-cell scope; stays in
  compliance subsystem).

### Outbound events (cell-cell candidates as PRODUCERS)

- `partner.commission_changed` — DOTTED CHANNEL, fails Python-side
  `validate_channel` regex. **Must be renamed** to
  `partner_commission_changed` before any consumer can subscribe.
  Sprint 3 follow-up: register in PG_CHANNEL_MAP after rename.
- `crm.drive_change_detected` — NEW, proposed by W1.2. Currently
  drive_poll writes to `client_drive_changes` and the trigger fires
  `client_changed`; we may want a more specific channel.
- `crm.welcome_completed` — NEW, proposed. Emitted by
  `welcome_practice_service` after WA + Drive folder + practice row
  all succeed. Today it's a sequential service call; an event would
  let downstream observers (analytics, retention loop) react without
  coupling.

## Out-of-scope clarifications

- **Compliance alerts** (`alerts_engine`, `alert_dispatcher`,
  `compliance_alerts` table) — separate subsystem from CRM. Even though
  it's heavily integrated, the cell boundary keeps it OUT. Compliance
  has its own dedicated cell candidacy in Sprint 4 (per 99b § Sprint 4).
- **HR / payroll** (m066 series) — not CRM; out of scope.
- **Tax intelligence** (m115+) — not CRM; out of scope.

## Open questions for W1.2 (design)

1. Does `crm-cell` run **inside** the FastAPI process (same lifespan)
   or as a **separate Pro daemon** (like `wr2_supervisor`)?
   - In-process pros: shared db_pool, simple deployment.
   - Daemon pros: independent failure domain, doesn't take down
     FastAPI lifespan if cell crashes.
   - **Tentative recommendation:** in-process for Sprint 3, with the
     option to peel off later. The 14 modules already run in-process;
     making the cell a daemon means rewiring all of them.
2. How does the cell **declare** to the EventBus what it consumes?
   Today `PG_CHANNEL_MAP` is the registry. The cell adds itself by
   editing that constant — no new mechanism needed.
3. **Drive page_token on Fly.io** — drive_poll's reason for staying
   on Pro. The cell has the same constraint. Cell can have a
   "Pro-only sub-organelle" pattern (like WR2 has
   topic-selector/draft-generator on Pro only). W1.2 to decide.
4. **Genome integration** — does crm-cell get a `genome.yaml` entry
   in `apps/organism/organism/genome.yaml`? `nuz-sync` (cf. cicatrix)
   is explicitly excluded; this is the right time to set the
   precedent for crm-cell.

## What this doc does NOT decide

- The actual cell boundary (W1.2)
- The asset provenance schema (W1.3)
- The migration strategy (W2 — code)
- The HGT-relevant heuristics from the 14 modules (W1.2 + W2)

W1.2 picks up here.
