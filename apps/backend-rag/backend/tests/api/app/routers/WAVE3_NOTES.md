# Oracle Universal Router — Wave 3 Notes

Session: `session/oracle-quirks-cleanup` · Date: 2026-04-22 · Model: Claude Opus 4.7 (1M)
PR #177 (wave 2) → PR TBD (wave 3)

Wave 3 closes the three wave-2 follow-ups (stub cleanup, real-service
integration, drop-field observability) without touching the router's
public contract beyond removing the stubs that wave 2 had flagged.

---

## Empirical metrics (pytest-cov 7.1.0, Python 3.11.11)

Command (from `apps/backend-rag/`):

```
source .venv/bin/activate
PYTHONPATH=. coverage run -m pytest \
  backend/tests/api/app/routers/test_oracle_universal.py \
  backend/tests/api/app/routers/test_oracle_universal_integration_real.py -q
coverage report --include='backend/app/routers/oracle_universal.py,backend/services/oracle/oracle_service.py'
```

| Stage              | Tests | Router stmts | Router cov | Service stmts | Service cov |
| ------------------ | ----- | ------------ | ---------- | ------------- | ----------- |
| Wave 2 baseline    | 42    |  95          | 100.00%    | 209           | ~0%         |
| Wave 3 after 3 PRs | 47    |  98          | 100.00%    | 209           | 61.72%      |

Wave 3 adds 5 narrow-integration tests that for the first time exercise
the real `OracleService.process_query` adapter, lifting the service from
effectively 0% (wave 2 patched the whole coroutine) to 61.72%. The
uncovered 80 lines are concentrated in branches that require a live
Postgres pool (memory orchestrator, golden answer service, feedback
store) or the real orchestrator (error-handling branch 468-486).

Router grew from 95 → 98 stmts because wave 3 wires a dedicated logger
and a `sentry_sdk.set_tag` call on the drop-field branch (commit 3).

---

## Part 1 — Q3 stub removal (commit 1)

### Caller survey

Monorepo grep across `~/Desktop/nuzantara/` for path literals
`/api/oracle/drive/test`, `/api/oracle/gemini/test`,
`/api/oracle/user/profile`:

| File                                                                 | Kind                    | Runtime caller? |
| -------------------------------------------------------------------- | ----------------------- | --------------- |
| `apps/mouth/src/lib/api/schema.d.ts`                                 | generated types (TS)    | **No**          |
| `apps/backend-rag/backend/app/decorators/auth.py` (allow-list entry) | FastAPI perm bootstrap  | **No**          |
| `apps/backend-rag/tests/integration/app/routers/test_oracle_*.py`    | legacy auto-gen tests   | **No** (skipped) |
| `docs/SYSTEM_OVERVIEW.md`, `docs/LIVING_ARCHITECTURE.md`             | prose                   | **No**          |

Notes on the legacy integration file:

- `apps/backend-rag/tests/integration/` lives outside `pytest.ini`'s
  `testpaths = backend/tests`, so the suite is never collected by the
  default CI command.
- Even when collected explicitly, all 14 tests are `@pytest.mark.integration`
  and skip under the default marker selection.
- The fixtures patch symbols removed in the wave 2 OracleService refactor
  (`db_manager`, `google_services`, `reason_with_gemini`,
  `get_golden_answer_service`, `generate_query_hash`), so the file is
  **dead code** regardless.

**Decision: full removal.** Sunset banner rejected — no runtime consumer to
notify, and keeping the stubs would keep the `status=moved_to_service`
payload alive as a false-positive "OK" for anything that scrapes the
endpoints.

### Changes applied

- `backend/app/routers/oracle_universal.py`: drop three deprecated
  `@router.get(...)` handlers (35 LOC).
- `backend/app/decorators/auth.py`: drop `/api/oracle/gemini/test` from the
  API-key allow-list (it was the only stub that had been granted a
  non-default auth mode).
- `backend/tests/api/app/routers/test_oracle_universal.py`: replace the
  two wave-2 "deprecated lock-in" tests with two wave-3 absence tests
  (`test_removed_stubs_return_404`,
  `test_removed_stubs_absent_from_openapi`). Also drop three wave-1
  stub-body tests that are no longer meaningful.
- `apps/backend-rag/tests/integration/app/routers/test_oracle_universal_integration.py`:
  drop the three tests that hit the removed stubs. The other 11 tests in
  that legacy file are left untouched — they are still skipped by default
  and constitute a separate cleanup out of scope.
- `docs/SYSTEM_OVERVIEW.md` and `docs/LIVING_ARCHITECTURE.md`: update the
  surface count from 6 → 3 endpoints and add a removal note.
- `apps/mouth/src/lib/api/schema.d.ts`: **not touched**. It is generated
  from the OpenAPI spec, so the next mouth build (or `openapi-typescript`
  regenerate) will drop the three paths automatically. A manual edit
  would be out of source-of-truth.

---

## Part 2 — Narrow integration vs real OracleService (commit 2)

### Design

`OracleService.__init__` wires nine collaborators (PromptBuilder,
IntentClassifier, ResponseValidator, LanguageDetectionService,
UserContextService, ReasoningEngineService, DocumentRetrievalService,
OracleAnalyticsService, EntityExtractionService). All nine are pure
Python and can be instantiated in a test. `process_query` then reaches
two external boundaries:

