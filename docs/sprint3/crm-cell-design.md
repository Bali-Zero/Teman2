# Sprint 3 W1.2 — crm-cell design

**Date:** 2026-05-03 · **Author:** Sprint 3 Air session (Claude Opus 4.7 1M)
**Predecessors:** `docs/sprint3/crm-cell-inventory.md` (W1.1)
**References:**
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md` § Sprint 3
- `apps/bali-intel-scraper/cell.yaml` (light cell precedent)
- `packages/cell-core/cell_core/admission_test.py` (7 Leggi check framework)

> **DRAFT FOR USER REVIEW.** All architectural picks below are
> "conservative-default" — when two options were defensible I chose the
> one that minimizes blast radius and preserves rollback paths. Each pick
> has a section called "Reversal cost" so we can revisit it cheaply if
> Sprint 4-5 evidence pushes the other way.

## What we're building

A **light cell** wrapper around the existing CRM modules — same pattern
as `intel-scraper-cell` (Sprint 1). NOT a rewrite. The 14 modules from
W1.1 keep their current code; the cell adds:

1. **Genome scar registry** — accumulate "what went wrong" across runs.
2. **HGT publisher** — broadcast structural patterns on confidence ≥0.7
   (per Sprint 1 contract — propose-only quarantine via Kimi K2.6).
3. **ObservedShellBus event bridge** — durable run trace via
   `events_outbox` (mig 144 + 151).
4. **Cell descriptor** (`cell.yaml`) validated by `AdmissionTest`.

## The 4 open questions — picks

### Q1: in-process FastAPI vs separate Pro daemon?

**Pick: in-process** for Sprint 3, with a documented escape hatch to
peel off later.

**Why:**
- All 14 modules already run in-process (Tier 2) or as ad-hoc cron
  invoking the same `asyncpg.Pool` + `httpx.AsyncClient` (Tier 1).
  Making the cell a daemon means rewiring every module's connection
  + service injection.
- Existing cell precedent: `intel-scraper-cell` is `runtime:
  cron-agent-python` (per its `cell.yaml`) — that pattern is for
  scrapers that already run as standalone scripts. CRM is different —
  it's deeply integrated with FastAPI request handling.
- Failure isolation argument cuts both ways: if `crm-cell` blows up
  inside FastAPI, lifespan's existing `app.state.startup_failed`
  catch (per cicatrix § "Backend /health masks startup_failed")
  + Sentry redaction handle it. Going daemon adds a new failure
  domain to monitor (another LaunchAgent in the 53-plist landscape
  documented in cicatrix).

**Reversal cost (LOW):** the cell is defined by `cell.yaml` + a small
adapter module. Switching to daemon means writing a new
`scripts/crm_cell_daemon.py` entrypoint that imports the same
modules — ~150 LOC. The cell `cell.yaml` would need
`runtime: cron-agent-python` instead of `runtime: fastapi-inproc`.
No DB schema change.

**Decision:** `runtime: fastapi-inproc` in `cell.yaml`.

### Q2: PG_CHANNEL_MAP additions?

Three changes proposed in W1.1 inventory. Picks per change:

#### Q2a: Rename `partner.commission_changed` → `partner_commission_changed`?

**Pick: NO, NOT in this sprint.** The dotted name is a known issue
documented in cicatrix § "EventBus is PG LISTEN/NOTIFY" Phase-2
"Channels NOT in scope". It's emitted by `partners/events.py` which
is **partner domain, not CRM core** per W1.1 Tier 2 classification.

Renaming the channel touches: trigger function + Python emitter
+ any consumer + PG_CHANNEL_MAP entry. The trigger already runs in
production — the rename is reversible only by another migration.
Out-of-scope for crm-cell consolidation; track separately.

**Reversal cost (LOW):** decision to defer is itself reversible —
nothing is being changed.

#### Q2b: New `crm.drive_change_detected` channel?

**Pick: NO, reuse `client_changed`.** drive_poll today writes to
`client_drive_changes` table; the trigger fires `client_changed`.
That's already an outbox-backed durable channel. Adding a new
specific channel solves a problem we don't have (no consumer is
currently slowed down by needing to filter `client_changed` payloads).

Premature abstraction warning: when a real consumer needs Drive-only
events, add the channel then. Today's consumers (cache invalidation,
practice listener) are happy with the broader `client_changed`.

**Reversal cost (LOW):** if a future consumer needs the specific
channel, add a new trigger on `client_drive_changes` + new
PG_CHANNEL_MAP entry — one migration, one Python edit. No data
backfill needed (events are forward-flowing).

#### Q2c: New `crm_welcome_completed` channel?

**Pick: YES, but as a Sprint 3 W2 deliverable** (not part of this
design doc). Welcome flow is the one place where CRM has multiple
cooperating side effects (practice row INSERT + Drive folder + WA
message + Brevo email) that downstream observers (analytics,
retention loop, future onboarding cell) will want to react to as
ONE atomic event. Today they have to scrape 3-4 separate signals.

Channel name: `crm_welcome_completed` (underscores per validate_channel
regex). Migration: AFTER INSERT trigger on a yet-to-be-created
`crm_welcome_runs` table that the welcome service writes when all
sub-steps succeed. Migration target: 153.

**Reversal cost (MEDIUM):** once the channel ships, consumers can
subscribe; removing it means coordinating with consumers. But for
Sprint 3 scope, we just commit to ADDING it in W2. Backout = revert
the migration.

### Q3: Drive page_token Pro-only sub-organelle?

**Pick: YES — Pro sub-organelle pattern,** mirroring WR2's
topic-selector / draft-generator.

The constraint is real and documented (CLAUDE.md § "Drive Polling
(Air only)"): Fly auto_stop loses page_token, so drive_poll cannot
run on Fly. The cell concept tolerates this — `cell.yaml` declares
`runtime` which can be a list of locations, and the cell-core
admission framework already accepts mixed-deployment cells.

The sub-organelle is just `drive_poll_service` + its 5-min cron
wrapper (`scripts/drive_poll_cron.sh`). Everything else in
crm-cell is in-process FastAPI on Fly.

**Reversal cost (NONE for this decision):** drive_poll is already
Pro-only today. The "decision" is just acknowledging it in the
cell descriptor.

**`cell.yaml` representation:**
```yaml
runtime: fastapi-inproc + pro-cron-suborganelle
sub_organelles:
  - name: drive_poll
    location: pro
    schedule: "*/5 * * * *"
    script: scripts/drive_poll_cron.sh
    constraint: page_token_persistence_required
