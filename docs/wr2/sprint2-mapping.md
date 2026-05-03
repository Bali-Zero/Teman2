# WR2 mapping — Sprint 2 (cognitive levels + event contracts)

**Date:** 2026-05-03 · **Author:** Sprint 2 Air session (Claude Opus 4.7 1M)
**References:**
- `docs/audits/sprint0/wr2-ipc-mechanism.md` — audit IPC compliance with Symbiosis Law 4
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md` § Sprint 2

## Why this doc

Sprint 0 audited each WR2 LaunchAgent for Symbiosis Law 4 compliance
(Event-driven). Sprint 2 needs the operational counterpart: a **mapping**
that, for every WR2 organelle, pins down (1) cognitive level — connector
L1 / supervisor L2 / strategos L3 / oracle L4, (2) the precise event
contract it emits or consumes, (3) which downstream consumers depend on
it. The mapping is the SSOT consulted before any change to a WR2 plist
or any new consumer wiring.

> Cognitive levels are an architectural classification, NOT a "complexity"
> ranking. L1 = ground-truth ingest / signal extraction / metric capture.
> L2 = orchestrator / proxy / consumer (no creative output). L3 = synthesis
> across L1 outputs (briefs). L4 = strategic recommendations (oracle decides
> nothing — the war-room operators do).

## Cognitive level legend

| Level | Role | Example outputs |
|---|---|---|
| **L1** | Ground-truth ingest, signal extraction, metric capture, learning loops | trend signals, post metrics, dossiers, KG learner |
| **L2** | Orchestration / consumer / infrastructure | supervisor (LISTEN-only), pg-proxy (TCP), sla-worker (timeout sweep) |
| **L3** | Synthesis across L1 outputs | weekly_strategic_briefs |
| **L4** | Strategic recommendations | ultra_moves, anomaly alerts, cross-dossier theses |
| **operational** | War-room production pipeline (drafts → posts) | topic-selector, draft-generator, image-generator, canva-apply, newsletter |

## The 17 WR2 organelle (LaunchAgent inventory)

Source: `infra/launchagents/com.balizero.wr2.*.plist`. The Pro-only operational
organelle (topic-selector, draft-generator, image-generator, canva-apply)
are sourced from `scripts/wr2_*.py` and registered in launchd on Pro.

| # | Organelle | Plist | Cognitive Level | Producer / Consumer | Event-driven? |
|---|---|---|---|---|---|
| 1 | `connector` | `com.balizero.wr2.connector.plist` | L1 | producer | ✅ |
| 2 | `dossier-compiler` | `com.balizero.wr2.dossier-compiler.plist` | L1 | producer | ✅ |
| 3 | `learner-nightly` | `com.balizero.wr2.learner-nightly.plist` | L1 | producer | ✅ |
| 4 | `measurer` | `com.balizero.wr2.measurer.plist` | L1 | producer | ✅ (Sprint 2 W1, mig 152) |
| 5 | `trend-hunter` | `com.balizero.wr2.trend-hunter.plist` | L1 | producer | ✅ |
| 6 | `pg-proxy` | `com.balizero.wr2.pg-proxy.plist` | L2 (infra) | substrate | n/a (TCP) |
| 7 | `sla-worker` | `com.balizero.wr2.sla-worker.plist` | L2 | producer (status update) | ✅ |
| 8 | `supervisor` | `com.balizero.wr2.supervisor.plist` | L2 | consumer (LISTEN) | ✅ |
| 9 | `strategos` | `com.balizero.wr2.strategos.plist` | L3 | producer | ✅ |
| 10 | `oracle` | `com.balizero.wr2.oracle.plist` | L4 | producer | ✅ |
| 11 | `topic-selector` | `com.balizero.wr2.topic-selector.plist` | operational | producer (dual emitter) | ✅ |
| 12 | `draft-generator` | `com.balizero.wr2.draft-generator.plist` | operational | producer | ✅ |
| 13 | `image-generator` | `com.balizero.wr2.image-generator.plist` | operational | producer | ✅ |
| 14 | `canva-apply` | `com.balizero.wr2.canva-apply.plist` | operational | producer | ✅ |
| 15 | `newsletter` | `com.balizero.wr2.newsletter.plist` | operational | producer | ✅ |
| 16 | `hardening` | `com.balizero.wr2.hardening.plist` | operational (maintenance) | producer (filesystem + Telegram) | ⚠️ observed-shell tier (Sprint 2 W3) |
| 17 | `canva-renderer` | `com.balizero.wr2.canva-renderer.plist` | operational (legacy) | filesystem-only | ⚠️ orphan — pending dismissal |

## Event contracts (per organelle)

The contract for each organelle has a stable shape:

```
{
  "channel": "<pg_channel name>",
  "event_type": "<dotted name returned by EventBus>",
  "trigger_table": "<table whose AFTER INSERT/UPDATE fires the trigger>",
  "trigger_migration": "<migration file that defines the trigger>",
  "payload_schema": { "<field>": "<type>", ... },
  "consumers": [ "<who LISTENs>" ],
  "trace_id_field": "<field used for cross-organelle correlation>",
  "artifact_uri_field": "<field carrying durable URI to artifact, when applicable>"
}
```

For payloads:
- Every channel injects `_outbox_id` (BIGINT) automatically per migration 146
  contract. Consumers must dedup on it for replay safety.
- `occurred_at` is always TIMESTAMPTZ. Trigger expressions use the row's
  timestamp column (e.g. `NEW.created_at`, `NEW.collected_at`,
  `NEW.retrained_at`) when available, else `NOW()`.
- Triggers wrap `INSERT INTO events_outbox` THEN `pg_notify(...)` in the
  user transaction (mig 146 pattern). Rollback erases both consistently.

### L1 — connector

```yaml
channel:           cognitive_event
event_type:        cognitive.event
trigger_table:     cross_dossier_theses
trigger_migration: 114_cognitive_layer_tables.sql + 146_eventbus_triggers_use_outbox.sql
payload_schema:
  id:                BIGINT
  table:             "cross_dossier_theses"
  event_type:        "thesis_created"
  occurred_at:       TIMESTAMPTZ
  thesis_id:         UUID
  topic_cluster:     TEXT
  confidence:        DOUBLE PRECISION
  _outbox_id:        BIGINT
