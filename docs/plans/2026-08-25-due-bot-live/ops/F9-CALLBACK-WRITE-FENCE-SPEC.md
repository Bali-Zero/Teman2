# F9-CALLBACK-WRITE-FENCE-SPEC.md — the invariant, and fixes as its consequences

> Written by B5 in response to the cross-family refutation
> (`F9-REFUTATION-2026-08-25.md`, `gpt-5.6-sol` xhigh) and the orchestrator's
> instruction: findings #1/#3/#4 are one structural defect, not four
> bugs — "a decision made from a belief about leadership that is not
> re-established at the moment of acting." Per the Agent PR Contract, this
> spec names the invariant first; the fixes below are its consequences, not
> four independent patches.

## The invariant

**No outbound write and no mutation may proceed on a leadership belief
established before this instant. Every write must re-establish — atomically,
immediately before the write itself — that the acting node currently holds a
LIVE epoch and an unexpired lease. A read from earlier in the same tick is
not proof; only a fresh check run immediately before the write is.**

## Consequence 1 — the write-fence (closes #1, #3, #4)

`evaluate_and_act_once` writes to Meta (an outbound, state-changing WABA
callback override) from exactly two places: the already-leader branch
(retrying a prior tick's confirmation) and immediately after a successful
`try_promote`. Both fired unconditionally — the already-leader branch
trusted `current.active_node_id` from a read moments earlier, ignoring
`leader_epoch` ownership and `lease_expires_at` entirely (#3/#4); the
post-promotion branch trusted its own just-won epoch with no check that
nobody else had already raced past it in the (small but real) window
between the CAS committing and the write firing (#1's exact scenario: "DB
leader B, WABA callback A").

Fix: one new helper, `_fence_write_with_live_epoch`, called immediately
before BOTH writes. Two live checks, in order, both against a FRESH read —
never the caller's earlier belief:

1. `evaluate_authorize` — the SAME 3-way rule (epoch match, node match,
   lease not expired) a CRM mutation endpoint uses per F7. This is what
   makes "am I still leader right now" mean the SAME thing for an outbound
   WABA write as for every other protected action — #4 named exactly this
   inconsistency (an expired lease rejects a mutation via `authorize()` but
   the WABA-write path checked nothing at all).
2. `renew()` — extends the lease NOW, as a CAS on the SAME `(node_id,
epoch)`. `authorize()` is deliberately read-only (safe for a read-only
   caller like a CRM mutation gate); this fence is allowed to mutate, so it
   also keeps a legitimate leader's lease topped up going forward — closing
   a separate, previously-unexercised gap this review surfaced: nothing
   anywhere called `renew()` before this fix, so a leader's lease was only
   ever set once, at promotion, and never renewed.

Both checks must pass or the write is refused
(`ActionKind.REFUSED_STALE_LEADERSHIP_BEFORE_WRITE`). Neither
`ingress_leader.py` nor `ingress_state_repo.py` needs to change — `renew()`
and `evaluate_authorize` already implement exactly the right CAS/check
semantics; the gap was that `failoverd.py` never called them at the one
moment it mattered.

**Deliberately NOT done**: adding a "the incumbent's lease must already be
expired" condition to `try_promote`'s own CAS (which would also close part
of #1's root cause). Considered and rejected: `try_promote` is only ever
reached when this node does NOT already hold the seat, and F9's failure
detector (3-consecutive/30s-sustained) is intentionally independent of the
lease-expiry timer — the existing drill's promotion timing (ticks at
T0+0/1/2s against a 60-120s bootstrap lease) depends on that independence.
Gating promotion itself on lease expiry would block the legitimate
Mini→Pro takeover for up to a full lease duration in the common case where
Mini's last-renewed lease hasn't naturally lapsed yet, for no additional
safety once the write-fence exists: the write-fence alone eliminates the
concrete harm (a DB/WABA-callback mismatch) — a "wasted" re-promotion that
never mismatches Meta is a wasted epoch bump, not a correctness bug.

### Declared residual of that choice

_(Written by the orchestrator, not the lane — B5 named this in conversation
and agreed to record it, then hit a quota wall before it could. It is here
so it does not live only in a chat log.)_

Because promotion is gated on epoch equality and not on the incumbent's
lease having lapsed, **two failoverd processes on the same node can inflate
the epoch indefinitely**, each taking the seat from the other tick after
tick. Every individual write stays correct — the fence guarantees that — so
this is not a correctness defect, and the SSOT never disagrees with Meta.
What is unbounded is the epoch counter and the write volume behind it.

It requires misconfiguration to occur (one node, two daemons — the launchd
plist admits only one). It is recorded rather than fixed because the honest
statement is "bounded by nothing except deployment discipline", and a reader
who assumes epoch growth is self-limiting would be wrong. If a bound is ever
wanted, the natural one is the lease-expiry gate deliberately rejected
above, and re-opening that decision means re-examining the drill timing it
protects.

## Consequence 2 — DB-level backstop (closes #7)

Migration 291's own `COMMENT ON TABLE` claims "Written ONLY via
compare-and-swap ... never a bare UPDATE" — a comment, not a constraint.
Migration 292 adds a `BEFORE UPDATE` trigger rejecting any UPDATE that
decreases `leader_epoch`, independent of whether the application code
calling it stays correct — a bare `UPDATE` bypassing `ingress_state_repo.py`
entirely (an operator fixing something by hand, a future bug) can still
never roll the epoch back. Allows "unchanged" (`renew()`'s shape) and
"increased" (`try_promote()`'s shape); never "decreased".

## Consequence 3 — startup applies the same discipline (closes #8)

`main()`'s pool creation trusted ONE attempt at boot and, on failure, let
the whole process exit — relying on launchd's `KeepAlive`+
`ThrottleInterval=30` to relaunch it, forever, even for an ordinary
boot-ordering race (Postgres not yet up when this daemon starts). That is
superscar family #7 "throttled, not avoided" — a genuinely long-running
loop should absorb a transient dependency outage itself. Fix:
`_create_pool_with_retry` — bounded exponential backoff (default 6
attempts, ~2 minutes total) around `asyncpg.create_pool`, inside the
process. A PERMANENTLY broken DSN still fails, just after the budget is
exhausted rather than after one try.

**Deliberately NOT retried**: `FailoverdConfig.from_env()`'s missing-env-var
check stays an immediate fail-fast. A human must edit the env file; no
amount of in-process retrying resolves a missing value, and the existing
wrapper-script kill-switch design (`team-bot-failoverd-wrapper.sh`) already
anticipates this exact restart-and-throttle shape for a genuine
misconfiguration (`exit 78` on a missing/placeholder env file). Only the
TRANSIENT case (Postgres reachable in principle, just not yet, or briefly)
gets the retry.

## Design questions answered in writing (NOT code) — #5, #6

**#5 — no durable intermediate state between the CAS and the outbound
POST.** A crash after the CAS commits but before the POST fires (or after
the POST but before the GET-readback confirms) leaves the SSOT row
correct about _who_ is leader but silent about whether Meta's callback
was ever actually updated to match. `ActionKind.PROMOTED_BUT_CALLBACK_UNCONFIRMED`
already names this outcome for a live process, but nothing durable
survives a restart. Proposed shape (not built tonight): add a nullable
`callback_confirmed_at timestamptz` to `team_bot_ingress_leader`, set to
NULL in the SAME UPDATE that bumps the epoch, and flipped to `now()` by a
SEPARATE, idempotent UPDATE only after `override_callback`'s GET-readback
verification succeeds. This does not change today's actual RECOVERY
behavior (re-POSTing on the next tick is already correct — `override_callback`
is idempotent on Meta's side) — it exists purely so an operator (or a
future health check) can read the SSOT row directly and know, without
guessing, whether the last promotion's callback write ever actually landed.

**#6 — wall-clock trust model, currently implicit and unstated.** Every
`now` in this system is `datetime.now(UTC)`, sourced independently on
Mini and Pro, with no NTP-drift bound stated or enforced anywhere in this
lane's code. The current IMPLICIT assumption — "both nodes run standard
macOS NTP sync, closely synchronized" — is likely true in practice but
never verified or failed-safe against. Two concrete risks the refuter
named: a BEHIND clock can make an expired lease look live to
`authorize()`; an AHEAD clock can satisfy the 30s-sustained-failure
threshold prematurely. Proposed split (not built tonight): (1) move the
LEASE/EPOCH clock authority fully server-side — compute `lease_expires_at`
and the `now` used in `authorize()`'s comparison from Postgres's own
`now()`, not a client-supplied parameter — eliminating the clock-trust
question for the SSOT entirely, since every node's write is then
timestamped by the SAME single clock; this is a moderate, well-scoped
change to `ingress_state_repo.py`'s SQL. (2) leave `MiniFailureTracker`'s
LOCAL failure-observation timer on a local clock — it inherently needs one
to reason about "how long has MY process seen failures," and the stakes
are lower (worst case: a slightly early/late FAILOVER ATTEMPT, gated
afterward by the now-clock-trustworthy SSOT checks anyway — not an
incorrect AUTHORIZATION decision). This split is a recommendation for
whoever picks this up, not a commitment.

## Consequence 4 — the gap doc gets a third leg (finding #2)

Finding #2 ("authorize() is a check, not a fence — a stale action can
commit after takeover") is NOT this lane's fix alone — the fence has to
live where the mutation actually commits (CRM endpoints, F6's confirmation
store), which are other lanes' modules. `F6-F9-PENDING-ACTION-EPOCH-GAP.md`
gets a new section pointing here: the write-fence pattern in Consequence 1
above IS the reference implementation of what #2 asks those other
consumers to also do — check live, immediately before the write, never a
belief read earlier.

## Test plan

Every new test proving #1/#3/#4/#7/#8 was written BEFORE its corresponding
production fix and confirmed to fail (ImportError/AttributeError for the
not-yet-existing `_fence_write_with_live_epoch`/`_create_pool_with_retry`;
a passing `UPDATE ... SET leader_epoch = <lower>` for #7 before migration
292 exists) — then the fix was applied and the same tests confirmed green.
See the commit message for the exact red-then-green transitions observed.
