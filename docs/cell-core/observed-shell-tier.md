# Observed-shell tier

A third runtime classification distinct from "full cell" and "leave alone".

## Why this exists

The brainstorm round 2 (Codex disagreement on flat round-1 promotion) named
a class of automations that:

- **don't fit the cell mold** — they would fail the 7 Leggi admission test
  (no genuine reasoning, no decisional autonomy, no cell-organism stack)
- **but DO need observability** — silent failures should be detected by
  monitoring within minutes, not by a quarterly audit

Examples Codex named: translation hourly cron, BI exchange-rate daily,
imigrasi-monitor / oss-monitor / pajak-monitor, fly-pg-backup,
qdrant-snapshot, mos-maintenance, sync-memory-to-nlm, webhook ingest.
These are mechanical jobs — call API, transform data, write to disk or
DB. No reasoning. No fallback chain. No HGT. They run, they succeed or
fail, and they should leave a trace.

The observed-shell tier gives them a single emit() to write that trace
without dragging in `cell-core` (which has Genome, Homeostasis, PulseLoop,
SafetyGate — all overkill for a hourly translation job).

## What it is

Three things together:

1. **Migration 151** (`151_observed_shell_events.sql`) — a Postgres table
   `observed_shell_events` with `(automation_name, status, payload, trace_id, created_at)`
   columns. ROLLBACK marker present. Two partial indexes for fast
   "last 7 days for X" and "errors today" queries.

2. **`backend.services.events.observed_shell.ObservedShellBus`** — a
   simple class with `emit(automation_name, status, payload?, trace_id?)`.
   Falls back to `~/logs/observed-shell.jsonl` if the DB pool is None
   or the INSERT fails. **Best-effort, does not propagate exceptions to
   the caller** under any documented code path (serialization failures,
   DB errors, JSONL write errors, unknown status are all caught). The
   cell must not see an exception just because observability is
   unavailable.

3. **Status taxonomy** — `ok | error | warning | skipped`. Mirrors
   launchctl semantics. `skipped` means "no work to do" (legitimate
   no-op); `warning` means "partial success" (e.g. 9/10 items processed).

## What it is NOT

- **Not a replay queue.** Unlike `events_outbox` (mig 144), there is no
  `consumed_at` column, no `replay_unconsumed()`, no per-handler ack.
  Observed-shell is fire-and-store. Consumers (dashboards, alerters)
  poll or query the table on demand.

- **Not for cell IPC.** Cells emit through `events_outbox` + `pg_notify`
  via `EventBus.emit_pg`. Observed-shell is for the OUTSIDE of the cell
  layer.

- **Not a generic logging backend.** Use `logger` for free-form logs.
  Observed-shell is structured: every emit MUST have an automation_name
  + status. The point is that `SELECT * FROM observed_shell_events
  WHERE automation_name='translate.hourly' AND status='error' AND
  created_at > now() - interval '24h'` answers a precise monitoring
  question.

## Sample integrations

### Python (in-process; cron-agent-python strategies, FastAPI background tasks)

```python
from backend.services.events.observed_shell import ObservedShellBus

bus = ObservedShellBus(db_pool)   # db_pool from app.state.db_pool

await bus.emit(
    "translate.hourly",
    "ok",
    {
        "duration_ms": 1234,
        "items_processed": 42,
        "items_failed": 0,
    },
    trace_id="run-2026-05-02T03:00",
)
```

In a FastAPI lifespan setup, attach once and reuse:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.observed_shell = ObservedShellBus(app.state.db_pool)
    yield