```

### Q4: Genome integration in `apps/organism/organism/genome.yaml`?

**Pick: YES, register crm-cell in genome.yaml.** Different rationale
from `nuz-sync`'s exclusion (cicatrix § "Untracked files lost when
sibling automation switches branches").

`nuz-sync` is excluded because **it's the suspected branch-hijack
producer** — auto-recovery during a hijack-in-progress would amplify
blast radius. crm-cell has no such structural risk:

- It doesn't switch branches (no git invocations).
- It doesn't write to `~/Library/LaunchAgents/` (cicatrix §
  "Unknown agent overwrites loaded LaunchAgent plist files" producer
  unidentified, but crm-cell is read-only against launchd).
- It runs in-process, so failure → FastAPI lifespan handles it,
  not the supervisor.

What genome.yaml inclusion BUYS: the supervisor can detect crm-cell
runtime issues via the existing pulse loop (cell pulse → green/yellow/
red classification per cicatrix § "Backend /health masks
startup_failed"). For a cell that runs in-process, this is essentially
free — the FastAPI healthcheck already exists.

**Reversal cost (LOW):** remove the genome.yaml entry. Cell still
runs without supervisor monitoring (just lacks centralized health
view).

## Cell boundary — what's IN vs OUT

Per W1.1 inventory, 14 modules. The boundary picks:

### IN-CELL (8)

| # | Module | W1.1 Tier | Why in cell |
|---|---|---|---|
| 1 | `crm_automation_engine` (orchestrator + 5 sub-modules) | T1 | The whole cron job is the cell's heartbeat |
| 2 | `practice_status_listener` | T1 | LISTEN consumer of `practice_changed`, the cell's primary inbound event |
| 4 | `notifiers.py` | T2 | Read by listener; tightly coupled |
| 5 | `welcome/welcome_practice_service.py` | T2 | Multi-step orchestration that produces the new `crm_welcome_completed` event |
| 6 | `welcome/welcome_email_service.py` | T2 | Sub-step of welcome |
| 7 | `welcome/welcome_whatsapp_service.py` | T2 | Sub-step of welcome |
| 8 | `drive_poll_service` (Pro sub-organelle) | T3 | Drive owns CRM client folder hierarchy |
| 9 | `birthday_notifier_service` | T3 | Date-driven nudge cron in same family |

### STAYS-IN-MONOLITH (4)

These are HTTP-layer CRUD with many callers — moving them is a refactor
beyond cell-cell consolidation scope.

| # | Module | Reason |
|---|---|---|
| 10 | `practices.py` (implicit core CRUD) | Used by every `/api/practices/*` router |
| 11 | `client_service.py` | Used by every `/api/clients/*` router |
| 12 | `assignment.py` | Cross-cutting; engine + portal both use it |
| 13 | `enrichment.py` (request-time + background) | Hybrid; the cell uses it as a library |

The cell **calls** these from in-process; they remain library-style
modules. The cell DOES NOT own their HTTP routes.

### DISMISS (2)

| # | Module | Action |
|---|---|---|
| 14 | `proactive_compliance_monitor` | Already deprecated (CLAUDE.md). DELETE in W2 along with all import sites. Replaced by `AlertsEngine` (compliance domain, not crm-cell). |
| 15 | `automation.py` (CRM re-export hub) | Once crm-cell consolidates, this re-export is dead weight. DELETE in W2 with grep verification. |

(Counts: 8 in + 4 stay + 2 dismiss = 14, matching W1.1 inventory.)

## Cell descriptor (`cell.yaml`)

Following the `intel-scraper-cell` template:

```yaml
# crm-cell — Sprint 3 W2
# Reference: docs/sprint3/crm-cell-design.md
# Validated against 7 Leggi via packages/cell-core/cell_core/admission_test.py.

name: crm-cell
version: 0.1.0
level: L1
runtime: fastapi-inproc + pro-cron-suborganelle
owner: crm-team

cell_class: cell

# 7 Leggi declarations
exposes_gui: false
llm_invocation: gemini_3_flash   # used by enrichment.py via existing GenAI client
external_sources:
  - google_drive_api      # via service account, drive_poll only
  - brevo_api             # transactional emails (zantara@balizero.com only)
  - whatsapp_business_api # welcome_whatsapp_service
  - telegram_bot_api      # notifiers (Zero + team alerts)
client_data_access: true  # CRM IS the client data domain — UU PDP scope
publishes_via: pg_notify  # via existing client_changed / practice_changed
                          # triggers + new crm_welcome_completed (mig 153)
fallback_modes:
  - postgres_down            # FastAPI lifespan handles via existing graceful degradation
  - drive_unreachable        # circuit breaker in drive_poll_service (3-fail open)
  - brevo_down               # email queued in notification_log, retry from there
  - whatsapp_down            # message queued, retry on next welcome run
  - telegram_down            # alerts swallowed (best-effort), logged
kill_switch: true            # disable engine: comment out crontab; disable listener:
                             # CRM_LISTENER_DISABLED=1 env var (to be added in W2)
auto_publishes: false        # all client comms go through human-gate or RBAC-bound API
depends_on_other_cell_decisions: false   # CRM operates on its own data; consumes
                                         # client/practice events but doesn't wait
                                         # on other cells' verdicts before acting

sub_organelles:
  - name: drive_poll
    location: pro
    schedule: "*/5 * * * *"
    script: scripts/drive_poll_cron.sh
    constraint: page_token_persistence_required
    cell_pulse: heartbeat_via_circuit_breaker_state
  - name: nightly_engine
    location: pro
    schedule: "0 23 * * *"   # 07:00 WITA = 23:00 UTC
    script: scripts/crm_automation_engine.py
    constraint: none

