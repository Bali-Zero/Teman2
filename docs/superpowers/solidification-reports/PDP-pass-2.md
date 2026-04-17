# PDP Pass 2 — Silent-Handler Remediation + `background.spawn()`

**Session:** 2026-04-18 strategic-9 · **Agent:** air-c1
**Branch:** `compliance/pdp-pass-2` (4 commits, worktree `.worktrees/pdp-pass-2`)
**Scope:** `apps/backend-rag/backend/` excluding `llm/` (→ air-c3) and `agents/` (→ air-c2)

---

## 1. Audit — before vs after

### 1.1 PDP silent-exception audit (`scripts/pdp_silent_exceptions_audit.py`)

| severity | pass 1 end | pass 2 end | delta |
| -------- | ----------:| ----------:| -----:|
| critical |          0 |          0 |     — |
| high     |         25 |         10 |   −15 |
| medium   |        133 |        130 |    −3 |
| **total**|    **158** |    **140** | **−18** |

All 10 HIGH residuals live in `backend/llm/*` (9) and `backend/agents/*` (1),
both off-limits for c1 by session scope. In-scope HIGH residue is **0**.

Target "high ≤ 10" ✅ met.

### 1.2 Asyncio fire-and-forget audit (new this pass, `scripts/audit_asyncio_tasks.py`)

| category | before | after | delta |
| -------- | ------:| -----:| -----:|
| SAFE     |     35 |    35 |     — |
| DROPPED  |     34 |     2 |   −32 |
| UNCLEAR  |      3 |     4 |    +1 |

The 2 remaining DROPPED are false positives (`services/olympus/guardian.py` L118–L119
— tasks are appended to the `self._tasks = [...]` literal which the lexical
classifier does not recognise as a collection-append). The 4 UNCLEAR are all
docstring / comment mentions (`"""... asyncio.create_task ..."""`), not live
calls. No real fire-and-forget leaks remain in-scope.

---

## 2. Fixes applied

### 2.1 Silent-handler typing (2 commits)

| commit | modules | findings closed |
| ------ | ------- | ----:|
| `e0a8a87ef` | `services/rag/agentic/llm_gateway.py` | 9 |
| `b514bba19` | `services/crm/practice_status_listener.py`, `channels/optimizations.py`, `middleware/error_monitoring.py`, `services/integrations/drive/drive_audit.py`, `services/llm_clients/openrouter_client.py`, `services/portal/_mixins/billing.py` | 7 |

**Key refactor** (`llm_gateway.py`):

All 10 metric counters / histograms referenced in the fallback cascade were
lazy-imported inside `try: from backend.app.metrics import X ... except
ImportError: pass`. Since `backend.app.metrics` unconditionally imports
`prometheus_client` at module top level (line 11), the `ImportError` guard
was unreachable dead defence — either the whole module imports cleanly or
the entire app fails to start. We hoisted the 10 names to the top-level
import block and deleted the 9 try/except wrappers. Net −33 lines,
behaviour identical.

**Pattern for single-site fixes** (6 other modules): replace
`except Exception: pass` with the concrete exception types that can actually
be raised (`asyncio.CancelledError` → cooperative shutdown → debug log;
`asyncpg.PostgresError | ConnectionError` → warning log; `json.JSONDecodeError
| UnicodeDecodeError` → debug log for malformed input; etc.) and add a
meaningful logger call so the handler is no longer silent.

### 2.2 `background.spawn()` helper (commit `07c3f78d2`)

New module: `backend/services/common/background.py` — fire-and-forget
primitive with strong-ref + error surfacing.

```python
from backend.services.common.background import spawn
spawn(long_running_coro(), name="cache_invalidate_client_123")
```

Semantics:

1. Task is retained by a module-level `_inflight: set[asyncio.Task]` until
   completion → GC cannot drop it (fixes the CPython weak-ref gotcha).
2. On completion the `done_callback` removes the task from `_inflight` and,
   if the task raised and was **not cancelled**, logs `logger.error(...,
   exc_info=exc)` — previously swallowed exceptions now surface with full
   traceback.
3. Cancellations are intentionally silent (preserves cooperative shutdown).
4. Caller can still store / cancel / await the returned `asyncio.Task`.

8 tests in `backend/tests/unit/services/common/test_background.py` cover the
contract end-to-end (return type, inflight lifecycle, name propagation,
exception surfacing, cancellation silence, GC prevention, multi-task
independence, inflight cleanup). All green.

### 2.3 Asyncio migration (commit `97997ee62`)

Replaced `asyncio.create_task(...)` with `spawn(..., name=...)` at every
confirmed DROPPED site across 14 modules (26 call sites):

| module | sites |
| ------ | -----:|
| `services/events/handlers.py` | 7 |
| `app/routers/crm_practices.py` | 5 |
| `app/routers/visa_oracle.py` | 4 |
| `services/rag/agentic/orchestrator_core.py` | 4 |
| `services/crm/cache_query.py` | 2 |
| `services/rag/evaluation/monitoring.py` | 2 |
| `services/portal/_mixins/documents.py` | 2 |
| 7 single-site modules (auth, conversations, crm_enhanced_documents, company_router, crm_clients, workflow/queue, analytics/team_timesheet_service) | 1 each |

