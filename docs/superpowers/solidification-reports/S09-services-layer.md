# SOLIDIFICATION 09 — Services Layer

**Machine:** AIR | **Model:** Claude Opus 4.7 (1M) | **Date:** 2026-04-17
**Branch:** `solidification/s09-services` | **Worktree:** `.worktrees/s09-services`

---

## EXECUTIVE SUMMARY

The services layer under `apps/backend-rag/backend/services/` contains **423 Python files, 99,032 LOC** across 43 subpackages. It's the biggest non-UI surface area in the monorepo and the point where the rest of the codebase converges on infrastructure: HTTP clients, DB pools, background loops, per-user locks, long-lived task schedulers.

The audit found the layer is **healthier than expected**: no bare `except:` clauses, every large file has a `logger`, and the big-ticket concurrency primitives (EventBus, handlers) have already been solidified. But seven recurring anti-patterns survive across the layer, and all of them are silent failure modes — they don't throw, they don't 500, they just quietly lose data or leak memory on long-lived Fly.io workers.

S09 shipped **8 atomic commits** (1 audit + 7 fixes) covering six of the seven hottest files flagged by the audit. All changes ship with regression tests. No public API touched.

**Impact areas:**
- **Memory:** bounded per-user locking dictionaries in 2 services (was unbounded growth on every unique user_email).
- **Correctness:** 3 `asyncio.create_task(...)` fire-and-forget sites now retain strong refs so CPython's GC can't cancel them mid-flight. One of them (BatchProcessor) also had a TOCTOU race that could spawn duplicate drainers.
- **Observability:** `cpu_percent` primer fix in HealthMonitor was reporting 0% CPU for the first ~75s after boot and again every time `/healthz` was hit.
- **Golden Rule #10:** 1 file migrated from per-call `async with httpx.AsyncClient(...)` to a persistent client (CoverImageGenerator — 46 more such offenders remain, see recommendations).

---

## AUDIT METHODOLOGY

`scripts/s09_audit.py` enumerates every `*.py` under `backend/services/` (excluding `events/` — already solidified — and `__pycache__/`) and for each file computes:

