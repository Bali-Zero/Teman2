# Gear-3 gate conditions — PR #4959 (GARUDA VOA train 2/4, backend)

> Verdict: **PASS-WITH-CONDITIONS** on `1785c8b3867f759e0c2baae4f74b97375048ea0e`.
> Posted as `harness/fable-gate` by the independent Gear-3 grader (Opus 5, effort xhigh),
> 2026-08-26. Supersedes the bare `PASS` posted on the same SHA at 00:12:22Z by the seat
> that authored `1785c8b38` three minutes earlier — a generator=grader collision, not an
> independent verdict.
>
> The eight product invariants HOLD and the funnel is dark by flag, which is why this
> ships. Neither open condition is in the code that serves customers: one is in the gate
> that is supposed to prove that code right, one is in an error envelope on a lane that
> is unwired in production. Both are cheap. Both become expensive on the day the Xendit
> sandbox keys land, which is exactly the follow-up that never gets scheduled.

## Enforcement

| # | Condition | Trigger / deadline | Owner |
|---|---|---|---|
| F1 | Contract-parity gate must cover every mounted operation | **Before train 3 (frontend) lands** — it consumes the generated client | train-02 lane, routed by team-lead |
| F2 | L3 error envelope must match the frozen contract | **Before `GARUDA_XENDIT_SECRET_KEY` is installed** | train-02 lane, routed by team-lead |
| F3 | Close the Sentry frame-locals PII channel on the two new surfaces | **Before `GARUDA_XENDIT_SECRET_KEY` is installed** | train-02 lane, routed by team-lead |

A condition is discharged only by a test that goes RED without the fix. F1 in particular
must be seen failing before it is believed: its whole defect is that it passes while wrong.

---

## F1 — the contract-parity gate is blind to 7 of the 10 live GARUDA operations

**Where:** `apps/backend-rag/backend/tests/app/routers/test_garuda_voa_openapi_parity.py:91-97`
(`_MOUNTED_OPERATION_IDS`) and `apps/backend-rag/backend/app/routers/garuda_orders_router.py:191,273,304,329,385`
(five `@router` decorators, none carrying `operation_id=`).

**Measured, not inferred.** Building the deployed `main_api.app` and enumerating
`/api/visa/voa` yields ten operations. Three carry contract operationIds. Five (all of L3)
carry FastAPI auto-generated ids such as `create_order_from_check_api_visa_voa_orders_post`,
so they cannot be matched to the frozen contract at all. Two (L4) carry the right ids but
are absent from `_MOUNTED_OPERATION_IDS`.

Live vs frozen response sets:

| operationId | live | frozen (`contracts/openapi.yaml`) |
|---|---|---|
| `createOrderFromCheck` | `{201,422}` | `{201,400,401,404,409,422,429,500,503}` |
| `getOrderAndPractice` | `{200,422}` | `{200,401,404,500,503}` |
| `observePaymentBrowserReturn` | `{204,422}` | `{204,400,401,404,409,422,500,503}` |
| `receivePaymentWebhook` | `{204}` | `{202,204,400,401,404,409,422,500,503}` |
| `resolveLateOrder` | `{200,422}` | `{200,400,401,403,404,409,422,500,503}` |
| `requestMagicLink` | `{202,422}` | `{202,400,404,409,422,429,500,503}` |
| `exchangeMagicLink` | `{204,422}` | `{204,400,401,404,409,422,429,500,503}` |

**The gate states this out loud and passes anyway.** Running
`test_unmounted_frozen_operations_are_counted_not_failed` prints, verbatim:

```
garuda-voa: 10 frozen operation(s) not yet mounted: ['createOrderFromCheck',
'exchangeMagicLink', 'getOrderAndPractice', 'listIntakeDocuments',
'observePaymentBrowserReturn', 'receivePaymentWebhook', 'requestMagicLink',
'resolveLateOrder', 'transitionPractice', 'uploadIntakeDocument']
1 passed
```

Seven of those ten answered HTTP requests in the same process, in the same run. Only
`uploadIntakeDocument`, `listIntakeDocuments` and `transitionPractice` are genuinely unmounted.

**Failure scenario:** any future edit to a checkout, webhook, or magic-link response shape
drifts from the frozen contract with nothing going red — on precisely the two lanes that
carry money and authentication. This is cicatrix family #2 (esiste != armato) crossed with
#6: the file's own docstring records that it exists because "the contract agreed with itself
while the router's real generated schema drifted", and it now reproduces that on the surfaces
that matter most.

**Fix (the file already prescribes it):** add `operation_id="createOrderFromCheck"` etc. to
the five L3 decorators; move all seven live operationIds into `_MOUNTED_OPERATION_IDS`; add a
dedicated `_assert_status_parity` call per operation, as the docstring's own instruction at
lines 197-204 requires. Expect red on the first run — that is the discharge.

---

## F2 — L3 error responses violate the frozen error envelope and drop the privacy headers

**Where:** `apps/backend-rag/backend/app/routers/garuda_orders_router.py` (28 `HTTPException`
raise sites, e.g. `:71-73`, `:110-112`, `:207`, `:219`, `:243-266`, `:300`, `:352-354`,
`:359-361`, `:366-368`, `:402`, `:417-432`), reshaped by
`apps/backend-rag/backend/app/setup/exception_handlers.py:86-90`
(`http_exception_handler`, registered in both factories:
`app/setup/app_factory.py:695` and `app/main_api.py:233`).

**Measured against the running app**, flag off:

- L2 / L4 — `{"code":"GARUDA_PUBLIC_DISABLED","retryable":false,"message_key":"garuda_voa.error.unavailable"}`
  plus all three privacy headers.
