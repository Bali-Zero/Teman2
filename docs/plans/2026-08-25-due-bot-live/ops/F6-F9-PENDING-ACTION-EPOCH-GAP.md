# F6-F9-PENDING-ACTION-EPOCH-GAP.md — open cross-lane question

> **Status: OPEN.** Raised by B5 (F9 failover) at the orchestrator's request after
> reviewing B3's F6 confirmation store post-merge. Not B5's to solve alone — do not
> widen either lane's scope to close this without an owner ruling on the resolution
> shape. Whoever wires F6 to F9 (or decides they should stay unwired) should start
> here, not rediscover this in production.

## The question, precisely

**What is the failover contract for state held OUTSIDE the F9 leader record?**

F9's `team_bot_ingress_leader` table (Postgres, one row, CAS'd via `leader_epoch`) is
the fleet-wide SSOT for who is the active ingress node. It is checked LIVE, on every
call, by `IngressLeaderStore.authorize(node_id, epoch, now)` — no caller ever holds a
value from a previous read across a mutation.

F6's `PendingAction` state machine (`apps/team-bot/team_bot/confirmation/store.py`,
`SqlitePendingActionStore`) is a SEPARATE store — SQLite, one file per node (team-bot
v1 is single-process, per that module's own class docstring: "concurrent multi-process
writers are out of scope for this unit"). It carries a `leader_epoch` field on every
row and checks it in `confirm()` — but that check compares against `self._epoch`, an
attribute set ONCE at `SqlitePendingActionStore.__init__(current_epoch: int = 0)` and
never refreshed by any method in the file. The module never imports
`backend.services.team_bot_ingress` — there is no live read of F9's leader record
anywhere in F6's confirm/execute path today. The store's own docstring names this
explicitly: _"In v1 there is exactly one epoch (0) and this check is inert"_ — the
mechanism exists as a field, not yet as a wired contract.

Two concrete failure directions follow, both currently open:

1. **A PendingAction becomes invisible across a takeover.** A mutation is proposed on
   node A's SQLite file. Before it is confirmed, F9 promotes node B. Node B's team-bot
   process opens its OWN SQLite file (Mini<->Pro replication is explicitly out of
   scope for `SqlitePendingActionStore` per its own docstring) — the pending action
   simply is not there. The staff member's confirmation reply has nothing to attach
   to.
2. **A demoted-but-still-alive node executes under a stale belief.** If node A's
   process keeps running after being demoted (killed, not merely failed-over-from),
   its `SqlitePendingActionStore` instance still holds whatever `self._epoch` it was
   constructed with. Nothing in `confirm()`/`execute()` re-checks that belief against
   F9's live leader record — the epoch field it DOES check is its own local one, not
   F9's. A confirmation routed to node A after a takeover would currently be
   evaluated against node A's own stale, self-consistent epoch, not rejected the way
   `IngressLeaderStore.authorize()` would reject it if it were asked.

`backend/tests/duebot/failover/test_staging_drill.py::test_pending_action_confirmation_after_takeover_needs_a_live_epoch_check`
proves the SHAPE of direction (2) using only this lane's own code (no import from
`apps.team_bot`) — see that test's docstring for exactly what it does and does not
prove.

## A second consumer of the same gap class

Zero's directive #1 (per-member team-bot memory: three layers in a local SQLite store
on Mini, replicated to Pro, with the explicit requirement _"la memoria sopravvive al
failover"_) puts per-member memory in exactly the same shape as F6's PendingAction —
node-local SQLite state that must survive, or be correctly judged stale by, an F9
takeover. B8 is building that store now and has been pointed at this file before
designing it. Nobody should design a fix here for F6's pending actions alone: the same
"is this node-local SQLite state current, and does the OTHER node see it after a
takeover" question now has two independent consumers (F6 confirmations, team-bot
memory), and a resolution shape picked without both in view — e.g. one that hardcodes
`PendingAction`-specific fields into the check — would need re-doing the day the second
consumer arrives. This paragraph is B5 naming the second instance, not designing
either fix; sizing the actual resolution is still the open call above.

## A reference implementation now exists (finding #2)

A cross-family refutation of F9 (`F9-REFUTATION-2026-08-25.md`, finding #2)
named the SAME class of bug directly inside this lane's own module:
`authorize()` is a plain read-then-compare — nothing atomically binds its
verdict to the mutation it is meant to gate, so a check that returns
AUTHORIZED can still be stale by the time the protected write actually
commits, if any time passes between the two. `F9-CALLBACK-WRITE-FENCE-SPEC.md`
fixes this for F9's OWN outbound WABA write (the one mutation this lane
controls end to end): a new `_fence_write_with_live_epoch` helper re-checks
`authorize()` AND extends the lease via `renew()` immediately before the
write, never trusting a belief read earlier in the same tick. Whoever wires
this same discipline into F6's confirm/execute path (or a CRM mutation
endpoint generally) has a concrete, tested reference to copy rather than
inventing the shape from scratch.

## Candidate resolution shapes (not a decision — for whoever rules on this)

- **B3's confirm/execute path calls F9's `IngressLeaderStore.authorize()`** (already
  built, already the pattern a CRM mutation endpoint is meant to use per F7) before
  transitioning PROPOSED -> CONFIRMED or CONFIRMED -> EXECUTED. This is the smallest
  diff — F9 already exposes exactly the check needed; the gap is purely that F6's
  store was built and merged before F9 existed to call.
- **Mini -> Pro SQLite replication gets built** so a pending action proposed on one
  node is visible on the other regardless of which one answers a later confirmation —
  closes failure direction (1), independent of (2).
- **Auto-failover stays refused while any PendingAction is non-terminal.** A cheaper
  partial mitigation: F9's failoverd could check for zero outstanding
  PROPOSED/CONFIRMED rows before promoting, refusing (not silently proceeding) if any
  exist — narrows the blast radius without solving cross-node visibility, and pairs
  naturally with today's already-frozen "AUTO-failover stays DARK until a
  staging-WABA drill" rule (F9) rather than replacing it.

None of these is committed. This file exists so the choice is made on purpose, by
whoever owns wiring F6 to F9, not discovered as a production incident.

## Why this cannot bite today

`TEAM_BOT_FAILOVER_AUTO_ENABLED` defaults false and stays false until the operator
steps in `FUNNEL-SETUP.md` are all done AND the staging-WABA drill passes — no real
failover can happen yet, so neither failure direction above has a live path. This gap
is a precondition to check BEFORE arming, not an active incident — see
`FUNNEL-SETUP.md` step 7, which now points here.
