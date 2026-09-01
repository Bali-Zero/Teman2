# L4 continuation — the store that makes login actually work

> Written by the orchestrator 2026-08-25, immediately after gating PR #4871.
> PR #4871 landed L4's **part 1 of 3**: the archived-client impersonation cure and
> the magic-link _seam_. This file specifies part 2. Part 3 (portal practice view,
> parcel tracker, visa delivery page) is unchanged from the mandate and is not
> specified here.

## What is true today (measured, not remembered)

- `apps/backend-rag/backend/app/routers/garuda_portal_auth.py` exists and its
  contract behaviour is tested — but the tests build their own bare `FastAPI()`
  and `include_router` it directly. Observing the router is not observing
  reachability: there is **no `router_manifest.py` entry and no
  `include_router` call** for it in `app/setup/`. `garuda_voa`,
  `garuda_voa_public` and `garuda_orders_router` are all mounted; this one is not.
- The only `MagicLinkStore` shipped is `UnconfiguredMagicLinkStore`, which raises
  `PersistencePolicyUnavailable` on **every** call. Both endpoints therefore 503.
  This is deliberate and correct — see below — not an oversight.
- `magic_link_tokens` **exists** (migration 237, already on the integration
  branch, not authored by #4871): `email`, `token_hash CHAR(64)` (sha256 hex,
  unique index), `expires_at`, `used_at`, `created_ip`, `created_at`, plus an
  `(email, created_at DESC)` index sized for rate-limiting and an `expires_at`
  index for the sweep. The table is a good fit for the contract as written.
- `magic_link_tokens` has **no retention-policy row**. Grepping the retention
  migrations (264, 268, 281, 284) for it returns nothing; the only file that
  mentions the table is its own CREATE. This is exactly why the store fails
  closed — writing a row into a table with no lawful retention basis is the
  thing L1 exists to prevent.

## The three things part 2 must produce

### 1. A retention-policy row for `magic_link_tokens`

Follow the shape 281 (`garuda_voa_retention`) and 284 (`garuda_orders`) already
use — do not invent a second pattern. Note that the policy table is **append-only
by trigger** (`264_visa_decision_retention_policy.sql:61`): a test fixture cannot
DELETE its row in teardown, and L3 learned this by running it and watching ten
tests error. Close the row, never delete it.

Retention basis to argue explicitly in the migration comment: a magic-link token
is an authentication artefact with a 15-minute TTL. It has no reason to outlive
its own expiry by more than the window needed to investigate an abuse report.
State the number chosen and why; do not copy a number from another table because
it was nearby.

### 2. A concrete `PostgresMagicLinkStore`

It must satisfy the contract the Protocol and the module docstring already fix.
These are not suggestions — the router, the tests, and DECISIONS.md Q1 all depend
on them:

- **Token**: `secrets.token_urlsafe(32)`. Store **only** `sha256(raw).hexdigest()`.
  The raw token exists in exactly one place — the email body. It must never reach
  a DB column, a log line, an error message, a response body, or a URL path or
  query string.
- **Comparison** happens on the hash, via the unique index. If any code path ever
  compares raw tokens in Python, use `hmac.compare_digest`.
- **Expiry is enforced in the SQL predicate**, not in Python after the fetch —
  a row that is expired must not be returned at all.
- **Single-use must be atomic.** One statement:
  `UPDATE magic_link_tokens SET used_at = NOW() WHERE token_hash = $1 AND used_at IS NULL AND expires_at > NOW() RETURNING …`.
  A read-then-write sequence loses the concurrent double-exchange race and both
  callers get a session. Write the test that drives two exchanges concurrently
  and asserts exactly one wins.
- **Indistinguishability (DECISIONS.md Q1)**: unknown, expired and already-consumed
  tokens must produce the **byte-identical** response. `ExchangeOutcome` has no
  reason field precisely so a router cannot leak the distinction; do not add one,
  and do not let the three cases differ in status, body, headers, or a branch that
  makes one measurably slower than the others.
