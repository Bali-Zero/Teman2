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

Until then, **sandbox keys work today with no code change at all**, which is exactly what a dark
launch needs.

## Phase 1 — sandbox, available immediately, no code change

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

- ✅ **The public funnel is open.** `GET /api/visa/voa/eligibility-checks/<bogus id>` answers
  `404 {"code":"RESULT_NOT_FOUND"}` — the handler's own not-found shape, not the flag-off shape —
  with `/health` 200 alongside, on **both** `nuzantara-rag.fly.dev` and `balizero.com`.
- ❓ **The outbox consumer's spawn is unproven**, and the obvious probe cannot settle it:
  `_run_garuda_outbox_scheduler` (`main_api.py:175-200`) logs only at start, on cancel, and on
  exception — it is **silent while idle**, so an empty log grep is what a healthy scheduler and a
  never-started one both produce. The one decisive line is emitted at boot and has aged out of
  Fly's ~100-line buffer. Restarting only the `api` machine (`7817d92c4117d8`) re-emits it.
- ⬜ **Nothing has ever been exercised**: `garuda_orders` = 0 rows, `garuda_order_outbox` = 0 rows.

"The funnel is open" and "the funnel works" are different claims. Only the first is proven.

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
