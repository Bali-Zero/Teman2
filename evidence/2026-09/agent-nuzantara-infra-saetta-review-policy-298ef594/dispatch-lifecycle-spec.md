# SAETTA review dispatch — lifecycle and fault-isolation spec (correction cycle 2)

Frozen 2026-09-13 before any cycle-2 source edit. Base 316a8e84, prior evidence head 7c19fbce,
round-2 source candidate 759e08b0. Scope: `scripts/council_journal.py`, R9 v2 in
`scripts/evidence_pack_lint.py`, their tests, `FLEET_TOPOLOGY.json` route consistency.

## Lifecycle per seat (one thread each, all eligible seats started together)

1. SPAWN — `Popen(start_new_session=True)`; the child is session and group leader, so PGID == PID
   and both are OWNED by this runner. Any exception from spawn is caught: the seat records
   `outcome=NON_JUDGMENT`, `non_judgment_reason=spawn_error`, `closure=not_spawned`; no signal is
   ever sent for it.
2. WAIT — output pipes drained by reader threads; the leader's exit is detected WITHOUT reaping
   (`waitid(WNOWAIT)` where available, kqueue `NOTE_EXIT` on Darwin), bounded by the timeout
   (max 300s). While the leader is an unreaped zombie its PID/PGID cannot be reused.
3. CLOSE — still before reaping: list live group members from the process table (a missing leader
   is not proof of an empty group), SIGTERM the group if members remain, grace, SIGKILL, list
   again. Only then reap the leader. No `killpg` after reap, ever.
4. RECORD — `closure=verified` only when the final member list (non-zombie, same PGID) is empty;
   otherwise, or on any exception inside CLOSE, `closure=ambiguous` with the reason. Remote seats
   (ssh) also record the remote shell PID/PGID printed by the remote command and a bounded remote
   process-table check; unobserved remote closure is `ambiguous`.
5. JOURNAL — each seat's line is appended as soon as that seat returns; an exception in one seat's
   thread becomes that seat's NON_JUDGMENT `runner_error` with `closure=ambiguous` and never
   aborts the fan-out.

## Acceptance (frozen)

- A1 spawn isolation: a missing executable and a raising `Popen` each yield that seat's
  NON_JUDGMENT spawn_error while every other eligible seat is actually invoked.
- A2 cleanup isolation: an exception during CLOSE is recorded (`closure=ambiguous`), the fan-out
  completes, and R9 v2 BLOCKS a pack whose final-candidate invocation has ambiguous closure even
  beside a PASS.
- A3 ownership: every `killpg` happens while the leader is still unreaped (asserted in-test); a
  resistant descendant ignoring SIGTERM that outlives its leader is found, killed and verified
  gone; a timeout is recorded with closure.
- A4 Codex route: `FLEET_TOPOLOGY.json` `council_policy_v2.routes` names every seat of
  `SEAT_ROUTES` explicitly (no wildcard) and `seats` equals `COUNCIL_V2_SEATS` families.
- A5 retained: quoted/backslash findings kept and any BLOCK wins; exact `gemini-3.1-pro-high`
  identity; zero judgments, omitted seat, late BLOCK, candidate mismatch, no opt-out.
