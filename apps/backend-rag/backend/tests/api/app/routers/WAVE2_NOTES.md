# Oracle Universal Router — Wave 2 Notes

Session: `session/oracle-coverage` · Date: 2026-04-22 · Model: Claude Opus 4.7 (1M)
PR #172 (wave 1) → PR TBD (wave 2)

---

## Coverage — Empirical (pytest-cov, Python 3.11.9)

Command:
```
cd apps/backend-rag
PYTHONPATH=. venv/bin/python -m pytest \
  backend/tests/api/app/routers/test_oracle_universal.py \
  --cov=backend.app.routers.oracle_universal \
  --cov-branch --cov-report=term-missing
```

| Stage              | Tests | Stmts | Miss | Branch | BrMiss | Cover   |
| ------------------ | ----- | ----- | ---- | ------ | ------ | ------- |
| Baseline (wave 1)  | 27    |  98   |  0   |   4    |   0    | 100.00% |
| After wave 2       | 42    | 107   |  0   |   6    |   0    | 100.00% |

**Wave 1 was already at 100% line + branch** on `oracle_universal.py`. The
PR #172 body called the coverage "unverified"; wave 2 verified it end-to-end
with pytest-cov (command + raw numbers above). The real wave 1 gaps were
*behavior* gaps — timeout handling, 401 auth path, boundary validation —
not line-coverage gaps. Wave 2 added 15 tests that exercise those
behaviors without changing the line-coverage headline.

The `Stmts` bump 98 → 107 (and `Branch` 4 → 6) comes from the Q1/Q2 router
edits, not from the tests. All new statements + branches are covered.

Net: wave 2 adds **15 tests** (27 → 42), fixes **2 router quirks**
(Q1 warn-on-drop, Q2 dedicated ValidationError branch), and flags **3
stub endpoints** as OpenAPI-deprecated (Q3). No wave 1 assertions were
relaxed; all 27 legacy tests still pass unchanged.

---

## Tests added in wave 2 (15)

### Upstream timeout (3) — the big missing of wave 1

- `test_query_upstream_timeout_is_swallowed_as_200_success_false` — bare
  `asyncio.TimeoutError` raised by the service must not escape as a 500.
- `test_query_upstream_timeout_with_message_surfaces_error_string` —
  `TimeoutError` subclass with a message keeps the message in `error`.
- `test_query_simulated_wait_for_timeout_is_swallowed` — if a caller
  wraps `process_query` in `asyncio.wait_for(..., timeout=0.01)`, the
  resulting timeout is handled the same way as any other exception.

**Lock-in:** the router does NOT today wrap `process_query` in
`asyncio.wait_for` — timeouts are the service layer's problem.
If that changes, these tests force a conscious choice (504 vs. 200
success=false) rather than a silent behavioral drift.

### Auth dependency (2)

- `test_query_returns_401_when_auth_dependency_raises` — if
  `get_current_user` raises `HTTPException(401)`, `/query` responds
  401 and `oracle_service.process_query` is never called.
- `test_query_auth_failure_propagates_custom_status` — 403 + custom
  header `X-Bali-Reason: kyc-pending` flow through verbatim.

### Limit boundary (3)

- `test_query_accepts_limit_equal_to_upper_bound` — `limit=50` passes.
- `test_query_accepts_limit_equal_to_lower_bound` — `limit=1` passes.
- `test_query_rejects_limit_51_with_pydantic_detail` — `limit=51` is
  422 with the detail payload pointing at `limit`.

### Quirk lock-in (7)

- Q1: `domain_hint`, `context_docs`, `response_format` each gets a
  dedicated test proving the field is NOT forwarded to the service
  AND the drop is logged at WARN (4 tests — 3 for drops, 1 to prove
  the default case is quiet).
- Q2: `test_query_malformed_service_response_logs_validation_error` —
  when `OracleQueryResponse(**result)` fails, the response is still
  200 + `success=False` but the error string is now tagged
  `response_validation_error:` and a WARN log is emitted.
- Q3: two OpenAPI-level tests —
  `test_drive_test_stub_is_marked_deprecated_in_openapi` asserts the
  `deprecated=True` flag reaches the generated schema for the three
  stubs but NOT for `/health` or `/query`;
  `test_deprecated_stubs_still_return_original_payload` locks in that
  the response bodies were NOT changed (no schema break for strict
  clients).

---

## Quirk outcomes

### Q1 — domain_hint / context_docs / response_format silently dropped

**Status:** kept in request model, drop is now logged at WARN, lock-in
tests added. No OpenAPI break.

**Why not remove:** the fields are published in `apps/backend-rag/openapi.json`
and flow into the auto-generated `apps/mouth/src/lib/api/schema.d.ts`. Three
existing integration tests in `backend/tests/integration/
test_oracle_extended_integration.py` already send them. Removing the fields
would silently break those callers without a deprecation window.