- L3 — `{"detail":{"code":"GARUDA_PUBLIC_DISABLED","retryable":false},"correlation_id":"..."}`
  plus **no privacy headers at all**.

`products/garuda-voa/contracts/errors.yaml:6-9` defines `ErrorResponse` as
`additionalProperties: false, required: [code, retryable, message_key]`. L3 nests the tuple
under `detail`, omits `message_key`, and adds `correlation_id`.

**Two distinct failures, one cause:**

1. The TypeScript client generated from the frozen contract reads `err.code` and gets
   `undefined` on every L3 error, so train 3's error and decline mapping falls through to a
   generic message on the checkout lane. The product invariant is "never a bare error".
2. `_privacy_headers(response)` at `garuda_orders_router.py:99-102` mutates the injected
   `Response`, and FastAPI merges those headers into the final response only when the handler
   **returns**. On a raised `HTTPException` that merge never runs, so every L3 error ships
   without `Cache-Control: no-store, private`, `Referrer-Policy: no-referrer`, and
   `X-Robots-Tag`. The contract's `x-public-privacy-response-headers` says every response,
   success and error alike; `test_every_public_response_carries_the_privacy_headers` asserts
   that about the YAML document, never about the server.

**Fix:** give L3 the same `_error()` + `route_class` treatment L2 already has
(`garuda_voa_public.py:73-99`, `:183-191`) — return contract-shaped `JSONResponse`s carrying
`_PRIVACY_HEADERS`, rather than raising `HTTPException` into a generic handler that rewraps
them. F1 is why this shipped unnoticed; discharging F1 first will surface F2 automatically.

---

## F3 — PII reachable via Sentry frame locals on two newly added surfaces

**Where:** `apps/backend-rag/backend/app/routers/garuda_orders_router.py:220-266` and
`apps/backend-rag/backend/services/garuda_documents/service.py:117`. Platform context:
`apps/backend-rag/backend/app/setup/sentry_config.py:329-337`.

`sentry_sdk.init` does not set `include_local_variables`, so the SDK default `True` applies
and frame locals are captured on every event. `_before_send` -> `_scrub` walks the event, but
the module's own docstring at `sentry_config.py:126-133` concedes it cannot reach a bare
personal name, and `_LABELLED_ID_RE` at `:182-185` requires `[\s:=#]*` between the label and
the digits — a dataclass repr renders `passport_number='A1234567'`, and the quote breaks the
match.

1. `garuda_orders_router.py:235-266` catches exactly six named exceptions around
   `repository.create_order_and_checkout`. Any other exception (a raw asyncpg error, an
   unmapped provider failure) propagates uncaught while `applicant` and `applicant_raw` are
   still live in the frame — full legal name and passport number, unredacted, to Sentry.
2. `garuda_documents/service.py:117` calls `logger.exception(...)` at ERROR level, above
   Sentry's `event_level`, inside `submit_document` — whose frame still holds `raw_bytes`,
   the uploaded passport image. No key- or shape-based rule in `_scrub` touches binary data.

**Why this is a condition and not a block:** it is a platform property shared with every
PII-handling router already in this app, and both paths are unreachable in production today —
L3 is unwired without `GARUDA_XENDIT_SECRET_KEY` (`service_initializer.py:1478-1479`), and
`_work_item_hook` is `None`. Both go live on the same day the keys are installed.

**Fix:** set `include_local_variables=False` in `sentry_sdk.init` for this service, or add a
bare `except Exception:` at the two sites that re-raises without the PII-bearing frame in
scope. Adjacent and currently safe but fragile: `services/garuda_portal/magic_link_store.py:159`
uses `logger.warning(..., exc_info=True)` in a frame holding `raw_token`; WARNING is a
breadcrumb today and breadcrumbs carry no frames, but the sibling `garuda_portal_auth.py`
documents choosing `.error()` over `.exception()` at the same boundary for exactly this reason
and this file does not. One severity bump makes it live.

---

## Informational — not conditions

- **F4.** All 7 tests in `apps/backend-rag/backend/tests/services/garuda_flow/test_retention.py`
  ERROR rather than SKIP without a local Postgres: the `garuda_281_sandbox` fixture at
  `apps/backend-rag/backend/tests/scripts/visa_engine/test_garuda_voa_retention.py:109` calls
  `asyncpg.connect(_ADMIN_URL)` with no reachability guard, while every sibling Postgres test
  in this PR skips cleanly. Green in CI, which has Postgres.
- **Invariant 3 is only half-present in this train.** DECLINE is a 201 carrying a closed
  19-code vocabulary and is never a bare error, but nothing in this diff produces an
  alternative or a WhatsApp handoff. `services/garuda_ops/funnel_dashboard.py` ships the
  `decline_to_whatsapp` metric while `declined_whatsapp_handoffs` is caller-supplied and no
  caller exists. Correctly train 3's scope — flagged because nothing pins a
  reason_code -> alternative mapping, so a code with no alternative fails silently downstream.
- **CI at posting time.** Backend Shards 1-3, CodeQL (python), Schemathesis and E2E were
  still pending. This verdict rests on the grader's own local runs, not on a green CI rollup.
  A fresh CodeQL run is pending on `1785c8b38`; anything above `note` changes the picture.

## What the grader did NOT examine

- Test-coverage adequacy of the production code — the gap that produced `1785c8b38`. This
  pass verified what the code does, never what would go red if it were wrong. Other one-line
  policy helpers in this diff were not swept for the same shape.
- The 2,441 lines of SQL in migrations 281/284/285/286/287 line-by-line (audited by a
  dedicated read-only pass; numbering and the `-- === ROLLBACK ===` convention spot-verified).
- `services/garuda_ops` internals beyond its tests and its logging sites.
- Any live or staging surface — the funnel is dark and no Xendit keys are installed.
