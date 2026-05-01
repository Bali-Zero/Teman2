# Cell Pulse Observatory — Fase 0 Design

**Date:** 2026-05-01
**Author:** Antonello Siano + Claude Opus 4.7
**Status:** Design complete, blockers from cross-LLM review captured below. **Implementation NOT to start until BLOCKER #1–#4 are resolved** (see §Issues to resolve before PR-1).

**Cross-LLM review:** 2026-05-01, 2/4 quorum (Gemini 3.1 Pro REJECT, DeepSeek R1 APPROVE_WITH_CHANGES; Codex shell-explore overflow, NotebookLM auth fail). Convergent BLOCKER on lazy-import architecture defect. Full synthesis: `/tmp/cell-observatory-review/SYNTHESIS.md` (transient, copy embedded below in §Issues).

---

## 1. Intent

Fase 0 of a multi-phase plan: **OpenClaw spinal cord + cell+genoma organs** (Vision D). This phase is **observability-only, read-only.** No proposals, no HGT, no SafetyGate writes, no autonomous decisions. The goal is to build a baseline empirical dataset of cell pulse events + cheap-LLM classification before deciding what to automate in Fase 1+.

## 2. Scoping decisions (from 6 brainstorm clarifying questions)

| # | Decision |
|---|---|
| 1 | Vision D — full nervous system long-term |
| 2 | Tiered trust per domain (= L2 autonomous-ops applied to biology) |
| 3 | OpenClaw↔cell coupling via EventBus (PG LISTEN/NOTIFY + events_outbox post-PR #342) |
| 4 | Model routing α — strict specialization: MiniMax M2 (high-volume classifier) + Kimi K2 (Fase 1+) + Qwen3-Max (Fase 2+) |
| 5 | Phase 0 = observability-only |
| 6 | Dashboard inside `apps/admin-dashboard-local` |

Approach selected from 3 alternatives: **Approccio 2 — Listener Python + lightweight classifier MiniMax**. Rejected:
- Approccio 1 (pure listener, zero LLM): too passive, no learning signal.
- Approccio 3 (OpenClaw runtime hosts everything from day 1): too many simultaneous new dependencies, premature coupling between runtime and data.

## 3. Architecture & topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND-RAG (Fly.io)                    │
│   apps/backend-rag/backend/services/events/                     │
│   ├─ EventBus.emit_pg("cell_pulse_observed", payload)           │
│   │   (post-PR #342 phase 2: writes events_outbox before        │
│   │    pg_notify, durable across listener disconnect)           │
│   ▼                                                             │
│   PostgreSQL: events_outbox + pg_notify(channel, txt)           │
└────────────────────────┬────────────────────────────────────────┘
                         │ LISTEN cell_pulse_observed
                         │ + replay from outbox on reconnect
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PRO LOCAL (Mac H24)                          │
│   apps/cell-observatory-collector/  ← NEW Python service        │
│   ├─ collector.py    (asyncpg LISTEN + dedup _outbox_id)        │
│   ├─ classifier.py   (MiniMax M2 OpenAI-compat, async batch)    │
│   └─ storage.py      (~/.cell-observatory/observatory.db,       │
│                       SQLite WAL, FTS5 on label/reasoning)      │
│                                                                 │
│   LaunchAgent: com.nuzantara.cell-observatory.plist             │
│   (KeepAlive=true per scar P0-3,                                │
│    log to ~/logs/cell-observatory/, NOT /tmp)                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP /api/observatory/* (loopback only)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              apps/admin-dashboard-local (Pro-only)              │
│   New tab: /cell-pulse-observatory                              │
│   ├─ Timeline view (24h/7d/30d)                                 │
│   ├─ Anomaly hot-list                                           │
│   ├─ Per-cell breakdown                                         │
│   ├─ Confidence histogram                                       │
│   ├─ Disagreement watch (LLM vs cell self-classifier)           │
│   └─ MiniMax cost ledger                                        │
└─────────────────────────────────────────────────────────────────┘
```

## 4. Data schema

### 4.1 Pulse event payload (channel `cell_pulse_observed`)

```json
{
  "_outbox_id": 142857,
  "event_version": "v1",
  "cell_id": "organism",
  "cell_kind": "innervation_supervisor",
  "pulse_id": "01HQ8K3X9...",
  "pulse_timestamp": "2026-05-01T14:32:11.847Z",
  "phase": "homeostatic",
  "sensors": [
    {"name": "fly_health", "reachable": true, "status_code": 200, "latency_ms": 47},
    {"name": "qdrant_health", "reachable": true, "status_code": 200, "latency_ms": 12}
  ],
  "pulse_result": {
    "classifier_self": "green",
    "trend_window_min": 15,
    "trend_label": "stable"
  },
  "homeostatic_state": {"energy_pct": 87, "load_factor": 0.34},
  "scar_signals": [],
  "metadata": {"host": "Nuzantara", "machine_role": "Pro", "cell_core_version": "0.1.4"}
}
```

Invariants: `event_version` for backward compat; `_outbox_id` injected by `outbox.publish()` (PR #342 contract); `pulse_result.classifier_self` is the cell's own classification; payload <8KB.

### 4.2 SQLite schema — `~/.cell-observatory/observatory.db`

```sql
CREATE TABLE pulse_events (
    outbox_id INTEGER PRIMARY KEY,
    cell_id TEXT NOT NULL,
    cell_kind TEXT NOT NULL,
    pulse_id TEXT NOT NULL,
    pulse_timestamp INTEGER NOT NULL,
    phase TEXT NOT NULL,
    classifier_self TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    received_at INTEGER NOT NULL,
    received_lag_ms INTEGER NOT NULL
);
CREATE INDEX ix_pulse_events_cell_ts ON pulse_events(cell_id, pulse_timestamp DESC);
CREATE INDEX ix_pulse_events_classifier ON pulse_events(classifier_self, pulse_timestamp DESC);

CREATE TABLE pulse_classifications (
    outbox_id INTEGER PRIMARY KEY REFERENCES pulse_events(outbox_id),
    classified_at INTEGER NOT NULL,
    label TEXT NOT NULL,                  -- normal | anomaly | critical | uncertain
    confidence REAL NOT NULL,             -- 0.0..1.0
    reasoning TEXT,
    label_diff TEXT,                      -- 'agree' | 'disagree'
    model TEXT NOT NULL,                  -- 'minimax-m2' v1
    model_version TEXT,                   -- nullable, API-reported
    cost_usd REAL NOT NULL,
    latency_ms INTEGER NOT NULL,
    error TEXT
);
CREATE INDEX ix_classifications_label ON pulse_classifications(label, classified_at DESC);

CREATE TABLE pulse_daily_rollup (
    day TEXT NOT NULL,
    cell_id TEXT NOT NULL,
    n_pulse INTEGER NOT NULL,
    n_self_green INTEGER NOT NULL,
    n_self_yellow INTEGER NOT NULL,
    n_self_red INTEGER NOT NULL,
    n_classified INTEGER NOT NULL,
    n_anomaly INTEGER NOT NULL,
    n_critical INTEGER NOT NULL,
    n_disagree INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    PRIMARY KEY (day, cell_id)
);

CREATE VIRTUAL TABLE pulse_classifications_fts USING fts5(
    outbox_id UNINDEXED,
    label, reasoning,
    content='pulse_classifications', content_rowid='outbox_id'
);

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL);
INSERT INTO schema_version VALUES (1, strftime('%s','now')*1000);
```

Retention: 90 days raw, daily rollup permanent. Pruning daily 04:00 WITA via dedicated LaunchAgent. WAL + `synchronous=NORMAL`. No PII.

## 5. Python service `apps/cell-observatory-collector/`

### Package layout

```
apps/cell-observatory-collector/
├── pyproject.toml
├── README.md
├── cell_observatory/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── collector.py          # asyncpg LISTEN, dedup, dispatch
│   ├── classifier.py         # MiniMax M2 client + prompt
│   ├── storage.py            # SQLite WAL, idempotent insert
│   ├── rollup.py             # daily rollup
│   ├── prune.py              # 90d retention
│   ├── api.py                # FastAPI loopback :17891
│   └── models.py             # Pydantic v2 schemas
├── tests/
└── scripts/
    ├── bootstrap_db.sh
    └── healthcheck.sh
```

### 5.1 Collector core

```python
async def run_collector():
    while True:
        try:
            async with asyncpg_connect() as conn:
                await conn.add_listener("cell_pulse_observed", _on_notify)
                await _replay_outbox_unconsumed(conn)
                await _keep_alive(conn)
        except (asyncpg.ConnectionDoesNotExistError, OSError) as e:
            log.warning("listener disconnected, reconnect in 5s", error=str(e))
            await asyncio.sleep(5)
```

### 5.2 Classifier (MiniMax M2)

```python
class MinimaxClassifier:
    BASE_URL = "https://api.minimax.io/v1/chat/completions"
    MODEL = "MiniMax-M2"
    PRICE_INPUT_USD_PER_M = 0.30
    PRICE_OUTPUT_USD_PER_M = 1.20

    async def classify(self, event: PulseEvent) -> ClassificationResult:
        prompt = render_prompt(event)
        response = await self._call_with_retry(prompt, max_retries=2)
        return parse_structured(response, schema=ClassificationOutput)
```

Decisions: structured output via Pydantic v2 (`reasoning` first, `label` Literal, `confidence` 0-1). Cost ledger per call, daily rollup. Rate limit 1 req/sec conservative, max 50 in-flight via `asyncio.Semaphore(50)`. Latency budget <2s p95. MiniMax key in `~/.nuzantara-secrets.env` (NOT in plist per scar P0-3 secret leak).

### 5.3 Prompt v1 (versioned)

```
PROMPT_VERSION = "v1"

SYSTEM:
You are an SRE classifier for biological-cell-style health pulses.
Given sensor readings + self-classification by the cell, output JSON with:
- reasoning: 1-2 sentences
- label: 'normal' | 'anomaly' | 'critical' | 'uncertain'
- confidence: 0.0 to 1.0

Rules:
- normal = sensors within expected band, no trend break
- anomaly = ONE sensor unusual but not failing, OR self-yellow with stable trend
- critical = multi-sensor failure, OR self-red, OR trend break threshold crossing
- uncertain = ambiguous, missing data, never seen pattern

Confidence calibration: 0.9+ only when matches known scar OR signals are unambiguous.
```

### 5.4 Loopback API

```
GET  /api/observatory/pulse?cell_id=&since=&limit=
GET  /api/observatory/pulse/{outbox_id}
GET  /api/observatory/anomalies?since=&label=
GET  /api/observatory/rollup?day=&cell_id=
GET  /api/observatory/cost?since=
GET  /api/observatory/health
POST /api/observatory/backfill
```

Bind: `127.0.0.1:17891`. Auth: `X-Observatory-Key: $OBSERVATORY_API_KEY` middleware.

## 6. cell-core changes (opt-in emitter)

### 6.1 Files touched: 2

```
packages/cell-core/cell_core/
├── pulse.py              ← MOD: 1 hook at end of pulse cycle
└── observatory.py        ← NEW: emitter (see BLOCKER #1 — needs redesign)
```

### 6.2 `cell_core/observatory.py` — see §10 BLOCKER B1 for corrected impl

The original brainstorm design used lazy import of `backend.services.events.EventBus`. Cross-LLM review found this fails for standalone cells (running outside backend-rag). **Use the direct asyncpg implementation in §10 BLOCKER B1**, not the lazy-import pattern.

Original brainstorm document (for diff traceability): `/tmp/cell-observatory-review/design.md` (transient — copy to `~/Desktop/nuzantara/research/cell-observatory/2026-05-01-design-brainstorm.md` if long-term retention desired).

### 6.3 `pulse.py` modification — see §10 BLOCKER B2 for corrected hook

Original brainstorm used blocking `await observatory.emit_pulse_observed(...)`. **Use the `asyncio.create_task()` fire-and-forget pattern in §10 BLOCKER B2.**

### 6.4 Cell activation

NO code changes to cells. Activation only via plist env var:

```xml
<key>CELL_OBSERVATORY_EMIT</key>
<string>true</string>
```

Edit via `scripts/patch_launchagents.sh --add-observatory-emit` (must `chmod u+w` before plutil edit, restore `chmod 0444` after — see Issue B3).

## 7. Dashboard tab `/cell-pulse-observatory`

Inside `apps/admin-dashboard-local/`. Components: `PulseTimeline`, `AnomalyHotList`, `CellBreakdown`, `ConfidenceHistogram`, `CostLedger`, `DisagreementWatch`, `PulseDetailDrawer`, `BackfillButton`.

Tech: Next.js 16, React 19, TypeScript strict, Tailwind, SWR (`refreshInterval: 30000`), SVG nativi (NO Recharts).

Auth: `process.env.OBSERVATORY_API_KEY` build-time, `X-Observatory-Key` header.

Performance budget: initial <1.5s SSR, refresh <300ms, memory <5MB heap.

Scar adherence: NO `useTranslation()` (Pro-only, monolingual). System-health card reads from collector directly, NOT from backend-rag `/health` (which masks `startup_failed`).

## 8. Build sequence

### Track A — foundation (independent PRs, parallel possible)

```
PR-1: cell-core observatory module (REQUIRES B1+B2 fix first)
  packages/cell-core/cell_core/observatory.py (new, asyncpg direct)
  packages/cell-core/cell_core/pulse.py (mod, fire-and-forget hook)
  packages/cell-core/tests/test_observatory.py (new)

PR-2: backend-rag PG channel registration (REQUIRES B4 verification first)
  apps/backend-rag/backend/services/events/<file>.py (mod, add channel)
  Possibly: apps/backend-rag/backend/services/events/outbox.py (mod, allowlist)

PR-3: cell-observatory-collector skeleton
  apps/cell-observatory-collector/ (new full structure)
  infra/launchagents/com.nuzantara.cell-observatory.plist
  infra/launchagents/com.nuzantara.cell-observatory-prune.plist

PR-4: dashboard tab observatory
  apps/admin-dashboard-local/src/app/observatory/* (new)
```

### Track B — activation (sequenced after Track A merged)

```
PR-5: organism cell pilot enable (REQUIRES B3 fix first)
  scripts/patch_launchagents.sh (mod, --add-observatory-emit + chmod handling)
  ~/Library/LaunchAgents/com.cell.organism.plist (CELL_OBSERVATORY_EMIT=true)
  → 48h observation gate.

PR-6: seo_cell + evaluator activation
  → 48h observation gate.

PR-7: prune cron + retention validation
```

### Verification gates

After Track A: 4 PRs merged, CI green, collector LaunchAgent loaded, dashboard renders empty state, `psql` verify 0 rows on `events_outbox WHERE channel = 'cell_pulse_observed'`.

After PR-5: events_outbox accumulates, dashboard shows organism timeline, classifier label distribution sane (>80% normal), MiniMax cost <$0.05/24h, **CRITICAL: zero behavior diff in cell organism PRE vs POST activation**.

After PR-6: 3 cells emit, volume 1-3k events/24h, cost <$0.30/24h, disagreement cases catalogued.

### Rollback procedure

Track A: revert PRs in reverse order, additionally `launchctl bootout gui/501/com.nuzantara.cell-observatory*`.

Track B: set `CELL_OBSERVATORY_EMIT=false` (or unset) in plist + `launchctl kickstart -k`. Cell reverts immediately at next pulse cycle.

## 9. Cost & resources

| | |
|---|---|
| Dev time (after Issues resolved) | 13-14 days, 7 PR (revised from 10d) |
| MiniMax cost (3 cells) | ~$0.30/day = $9/month |
| Pro CPU | <2% steady-state |
| Pro memory | ~80MB |
| Pro disk (90d) | ~150MB at 3k events/day |

## 10. Issues to resolve before PR-1

**Cross-LLM review identified 4 BLOCKER + 14 actionable items.** Original brainstorm design at `/tmp/cell-observatory-review/design.md` (transient); the corrected implementation patterns are inline below. All fixes happen during PR-1, not retroactively. Reviewer convergence detail in §Cross-LLM convergence below.

### BLOCKER B1 — Lazy-import architecture defect (Gemini + DeepSeek convergence)

`cell-core` is a standalone package at `packages/cell-core`. Real cells (`apps/cell`, `apps/organism`, `apps/evaluator/seo_cell`) run as standalone Python processes via LaunchAgent. They do NOT have `apps/backend-rag/backend/` on `sys.path`. Original design's lazy `from backend.services.events import EventBus` will raise `ImportError` for ALL real cells → graceful no-op handler triggers → **zero events emitted, ever**. Feature would ship and silently do nothing.

**Fix:** Replace lazy EventBus import with direct asyncpg in `cell_core/observatory.py`:

```python
async def emit_pulse_observed(...):
    if not is_enabled():
        return
    pool = await _get_or_create_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO events_outbox (channel, payload) VALUES ($1, $2) "
                "RETURNING outbox_id",
                "cell_pulse_observed",
                json.dumps(payload),
            )
            payload["_outbox_id"] = row["outbox_id"]
            await conn.execute(
                "SELECT pg_notify($1, $2)",
                "cell_pulse_observed",
                json.dumps(payload),
            )
```

Connection pool: `asyncpg.create_pool(min_size=1, max_size=3)` lazy-init at first emit.
Failure: catch + WARN log + return (non-blocking).

### BLOCKER B2 — Pulse cycle latency coupling (Gemini)

Original design used `await observatory.emit_pulse_observed(...)` in `PulseLoop.run_cycle()`. This blocks the cell's homeostatic loop on Postgres Fly latency. Pool exhaustion / TCP stall could hang biological cycles indefinitely.

**Fix:** Fire-and-forget via `asyncio.create_task()`:

```python
try:
    from cell_core import observatory
    if observatory.is_enabled():
        asyncio.create_task(observatory.emit_pulse_observed(...))
except Exception as exc:
    logger.warning("observatory hook error (non-blocking)", error=str(exc))
```

Caller does NOT await the task. Failures isolated inside the coroutine via internal try/except.

### BLOCKER B3 — `patch_launchagents.sh` chmod 0444 deadlock (Gemini)

After scar P0-3 (2026-04-29), 49 plist files were `chmod 0444` (read-only) for hardening. The existing `patch_launchagents.sh` does not `chmod u+w` before `plutil` operations → silent permission-denied → activation appears to succeed but env var is not actually set.

**Fix:** Update `patch_launchagents.sh`:

```bash
for plist in "${PLISTS[@]}"; do
    chmod u+w "$plist" 2>/dev/null || true   # unlock
    plutil -insert EnvironmentVariables.CELL_OBSERVATORY_EMIT \
           -string "true" "$plist" -append
    chmod 0444 "$plist"                       # re-lock per scar P0-3
done
```

Verify with `plutil -lint` after edit. Backup `.pre-observatory-emit` before unlock.

### BLOCKER B4 — `outbox.publish` allowlist + `_outbox_id` injection contract (DeepSeek)

`EventBus.emit_pg()` calls `outbox.publish()` which (per PR #342) may validate channel against an internal list. Adding `cell_pulse_observed` to `PG_CHANNEL_MAP` may not be sufficient — also need to verify allowlist in `outbox.py`. Additionally: original design assumed `_outbox_id` injection was automatic; if we go direct asyncpg per B1 fix, we MUST inject `_outbox_id` manually using the INSERT-RETURNING pattern shown in B1 fix above.

**Fix:**
1. Read `apps/backend-rag/backend/services/events/outbox.py` to verify allowlist scope.
2. If allowlisted: add `cell_pulse_observed` to that list as part of PR-2.
3. Verify B1 fix code injects `_outbox_id` correctly via INSERT RETURNING.
4. Add validation regex `^[a-z][a-z0-9_]{0,62}$` matching existing channel naming convention.

### High-risk gaps (G1-G4, lower severity than blockers but must address before PR-5 enable)

- **G1: Pulse-storm OOM (Both reviewers).** `Semaphore(50)` doesn't bound queue itself — only concurrent in-flight. Replace with `asyncio.Queue(maxsize=10000)` + drop-oldest behavior + structured WARN log on saturation.
- **G2: Rollback teardown incomplete (Both).** Reverting PRs doesn't `launchctl bootout` daemon, doesn't drop pg_notify channel, doesn't clean orphan outbox rows. Add `scripts/observatory_rollback.sh` for full teardown.
- **G3: SQLite blocking under concurrency (Gemini).** Native `sqlite3` blocks asyncio loop during FTS5/WAL syncs → may stall asyncpg `_keep_alive` heartbeat → false disconnects → redundant outbox replays. Use `aiosqlite` OR offload to `asyncio.to_thread()`.
- **G4: Missed-pulse detection missing (DeepSeek).** Collector only processes received events. If cell stops emitting completely, no alert. Add `PulseWatchdog` checking per-cell max gap, emit admin warning at 2× expected interval.

### Ambiguities (A1-A4, fold into PR descriptions)

- **A1: Backfill idempotency.** `POST /api/observatory/backfill` will violate UNIQUE constraint on existing rows. Use `INSERT ... ON CONFLICT (outbox_id) DO UPDATE`.
- **A2: Daily rollup vs 30s refresh contradiction.** "Last 24h" view promises 30s freshness but rollup is daily. Document explicitly: timeline queries raw `pulse_events` (with `pulse_timestamp` index), `CellBreakdown` queries rollup with current-day delta from raw.
- **A3: `pulse_id` provenance.** `PulseResult` class in cell-core has no `pulse_id` field today (only `timestamp`). Add `pulse_id: str = ulid_factory()` in PR-1, with backward-compat default factory.
- **A4: `PG_CHANNEL_MAP` actual file.** Gemini claims it's in `event_bus.py`, design said `__init__.py`. Verify before PR-2 (5min check).

### Missing items (M1-M7, optional fase 0 / required pre fase 1)

- **M1 (Fase 0 required): Smoke test end-to-end.** `scripts/test_observatory_pulse.sh` simulates pulse → events_outbox → collector → SQLite → dashboard. Catches B1+B4 immediately.
- **M2 (Fase 0 required): Self-monitoring.** LaunchAgent `com.nuzantara.cell-observatory-selfcheck.plist` every 5min hits `/health`, logs CRITICAL on unreachable.
- **M3 (Fase 0 required): MiniMax circuit breaker.** On consecutive 5xx/429, bypass classifier temporarily (raw insert continues).
- **M4 (Fase 0 nice-to-have): Compound index `(classifier_self, label)` for DisagreementWatch.**
- **M5 (Fase 0 required, baked into B3 fix): chmod 0444 restoration in patch_launchagents.sh.**
- **M6 (Fase 0 required): Configurable cost threshold.** `OBSERVATORY_COST_ALERT_THRESHOLD_USD` env var, default 1.0.
- **M7 (Fase 1+ scope): ScarDetector for known scars.** Wire `scar_signals[]` to detect plist corruption pattern, etc. Out of scope for fase 0 but worth queueing.

### Cross-LLM convergence summary

Both reviewers (Gemini 3.1 Pro + DeepSeek R1) independently identified BLOCKER B1. This is the strongest signal possible from cross-LLM review: convergence under independence ≈ true defect, not artifact of one model's bias. Pattern matches PR #181 prior validation (memory `decision_cross_llm_review_concrete_value.md`).

Reviewers diverged on which secondary issues to prioritize:
- Gemini prioritized B2 (latency coupling) and B3 (chmod) — operational risk.
- DeepSeek prioritized B4 (allowlist) and missing items (smoke test, self-monitoring) — completeness.

Both endorse: events_outbox decoupling, scar adherence (KeepAlive, no /tmp logs, chmod 0444, backup pre-edit), no Anthropic API, staged rollout, schema design.

Failed reviewers:
- **Codex GPT-5.4**: Twice went into shell-explore mode (file source dumps, no verdict). Lesson for future cross-LLM rounds: `codex-review` with large prompts overflows. Use `claude-redteam` (Opus CLI) substitute or split prompt into per-section reviews.
- **NotebookLM NB-1**: Google rejected query (account-level restrictions). Needs `nlm login` re-auth before next round.

## 11. Adherence to Nuzantara golden rules + scar lessons

| | |
|---|---|
| Virtualenv mandatory | ✅ `apps/cell-observatory-collector/.venv` |
| No system Python | ✅ `python -m cell_observatory` |
| Async first (httpx, asyncpg) | ✅ |
| Type hints (Pydantic v2) | ✅ |
| No hardcoded secrets | ✅ env-only, key in `~/.nuzantara-secrets.env` |
| Logger never print | ✅ structlog JSON |
| Persistent httpx.AsyncClient | ✅ |
| KeepAlive=true on LaunchAgent | ✅ scar P0-3 |
| Log NOT to /tmp | ✅ `~/logs/cell-observatory/` |
| chmod 0444 plist | ✅ B3 fix preserves |
| Backup `.pre-observatory-emit` before edit | ✅ |
| WIP-commit-every-10min | ⚠️ enforce during impl |
| Anthropic API key NOT used | ✅ HARD RULE |
| MiniMax (paid per-token, NOT Anthropic) | ✅ allowed |
| Health check NOT from `/health` masking startup_failed | ✅ collector reads its own state |

## 12. Future phases (out of scope for this design)

- **Fase 1**: Kimi K2 thinking as secondary classifier (cross-LLM red-team), `POST /api/observatory/proposal` endpoint, server-side annotation persistence.
- **Fase 2**: SafetyGate integration (Kimi proposals → DNAInterpreter), HGT cross-cell.
- **Fase 3**: migrate classifier into OpenClaw runtime (original Approccio 3), Consiglio v2 trigger, Qwen3-Max meta-reasoning.
