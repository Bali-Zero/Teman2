# Backend Jobs + Agents Orchestration — Design

**Date:** 2026-04-18
**Session:** PB3 (Pro) — `pro/backend-jobs-agents-orchestration`
**Scope:** Core workstreams 1-3 of the session brief (unified job runner, legacy job migration, agent safety layer). Workstreams 4-7 (article composer state machine, journey event sourcing, Agent Mesh v2 prep, broader test coverage) are explicit stretch / follow-up, each with its own future brainstorming pass.

## Goal

Replace the current fragmented scheduling surface (Fly `[[processes]]` + Air crontab curling HTTP endpoints + ad-hoc Python APScheduler usage in `services/autonomous_agents/`) with a single in-process async runner that owns cron semantics, idempotency, retry, concurrency, and run-history persistence for backend-side jobs. Add a default-on safety middleware stack that enforces the OAuth-only rule project-wide and absorbs the known Claude CLI Linux/non-TTY hang.

## Decisions locked during brainstorming

| # | Decision | Choice |
|---|---|---|
| 1 | Scope | Core 1-3 must-ship; 4-7 follow-up |
| 2 | Runner tech | Custom async runner (croniter + Postgres advisory locks) |
| 3 | Idempotency | Tick-based default, optional handler-provided override |
| 4 | Tick origin | Runner owns schedule; HTTP endpoint stays for manual kick + legacy alias |
| 5 | Safety layer | Default-on middleware (OAuth guard + cost cap + Claude CLI fallback), per-job opt-out with required `reason=` |
| 6 | Schedule config | Code-only (`register_job()` args); `docs/jobs-schedule.md` auto-generated from registry |
| 7 | Legacy migration | Per-job allowlist via `JOBS_RUNNER_ENABLED` env var; Air crontab entries kept until runner proven, removed in separate PR |

## Non-goals (in this PR)

- Replacing `services/article_composer/` pipeline or adding its state machine.
- Journey event sourcing / `journey_stage_changed` EventBus channel.
- Agent Mesh v2 — registry-driven multi-agent spawn.
- Removing Air crontab entries for migrated jobs (done in a follow-up after stable-operation observation).
- Distributed tracing, cost dashboards, per-handler domain metrics.

## Architecture

Single custom async runner embedded in the FastAPI backend process, scoped to Fly `nuzantara-rag` (`min_machines=1`, always-on). Process topology is one `asyncio.Task` inside the API process. Advisory locks guard against hypothetical second schedulers during rolling deploys.

```
backend/jobs/
├── __init__.py
├── runner.py              # scheduler loop, dispatch, middleware chain execution
├── registry.py            # register_job() + immutable registry
├── middleware.py          # oauth_guard, cost_cap, claude_cli_fallback
├── locks.py               # pg_try_advisory_lock helpers
├── models.py              # JobRun dataclass + JobRunRepository
├── retry.py               # RetryPolicy, classification helpers, transient_on decorator
├── context.py             # JobContext, CostMeter
└── handlers/
    ├── __init__.py        # imports each handler module -> self-registration
    ├── auto_practice_creator.py
    ├── conversation_cleanup.py
    ├── consiglio_auto.py
    └── kg_curiosity.py

backend/app/routers/
└── jobs_admin.py          # POST /api/jobs/{name}/run, GET /api/jobs, GET /api/jobs/{name}/runs

backend/migrations/
├── migration_112_job_runs.py   # async def apply(conn) + async def rollback(conn); follows 108 pattern
└── apply_migration_112.py      # driver (asyncpg.connect DATABASE_URL -> calls apply)

scripts/
└── gen_jobs_schedule_doc.py   # regenerates docs/jobs-schedule.md from registry; CI --check mode

docs/
└── jobs-schedule.md       # auto-generated; single source of truth for humans
```

**Isolation boundaries.** `runner.py` knows nothing about specific jobs. `registry.py` has no execution logic. `middleware.py` composes around handler calls. `models.py` / `locks.py` are pure PG adapters. Each file is independently testable.

**Unchanged files.** Existing `backend/jobs/auto_practice_creator.py` and `backend/jobs/conversation_cleanup.py` core logic are not rewritten. We add thin wrappers in `backend/jobs/handlers/*.py` that import and reuse them.