consumers:
  - dashboard SSE
  - learner_M14 (skill/scar promotion if confidence > threshold)
  - oracle (input for ultra_move synthesis)
trace_id_field:    thesis_id
artifact_uri_field: (none — thesis lives in DB row only)
```

### L1 — dossier-compiler

```yaml
channel:           intel_event
event_type:        intel.event
trigger_table:     research_dossiers
trigger_migration: 113_intel_radar_findings.sql + 146_eventbus_triggers_use_outbox.sql
payload_schema:
  id:                BIGINT
  table:             "research_dossiers"
  event_type:        "dossier_created" | "dossier_updated"
  occurred_at:       TIMESTAMPTZ
  dossier_id:        UUID
  slug:              TEXT
  status:            TEXT
  _outbox_id:        BIGINT
consumers:
  - curiosity_gap_closer
  - war_room_intake (topic-selector)
  - zantara_rag_indexer (Qdrant upsert)
  - crm_alert_router
trace_id_field:    dossier_id
artifact_uri_field: (none — dossier lives in DB row only)
```

### L1 — learner-nightly

```yaml
channel:           cognitive_event
event_type:        cognitive.event
trigger_table:     ultra_moves (from learner-side anomaly path) + skills/scars (cell-core writes)
trigger_migration: 114_cognitive_layer_tables.sql (cognitive side) + cell-core direct emits
payload_schema:
  id:                BIGINT
  table:             "ultra_moves" | "wr_anomaly_alerts" (when anomaly path)
  event_type:        "skill_promoted" | "scar_recorded" | "anomaly_detected"
  occurred_at:       TIMESTAMPTZ
  source_thesis_id:  UUID  (when promotion is from thesis)
  delta_pct:         DOUBLE PRECISION  (M14 retrain side)
  _outbox_id:        BIGINT
