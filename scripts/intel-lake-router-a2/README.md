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
           │   → reads intel-lake-routing-  │
           │     rules.json                 │
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
| `intel-lake-router-cron-standalone.py` | `~/scripts/` | The classifier (asyncpg + re, **zero backend imports**) |
| `intel-lake-routing-rules.json` | `~/scripts/` | Rules + NB-INTEL UUIDs (kept in sync with backend `_RULES`) |
| `intel-lake-router-cron.sh` | `~/scripts/` | Bash wrapper: loads secrets, runs Python, holds flock |
| `com.balizero.intel-lake-router.5min.plist` | `~/Library/LaunchAgents/` | StartInterval 300, RunAtLoad true |

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
5. Rules loaded from external JSON — single source of truth shared with
   backend `_RULES` (manual sync for now; Tier 1.5 GET /api/intel/lake/rules
   endpoint is a future improvement).
6. None-safe `source_domain` handling: `(domain or '').strip().lower()`.
7. Explicit `$N::jsonb` cast in SQL, never raw dict.

## Unit tests

```bash
~/.pyenv/versions/3.11.11/bin/python3 - <<'PYEOF'
import importlib.util
spec = importlib.util.spec_from_file_location("m", "scripts/intel-lake-router-a2/intel-lake-router-cron-standalone.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
rules, fb = m._load_rules()
cases = [
    ("imigrasi.go.id", "nb-intel"), ("pajak.go.id", "nb-intel"),
    ("bkpm.go.id", "nb-intel"), ("arxiv.org", "nb-intel"),
    ("detik.com", "blog"), ("reddit.com", "archive"),
    ("unknown", "needs_review"), ("", "needs_review"),
    (None, "needs_review"), ("randomsite.example", "needs_review"),
]
for d, exp in cases:
    r = m._classify(d, rules, fb)
    assert r["status"] == exp, f"{d!r} → {r['status']}, expected {exp}"
print(f"PASS: {len(cases)}/{len(cases)}")
PYEOF
```

Last green: 16/16 cases on 2026-05-13.

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

- Backend router code (source of truth for `_RULES`):
  `apps/backend-rag/backend/services/intel/intel_lake_router.py`
- Schema: `apps/backend-rag/backend/db/migrations_v2/168_intel_lake_schema.sql`
- Service layer: `apps/backend-rag/backend/services/intel/intel_lake_service.py`
- Router endpoint: `apps/backend-rag/backend/app/routers/intel_lake.py`
- PG proxy LaunchAgent: `com.balizero.wr2.pg-proxy` (separate concern,
  hosts the `localhost:15432` forwarding A2 depends on)