**Scope exclusions (boundary respected).** No changes to `core/`, `middleware/`, `services/compliance/`, `services/intel/`, `services/rag/`, `services/observability/`, `self_healing/`, `core/reasoning.py`, `core/reranker.py`, `routers/dream.py`, `routers/newsletter.py`, `routers/debug.py`.

## Components

### Registry

```python
@dataclass(frozen=True)
class JobDeclaration:
    name: str                                # unique, kebab-case
    cron: str                                # croniter expression
    handler: Callable[[JobContext], Awaitable[JobResult]]
    timezone: str = "Asia/Makassar"          # WITA default (matches S10 staggering)
    timeout_seconds: int = 300
    retry_policy: RetryPolicy = DEFAULT_RETRY
    skip_middleware: tuple[str, ...] = ()
    skip_reasons: Mapping[str, str] = field(default_factory=dict)
    idempotency_key: Callable[[JobContext], str] | None = None
    enabled_when: Callable[[], bool] | None = None

def register_job(**kwargs) -> None: ...
def get_registry() -> list[JobDeclaration]: ...   # read-only view
```

Registration at import time via `backend/jobs/handlers/__init__.py`. Registry is frozen after `lifespan` startup completes. Registry rejects `skip_middleware` entries without a matching non-empty `skip_reasons[name]`.

### Runner

Single `asyncio.Task`. Tick granularity: 10 seconds.

```python
class JobsRunner:
    async def start(self, db_pool, enabled_names: set[str]): ...
    async def stop(self, grace_seconds: int = 30): ...
    async def _tick_loop(self): ...
    async def _dispatch(self, decl, scheduled_tick: datetime): ...
    async def _execute_with_middleware(self, decl, ctx): ...
```

`enabled_names` comes from `os.getenv("JOBS_RUNNER_ENABLED", "").split(",")` at startup. Empty = runner scheduling off; all jobs still reachable via manual kick. This is the migration switch.

### Middleware (default-on, outer-to-inner order)

1. **`oauth_guard`** — raises `OAuthViolation` if `ANTHROPIC_API_KEY` is present in process env at dispatch time. Logs violation with job name.
2. **`cost_cap`** — budget of `$1.00/run` default. Handler receives `CostMeter` via `JobContext`; calls `meter.charge(cents, reason)` on paid calls. Exceeding cap cancels with `status='cost_exceeded'`. Overridable per job.
3. **`claude_cli_fallback`** — detects Linux + non-TTY at runner startup once; sets `ctx.claude_cli_available = False`. Does NOT modify `KG_REASONING_PROVIDER` (memory: `KG_REASONING_PROVIDER=openai` is permanent on Fly). Purely informational — handlers that would shell out to `claude -p` consult this flag and route to OpenAI/Gemini/Ollama.

Opt-out requires `skip_reasons[name]` = non-empty string. Registry rejects declarations that violate this.

### Locks

```python
@asynccontextmanager
async def advisory_lock(conn, key: str) -> AsyncIterator[bool]:
    lock_id = stable_hash_int64(key)
    got = await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_id)
    try:
        yield got
    finally:
        if got:
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)
```

Per-dispatch key = `f"job:{decl.name}:{scheduled_tick.isoformat()}"`. Non-blocking: `pg_try_advisory_lock`. If not acquired, dispatch silently skipped.

### Persistence

```python
@dataclass
class JobRun:
    id: int
    job_name: str
    scheduled_tick: datetime
    idempotency_key: str
    status: Literal["pending","running","completed","failed","skipped","cost_exceeded"]
    started_at: datetime | None
    finished_at: datetime | None
    attempt: int                             # 1-indexed
    error: str | None
    cost_cents: int
    meta: dict[str, Any]

class JobRunRepository:
    async def create_pending(self, ...) -> JobRun: ...
    async def mark_running(self, run_id): ...
    async def finish(self, run_id, status, error, cost_cents, meta): ...
    async def find_by_idempotency_key(self, key) -> JobRun | None: ...
    async def list_recent(self, job_name, limit): ...
    async def mark_orphans(self, older_than: datetime): ...
```