consumers:
  - oracle (inputs ultra_moves)
  - dashboard SSE
  - Telegram notifier (critical anomalies + ultra_moves)
trace_id_field:    source_thesis_id (when present)
artifact_uri_field: (none — direct DB row)
```

### L1 — measurer (Sprint 2 W1, mig 152)

```yaml
channel:           measurer_event
event_type:        measurer.event
trigger_tables:    post_metrics_history, m13_retrain_log
trigger_migration: 152_measurer_event_trigger.sql
payload_schema:
  metric_id | retrain_id:  BIGINT
  post_id:                 UUID  (post_metrics_history only)
  horizon_hours:           INT   (post_metrics_history only)
  metric_name:             TEXT  (post_metrics_history only)
  metric_value:            DOUBLE PRECISION  (post_metrics_history only)
  source:                  TEXT  (ig_graph | linkedin | tiktok | ga4 | computed)
  trigger_type:            TEXT  (m13_retrain_log only)
  delta_pct:               DOUBLE PRECISION  (m13_retrain_log only)
  event_type:              "metric_recorded" | "retrain_executed"
  occurred_at:             TIMESTAMPTZ  (collected_at | retrained_at)
  _outbox_id:              BIGINT
consumers:
  - measurer dashboards (replaces 6h polling)
  - M14 learner (per Sprint 2 plan — feedback loop)
trace_id_field:    metric_id (per metric) | retrain_id (per retrain)
artifact_uri_field: (none — metric is the DB row)
```

### L1 — trend-hunter

```yaml
channel:           intel_event
event_type:        intel.event
trigger_table:     trend_signals
trigger_migration: 113_intel_radar_findings.sql + 146_eventbus_triggers_use_outbox.sql
payload_schema:
  id:                BIGINT
  table:             "trend_signals"
  event_type:        "signal_recorded"
  occurred_at:       TIMESTAMPTZ
  signal_id:         UUID
  topic:             TEXT
  source:            TEXT
  strength:          DOUBLE PRECISION
  _outbox_id:        BIGINT
consumers:
  - dossier_compiler (batch pre-compute on new trends)
  - connector (cross-thesis input)
  - intel-radar dashboards
trace_id_field:    signal_id
artifact_uri_field: (none)
```

### L2 — pg-proxy

```yaml
channel:        n/a
contract:       TCP proxy 5432 ↔ flycast Postgres. Substrate, not IPC participant.
notes:          Counted in WR2 inventory because it lives in the WR2 plist namespace,
                but does not produce or consume events. Kill-switch impact: if down,
                every other WR2 organelle on Pro loses DB connectivity.
```

### L2 — sla-worker

```yaml
channel:           wr2_status_change
event_type:        wr2.status_change
trigger_table:     war_room_drafts (UPDATE on status='abandoned')
trigger_migration: 138_wr2_status_notify.sql
payload_schema:
  draft_id:          UUID
  status_old:        TEXT
  status_new:        "abandoned"
  occurred_at:       TIMESTAMPTZ
  reason:            "sla_timeout"
  _outbox_id:        BIGINT (NOT injected for wr2_status_change — see notes)
consumers:
  - wr2_supervisor.py (launchd daemon, LISTEN-only consumer)
notes: |
  wr2_status_change is intentionally NOT in PG_CHANNEL_MAP (cf. cicatrix-scars.md
  P0-2 phase 2 footnote): only consumed by the launchd supervisor outside the
  FastAPI process, so the EventBus reconnect-hook has no need to replay it.
  In-process FastAPI consumers receive the equivalent fanout via war_room_event
  (mig 112) which IS in PG_CHANNEL_MAP and IS outbox-backed.
