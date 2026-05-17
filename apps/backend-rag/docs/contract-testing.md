# Contract Testing (Schemathesis)

> Finding #3 of the modernization audit 2026-05-18. Shipped non-blocking
> in PR `ci/schemathesis-contract-tests-2026-05-18` to baseline the
> failure surface without blocking unrelated PRs.

## What it does

[Schemathesis](https://schemathesis.readthedocs.io/) is a property-based
contract testing tool. Given the FastAPI `/openapi.json` spec, it
generates Hypothesis payloads for every operation and asserts the
response conforms to the declared schema (status code, content-type,
body shape, response headers). It also runs a configurable set of
`--checks=all` (e.g. `status_code_conformance`,
`response_schema_conformance`, `not_a_server_error`, `content_type_conformance`).

The check runs in **ASGI-direct mode** (`--app=backend.app.main:app`),
i.e. the FastAPI app is loaded as a Python object and called via the
ASGI protocol — no live HTTP server, no external services required. The
app boots in degraded mode (`app.state.startup_failed=True`); endpoints
that exercise DB/Redis/Qdrant respond with 5xx, but `/openapi.json` is
fully populated because routes are registered at import time.

## Why we need it

The scar from 2026-05-02 (PR #422 → #423 → #424, 3 hotfix chained):
unit tests green, production endpoint returned 404 because the router
was added to `router_manifest.py` but never imported by
`router_registration.py`. Another shape of the same scar: a router was
included but its path was missing from `PUBLIC_ENDPOINTS`, so
`HybridAuthMiddleware` blocked unauthenticated `/health` requests with
401 in prod despite a green unit suite.

Schemathesis catches both classes at PR-check time:

- A 404 on a path that the spec declares as `200|4xx` fails
  `status_code_conformance`.
- A 401 on a path the spec declares as `200` without a `401` response
  fails the same check.

## Reproduce locally

```bash
cd apps/backend-rag
source .venv/bin/activate
pip install 'schemathesis>=3.36.0,<4.0'

# ASGI mode — no live server needed
PYTHONPATH=. schemathesis run \
  --app=backend.app.main:app \
  --checks=all \
  --hypothesis-max-examples=10 \
  --stateful=none \
  -H "Authorization: Bearer dummy" \
  /
```

Drop `--hypothesis-max-examples=10` for a faster smoke run (default is
100 examples per operation = much slower).

To debug a single failing operation:

```bash
PYTHONPATH=. schemathesis run \
  --app=backend.app.main:app \
  --include-path "/api/channels/{name}/health" \
  --hypothesis-max-examples=50 \
  /
```

## Interpret the report

The CI job uploads `schemathesis-report/` as a workflow artifact. Two
artifacts inside:

- `run.log` — full Schemathesis stdout with per-operation result
  (`P` pass, `F` fail, `E` error). Failed operations include the
  minimal Hypothesis-shrunk payload that triggered the failure.
- `junit.xml` — machine-readable JUnit report. Can be wired into a
  GitHub Check annotation later.

A typical failure entry:

```
F GET /api/channels/{name}/health
    response_schema_conformance: response body does not match the schema
    in /components/responses/HealthResponse (missing required key `status`).
    Repro: schemathesis replay <hash>
```

False positives to ignore:

- **5xx on endpoints that need DB/Qdrant/Redis.** In degraded mode the
  service is unreachable; the endpoint returns 503 or 500, which fails
  `not_a_server_error`. Suppress per-operation via OpenAPI extension
  `x-schemathesis-skip: true` if the endpoint cannot be tested without
  a real backend. **Do NOT blanket-disable the check** — that's the
  whole point.
- **Hypothesis timeouts on endpoints that wrap LLM calls.** Already
  handled by `--hypothesis-deadline=10000` + `too_slow` suppression.

## Promote to required (blocking) check

Promotion criteria (all three must hold):

1. **Two consecutive weeks** of contract-tests runs on `main` with zero
   genuine failures (only false positives that have been documented
   and suppressed).
2. **No flaky runs.** If Hypothesis seeds need pinning to stabilize,
   pin them and document why.
3. **Triage owner identified.** Someone on the team commits to looking
   at the report within 1 business day of a failure.

Once green, remove `continue-on-error: true` from
`.github/workflows/contract-tests.yml` and add the job name to the
`Required status checks` list in the GitHub branch protection rules
for `main`.

## Future scope

- **Stateful tests** (`--stateful=links`) once we wire OpenAPI `links`
  on at least one chain (e.g. `POST /api/clients` → `GET
/api/clients/{id}`). Catches contract violations that only surface
  across multiple requests.
- **Auth profile.** Currently a dummy Bearer token. Could be upgraded
  to a real JWT minted with the test `JWT_SECRET` so endpoints that
  validate the token (not just its presence) actually exercise the
  authenticated path.
- **Coverage delta.** Schemathesis reports operation coverage; a
  follow-up PR could fail the build if coverage regresses below a
  threshold.