### HTTP surface (`routers/jobs_admin.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/jobs/{name}/run` | `X-API-Key` admin | Manual kick; `scheduled_tick=now`, bypasses enabled-allowlist |
| GET | `/api/jobs` | `X-API-Key` admin | Registry + last run per job + 7d stats |
| GET | `/api/jobs/{name}/runs?limit=50` | `X-API-Key` admin | Recent history |

`POST /api/admin/practice/auto-create` is preserved as a thin alias to `/api/jobs/auto-practice-creator/run` — zero breakage for the existing Air crontab entry (`30 7 * * * curl .../api/admin/practice/auto-create`).

### Handlers

Four handler modules. Each imports existing logic, defines `handle(ctx: JobContext) -> JobResult`, calls `register_job(...)` at import time, and does NOT re-implement domain logic.

- `auto_practice_creator.py` — wraps existing `backend/jobs/auto_practice_creator.py` core function. Cron `30 7 * * *` Asia/Makassar (matches current Air entry).
- `conversation_cleanup.py` — wraps existing `backend/jobs/conversation_cleanup.py` (daily per its docstring; not wired to any external cron today). Cron `15 4 * * *` Asia/Makassar — staggered 15 min before KG Curiosity (`30 4`) to avoid 04:00 WITA pile-up per S10 notes.
- `consiglio_auto.py` — thin call into Consiglio v1's internal auto-deliberation function (not a subprocess to the CLI). Cron preserves existing cadence.
- `kg_curiosity.py` — thin call into KG Curiosity Loop dispatcher. Cron `30 4 * * *` (matches existing `0 4:30 WITA`).

### Schedule documentation

`scripts/gen_jobs_schedule_doc.py` imports the registry in headless mode (no DB, no lifespan), writes `docs/jobs-schedule.md` as a markdown table (name, cron, tz, timeout, retry, middleware, description). CI gate: `python scripts/gen_jobs_schedule_doc.py --check` exits non-zero if the committed doc diverges from the current registry.

## Data flow

### Happy path

```
T=0   tick loop iterates registry
      last_tick   = SELECT MAX(scheduled_tick) FROM job_runs WHERE job_name=...
      next_due    = croniter(decl.cron, last_tick or startup).get_next()
      if now() < next_due: continue

      decl.name not in JOBS_RUNNER_ENABLED?  -> skipped, reason="not in allowlist"

      idempotency_key = decl.idempotency_key(ctx) if set else f"{decl.name}:tick:{scheduled_tick.isoformat()}"
      find_by_idempotency_key(key) completed within window?  -> skipped

      advisory_lock acquired?  -> if no, silent skip

      INSERT job_runs (status='pending', attempt=1)
      mark_running(run_id)

      await oauth_guard(ctx); await claude_cli_fallback(ctx); await cost_cap(ctx, limit=$1.00)
      await asyncio.wait_for(decl.handler(ctx), timeout=decl.timeout_seconds)

      finish(run_id, status='completed', cost_cents=meter.total, meta=result.meta)
      release advisory lock
```

### Retry path

Handler raises `TransientError`. Current attempt finalized as `failed`; next attempt with same `idempotency_key` fires after backoff (0.5s / 2s / 8s, max 3 attempts). Multiple rows in `job_runs` for the same `scheduled_tick`, same `idempotency_key`, increasing `attempt`. Partial index on `idempotency_key WHERE status IN ('completed','running')` keeps lookup O(1) after success.

Non-transient exceptions (anything not classified `TransientError`) do not retry. One row, `status='failed'`. Next scheduled tick starts fresh with a new idempotency key.

### Crash recovery

On startup, runner scans `status='running'` rows older than `timeout_seconds + 30s grace` and marks them `status='failed'` with `error='orphaned'`. This is the only mutation the runner makes to historical rows.

### Manual kick

`POST /api/jobs/{name}/run` → dispatches with `scheduled_tick=now()`, `source='manual'`. Bypasses `enabled_names` check. Returns `{ run_id, status }` immediately for poll-based observation via `GET /api/jobs/{name}/runs?limit=1`.

### Migration overlap

While `JOBS_RUNNER_ENABLED` does not include a job, the runner does not schedule it (skipped with `reason="not in allowlist"`). Air crontab continues to curl the HTTP endpoint; the runner's manual-kick path executes the same handler and records a `job_runs` row. When the allowlist is extended, the runner schedules ticks; a second tick from Air crontab on the same day finds a completed idempotency row and skips. Air entries are removed in a separate PR after observing stable operation.