- **`account_session_secret` keeps `repr=False`.** PR #4871 proved, with a real
  `sentry_sdk.init()` + envelope inspection and a control run, that removing it
  puts the secret back into Sentry. That proof is in the gate comment on #4871.

Two contract fields have **no home in migration 237** and the lane must decide
where they live before writing code, not during:

- `idempotency_key` on both `issue` and `exchange`, with `IdempotencyConflict`
  and `idempotency_replayed` semantics. L3 already solved this shape in
  `garuda_order_idempotency` — reuse that pattern rather than inventing a third.
- `account_session_secret` / `result_session_secret` — the session this exchange
  establishes. There is no session table in 237. Find the existing portal session
  mechanism (`portal.py` already authenticates clients somehow) and extend it;
  only add a table if no existing one fits, and say which you checked.

### 3. Mount the router

Manifest entry + `include_router` in **both** `include_routers()` and the correct
process-group function, then run the parity gate:

```
PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py \
  backend/tests/setup/test_manifest_registration_parity.py -q
```

Registration is explicit imports and calls — the manifest does not register
anything by itself. PRs #54/#55/#60 and #422→#424 all shipped routers that
404'd in prod because only the dev path was edited.

## Added 2026-08-25 after an independent security read of the router

Both verified by the orchestrator before being written here, not taken on the
reviewer's word.

### Timing-equivalence across the three deny branches

Byte-identical responses are necessary and **not sufficient**. The router
enforces indistinguishability at the type level — `ExchangeOutcome` carries no
reason field, so nothing distinguishing can reach the wire — but the router only
reads `outcome.authorized`. All three branches run inside the adapter, so the
timing oracle, if one exists, belongs to the store.

The naive shape leaks: "no row found → return immediately" against "row found but
expired → hash lookup, compare, return" does measurably different work, and an
identical response body does not hide it. Always perform the real hash lookup and
the real comparison before branching; never short-circuit on "no row". If the
measurement proves too noisy to assert on reliably in CI, say so explicitly and
describe the discipline implemented instead — do not silently drop it.

### Rate limiting is absent and currently owned by nobody

`"RATE_LIMITED": (429, True, "garuda_voa.error.rate_limited")` is in
`_ERROR_CATALOG` (`garuda_portal_auth.py:105`) and **no code path returns it**.
Every other catalog entry is reachable; that one is contract vocabulary with
nothing behind it, which reads as coverage while providing none.

Once the store makes these endpoints functional — they are not today —
`/magic-links` is a mail-bomb aimed at whoever owns the result and `/sessions` is
a brute-force surface against a short-lived token. Migration 237 already
anticipated the storage side: its `(email, created_at DESC)` index exists
precisely for "rate-limit / cleanup queries scan by email + recency".

The lane owes a **judgement**, not necessarily an implementation: if the throttle
belongs in the router, say so and leave it for its own PR; if it belongs in the
store because the counting surface is the table being written anyway, implement it
and say why. Deciding silently is the one unacceptable outcome.

## Acceptance — what would make this RED

A green suite is not the deliverable. The lane closes when:

1. Two concurrent exchanges of the same token: exactly one 204, one 401.
2. Revert the `AND used_at IS NULL` predicate → the concurrency test goes red.
3. An expired token, a consumed token and a never-issued token produce
   byte-identical responses (compare the full response, not the status code).
4. `grep` the raw token across every log line, response body and DB column
   emitted during a full issue→exchange cycle: zero hits.
5. The router answers on the real app — a request through the mounted
   application, not a bare `FastAPI()` built in the test.
6. With `GARUDA_PUBLIC_ENABLED` off, the endpoints behave as the flag contract
   requires (checked per-request, not at mount, as L2 and L3 both do).

## Boundaries

- Branch from a **fresh** `origin/feature/garuda-voa` after #4871 merges; new
  worktree, claim commit first.
- Migration number binds at landing time, not now (W40). 284 is taken by L3.
- Refuter: cross-family, and it must be given the _concurrency_ and
  _indistinguishability_ claims specifically — those are the two that a
  single-threaded test suite will happily confirm while being wrong.
