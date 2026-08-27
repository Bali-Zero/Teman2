# When the payment keys arrive — the exact steps (2026-08-27)

> Answers item 6 of Zero's 2026-08-25 ruling: _"l'elenco esatto dei passi per quando arrivano le
> chiavi Xendit"_. Every fact below was read from `origin/main` this turn and is cited to
> `file:line`. Nothing here is inferred from a plan document.

## The headline, because it is the opposite of what you would assume

**Setting the live keys will NOT work.** `XenditPaymentProvider.__init__` refuses them:

```
apps/backend-rag/backend/services/payments/xendit.py:95
    if not secret_key.startswith("xnd_development_"):
        # Fail closed rather than risk a live key reaching this sandbox
        # adapter — ASSEMBLY-LINE G5 forbids a real charge in this build.
        raise ValueError(
            "XenditPaymentProvider requires a sandbox (xnd_development_) secret key"
        )
```

So the day the **live** keys arrive is a **code change**, not a secrets change. That guard is
deliberate and should not be deleted in a hurry — it is the one thing standing between this build
and a real charge on a real card. Going live means replacing it with a decision (an explicit
"live" mode that is switched on knowingly), not removing it.

> ### ⚠️ Correction, 2026-08-27 — this document said the opposite, and it was wrong
>
> An earlier version of this file claimed _"sandbox keys work today with no code change at
> all"_. **That was false when written.** The provider block described below lived only inside
> `initialize_services`, and the Fly process that actually mounts the GARUDA routers (`api`)
> never runs that function — it runs `initialize_services_light`. Setting the four sandbox
> variables on their own would have changed nothing: the routers would have gone on answering
> **503**, and the 503 would have looked exactly like the documented "keys not configured yet"
> fail-closed, so nobody would have suspected wiring.
>
> This was found by running the live funnel as a customer, not by any test — the guard that now
> prevents it (`backend/tests/setup/test_api_process_wires_the_state_its_routers_read.py`)
> did not exist because nothing in the repo compared what a process _mounts_ against what its
> init path _wires_. Fixed in **PR #5098**.
>
> **The claim is true only from #5098 onward.** If you are reading this on a checkout that
> predates it, sandbox keys alone will not switch the product on.

With that fix in place, **sandbox keys work with no further code change**, which is exactly what
a dark launch needs.

## Phase 1 — sandbox, available immediately, no code change (requires PR #5098)

The provider block is gated on one variable being non-empty
(`app/setup/service_initializer.py:1478-1479`). While it is empty, the block is skipped and
`app.state.garuda_order_repository` / `garuda_payment_provider` stay unset — which the webhook
route and `get_repository()` already answer with a fail-closed **503**. That is today's state.

Set these four on `nuzantara-rag`:

| Variable                       | Read at                    | Note                                                                       |
| ------------------------------ | -------------------------- | -------------------------------------------------------------------------- |
| `GARUDA_XENDIT_SECRET_KEY`     | `service_initializer:1478` | **The gate.** Must start `xnd_development_` or startup raises ValueError.  |
| `GARUDA_XENDIT_CALLBACK_TOKEN` | `service_initializer:1492` | Verifies the `x-callback-token` header on every webhook (`xendit.py:175`). |
| `GARUDA_XENDIT_FEE_BPS`        | `service_initializer:1499` | **Defaults to `"0"`.**                                                     |
| `GARUDA_XENDIT_FEE_FIXED_IDR`  | `service_initializer:1500` | **Defaults to `"0"`.**                                                     |

Two more are already correct and need no action:

- `GARUDA_PUBLIC_BASE_URL` — defaults to `https://balizero.com` (`service_initializer:1496`), the
  canonical apex. `www.` 308-redirects to it.
- `GARUDA_ENVIRONMENT` — defaults to `"PRODUCTION"` (`service_initializer:1432`, `:1506`).

⚠️ **The two fee variables default to zero, silently.** Those figures must come from the actual
Xendit contract — they are not in this repo and must not be guessed here. Leaving them at `0` does
not fail; it just makes the fee arithmetic wrong in whatever consumes it, without any error. Decide
them deliberately, from the signed rate card, before a real reconciliation depends on them.

## Phase 2 — the code change that live keys require

Not a secrets task. It needs its own PR, and at minimum:

1. Replace the `xnd_development_` prefix guard with an explicit two-mode provider — sandbox stays
   the default, live is opt-in and named. Never widen the guard to "accept anything".
2. `_SANDBOX_BASE_URL = "https://api.xendit.co"` (`xendit.py:47`) is **already Xendit's real API
   host** — the sandbox/live split is carried by the KEY, not the URL. So do not go looking for a
   second base URL to switch; there isn't one, and that is precisely why the key-prefix guard is
   load-bearing.
3. A test that a live-prefixed key is refused unless live mode is explicitly on — guilt and
   innocence both, or the guard is decorative.