trace_id_field:    draft_id
artifact_uri_field: (none — status update only)
```

### L2 — supervisor

```yaml
channel:        wr2_status_change (LISTEN-only)
role:           CONSUMER. Drives the WR2 chain (draft → image → canva → review).
implementation: scripts/wr2_supervisor.py launchd daemon, raw asyncpg LISTEN.
notes: |
  Supervisor is a pure consumer; it doesn't owe Event-driven Law on output.
  Its actions are spawn child processes (draft-generator, image-generator, ...)
  which write to war_room_drafts and indirectly fire the next event.
  Failure mode: if supervisor is down, the chain stalls; sla-worker eventually
  fires a status='abandoned' update which fires a final event (visible to
  external consumers).
```

### L3 — strategos

```yaml
channel:           cognitive_event
event_type:        cognitive.event
trigger_table:     weekly_strategic_briefs
trigger_migration: 114_cognitive_layer_tables.sql + 146_eventbus_triggers_use_outbox.sql
payload_schema:
  id:                BIGINT
  table:             "weekly_strategic_briefs"
  event_type:        "brief_published"
  occurred_at:       TIMESTAMPTZ
  brief_id:          UUID
  iso_week:          TEXT  ("2026-W18")
  source_thesis_ids: UUID[]
  _outbox_id:        BIGINT
consumers:
  - oracle (synthesizes ultra_moves on top of strategos briefs)
  - dashboard SSE
  - Telegram delivery (strategos_delivery.py)
trace_id_field:    brief_id
artifact_uri_field: (Markdown body lives in DB row TEXT column — no external URI)
```

### L4 — oracle

```yaml
channel:           cognitive_event
event_type:        cognitive.event
trigger_table:     ultra_moves
trigger_migration: 114_cognitive_layer_tables.sql + 146_eventbus_triggers_use_outbox.sql
payload_schema:
  id:                BIGINT
  table:             "ultra_moves"
  event_type:        "ultra_move_proposed"
  occurred_at:       TIMESTAMPTZ
  move_id:           UUID
  category:          TEXT  ("market_shift" | "regulation_alert" | "rev_opportunity")
  confidence:        DOUBLE PRECISION
  source_brief_id:   UUID  (strategos)
  _outbox_id:        BIGINT
consumers:
  - dashboard SSE
  - Telegram delivery (oracle_delivery.py — Zero approval gate)
notes: |
  Oracle proposes, war-room operators decide. The trigger emits the event;
  Telegram delivery is downstream of the DB write. Per DeepSeek round-2
  brainstorm, oracle is NEVER a SPOF decisionale — it's a recommender.
trace_id_field:    move_id
artifact_uri_field: (Markdown rationale + chart URLs in DB row)
```

### Operational — topic-selector (dual emitter)

```yaml
channel_primary:   war_room_event
channel_secondary: wr2_status_change
trigger_table:     war_room_drafts (INSERT — primary), war_room_drafts (status='briefed' — secondary)
trigger_migration: 112_war_room_tables.sql (war_room_event) + 138_wr2_status_notify.sql (wr2_status_change)
payload_schema:
  draft_id:          UUID
  topic:             TEXT
  event_type:        "draft_briefed"
  occurred_at:       TIMESTAMPTZ
  status:            "briefed"
  _outbox_id:        BIGINT (war_room_event side; wr2_status_change side is launchd-internal)
consumers:
  war_room_event:
    - publisher_worker
    - measurer_worker (when status='posted' downstream)
    - dashboard SSE
  wr2_status_change:
    - wr2_supervisor.py (spawns draft-generator)
trace_id_field:    draft_id
artifact_uri_field: (brief Markdown lives in DB row)
```

### Operational — draft-generator

```yaml
channel:           wr2_status_change
event_type:        wr2.status_change
trigger_table:     war_room_drafts (UPDATE status='briefed' → 'drafted')
trigger_migration: 138_wr2_status_notify.sql
payload_schema:
  draft_id:          UUID
  status_old:        "briefed"
  status_new:        "drafted"
  occurred_at:       TIMESTAMPTZ
  artifact_uri:      file:///<workspace>/<slug>.md