## Migration 112 — `job_runs`

```sql
-- up
CREATE TABLE job_runs (
    id              BIGSERIAL PRIMARY KEY,
    job_name        TEXT NOT NULL,
    scheduled_tick  TIMESTAMPTZ NOT NULL,
    idempotency_key TEXT NOT NULL,
    status          TEXT NOT NULL
                    CHECK (status IN ('pending','running','completed','failed','skipped','cost_exceeded')),
    attempt         SMALLINT NOT NULL DEFAULT 1,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error           TEXT,
    cost_cents      INTEGER NOT NULL DEFAULT 0,
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_job_runs_name_tick     ON job_runs (job_name, scheduled_tick DESC);
CREATE INDEX idx_job_runs_idempotency   ON job_runs (idempotency_key)
                                         WHERE status IN ('completed','running');
CREATE INDEX idx_job_runs_status_name   ON job_runs (status, job_name)
                                         WHERE status IN ('running','pending','failed');

-- down
DROP TABLE IF EXISTS job_runs;
```

Migration number is **112**. Current head on `main` is 111 (`migration_111_notification_log.py`); 109 is `funnel_sessions`, 110 is `notification_prefs`. Follows existing Python migration pattern — `async def apply(conn)` and **mandatory** `async def rollback(conn)` (per `migration_base.py`: "New migrations (number > 111) MUST supply rollback_sql", introduced 2026-04-18). Rollback drops indexes then the table — no FK dependencies.

## Error handling

### Exception taxonomy

```python
class JobError(Exception): pass
class TransientError(JobError):     """Retry-eligible."""
class PermanentError(JobError):     """Do not retry."""
class OAuthViolation(PermanentError): ...
class CostExceeded(PermanentError): ...
```

Retry rule: `isinstance(exc, TransientError) and attempt < max_attempts`. **Anything unclassified is treated as `PermanentError`.** Handlers must explicitly wrap retryable code in `try/except ... as e: raise TransientError from e`, or use the `@transient_on(*exc_classes)` decorator that auto-classifies known transient exceptions (`asyncpg.PostgresConnectionError`, `httpx.ConnectError`, `httpx.ReadTimeout`, `asyncio.TimeoutError`).

### Timeout

`asyncio.wait_for(handler(ctx), timeout=decl.timeout_seconds)`. `TimeoutError` is classified as transient (retry). Hard upper bound: after `timeout_seconds + 30s`, lock is force-released and `running` row marked orphaned regardless of handler cancellation cooperation.

### Structured logging

Stable event schema (`event=job.*`) bound with `job_name`, `run_id`, `attempt` at dispatch so downstream handler logs carry context automatically. Uses existing backend `structlog` configuration.

Events: `job.dispatch`, `job.start`, `job.finish`, `job.retry`, `job.skip`, `job.orphan`, `job.violation`, `job.tick_error`.

### Alerting (reuses Telegram notifier to channel `1125336968`)

1. `event=job.violation middleware=oauth_guard` → immediate Telegram ping.
2. Any `(job_name, day)` with ≥3 `failed` rows → Telegram digest once/day/job. Dispatched by the `jobs-health-monitor` meta-job.
3. Enabled job with no completed run in `2 × cron_interval` → Telegram ping (stale-job detection), same meta-job.

Meta-job `jobs-health-monitor` cron `0 9 * * *` WITA. Additive to Air `job_health.py` — that script is removed in a follow-up PR, not this one.

### Observability surface

`GET /api/jobs` returns per-job registry + last run + 7d stats (completed / failed / skipped counts, p50/p95 duration).

### Failure modes explicitly accepted

- **Clock skew** between replicas absorbed by advisory lock + deterministic idempotency key.
- **DB down at tick time** — tick loop catches `asyncpg` errors, logs `job.tick_error`, retries next 10s. Missed tick is NOT backfilled (matches Unix cron; avoids DB-recovery stampede).
- **Lifespan shutdown mid-job** — `stop(grace_seconds=30)` bounded await. Handlers exceeding 30s force-cancelled, marked `failed` with `error='shutdown'`. Tick-based idempotency keys mean no auto-retry on next startup; handler-override keys may retry (handler responsibility).
- **Two replicas during rolling deploy** — advisory lock; one wins, other skips.