## What is already true, and what is still unproven

Verified live on 2026-08-27, after Zero set `GARUDA_PUBLIC_ENABLED=true` and
`GARUDA_OUTBOX_CONSUMER_ENABLED=true` and redeployed all 4 machines:

- ❌ **RETRACTED — the funnel is NOT open, and this bullet used to claim it was.** The evidence
  offered was `GET /api/visa/voa/eligibility-checks/<bogus id>` answering
  `404 {"code":"RESULT_NOT_FOUND"}`. That probe proves the **flag**, not the funnel: the GET
  handler short-circuits on a missing result-session cookie _before_ it ever touches the store,
  so a healthy funnel and a completely unwired one both produce that 404. It is a probe that
  cannot go red.
- ❌ **On `balizero.com` the funnel is not reachable at all.** Measured 2026-08-27:
  `https://balizero.com/visa/voa` returns HTTP **200** carrying a Next.js
  `NEXT_HTTP_ERROR_FALLBACK;404` — "Page Not Found". Cause: `apps/mouth/.../visa/voa/layout.tsx`
  calls `notFound()` unless `GARUDA_PUBLIC_ENABLED` is the literal `"true"`, and that variable was
  set on **Fly** (the backend) — the frontend is a **separate Vercel deployment with its own
  env**. Same variable name, two platforms, neither aware of the other. Flipping the Vercel one is
  the gesture `products/garuda-voa/product.yaml` owner-decision 0 calls go-live, and that decision
  is `blocked-on-all-above-and-on-the-parent-page`; it is Zero's call, not a session's.
- 🔴 **The first customer action answered HTTP 500 on every request until PR #5108.** Two
  independent defects stood between "flag on" and "a visitor gets a verdict", and neither was
  visible to any test:
  1. **PR #5098** — the GARUDA stores were wired only in `initialize_services`, which the `api`
     process (the only one that MOUNTS these routers) never runs. Result: `503
PERSISTENCE_POLICY_UNAVAILABLE`, indistinguishable from this document's own "keys not
     configured yet" fail-closed.
  2. **PR #5108** — with the store finally wired, `check_store.create()` pre-serialized
     `reason_codes` with `json.dumps` while both pools register a `jsonb` codec whose encoder IS
     `json.dumps`. Double-encoded, the array landed as a JSONB scalar string, and migration 286's
     CHECK calls `jsonb_array_length()` on it: SQLSTATE 22023, escaping as a bare 500 for every
     payload shape. The integration suite passed 10/10 because its pools lacked the codec.
- ⬜ **Nothing has ever been exercised**: `garuda_voa_check_results` = 0 rows,
  `garuda_voa_check_idempotency` = 0 rows, `garuda_orders` = 0 rows, `garuda_order_outbox` = 0 rows.

**Read this as the lesson it cost.** "Flag on" ≠ "wired" ≠ "works" ≠ "reachable by a visitor" —
four different claims, and this product satisfied only the first for three days while every gate
was green. Do not accept a probe that a broken system would also pass.

## The residual risk the keys will expose, named precisely

Measured 2026-08-27: **no test in this repo ever reaches a real Xendit endpoint.** Every payment
test uses `httpx.MockTransport` or an `AsyncClient` that is never called — verified by grep across
`backend/tests/services/payments/` and `backend/tests/services/garuda_orders/test_webhook_router.py`.
80 tests pass there, and they prove the parts that are ours: event parsing, checkout redirect,
rejecting an invalid signature _before_ any state change, the order state machine, and idempotent
second delivery.

What they cannot prove, and what the sandbox key will test for the first time:

1. **that our invoice payload matches Xendit's actual API contract** — field names, required
   fields, the amount's units and type;
2. **that our signature verification matches Xendit's real callback format** — a mismatch here
   fails CLOSED (the webhook rejects a genuine payment), which is the safe direction but looks
   identical to an attack in the logs;
3. **that the redirect Xendit actually sends the browser back to** is the one
   `GARUDA_PUBLIC_BASE_URL` builds.

None of these is a reason to delay. They are the reason the first sandbox purchase must be made
and _watched_, rather than declared once the key is set.

## The one test purchase that closes all of it

The mandate's own DoD. Once Phase 1 is set, one order through the sandbox proves, in a single
stroke, everything a log line cannot:

1. an order row appears in `garuda_orders`;
2. the paid webhook enqueues `portal_invite`, `payment_paid_email`, `practice_release` into
   `garuda_order_outbox`;
3. those rows gain a non-null `dispatched_at` — **this is the consumer proving itself**;
4. a `clients` row exists, a portal invitation is actually delivered by email, and the order
   confirmation email arrives;
5. the queue drains to empty.

Anything short of that leaves the state this product was in until today: green everywhere, inert in
production.