Tests updated where `patch("...asyncio.create_task", MagicMock())` was used —
they now patch `...spawn` directly (`tests/routers/test_crm_practices.py`,
`tests/routers/test_crm_clients.py`). 25/25 pass on the touched suites.

**Explicit non-migrations** (verified SAFE by code reading):

- `services/olympus/guardian.py` L118–L119 — tasks are members of the
  `self._tasks = [...]` literal.
- `services/workflow/queue.py` L166 — `heartbeat_task = ...` is stored and
  awaited at worker shutdown.
- `services/analytics/team_timesheet_service.py` L59 — `self.auto_logout_task`.
- `services/rag/agentic/orchestrator_core.py` L864 — `nlm_task = ...` is
  awaited within the same function.

These were correctly classified SAFE by the audit and are left untouched.

---

## 3. Helper design notes

`background.spawn()` is deliberately **not** a context manager or a class.
Three design choices worth recording:

- **Module-level `_inflight` set** (not a scoped registry per-caller). Every
  fire-and-forget task is transient by definition; a global set is the
  simplest way to retain strong-refs without threading ownership through
  every call site.
- **`add_done_callback` instead of a supervising loop**. We do not want
  another long-lived task; the callback fires from inside the event loop
  that scheduled the task, runs in O(1), and cleans up `_inflight`
  immediately.
- **Cancellation is silent**. `CancelledError` is how cooperative shutdown
  propagates through awaited tasks. Surfacing it as an ERROR would swamp
  the logs every time the app stops. If a future caller wants cancellation
  alerts, they can still await the returned task and catch it there.

Not implemented (YAGNI):

- No timeout — `asyncio.wait_for` at call site is the correct place.
- No retry — call sites that need retry already implement it with
  `tenacity` or similar.
- No metrics — `backend.app.metrics` already has `background_tasks_total`
  counters that any caller can bump as needed.

---

## 4. Test coverage

| suite | file(s) | tests | status |
| ----- | ------- | -----:| ------ |
| background helper | `tests/unit/services/common/test_background.py` | 8 | ✅ |
| crm routers | `tests/routers/test_crm_practices.py`, `tests/routers/test_crm_clients.py` | 17 | ✅ |
| llm gateway | `tests/unit/services/rag/agentic/test_llm_gateway*.py` | 49 | ✅ (2 pre-existing ModuleNotFoundError on `fakeredis`, unrelated) |

Full in-scope suite was not re-run end-to-end (fakeredis-gated suites and
integration tests need external services not available on Air). Import
chain verified for all 22 modified modules.

---

## 5. Raccomandazioni per pass successive

1. **`backend/llm/*` HIGH silent-handlers (9 residuals)** — assigned to
   air-c3. Same pattern as `llm_gateway.py` refactor: most are
   `ImportError/pass` around optional metric emit points, which should be
   hoisted to top-level once c3 audits whether prometheus_client is a hard
   dep in that sub-module too.
2. **`backend/agents/*` HIGH silent-handler (1 residual)** — assigned to
   air-c2.
3. **Guardian false positives in the asyncio audit** — improve
   `scripts/audit_asyncio_tasks.py` to recognise `[... create_task(...) ...]`
   list literals as SAFE. Trivial AST upgrade. Filed as a TODO in the
   audit script header for a future pass.
4. **Medium silent-handlers (130 residuals)** — outside pass-2 scope.
   Low-value bulk; recommend a targeted sub-pass only for CRM/portal modules
   where UU-PDP audit trail matters (PII handlers).
5. **`spawn()` adoption discoverability** — add a VADEMECUM entry:
   "fire-and-forget background work → `spawn()`, never bare
   `asyncio.create_task(coro)`". Most drift happens at PR-review time; a
   checklist item catches it early.

---

## 6. Commits (this branch)

```
97997ee62 refactor(pdp): migrate 26 fire-and-forget asyncio sites to background.spawn()
b514bba19 fix(pdp): typize 7 silent handlers across 6 modules
e0a8a87ef refactor(rag/llm_gateway): remove 9 dead ImportError/pass guards
07c3f78d2 feat(background): spawn() primitive + asyncio audit
```

All based on `origin/main @ 71dfacb54`. No merges, no pushes — awaiting
review by Zero.

---

## 7. Scope boundary flags

Two places where the prompt assumed a broader scope than c1's session
boundary:

- Prompt top-of-mind file list ("rag/agentic 16, service_initializer 6,
  confirmation_service 6...") counted *all 158* findings, not only the 25
  HIGH ones. The real HIGH distribution skewed heavily toward
  `llm/llm_gateway.py` (9) which turned out to be in-scope as a service
  layer file, plus `llm/*` and `agents/*` residuals that are off-limits.
- Target "high ≤ 10" is achieved cleanly for the c1 slice (in-scope HIGH =
  0), but the remaining 10 HIGH live in files that will stay off the
  target metric until c2/c3 run their passes.

No scope creep taken — every change is on files the session prompt
whitelisted. The helper module `backend/services/common/background.py` is
new and empty-of-dependencies; it does not touch `llm/` or `agents/`.