## Testing strategy

### Pyramid

**Unit (~70%, fast, in-memory):** `test_registry.py`, `test_retry_policy.py`, `test_croniter_wrap.py`, `test_middleware_oauth_guard.py`, `test_middleware_cost_cap.py`, `test_middleware_claude_cli_fallback.py`, `test_idempotency_key.py`.

**Integration (~25%, real PG + real Redis, no mocks):** `test_advisory_lock.py`, `test_dispatch_happy_path.py`, `test_dispatch_retry.py`, `test_dispatch_permanent_fail.py`, `test_idempotency_skip.py`, `test_crash_recovery.py`, `test_concurrent_replicas.py`, `test_missed_tick_no_backfill.py`, `test_timeout_enforcement.py`. Anchored in feedback memory: integration tests must hit a real database, not mocks.

**End-to-end (~5%, full FastAPI lifespan):** `test_lifespan_start_stop.py`, `test_admin_endpoints.py`, `test_legacy_endpoint_alias.py`.

### TDD order

1. Registry tests → `registry.py`
2. Retry-policy tests → `retry.py`
3. Advisory-lock integration tests (real PG) → `locks.py`
4. Repository integration tests → `models.py` + migration 112
5. Dispatch happy-path test → minimal `runner.py`
6. Retry + timeout tests → expand runner
7. Middleware tests → `middleware.py`
8. Handler migration tests → wire handlers
9. Admin endpoint tests + legacy alias test → wire router

### Fixtures

Pro local PostgreSQL 17 at `localhost:5432/nuzantara_test`. `pg_pool` fixture applies migrations up to 112, truncates `job_runs` at teardown. `runner` fixture uses `tick_seconds=0.1` for fast integration tests; cron expressions use `* * * * * *` (croniter second-support). No time mocking.

### Coverage target

`backend/jobs/` ≥ 80% line coverage, enforced via `coverage report --fail-under=80` in CI.

### Verification before completion

1. `pytest backend/tests/jobs/ -v` all green (≥30 tests).
2. `coverage report` for `backend/jobs/` ≥ 80%.
3. Integration run against Pro local PG with `JOBS_RUNNER_ENABLED=auto-practice-creator` for one tick cycle; observe `job_runs` row + structured log output.
4. `python scripts/gen_jobs_schedule_doc.py --check` exits 0.
5. `mypy backend/jobs/` clean (strict mode for this new module).

### Out of scope for tests

- Handler domain logic (covered by existing test suites — S08 CRM 44 tests, Consiglio v1 87 tests, KG Curiosity 40 tests).
- Fly deployment behavior (verified locally, deploy is a separate check).
- Load tests (10 jobs × hourly ticks is not a scale concern).

## Hard rules respected

- **OAuth-only absolute** — `oauth_guard` middleware enforces at every dispatch; opt-out requires written `reason=`.
- **Claude CLI Linux hang** — `claude_cli_fallback` middleware sets `ctx.claude_cli_available`; `KG_REASONING_PROVIDER=openai` on Fly is NOT touched.
- **Scope boundaries** — no changes to Air B1/B2/B3 or PB1/PB2 paths (listed in "Architecture → Scope exclusions").
- **Migration monotonic** — 112 confirmed at PR-open. New migrations must supply `rollback(conn)` per `migration_base.py` contract.
- **Fly topology** — no new process, no new app. Runner lives in `nuzantara-rag` (always-on).
- **No auto-assignment** policy (CRM Automation memory) — not affected; auto_practice_creator handler preserves existing behavior.

## Follow-up PRs (not this session)

1. **Air crontab cleanup** — remove `30 7 * * * curl .../api/admin/practice/auto-create` etc. once runner has operated stably for N days. Keeps HTTP endpoint as manual ops tool.
2. **Air `job_health.py` retirement** — once `jobs-health-monitor` meta-job proven, remove Air-side script.
3. **Workstream 4** — Article Composer state machine + idempotency.
4. **Workstream 5** — Journey service event sourcing (`journey_stage_changed` EventBus channel).
5. **Workstream 6** — Agent Mesh v2 registry-driven spawn.
6. **Workstream 7** — test coverage expansion on `services/autonomous_agents/`.
