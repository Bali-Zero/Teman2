# Intel Lake Tier 1 Router — A2 (Pro-local cron bypass)

**Status**: ACTIVE on Pro since 2026-05-13 03:25 WITA.
**Purpose**: Apply Tier 1 regex rules to `intel_items.routing_status='unrouted'`
rows from Pro instead of from Fly, because `DISABLE_BACKGROUND_WORKERS=1`
(kill-switch from disk-full incident 2026-04-12) prevents the EventBus
listener — and therefore the in-process router subscriber — from running
on the Fly `rag` process.

The router code at
`apps/backend-rag/backend/services/intel/intel_lake_router.py` is deployed
(Fly v3192) but never subscribes, so all items stay `unrouted` until A2
sweeps them.

## Architecture

```
                     [12+ producers]
                            │
                            ▼
            POST /api/intel/lake/observations
                            │
                            ▼
                    intel_items  (PG)
                  routing_status='unrouted'
                            │
                            │  every 5 min
                            ▼
           ┌────────────────────────────────┐
           │  Pro LaunchAgent               │
           │  com.balizero.intel-lake-      │
           │  router.5min                   │
           │   → intel-lake-router-         │
           │     cron.sh (bash wrapper)     │
           │   → intel-lake-router-cron-    │
           │     standalone.py (asyncpg)    │
           │   → imports intel_lake_rules   │
           │     .py (sibling file)         │
           └────────────────────────────────┘
                            │
                            ▼
                  UPDATE routing_status,
                  routing_targets;
                  INSERT audit_log
```

DB connection goes through the existing
`com.balizero.wr2.pg-proxy` LaunchAgent which forwards
`localhost:15432` → `nuzantara-postgres.flycast:5432`.

## Files in this dir (deploy via symlink to `~/scripts/` and `~/Library/LaunchAgents/`)

| File | Deployed path on Pro | Purpose |
|------|----------------------|---------|
| `intel-lake-router-cron-standalone.py` | `~/scripts/` | The classifier driver (asyncpg, **zero backend imports**) |
| `apps/backend-rag/backend/services/intel/intel_lake_rules.py` | `~/scripts/intel_lake_rules.py` | Single source of truth for rules + NB-INTEL UUIDs (2026-09-23: retired the separate JSON copy — see below) |
| `intel-lake-router-cron.sh` | `~/scripts/` | Bash wrapper: loads secrets, runs Python, holds flock |
| `com.balizero.intel-lake-router.5min.plist` | `~/Library/LaunchAgents/` | StartInterval 300, RunAtLoad true |

**2026-09-23 — single rules source (PENDING-ARMS
`intel-lake-pro-fallback-router-rules-drift`):** the standalone script no
longer reads a JSON copy of the rules. It imports `classify()` and the
NB-INTEL UUIDs from `intel_lake_rules.py` — the same stdlib-only module the
Fly backend's `intel_lake_router.py` imports — loaded by path from a sibling
file (`~/scripts/intel_lake_rules.py`) or, when running from a repo
checkout, from `apps/backend-rag/backend/services/intel/intel_lake_rules.py`
relative to the repo root. Deploying an update to the rules is now: copy
`intel_lake_rules.py` to `~/scripts/intel_lake_rules.py` on Pro — nothing
else changes in sync.

## Tri-LLM design review (Codex + Gemini + DeepSeek, 2026-05-13)

A1 first attempt failed: importing the backend `backfill_unrouted()` from
`intel_lake_router.py` pulled `backend.app.core.config.Settings()` which
validates `JWT_SECRET_KEY` (min 32 chars) and `API_KEYS`. Placeholder env
vars failed validation. A2 sidesteps the whole config layer with a
standalone script.

Tri-LLM panel found 7 must-fix bugs in the v1 standalone design; all 7
addressed in the implementation:

1. `SELECT ... FOR UPDATE SKIP LOCKED` — prevents two cron instances from
   double-routing the same row when DB is slow.
2. `UPDATE ... RETURNING id` — audit log only inserts for rows that
   actually transitioned (no duplicate audits on no-op).
3. `async with conn.transaction():` wraps UPDATE+INSERT — atomicity.
4. Time-windowed failure counter — 3 fails within 30 min triggers
   Telegram. Old fails decay (avoids "reboot resurrects state file with
   3 fails" false alarm DeepSeek flagged).
5. Rules imported from `intel_lake_rules.py` — single source of truth
   shared with the backend's `_RULES` (2026-09-23: replaced the manually
   synced JSON copy, which had drifted; see PENDING-ARMS
   `intel-lake-pro-fallback-router-rules-drift`).
6. None-safe `source_domain` handling: `(domain or '').strip().lower()`.
7. Explicit `$N::jsonb` cast in SQL, never raw dict.

## Unit tests

Parity between this script's classification and the backend `_classify` is
enforced by pytest, not an ad-hoc script (2026-09-23 — both now import the
same `intel_lake_rules.classify`). The parity test loads THIS script from
its repo path, where the sibling candidate in `_RULES_MODULE_CANDIDATES`
never exists — it cannot catch a stale sibling on Pro; that class of drift
is covered separately by `TestSiblingLoaderPrecedence`, which builds a
tmp_path layout with both a sibling and a stale repo-path copy and asserts
the sibling wins:

```bash
cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/intel/test_intel_lake_rules_standalone_parity.py
```

## Retire path

Delete this whole subtree + `launchctl bootout gui/501/com.balizero.intel-lake-router.5min`
when the following trigger conditions are met:

- Fly `DISABLE_BACKGROUND_WORKERS=1` secret is removed (decision: Antonello)
- EventBus listener confirmed alive on `rag` process (smoke: `fly logs`
  showing `EventBus listener started for intel_lake_event`)
- Router subscriber re-fires on real-time events (smoke: POST observation,
  observe `routing_status` flip within 30s, not 5 min)

Running both Pro cron + Fly listener concurrently is **safe** (idempotent
`WHERE routing_status='unrouted'` guard) but wasteful — kill Pro cron once
Fly is healthy.

## Operational notes

- **Log**: `~/logs/intel-lake-router-cron.log`
- **State**: `~/logs/intel-lake-router-cron.state.json` (failure timestamps)
- **Lock**: `/tmp/intel-lake-router-cron.lock` (prevents overlapping ticks)
- **Throughput**: ~20-100 items/day expected; batch always small.
- **Lag**: max 5 min vs. real-time EventBus (acceptable for Tier 1
  classification, not for downstream NB-INTEL push which has its own
  cron).
- **SPOF**: Pro Mac. Dead Pro = no Tier 1 routing. Acceptable: Pro is the
  dev machine; dead Pro = bigger problems anyway.

## Cross-reference

- Rules single source of truth (`_RULES`, NB-INTEL UUIDs, `classify()`):
  `apps/backend-rag/backend/services/intel/intel_lake_rules.py`
- Backend router (imports the rules above, subscribes to the EventBus):
  `apps/backend-rag/backend/services/intel/intel_lake_router.py`
- Schema: `apps/backend-rag/backend/db/migrations_v2/168_intel_lake_schema.sql`
- Service layer: `apps/backend-rag/backend/services/intel/intel_lake_service.py`
- Router endpoint: `apps/backend-rag/backend/app/routers/intel_lake.py`
- PG proxy LaunchAgent: `com.balizero.wr2.pg-proxy` (separate concern,
  hosts the `localhost:15432` forwarding A2 depends on)
