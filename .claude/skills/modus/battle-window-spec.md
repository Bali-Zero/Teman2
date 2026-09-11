# Battle-window spec — the seven sections (PARABELLUM, RULED 2026-09-10)

> One file per window, one to two pages. A battle window is opened against this template and
> against nothing else. Colour table (BLUE/ORANGE): `docs/architecture/dual-consul/army-map.md`
> §1bis — referenced, never copied. Ruling: `docs/rules/RULINGS.md`, RULED 2026-09-10. Loop:
> `.claude/skills/modus/SKILL.md`.
>
> **One window = one mandate = one organ = one worktree.** Never two windows on the same path;
> two or three windows at a time at most. The staff room (Fable 5.1 + Astra, with Zero only)
> fixes the windows, the teams and the specs; it never fans out and never implements. Before
> executing, the window states its colour, its Dux role, its mandate id and its worktree path.

## 1. Mandate

Mission and window id · colour · organ · objective · gear · host · worktree and branch · base sha ·
one sentence saying what success changes.

## 2. Owned perimeter

Writable paths · forbidden and shared paths · one named owner per shared schema, fixture, generated
file and lockfile. Until a real write fence exists, VERIFY and the gate compare the changed paths
against this list BY HAND — `.lane-check.json`'s `scope_globs` only decides whether a check applies,
it does not reject an out-of-scope edit (`scripts/lane_check.py`).

## 3. Sibling contract

Schema/version and fixture hashes · success and error responses · producer and consumer ownership ·
the compatibility that must hold before either side merges. Frozen before BUILD. A change to it
goes back to the staff room through Zero, never negotiated window-to-window.

## 4. Acceptance

Falsifiable checks including at least one negative case, one integration check and one production
observation. Fixture success is not live integration and never stands in for it.

## 5. Team

Dux · optional implementer · adversarial reviewer · gate · release owner — each resolved from the
colour table. Effective model, effort and thread ids recorded at start, not reconstructed later.

## 6. Appetite and stop-loss

Hours ceiling · one coordinator-renewable absolute deadline inside those hours · token allowance ·
attempts, concurrency, depth and hops · adapter tool ceiling with **no ship reserve (N = 0)**: a
child at its cap checkpoints and returns the remaining work, and shipping belongs to the Dux and
consumes the mandate budget. Renewal authority named. Checkpoint destination is the fleet mailbox.
The same mission deadline is consumed by `scripts/mandate_budget.py` and by the Codex continuation
supervisor; child active time is measured and reported, never conflated with wall clock.

## 7. Evidence and release

Evidence pack and ledger refs · the `Bites:` consumer and its observation · merge order (backend
first only when backward-compatible; a shared lockfile serialises) · the gate receipt (mission id,
colour, HEAD sha, gate thread id, commands with exit codes, verdict, re-checked against the current
PR HEAD before posting) · deploy path · rollback trigger.