genome_integration:
  registered: true
  reason: |
    crm-cell is structurally distinct from nuz-sync (which is excluded per
    cicatrix § "Untracked files lost"). It does not switch git branches,
    does not write to ~/Library/LaunchAgents/, runs in-process. Supervisor
    pulse adds value for centralized health view.
  pulse_endpoint: /health     # existing FastAPI healthcheck

events:
  inbound:
    - practice_changed         # mig 075, consumed by practice_status_listener
    - client_changed           # mig 076, consumed by cache invalidation
    - compliance_alert         # mig 076, consumed for context (not action)
  outbound:
    - practice_changed         # via existing trigger when engine writes
    - client_changed           # via existing trigger when engine writes
    - crm_welcome_completed    # NEW (mig 153 in W2) — emitted on welcome
                               # multi-step success. Payload: {client_id,
                               # practice_id, drive_folder_id, channels_sent[],
                               # event_type='welcome_completed', occurred_at}

metrics:
  - practices_quality_fixes
  - leads_assigned
  - doc_checklists_populated
  - renewal_alerts_sent
  - stale_practices_escalated
  - welcome_runs_completed
  - drive_changes_processed
  - listener_events_consumed
  - listener_lag_seconds   # NEW — events_outbox row age at consumption
```

## Migration impact summary (for W2 planning)

- **Migration 153:** `crm_welcome_runs` table + AFTER INSERT trigger
  emitting `crm_welcome_completed` to events_outbox + pg_notify.
  Mirrors mig 152 pattern (see `docs/wr2/sprint2-mapping.md` § "L1 —
  measurer" for reference).
- **`PG_CHANNEL_MAP`** — add `"crm_welcome_completed":
  "crm.welcome_completed"` entry in
  `apps/backend-rag/backend/services/events/event_bus.py`.
- **Test mirroring:** `backend/tests/db/test_migration_153.py`
  following `test_migration_152.py` template (11 contract tests for
  trigger function dispatch, outbox-before-notify ordering,
  `_outbox_id` injection, ROLLBACK marker, idempotent re-run).
- **Cell descriptor:** `apps/cell-crm/cell.yaml` (new app dir under
  `apps/`, mirrors `apps/bali-intel-scraper/cell.yaml`).
- **Adapter module:** `apps/cell-crm/cell_crm/__init__.py` exposing
  `crm_cell` instance with `genome`, `hgt_publisher`, `event_bridge`
  attributes. ~80 LOC.
- **Admission test:** `packages/cell-core/tests/test_admission.py`
  add a `test_crm_cell_admission()` function loading the new
  `cell.yaml` and asserting all 7 Leggi pass.

## What this doc does NOT decide

- **Q2c migration 153 schema details** (column types, FKs) — W2 work.
- **`proactive_compliance_monitor` deletion plan** (grep-verify all
  callers, deprecation period) — W2 work.
- **`automation.py` re-export hub deletion** — W2, after grep
  confirms no live import sites.
- **Listener lag SLO threshold** (when does listener_lag_seconds
  trigger an alert?) — W2 ops decision, not architectural.
- **Mata-Garuda cell innervation cross-event design** (W1.3 territory).

## Risks called out

1. **Welcome flow has 4 sub-steps with different failure semantics.**
   Today they're called sequentially with try/except scattered. The
   `crm_welcome_completed` event MUST only fire on full success
   (all 4 sub-steps green). Failure modes need explicit handling
   in W2 (idempotent retry on partial failure → eventual emit).
2. **Listener lag is unmeasured today.** PR #439 verification
   workflow (#442) sets the precedent for measuring outbox lag —
   crm-cell should adopt the same pattern. Add to W2 backlog.
3. **Drive page_token loss is catastrophic** (CLAUDE.md says full
   re-scan). Cell should expose a "page_token_age_hours" metric so
   the supervisor can surface staleness BEFORE token expiration.
4. **Pro vs Air symmetry:** the engine runs on Pro crontab, but
   the FastAPI listener runs wherever the deploy is (Fly). If Pro
   is down, the engine doesn't fire — listener still works on Fly.
   Asymmetric availability is documented; no fix needed.

## Open question for W1.3 (Mata-Garuda)

**What does crm-cell consume from mata-garuda-cell?** Per 99b
synthesis: "Innervation incrociata bidirezionale Mata-Garuda ↔ WR2".
WR2 is mentioned, CRM is not. But Mata-Garuda's asset provenance
(W1.3 scope) seems CRM-relevant: when an enrichment lookup pulls
data from a non-Bali Zero source, the cell should be able to query
"who is the owner / what's the invalidation path?" before consuming
it.

Picked up in W1.3.

---

## ADDENDUM 2026-05-04 — Research-driven refinements

After Zero requested research on production CRM event-driven
systems (see [`research-and-brainstorm.md`](research-and-brainstorm.md)),
the design above is **validated unchanged** — no architectural
pivot needed. Two clarifications below.

### C1 — Confirmed default: in-process FastAPI cell, no daemon

**Validation:** Twenty CRM (the highest-star OSS CRM at our
scale, TypeScript+NestJS+PostgreSQL+BullMQ) uses the same pattern
— record-event triggers fire workflow handlers on shared workers,
not separate daemons. EspoCRM and SuiteCRM both keep their workflow
engines in-process. Our Q1 pick (in-process) is the industry
default at our scale (5000 clients, ~150 events/day).

**No change to migration plan**: 153 (`crm_welcome_completed`
trigger) + cell adapter ~250 LOC + admission test. Ships as
designed.

### C2 — Optional automation rule registry table — DEFERRED to Sprint 4+

**Research finding:** Twenty CRM has explicit workflow versioning
(each rule = versioned record in DB, Zero could pause/resume via
UI). EspoCRM stores workflow definitions in a dedicated table.
Our 13 automations are imperative Python today.

**Decision:** Defer the rule registry to Sprint 4+. Reasons:

1. **Premature abstraction at 13 rules.** Twenty CRM justifies it
   because users define their own workflows; we have only 13
   internally-authored automations. Building a registry to
   manage 13 hard-coded modules adds plumbing without payoff.
2. **Sprint 3 W2 already at +1 day from M1 (mata-garuda 3-layer
   schema).** Adding C2 would push W2 beyond comfort.
3. **Reversal cost is symmetric**: building C2 in Sprint 4
   costs the same as building it in Sprint 3 (~0.5 day for
   migration + cell-config-sync logic).

**Trigger to revisit:** when we hit ≥25 automations OR when Zero
requests Telegram-controllable pause/resume per rule. Whichever
comes first.

### LISTEN/NOTIFY scaling — confirmed safe at our scale

**Research finding:** PG LISTEN/NOTIFY breaks at `max_connections`
exhaustion (one listener = one connection). No quantitative
events/sec ceiling published by Postgres team, but anecdotal
production data: ~10K notify/sec on a single connection works.
PgDog proxy + logical replication outbox are the workarounds at
scale.

**Our scale:** ~150 events/day total (50 practice + 100 drive).
**Three orders of magnitude below the ceiling.** Direct LISTEN +
existing migration 146 outbox pattern is correct. No PgDog or
logical-replication migration needed for years.

### Drive polling — confirmed correct (no webhook pivot)

**Research finding:** Google Drive Activity API webhook push is
**not used in production CRM** at our scale because (a) cold-start
of webhook handler can take 2-30s on the consumer side,
(b) webhook reliability requires public HTTPS endpoint with retry
infra, (c) page_token loss on cold start = full re-scan = expensive.
Polling-every-5-min with persistent page_token in `system_settings`
is the production-proven pattern.

**Our design:** matches exactly. No change.

### What this addendum DOES decide

✅ C1 (in-process FastAPI cell) — confirmed, ships in W2.
✅ C2 (rule registry) — deferred to Sprint 4+.
✅ Direct PG LISTEN/NOTIFY — kept (no PgDog/logical-replication
   pivot needed for 2-3 years at current event rate).
✅ Drive polling-only — kept (no webhook adoption).

### What this addendum does NOT decide

❌ Whether crm-cell publishes any provenance rows itself or only
   queries Mata-Garuda's. Picked up in W2 once mata-garuda
   adapter API stabilizes.
❌ Whether automation rule retries get an exponential-backoff
   shared library — Sprint 4+ together with C2.