```

### Bash (LaunchAgent / launchd cron jobs) — Sprint 1 PR-1.2 ✅ shipped

The HTTP endpoint `POST /api/observed-shell/emit` lands in Sprint 1
PR-1.2 (`apps/backend-rag/backend/app/routers/observed_shell.py`). Use
the canonical bash wrapper rather than raw `curl`:

```bash
source scripts/observed-shell-emit.sh
observed_shell_emit "wr2.hardening.run" "ok" '{"missed_runs_caught":3}' "trace-abc"
```

The wrapper is **best-effort** — emit failure (DNS, refused, 5xx, missing
API key) returns 0 and only logs to stderr. The parent automation MUST
NOT fail because observability is unavailable. This mirrors
`ObservedShellBus.emit()` never-raises invariant at the network layer.

The endpoint is X-API-Key authenticated (not in `PUBLIC_ENDPOINTS`):

```bash
export OBSERVED_SHELL_API_URL="http://127.0.0.1:8080"
export OBSERVED_SHELL_API_KEY="$(grep ^API_KEYS ~/.nuzantara-secrets.env | cut -d= -f2 | tr -d '"' | head -1)"
```

#### Pattern: extrinsic wrapper around an unchanged Python script

The recommended pattern for retrofitting observability onto an existing
script (e.g. `apps/bali-intel-scraper/scripts/run_intel_pipeline.py`) is
to **leave the Python untouched** and wrap it with a sibling shell
wrapper such as `scripts/intel-scraper-with-observability.sh`:

- Source `observed-shell-emit.sh`
- emit `ok` + `phase=start` BEFORE the subprocess
- run the workload (Python pipeline, unchanged)
- emit `ok` + `phase=finish` + `duration_ms` (or `error` + `exit_code`)
  AFTER the subprocess

Same `trace_id` ties the start/finish emit pair together. Observability
stays decoupled from pipeline logic; rolling back the wrapper restores
the original LaunchAgent behavior unchanged.

## List of automations to migrate (Sprint 1 wave)

| Automation | Owner runtime today | Migrate emit when |
|---|---|---|
| `translate-articles.py` (hourly) | cron-agent-python | Sprint 1 W1 |
| `bi-exchange-rate` (daily 07:00) | cron-agent-python | Sprint 1 W1 |
| `imigrasi-monitor` (daily 06:00) | cron-agent-python | Sprint 1 W1 |
| `oss-monitor` (every 2h) | cron-agent-python | Sprint 1 W1 |
| `pajak-monitor` (daily 00:00 UTC) | cron-agent-python | Sprint 1 W1 |
| `fly-pg-backup.sh` (daily) | LaunchAgent | Sprint 1 W2 (shell wrapper) |
| `qdrant-snapshot` (cron) | LaunchAgent | Sprint 1 W2 (shell wrapper) |
| `mos-maintenance.sh` (daily) | LaunchAgent | Sprint 1 W2 |
| `sync-memory-to-nlm.sh` (daily) | LaunchAgent | Sprint 1 W2 |
| `wr2-hardening-chain.sh` (every 6h) | LaunchAgent | Sprint 1 W2 |
| Webhook ingests (post-publish-poller) | LaunchAgent | Sprint 1 W2 |

Each migration is **3-5 lines of Python or one curl wrapper**. Estimated
total work for the wave: <0.5 day across all 11 automations.

## What's enforced by this Sprint 0 PR

- The migration 151 file (with squawk-ignore directives that match
  Sprint 0 lessons — concurrent-index warning is a false positive on
  empty tables).
- The `ObservedShellBus` class.
- 4 unit tests (happy path, no-pool fallback, PG error fallback,
  invalid-status coerce).

What's NOT enforced and lands in Sprint 1: the actual integration of
the 11 automations above + the `/api/observed-shell/emit` HTTP endpoint
for the shell wrappers. That deliberate split keeps Sprint 0 PR
non-invasive — no code paths change behaviour today.

## References

- `apps/backend-rag/backend/db/migrations_v2/151_observed_shell_events.sql`
- `apps/backend-rag/backend/services/events/observed_shell.py`
- `apps/backend-rag/backend/tests/services/events/test_observed_shell.py`
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/01b_codex_round2.md`
  § "observed-shell tier proposal"
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md`
  § "Codex: classificazione observed-shell"