1. `_get_orchestrator(search_service)` → `create_agentic_rag(retriever,
   db_pool, ...)` which requires a live `asyncpg.Pool` + Qdrant + LLM.
2. `analytics.store_query_analytics(...)` → opens an `asyncpg`
   connection.

Exercising both would require a Postgres container, a Qdrant image and
an LLM key. That is true e2e territory, not "3-5 test" scope. Wave 3
instead stubs *only* those two boundaries:

- `oracle_service._get_orchestrator` is replaced with a coroutine that
  returns a `_FakeOrchestrator` whose `process_query` is an `AsyncMock`
  parameterised by a real `CoreResult`.
- `oracle_service.analytics.store_query_analytics` becomes a no-op
  `AsyncMock`.

Everything between these two — user context, language detection,
analytics dict-building, the router's Pydantic validation, the
dict → `OracleQueryResponse` mapping — runs for real. That is the
"narrow integration" point on the spectrum between wave 2 (router-only,
service fully mocked) and full e2e (out of scope).

### Tests (5)

1. `test_real_service_happy_path_english_anonymous` — no email, English
   query, asserts success=True + forwarded answer/sources + `en`
   language resolution + `user_profile=None`.
2. `test_real_service_italian_query_detected_as_it` — Italian markers
   make the real `LanguageDetectionService` return `it`.
3. `test_real_service_language_override_wins` — explicit override `id`
   short-circuits detection.
4. `test_real_service_surfaces_clarification` — orchestrator ambiguity
   flag reaches the router response as `clarification_needed` /
   `clarification_question`.
5. `test_real_service_golden_marker_sets_flag` — `golden` in `model_used`
   flips `golden_answer_used`, contract apps/mouth relies on.

TDD discipline: one test was sabotaged with `assert body["success"] is
False` to force RED; it flipped to True on the real flow, confirming
the test harness bites. A second RED was observed independently when
`CoreResult(timings={..., "domain_scores": {"company": 0.88}})` failed
Pydantic validation — see wave 4 TODO below.

---

## Part 3 — Dropped-field observability (commit 3)

Wave 2 added a WARN log when a caller sends `domain_hint`,
`context_docs` or a non-default `response_format`. The log lived on
`backend.app.routers.oracle_universal` (router-wide logger) and was
invisible to Sentry aggregation — you had to scrape Cloud Logging
free-text.

Wave 3:

- **Dedicated logger** `oracle.query.dropped_fields` owned by the router
  module. Ops can now route/mute/aggregate this event independently.
- **Sentry tag** `oracle.dropped_fields` set to the comma-joined field
  names. Fires only on the positive drop branch. `sentry_sdk.set_tag`
  is a no-op when `SENTRY_DSN` is unset or `SKIP_SENTRY_INIT=1`, so it
  is safe to call unconditionally.
- **PII safety**: the tag value is drawn exclusively from a hardcoded
  three-element field whitelist (`domain_hint`, `context_docs`,
  `response_format`). No user data can reach Sentry through this path,
  so the global `_before_send` hook in `sentry_config.py` has nothing
  to redact for this tag. `backend/tests/test_sentry_pii_redaction.py`
  (13 tests) still passes after the change, confirming no regression
  on the existing PII guarantees.

---

## Wave 4 TODO

1. **CoreResult.timings type drift.** `backend/services/rag/agentic/schema.py`
   declares `timings: dict[str, float]`, but
   `backend/services/oracle/oracle_service.py:422` reads
   `routing_stats.get("domain_scores", {})` and the router then reads
   `routing_stats.get("domain_scores", {})` in `domain_confidence`. The
   only way `domain_scores` can reach the response today is if
   `timings` is widened to `dict[str, Any]` (or `domain_scores` is
   promoted to its own `CoreResult` field). Fix: add a `domain_scores:
   dict[str, float]` field on `CoreResult`, update the orchestrator to
   populate it, and read it from oracle_service. Keeps `timings`
   strictly float-only.

2. **OracleService service-layer coverage (38% remaining).** The
   wave-3 integration tests left these branches untested because they
   require a live Postgres pool:
   - `memory_orchestrator` initialisation (lines 275-293, 311-334)
   - `golden_answer_service` caching (238-245)
   - `submit_feedback` (496-497)
   - `_get_db_pool` and the error-handling branch (184-192, 468-486)
   Wave 4 can either add a docker-compose Postgres fixture or split the
   service so the DB-bound helpers live behind a port that can be
   faked.

3. **Legacy integration suite cleanup.**
   `apps/backend-rag/tests/integration/app/routers/test_oracle_universal_integration.py`
   still has 11 tests patching removed symbols. They are all skipped by
   the default collector and by the `integration` marker, but the file
   is dead code and should be deleted or re-written to hit the current
   service layer. Out of scope for wave 3 (Q3-focused).

4. **auth.py allow-list audit.** While removing
   `/api/oracle/gemini/test` from the API-key list, the other
   oracle-scoped entries (`/api/oracle/health`,
   `/api/oracle/personalities`) were not reviewed. Verify they are
   still intentional.

5. **apps/mouth schema regeneration.** The next time the mouth team
   regenerates `schema.d.ts` from the backend's OpenAPI, the three
   removed path types will vanish. If a mouth feature still references
   them at the TypeScript level it will fail to type-check — a wanted
   explicit signal. Coordinate with the apps/mouth owner so the rebuild
   lands in the same sprint as this backend deploy.
