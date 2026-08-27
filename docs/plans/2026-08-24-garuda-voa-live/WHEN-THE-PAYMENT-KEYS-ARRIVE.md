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

| Variable                       | Read at                    | Note                                                                                                                     |
| ------------------------------ | -------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `GARUDA_XENDIT_SECRET_KEY`     | `service_initializer:1478` | **The gate.** Must start `xnd_development_` or startup raises ValueError.                                                |
| `GARUDA_XENDIT_CALLBACK_TOKEN` | `service_initializer` §5.7 | **Also a gate, as of 2026-08-27.** Verifies `x-callback-token` on every webhook. Empty is no longer armable — see below. |
| `GARUDA_XENDIT_FEE_BPS`        | `service_initializer:1499` | **Defaults to `"0"`.**                                                                                                   |
| `GARUDA_XENDIT_FEE_FIXED_IDR`  | `service_initializer:1500` | **Defaults to `"0"`.**                                                                                                   |

Two more are already correct and need no action:

- `GARUDA_PUBLIC_BASE_URL` — defaults to `https://balizero.com` (`service_initializer:1496`), the
  canonical apex. `www.` 308-redirects to it.
- `GARUDA_ENVIRONMENT` — defaults to `"PRODUCTION"` (`service_initializer:1432`, `:1506`).

⚠️ **The key and the token are ONE credential — arming half of it takes real money and delivers
nothing.** Corrected 2026-08-27, after measuring it. `verify_signature` rejects on
`not received or not hmac.compare_digest(received, token)`, so with an **empty configured token
EVERY input is rejected** — including a header carrying an arbitrary value, because
`compare_digest(x, "")` is False for any non-empty `x`. Nothing gets in, so this was never a
security hole. It was a money hole: the arming gate required only `GARUDA_XENDIT_SECRET_KEY` while
this token defaulted to `""`, so setting one variable and forgetting the other **opened checkout
while making every legitimate Xendit callback answer 401**. The customer is really charged, the
order never leaves `awaiting_payment`, and nothing surfaces to them — the only trace is a 401 in
the Fly logs that nothing alerts on.

That shape is now unreachable rather than merely documented:

- `XenditPaymentProvider.__init__` refuses a blank `callback_verification_token` outright, next to
  the existing sandbox-key guard — one place every caller must pass, so a future second call site
  cannot reintroduce it.
- §5.7 requires BOTH variables before it arms anything, and logs which half is missing by name
  instead of letting a `ValueError` become one generic "wiring failed" line.
- Guilt + innocence: `backend/tests/services/payments/test_xendit_callback_token_guard.py`. Removing
  the constructor guard turns 5 of them red.

So: **set both, or neither.** Setting only the key now fails closed with a named error, which is the
correct outcome — but it is still a wasted deploy, so set them in the same `fly secrets set` call.

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
- ✅ **CORRECTED 2026-08-27 (later the same day): legs 1-2 have now been exercised, and they
  work.** The "0 rows everywhere" line above this was true when written and is not any more. A live
  walk as an anonymous visitor produced `201 {"verdict":"ACCEPT","reason_codes":[],
"published_filing_deadline":"2026-09-26","price_idr":790000}`, a `Location: /visa/voa/<id>` and a
  `garuda_result_session` cookie (`HttpOnly; Secure; SameSite=none; Domain=.balizero.com`), and a
  subsequent GET with that cookie returned **200** with the byte-identical payload — so rows really
  are persisted and readable. `garuda_orders` and `garuda_order_outbox` remain at zero, correctly,
  because no order can be created without the payment key.
  **This is the probe the retracted bullet above was missing**, and it can go red: the result id and
  the session secret come from the response HEADERS (the 201 body carries neither), the same link
  with **no** cookie and with a **forged** cookie both answer `404 RESULT_NOT_FOUND` — identical
  shapes, so the error code does not even confirm the id exists — and replaying the same
  `Idempotency-Key` returns the SAME result id rather than minting a second check. A missing
  `Idempotency-Key` is rejected `400 IDEMPOTENCY_KEY_REQUIRED`: the header is mandatory on the
  CHECK, not only on the order.