**Why not wire through to the service:** `OracleService.process_query`
signature currently does not accept these fields. Wiring them is an
`OracleService` change, which the wave 2 brief explicitly prohibits
("NO modifications to OracleService if not strictly needed"). Correctly
routing by `domain_hint` requires new logic inside the domain router,
not just a kwarg passthrough.

**Wave 3 TODO:** either (a) wire the three fields into
`OracleService.process_query` — this is the user-observable fix — or (b)
remove them with a 2-release deprecation window (keep warn-log for one
release, then strip from model + openapi + schema.d.ts in the next one).
Option (a) is correct; (b) is acceptable if (a) proves too expensive.

### Q2 — generic `except Exception` swallows Pydantic `ValidationError`

**Status:** fixed. Dedicated `except ValidationError` branch added before
the generic `except Exception`. Response shape unchanged (still 200 +
`success=False`) but:
1. `error` field is prefixed `response_validation_error:` so Sentry /
   log queries can filter upstream schema drift from transient faults.
2. A WARN log line is emitted naming the router; easy grep target.

**Why not 500:** a 500 for a response-side ValidationError would surface
the router's internal contract to clients, which is a heavier break
than a success=false answer. The log + tagged error give operators the
signal without changing caller behavior.

### Q3 — `/drive/test`, `/gemini/test`, `/user/profile/{email}` are stubs

**Status:** kept, flagged `deprecated=True` at the OpenAPI decorator
level, info-logged on each call. Response bodies are unchanged (adding
a `"deprecated": true` key would break strict consumers).

**Caller audit (2026-04-22):** no Python, TypeScript, or documentation
caller actually hits these three endpoints in-repo. The only references
are:
- `openapi.json` declares them (auto-generated by FastAPI).
- `apps/mouth/src/lib/api/schema.d.ts` declares them (auto-generated from
  openapi.json).
- `backend/app/decorators/auth.py:242` lists `/api/oracle/gemini/test` in
  the public-endpoint allow-list (defensive, not a caller).

**Wave 3 TODO:** regenerate `apps/mouth` schema types (the `deprecated`
flag should now appear), then in a follow-up PR delete the three handler
bodies plus the auth.py:242 entry. That's a visible OpenAPI change and
deserves its own PR.

---

## What wave 2 did NOT do

- **No OracleService change.** Even though Q1 ideally needs it, the brief
  prohibits touching the service layer. The request fields are kept on
  the model with a documented drop.
- **No endpoint removal.** Q3 handlers are only flagged deprecated.
- **No integration tests against a real `OracleService`.** The optional
  fake-in-memory integration test was considered but skipped: wiring a
  fake `OracleService` without touching the real service module is an
  exercise in mocking, not an integration test. The value is low
  because the service is already mocked in all 42 unit tests via
  `patch("backend.app.routers.oracle_universal.oracle_service
  .process_query")`. A proper integration test needs Qdrant + Postgres
  fixtures and belongs in `backend/tests/integration/`, not here.
- **No refactoring of `oracle_universal.py` beyond Q1/Q2/Q3.** The
  Gemini/Drive stubs, the logger shape, and the `_happy_result` helper
  are untouched.

---

## Wave 3 TODO (prioritized)

1. **Q1 high-priority:** wire `domain_hint` through `OracleService.
   process_query` to the domain router so the hint actually influences
   routing. Separate PR touching `OracleService` + its unit tests.
2. **Q3 cleanup:** remove `/drive/test`, `/gemini/test`,
   `/user/profile/{email}` handler bodies + openapi + mouth schema +
   auth.py:242 entry. Single PR with a "BREAKING: remove deprecated
   oracle stubs" header.
3. **Integration test:** real `OracleService` with in-memory Qdrant +
   Postgres fixture, living in `backend/tests/integration/`. Exercises
   the ONE code path that unit tests cannot (the actual service + router
   interaction). Depends on (1) because `domain_hint` wiring should be
   covered by an integration test, not just a unit test.
4. **Pydantic v2 migration sweep:** `feedback.dict()` at
   `oracle_universal.py:190` is Pydantic-v1-style. It works in the v2
   backport layer but is deprecated. Swap to `feedback.model_dump()`
   in the same PR as (1) since that PR already touches feedback flow.

---

## Reality check

- Coverage % measured: **100.00% line + 100.00% branch**, pre and post.
- N tests added / passing: **15 added (27 → 42), all passing.**
- Quirk outcomes:
  - **Q1: deferred with mitigation** (warn-log + lock-in tests).
  - **Q2: resolved** (dedicated branch + log + test).
  - **Q3: deferred with mitigation** (deprecated flag + log + test).
- What wave 2 did NOT do: OracleService wiring (Q1 root cause),
  endpoint removal (Q3 end-state), integration test against real
  service. All three are punted to wave 3 above.