consumers:
  - wr2_supervisor.py (spawns image-generator)
trace_id_field:    draft_id
artifact_uri_field: artifact_uri (filesystem URI to the rendered Markdown body
                    pre-DB-finalize; DB row also carries the body once inserted)
```

### Operational — image-generator

```yaml
channel:           wr2_status_change
event_type:        wr2.status_change
trigger_table:     war_room_drafts (UPDATE image fields, status='drafted' → 'rendered')
trigger_migration: 138_wr2_status_notify.sql
payload_schema:
  draft_id:          UUID
  status_old:        "drafted"
  status_new:        "rendered"
  occurred_at:       TIMESTAMPTZ
  artifact_uri:      file:///<workspace>/<slug>.png  (or FlowKit if WR2_IMAGE_BACKEND=flowkit)
consumers:
  - wr2_supervisor.py (spawns canva-apply)
trace_id_field:    draft_id
artifact_uri_field: artifact_uri (PNG path, swap to s3://… when shipping FlowKit)
notes: |
  Backend selectable via WR2_IMAGE_BACKEND env (auto/flowkit/playwright,
  default auto = FlowKit-first with Playwright fallback). See
  docs/wr2/flowkit-integration.md.
```

### Operational — canva-apply

```yaml
channel:           wr2_status_change
event_type:        wr2.status_change
trigger_table:     war_room_drafts (UPDATE status='rendered' → 'reviewed')
trigger_migration: 138_wr2_status_notify.sql
payload_schema:
  draft_id:          UUID
  status_old:        "rendered"
  status_new:        "reviewed"
  occurred_at:       TIMESTAMPTZ
  canva_url:         https://canva.com/design/<id>
consumers:
  - wr2_supervisor.py (waits for human review then triggers newsletter)
trace_id_field:    draft_id
artifact_uri_field: canva_url
```

### Operational — newsletter

```yaml
channel:           war_room_event
event_type:        war_room.event
trigger_table:     war_room_posts (INSERT)
trigger_migration: 112_war_room_tables.sql + 146_eventbus_triggers_use_outbox.sql
payload_schema:
  post_id:           UUID
  draft_id:          UUID
  platform:          TEXT  ("blog" | "ig" | "linkedin" | "tiktok")
  event_type:        "post_published"
  occurred_at:       TIMESTAMPTZ  (NEW.published_at)
  post_url:          TEXT  (when known at publish time)
  _outbox_id:        BIGINT
consumers:
  - measurer_worker (kicks off post_metrics_history collection)
  - dashboard SSE
  - intel-radar (cross-correlation with trend_signals)
trace_id_field:    post_id (with draft_id as parent trace)
artifact_uri_field: post_url (when present) | mdx_path (file:// for blog)
```

### Operational — hardening (Sprint 2 W3 candidate)

```yaml
channel:           wr2.hardening.run  (NEW — observed-shell tier, NOT in PG_CHANNEL_MAP)
emitter:           ObservedShellBus.emit (apps/backend-rag/backend/services/events/observed_shell.py)
table:             observed_shell_events (mig 151)
payload_schema:
  automation_name:   "wr2.hardening.run"
  status:            "ok" | "error" | "warning"
  trace_id:          UUID  (per run)
  payload:
    missed_runs:    [...]   (output of missed_runs_cli)
    token_status:   {...}   (output of token_watchdog_cli)
    quota_status:   {...}   (output of quota_cli)
    sub_run_count:  3
  artifact_uri:      (none — output is JSON in payload)
consumers:
  - sentinel / monitoring dashboards (LISTEN on observed-shell tier)
notes: |
  hardening does NOT participate in WR2 cell IPC (it's operational maintenance).
  The observed-shell tier is the right substrate per Sprint 0 audit. The
  Sprint 2 W3 PR will wire this in scripts/wr2-hardening-chain.sh.
```

### Operational — canva-renderer (LEGACY, slated for dismissal)

```yaml
status:    LEGACY orphan, no DB write, filesystem-only output.
sprint_0_decision: confirmed legacy by audit; pending dismissal in a follow-up
                   chore PR. Until removed, the plist runs every 300s producing
                   PNG files under ~/.openclaw/workspace/canva-render/.
action_required:   `chore/wr2-cleanup-canva-renderer` to (a) unload from launchd
                   on Pro, (b) delete plist from infra/launchagents/, (c) mark
                   in registry as deprecated.
```

## Channel summary table

| pg_channel | event_type | source migrations | producers | in PG_CHANNEL_MAP | outbox-backed |
|---|---|---|---|---|---|
| `cognitive_event` | `cognitive.event` | 114 + 146 | connector, learner-nightly, strategos, oracle | ✅ | ✅ |
| `intel_event` | `intel.event` | 113 + 146 | dossier-compiler, trend-hunter | ✅ | ✅ |
| `war_room_event` | `war_room.event` | 112 + 146 | topic-selector (INSERT side), newsletter | ✅ | ✅ |
| `wr2_status_change` | (no event_type — launchd-only) | 138 | sla-worker, draft-generator, image-generator, canva-apply, topic-selector | ❌ (intentional) | ❌ (volatile by design — supervisor is launchd-only consumer) |
| `measurer_event` | `measurer.event` | 152 | measurer | ✅ (Sprint 2 W1) | ✅ |
| `wr2.hardening.run` | (observed-shell tier) | 151 | hardening (Sprint 2 W3 candidate) | n/a (different tier) | observed-shell-events table |

## Cross-organelle trace propagation

Trace IDs propagate down the WR2 pipeline via row foreign keys:

```
trend_signals.signal_id (L1 trend-hunter)
    └─ research_dossiers.id (L1 dossier-compiler — sources from signals)
        └─ cross_dossier_theses.id (L1 connector)
            └─ weekly_strategic_briefs.source_thesis_ids[] (L3 strategos)
                └─ ultra_moves.source_brief_id (L4 oracle)

war_room_drafts.id (operational topic-selector)
    └─ war_room_drafts.id (status updates: drafted → rendered → reviewed)
        └─ war_room_posts.draft_id (operational newsletter)
            └─ post_metrics_history.post_id (L1 measurer — Sprint 2 W1)
                └─ m13_retrain_log (L1 measurer feedback loop)
```

A consumer can reconstruct any vertical slice of the pipeline by joining
the trace IDs back to source tables. The `_outbox_id` injected by mig 146
is orthogonal — it identifies the **event** (for replay dedup), not the
**artifact** (for trace).

## What this doc replaces / supersedes

- The flat tabular view in `docs/audits/sprint0/wr2-ipc-mechanism.md` is
  retained as the audit findings (still authoritative on Law 4 compliance).
  This doc is the per-organelle **contract** that Sprint 2 W3 (observed-shell
  bridge) and any future consumer relies on.
- Future PRs that add a new WR2 organelle MUST add a section here with
  the same shape (channel, event_type, trigger_migration, payload_schema,
  consumers, trace_id_field, artifact_uri_field). A CI check that asserts
  this is on the Sprint 2 W3 backlog.

## Open items (Sprint 2 follow-ups)

- **W3:** wire `wr2-hardening-chain.sh` to `ObservedShellBus.emit`
  (artifact contract above). Sprint 2 W3 PR.
- **Cleanup:** open `chore/wr2-cleanup-canva-renderer` to remove legacy
  plist + Pro unload. Sprint 2 W3 or follow-up.
- **Telegram → DB:** when Telegram alerts are emitted by oracle/strategos
  delivery scripts, ensure the parent DB row carries enough metadata so
  consumers don't have to scrape Telegram. Already done; documented here
  as the rule for future organelles.