- 🟡 **The tracker changed answer on 2026-08-27 and the new answer is the correct one.** It used to
  return **503** — reading an order's status asked production for a payment credential it does not
  need. PR #5112 decoupled them, and after the deploy the same request returns
  **401 `SESSION_REQUIRED`**, measured with no cookie AND with a valid result-session cookie. So the
  tracker is gated on the **magic-link portal session**, not on the result link — better than
  assumed, and worth knowing before you read a 401 here as a fault.

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

## ⛔ The pre-arm blocker this document was missing — read before setting the keys

> ### ✅ Corrected 2026-08-28 — eight of the thirteen are now routed, and the alarm design below was wrong
>
> The section as written said **ten of thirteen** `job_type` values had no handler. Measured on
> `origin/main` this turn, `build_handlers` registers **8**: `checkout_ready_email`,
> `payment_paid_email`, `payment_failed_email`, `payment_expired_email`, `refund_email`,
> `practice_release`, `practice_received_email`, `portal_invite`. The five customer emails landed
> in **PR #5128** (`53efc00fab`). What is still unrouted is exactly the five `staff_page_*` money
> anomalies, and they are in **PR #5129** — open and armed at the time of writing, not merged.
>
> **The alarm design in the last paragraph is retired, and its retirement is the point.** It asked
> for an `unroutable` alarm _scoped to a declared-unbuilt allowlist_, because an unscoped
> `unroutable > 0` would have fired forever for ten known-missing types. Once #5129 lands there is
> no such category left: the allowlist is EMPTY, so the scoping mechanism has nothing to hold and
> plain **`unroutable > 0`** becomes a true signal. A scoped alarm shipped now would be a mute
> switch with no reason to exist — exactly the shape that silences a real signal (superscar #2).
> The alarm itself is still UNBUILT; it belongs in the same `_run_garuda_outbox_scheduler` block
> #5129 touches, so it is the change that follows it, tracked in the `modus` PENDING-ARMS outbox
> row (#5132).
>
> **What did NOT change:** every word about why this is latent today and live the instant you arm.
> None of these thirteen jobs is produced while `GARUDA_XENDIT_SECRET_KEY` is unset, so **not one
> of the eight routed handlers has ever delivered anything in production**. Routed is not armed.
> The proof is a real sandbox purchase, not this table.

**Historical record — the state on 2026-08-27, when this section was written:** production code
enqueues **13** distinct types — twelve from `garuda_orders/repository.py`, plus
`practice_received_email` from `garuda_portal/practice.py::mint_received_practice`, which is the one
people miss because it is enqueued by the function that mints the practice rather than by the
repository. `outbox_handlers.py` registered **3**: `payment_paid_email`, `practice_release`,
`portal_invite`.

The consumer handles the gap correctly — an unroutable type is counted, logged once per pass, and
its attempt bump is rolled back so it never marches toward exhaustion. **Nothing pages on it**, and
that is the exposure. The ten without a handler were:

| Then unhandled                                                                          | What it means the moment a real card is used                                                                                                                                                                                  | Now                  |
| --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| `payment_failed_email`, `payment_expired_email`, `refund_email`, `checkout_ready_email` | a customer whose card is declined, whose invoice expires, or who is refunded is told nothing                                                                                                                                  | routed — PR #5128    |
| the five `staff_page_*` jobs                                                            | duplicate charge, late-paid-after-refund, late-paid-after-terminal, payment failure, refund-out-of-order — **every money anomaly page reaches nobody**                                                                        | PR #5129, not merged |
| `practice_received_email`                                                               | the practice-received notice. Not silence: `payment_paid_email` IS handled, so a customer who pays successfully does get their payment confirmation — this is a missing second notice, which is why it sits last in this list | routed — PR #5128    |

**Why this is latent today and live the instant you arm.** The whole order lane answers 503 while
`GARUDA_XENDIT_SECRET_KEY` is unset, so none of these jobs is ever produced. Setting the key is
exactly what starts producing them. The happy path is covered; **every unhappy path is not**, and
the staff pages for money anomalies are the ones that matter most, because they are the mechanism by
which a human finds out something went wrong with someone's money.

Full detail, owners and the proof-of-armed criterion are in the `modus` PENDING-ARMS ledger. The
minimum before a real (not sandbox) purchase, restated 2026-08-28: **PR #5129 landed** (the five
staff pages, with `TELEGRAM_OWNER_CHAT_ID` as their decided destination) and a plain
**`unroutable > 0`** alarm on the drain pass. The four customer emails and the practice-received
notice are already done.

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