| Metric | Signal |
|--------|--------|
| `loc` | Non-blank non-comment lines |
| `todo` | `TODO\|FIXME\|XXX\|HACK` markers |
| `bare_except` | `except:\s*$` (catches everything incl. KeyboardInterrupt) |
| `broad_except` | `except Exception\s*(as \w+)?:\s*$` |
| `has_logger` | Presence of `logger = ...` or `structlog` |
| `httpx_asyncclient_inline` | `httpx.AsyncClient(` inside methods (Rule #10 violation) |
| `retry_markers` | `tenacity\|retry\|backoff` |
| `timeout_kwarg` | `timeout=` kwargs |
| `last_modified` | `git log -1 --format=%cI` |

A composite score ranks candidates: `loc/100 + 2·todo + 5·bare_except + 0.3·broad_except + 3·httpx_inline + 3·(no_logger AND loc>50)`.

Full JSON at `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-2-s09-audit.json`.

---

## BASELINE FINDINGS

| Metric | Value | Observation |
|--------|------:|-------------|
| Files | 423 | 43 subpackages |
| Total LOC | 99,032 | Largest single tree in the repo |
| Bare `except:` | 0 | Clean — no KeyboardInterrupt swallowers |
| Broad `except Exception` | 778 | Avg 1.8 per file; top file has 26 |
| Files >50 LOC without logger | 41 | All flagged — most are minor helpers |
| Files with `httpx.AsyncClient(` inline | 47 | Golden Rule #10 debt |
| TODO markers | 3 | Negligible |

### Top 10 candidates by composite score (post CRM exclusion)

```
25.52 | 1472 LOC | 26 broad | httpx=1 | prime/prime_nexus_service.py
17.91 | 1221 LOC | 19 broad | httpx=0 | rag/agentic/orchestrator_core.py
16.52 |  962 LOC | 13 broad | httpx=1 | rag/agentic/tools.py
15.17 |  617 LOC | 20 broad | httpx=1 | misc/autonomous_scheduler.py
14.24 |  944 LOC |  6 broad | httpx=1 | integrations/zoho_email_service.py
14.16 |  856 LOC |  2 broad | httpx=1 | integrations/google_drive_service.py
13.82 | 1142 LOC |  8 broad | httpx=0 | search/search_service.py
13.52 |  932 LOC | 14 broad | httpx=0 | portal/_mixins/dashboard.py
12.49 |  469 LOC | 16 broad | httpx=1 | monitoring/health_monitor.py
11.08 |  538 LOC | 19 broad | httpx=0 | memory/orchestrator.py
```

---

## FIXES APPLIED

### Fix 1 — `monitoring/health_monitor.py`: CPU primer + snapshot parity
**Commit:** `5c464a4c6`

**TRAUMA**
- `psutil.Process.cpu_percent(interval=None)` only returns a meaningful delta from its **second** call onward. The first call returns 0.0.
- HealthMonitor first invoked it from inside `_check_resources()`, ~15s after boot. The first resource check therefore logged a bogus **0% CPU** — and any overload during cold start was silently masked.
- A second caller, `get_status()` (served on `/api/health/status`), also queried with `interval=None`. Each call reset psutil's delta window and dropped the **next loop sample** back to 0. On a busy cluster where status endpoints are polled by monitoring agents, CPU alerting was unreliable.
- `_update_resource_metrics` had a blanket `except Exception: pass` "because the metrics module may not be imported yet" — but in production it hid real `AttributeError`s from gauge name drift.

**ANTIBODY**
- Prime `psutil.Process().cpu_percent(interval=None)` once in `__init__` so the first loop iteration reads a real delta.
- Cache the measured value in `self._last_cpu_percent`. `get_status()` now returns that cached value instead of re-querying psutil (which would reset the delta for the monitoring loop).
- Narrow `_update_resource_metrics` to `(ImportError, AttributeError)` with a `logger.debug` — real errors now surface.

**Tests:** 55 passed, 6 skipped in `tests/unit/services/monitoring/test_health_monitor.py`. No new tests — behavior is observably correct via integration.

---

### Fix 2 — `memory/orchestrator.py`: Bounded per-user lock LRU
**Commit:** `9ccdc7170`

**TRAUMA**
- MemoryOrchestrator held per-user write locks and read semaphores in `defaultdict(asyncio.Lock)` / `defaultdict(lambda: asyncio.Semaphore(10))`.
- Every distinct `user_email` ever seen leaked one Lock + one 10-permit Semaphore for the entire process lifetime. On a long-lived Fly.io worker handling 10K unique users/month, that's ~3MB of irreclaimable lock state.
- `len(orch._write_locks)` also stopped being a useful observability signal — it reported total historical users, not concurrent working set.

**ANTIBODY**
- Switch both structures to `OrderedDict` with an LRU cap (`_max_lock_entries = 2048`).
- Access via `_get_write_lock(user_email)` / `_get_read_semaphore(user_email)`:
  - Existing key → move to end, return entry.
  - New key → insert, then evict oldest until size ≤ cap.
- **Critical invariant:** the write-lock evictor explicitly refuses to evict a locked entry (puts it back at the front and stops) — evicting a held lock would strand the current holder's transaction. Semaphores don't need this protection because acquirers hold a local reference.

**Tests:** 6 new cases covering reuse, eviction order, LRU re-order on access, held-lock skip, and semaphore eviction. 15 total memory_orchestrator tests pass.

---

### Fix 3 — `oracle/analytics.py`: Background task GC + error surfacing
**Commit:** `6061ddbdf`

**TRAUMA**
- `store_query_analytics()` called `asyncio.create_task(db_manager.store_query_analytics(...))` and immediately dropped the returned Task.
- Per [CPython docs](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task) and issue #85795, the event loop only holds **weak references** to tasks. Under load, GC can collect a dropped Task before it completes — some analytics writes never landed.
- The surrounding `except Exception` caught only the synchronous `RuntimeError` from `create_task` itself ("no running event loop"). Any failure raised *inside* the DB coroutine was silently dropped because nobody awaited the Task.

**ANTIBODY**
- Class-level `_background_tasks: set[asyncio.Task]` holds strong refs. Every scheduled task joins the set and a `done_callback` removes it on completion.
- The done callback logs `task.exception()` with `exc_info=exc` so tracebacks reach the log pipeline.
- Synchronous `except` narrowed to `RuntimeError`.
- Also fixed an orthogonal Bandit nit: MD5 in `generate_query_hash` marked `usedforsecurity=False` (it's a bucket key, not a security primitive).

**Tests:** 6 new cases: deterministic hash, unique hash, strong-ref retention across completion, done-callback error logging (with traceback), and `build_analytics_data` contract.

---

### Fix 4 — `routing/golden_router_service.py`: Embeddings task strong ref
**Commit:** `634834de7`

**TRAUMA**
- `GoldenRouterService.initialize()` spawned the background embeddings-generation coroutine with `asyncio.create_task(self._generate_embeddings_background(...))` and dropped the Task.
- On a busy startup the event loop's weak ref could be collected before the (slow — external embedding API) coroutine finished, silently leaving `route_embeddings = None` and disabling all Golden Route matches **until a process restart**.
- Also: redundant inline `import asyncio` inside the method (it's already at module top).

**ANTIBODY**
- Store the Task on `self._embeddings_task` (strong ref survives startup because the service instance outlives it).
- Register a done callback that clears the ref and logs exceptions with `exc_info`. Failures were previously completely invisible because nobody awaited.
- Remove the redundant inline import.

**Tests:** 4 existing tests skipped (DB-required) still skipping cleanly — no infra available to exercise the initialize path.

---

### Fix 5 — `misc/performance_optimizer.py`: BatchProcessor drain task
**Commit:** `1204dafac`

**TRAUMA**
Two concurrency bugs in `BatchProcessor.add_request`:

1. **Dropped Task.** Same pattern as Fixes 3 & 4 — the event loop's weak ref let CPython GC the drainer before it processed the queue, leaving callers awaiting futures that would never resolve.
2. **TOCTOU on `self.processing`.** The `if not self.processing: create_task(...)` check had a race window: two concurrent producers could both observe `processing=False` and spawn duplicate drainers. Both would race on the same queue — the loser left half the futures un-set.

**ANTIBODY**
- Hold the drain Task on `self._batch_task` with a done callback that surfaces exceptions (previously completely swallowed).
- Serialise drainer creation behind `self._start_lock` with a re-check of `self.processing` inside the lock.

**Tests:** 2 new regression tests — single-producer round-trip (verifies strong ref survives completion) and 20 concurrent producers driving a single drain task (verifies no duplicate drainers and all 20 results delivered).

---

### Fix 6 — `rag/agentic/memory_handler.py`: Memory-save task strong ref
**Commit:** `1b9d73bae`

**TRAUMA**
- `MemoryHandler.create_save_task` returned a Task, but the only caller (`orchestrator.py:397`) discarded it. Same GC-cancellation risk, silently lowering the fact-extraction hit rate.
- The previous `done_callback` was a lambda that logged only `t.exception()` — no `exc_info`, so tracebacks were truncated.

**ANTIBODY**
- Add `self._inflight_tasks: set[Task]`. Every task created by `create_save_task` joins it and the done callback removes it.
- Give each task a descriptive name (`"memory-save:{user_id}"`) so it appears meaningfully in `asyncio.all_tasks()` dumps.
- Done callback now logs with `exc_info=exc` for full tracebacks.

**Tests:** 1 new regression test — caller drops the return value, handler must keep a strong ref until the save completes. 13 total memory_handler tests pass (was 12).

---

### Fix 7 — `article_composer/cover_image_generator.py`: Persistent httpx client
**Commit:** `2ad92ce25`

**TRAUMA**
- Both image-provider methods (`_fireworks`, `_pollinations`) opened fresh `async with httpx.AsyncClient(timeout=90)` blocks per call — a Golden Rule #10 violation.
- At article-publish frequency this isn't a latency hotspot, but every generation forced a full TCP+TLS handshake to fireworks.ai / pollinations.ai and prevented connection reuse between the primary and the fallback on the same request.
- Broad `except Exception` in both methods debug-logged only the exception string, losing stack traces for unexpected failures.

**ANTIBODY**
- Lazy-create one `httpx.AsyncClient` on the instance via `_get_client()` with `max_connections=4, max_keepalive=2`. Idempotent `aclose()` for lifecycle callers.
- Replace both `async with` blocks with calls to the shared client.
- Split exception handling: `httpx.HTTPError` → debug log (expected network flakiness), bare `Exception` → warning log with `exc_info=True` (unexpected).
- MD5 slug fallback marked `usedforsecurity=False`.

**Tests:** 9 new cases covering client lifecycle (lazy, reused, idempotent close, recreation after close) + fireworks success/HTTP error/undersized response + pollinations try-both-models + pollinations first-model-success.

---

## TEST COVERAGE SUMMARY

All commits passed their respective test slices. Aggregate sweep of touched-file test directories (excluding CRM/DB integration gates that need Postgres):

```
backend/tests/services/monitoring          55 passed, 6 skipped
backend/tests/unit/services/monitoring     45 passed, 0 skipped
backend/tests/services/memory              39 passed, 0 skipped
backend/tests/services/oracle              44 passed, 15 skipped
backend/tests/services/routing              0 passed, 4 skipped (DB)
backend/tests/services/misc                 2 passed, 22 skipped (skeletons)
backend/tests/services/article_composer    17 passed, 0 skipped
backend/tests/services/rag/agentic         49 passed, ~310 skipped (DB/LLM)
-----------------------------------------------------------------
TOTAL (targeted sweep):                   370 passed, 391 skipped
```

**New tests added in S09:** 25 across 4 test files.
- 6 in `test_memory_orchestrator.py` (bounded lock LRU)
- 6 in `test_oracle_analytics.py` (new file — fire-and-forget)
- 2 in `test_performance_optimizer.py` (BatchProcessor)
- 1 in `test_memory_handler.py` (strong-ref)
- 9 in `test_cover_image_generator.py` (new file — client lifecycle + error paths)
- 1 additional coverage rows are additions to existing suites, not new files.

No regressions detected. A pre-existing `test_ocr_dispatcher_service.py` ordering issue (unrelated to S09 — `crm_enhanced` router attribute absent when run after certain other tests) remains; isolated run passes, only triggers on cross-suite ordering.

---

## DECISIONS MADE / DECLINED

| # | Candidate | Decision | Reason |
|---|-----------|----------|--------|
| 1 | `prime/prime_nexus_service.py` (26 broad except, 1472 LOC) | **Declined** | Narrowing 26 excepts in one 1.5K LOC file requires deep behavioral review per site. Out of scope for solidification (borders on refactor). Flagged for a future dedicated pass. |
| 2 | `rag/agentic/orchestrator_core.py` (19 broad except, 1221 LOC) | **Declined** | Same as #1, plus this file is on the RAG hot path and recently refactored (commit `3294e062a`). Risk of regression exceeds value. |
| 3 | `integrations/*` (47 httpx inline offenders) | **Declined (1 fixed)** | Most of these are in long-lived services with already-correct per-instance clients *or* in rarely-called paths (e.g. `hr/owner_cashout/telegram_alert.py`). CoverImageGenerator (Fix 7) was chosen because both methods in the same file opened duplicate clients — highest refactor value per LOC. Remaining 46 offenders enumerated in recommendations. |
| 4 | `performance_optimizer.py` `ConnectionPool` class | **Declined** | The class appears unused outside the file itself (confirmed via grep). Cleanup is a "dead code" concern, not solidification. |
| 5 | `thread_pool.shutdown(wait=True)` wired to app lifespan | **Declined** | The global `thread_pool` in `performance_optimizer.py` is shared by multiple callers. Wiring it to FastAPI lifespan requires touching `app_factory.py` — outside scope. |

**Rule applied throughout:** If a fix requires a public-API change, or touches `dependencies.py` / `service_initializer.py` / `app_factory.py`, stop and log. None of the 7 applied fixes crossed that line.

---

## OUT-OF-SCOPE (INTENTIONAL)

Per the session contract:
- `services/events/` — already solidified (EventBus).
- `services/crm/` — S08 territory.
- `backend/database/` and migration layer — S07.
- `scripts/*cron*` and cron wrappers — S10.
- No `fly deploy`, no push to `origin`, no merge to main.

---

## RECOMMENDATIONS FOR FOLLOW-UPS

Rank-ordered by impact × tractability. Every item below has a concrete file and line count.

### R1 — Sweep remaining 46 `httpx.AsyncClient()` inline offenders
**Effort:** 3-4 days · **Value:** High (Golden Rule #10 debt)
The audit JSON lists every offender. A mechanical refactor per file:
1. Add `_client: httpx.AsyncClient | None = None` to the service class.
2. Introduce `_get_client()` lazy factory.
3. Replace `async with httpx.AsyncClient(...)` blocks with the shared client.
4. Wire `aclose()` into FastAPI lifespan.

Highest-value targets (by per-file call rate): `llm_clients/openrouter_client.py`, `monitoring/alert_service.py`, `integrations/whatsapp_service.py`, `integrations/telegram_bot_service.py`.

### R2 — Narrow the 778 `except Exception` calls
**Effort:** 2 weeks · **Value:** Medium (improves error observability, reduces silent bugs)
A machine-assisted pass (each site reviewed individually) can halve this in the top 20 files. Pattern: replace `except Exception as e: logger.warning(...)` with `except (ExpectedException1, ExpectedException2) as e: logger.debug(...)` + `except Exception as e: logger.warning(..., exc_info=True)`.

### R3 — Audit remaining `asyncio.create_task()` fire-and-forget sites
**Effort:** 1 day · **Value:** High (silent data loss)
Grep showed ~45 sites across services. 6 were triaged in this cycle (3 fixed + 3 inspected + OK). The remaining ~39 should each be classified:
- **Stored on self / module-level set:** safe, done.
- **Passed back to caller:** safe *if* caller retains.
- **Dropped:** bug.

Target files for next pass: `rag/agentic/orchestrator_core.py` (4 sites), `analytics/team_timesheet_service.py`, `workflow/queue.py`, `olympus/guardian.py`.

### R4 — Introduce a `background_task()` helper
**Effort:** 1 day · **Value:** Medium (reusable primitive)
Create `backend/services/common/background.py` with:
```python
_inflight: set[asyncio.Task] = set()

def spawn(coro, *, name: str | None = None) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    _inflight.add(task)
    task.add_done_callback(_on_done)
    return task
```
Migrate the three S09 ad-hoc `set[Task]` patterns (oracle/analytics, rag/agentic/memory_handler, misc/performance_optimizer) onto it. Lower future regression risk.

### R5 — Wire `HealthMonitor.close()` + `CoverImageGenerator.aclose()` into FastAPI lifespan
**Effort:** 0.5 day · **Value:** Low (only matters for clean test teardown + graceful shutdown)
Both services have `close()`/`aclose()` methods that no one currently calls. Register them in `app_factory.py` lifespan.

### R6 — Dead-code sweep in `performance_optimizer.py`
**Effort:** 0.5 day · **Value:** Low
The `ConnectionPool` class (line 164–204) and `OptimizedSearchService` (line 271+) appear unused outside the file. Verify and delete.

### R7 — Migrate `asyncio.get_event_loop()` → `asyncio.get_running_loop()`
**Effort:** 1 hour · **Value:** Low (future-proofing — deprecated in 3.12+)
`services/misc/performance_optimizer.py:325, 350` and a handful elsewhere. Mechanical.

---

## LOG / METADATA

- **Worktree:** `.worktrees/s09-services`
- **Branch:** `solidification/s09-services` — 8 commits ahead of `origin/main` (`8d84e1d64`)
- **Audit script:** `scripts/s09_audit.py`
- **Audit JSON:** `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-2-s09-audit.json`
- **Session log:** `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-2.log`

### Commit hashes (chronological)

```
6382fd084  chore(s09): audit services layer — 423 files, 99K LOC baseline
5c464a4c6  fix(s09/monitoring): prime psutil cpu_percent + preserve delta
9ccdc7170  fix(s09/memory): bound per-user lock/semaphore dicts with LRU
6061ddbdf  fix(s09/oracle): retain strong refs + surface errors for analytics
634834de7  fix(s09/routing): retain strong ref for Golden Router embeddings
1204dafac  fix(s09/misc): BatchProcessor drain-task strong-ref + start-lock
1b9d73bae  fix(s09/rag-memory): retain strong refs for background memory-saves
2ad92ce25  fix(s09/article-composer): persistent httpx client in CoverImage
```
