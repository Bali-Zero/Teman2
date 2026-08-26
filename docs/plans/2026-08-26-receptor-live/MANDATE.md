# MANDATE — a mechanical receptor for the LLM-tier rules

> For an **Opus 5 orchestrator session**, fresh context.
> Procedure: `.claude/skills/modus/SKILL.md` (general loop) composed with
> `docs/factory/ASSEMBLY-LINE.md` (product-shaped work). Full evidence and reasoning:
> `research/operations/2026-08-26-retro-fleet-sessions-25-26.md` — this mandate assumes that
> document's §7 (enforced rules) and §8 (sequence) and does not restate them.
> Everything marked MEASURED below was measured 2026-08-26. Re-measure before you plan further —
> these counts move under you, same as the KB mandate's did.

---

## 0. What this is, and why it exists

Not a gate. **A receptor** — the missing organ that makes "done" mean a run consumed a receipt, not
that a session declared it finished.

The retrospective (§2 of the research doc) found four true things about the fleet's own operating
discipline, and one of them is load-bearing for everything else: `AMENDMENTS.md`, the loop's own
scar file, took **zero entries on 24, 25, and 26/08** — the exact three days that shipped 4 product
mandates. Its own 22/08 entry had already named this pattern and it recurred anyway. A rule can be
written, agreed, and even re-discovered, and still produce nothing if no mechanical step consumes
it. This mandate is the fix for that specific failure mode, applied to the twelve LLM-tier routing
rules (R1-R12) the retrospective's synthesis pass extracted from prose that had been sitting,
unenforced, across `CLAUDE.md`, `modus/SKILL.md`, and `MODEL_ROSTER.md`.

So the unit of done is never "a rule is written" or "a PR merged." It is: **a receptor consumed a
receipt that the rule's own enforcer produced, on a real dispatch, and that consumption is
observable in `scripts/seat_mix_report.py`'s daily output (A7).**

## 1. Kill criterion

If, by Day 90, **`seat_mix_report.py` is not running daily with real deltas**, OR **a fresh
throwaway session still injects more than 10 mailbox broadcasts** (S3's own pass/fail probe), the
receptor mandate is itself theater — one more addition to the same 22-gate pile the retrospective
already measured being proposed as the cure for gate-sprawl (research doc §2), adding to the
problem instead of closing it. It SUSPENDS under Agent PR Contract rule 8: one PENDING-ARMS line
naming the cause, branches left alive, escalate to Zero rather than opening a fourth round.

Two falsifiable end-to-end proofs, taken directly from the plan's own §7 (not invented here):

- **S3's proof**: spawn a disposable session and COUNT mailbox injections. Pass = ≤10.
- **A1's proof**: the three seat-token strings that pass today under the prose classifier must NOT
  classify as different vendors under the closed vocabulary; a brand-new pack with no seat token
  must go red.

## 2. Lanes — tonight's burst (Day 0), machine-readable

Dispatched as one parallel burst on Pro. **13 of 14 tmux pane spawns failed** with `fork failed:
Device not configured` (pty-race under concurrency, 31/511 ptys in use — not a quota or fd
exhaustion); sequential and 2-3-at-a-time dispatch worked with zero failures. Full account:
research doc §9. Consequence for every lane below and every future burst on Pro: **dispatch ≤3
concurrent subagents at a time.**

```yaml
lanes:
  - id: L1   # skills-canon
    host: pro
    status: in_flight
    pr: null
    scope: Q0 — .claude/skills is SSOT; port 08-19 deltas into .agents; CI drift test
  - id: L2   # mailbox-state
    host: pro
    status: in_flight
    pr: null
    scope: S3 — key:+expires: mailbox, dedup, page-on-transition only
  - id: L3   # dependabot-serial
    host: pro
    status: in_flight
    pr: null
    scope: X2 — concurrency:dependabot-lockfile, cancel-in-progress:false, auto-rebase
  - id: L4   # hook-visibility
    host: pro
    status: in_flight
    pr: null
    scope: K1 — PreToolUse gate decision markers + Stop hook undecided-count + timeout-unit audit
  - id: L5   # haiku-agents
    host: pro
    status: in_flight
    pr: null
    scope: R1/E1 — 7 new agent-defs with model:haiku (ledger-writer, lint-fixer, i18n-sync, fixture-gen, log-triage, catalog-meta, docs-sync)
  - id: L6   # seat-build-tiers
    host: pro
    status: in_flight
    pr: null
    scope: E2/R2-R4 — seat_build.sh --tier mandatory, effort caps, context-window check
  - id: L7   # tp1-routes
    host: pro
    status: in_flight
    pr: null
    scope: R5 — 6 sibling TP1 route JSONs of glm-5.2-v1.json, PROBATION quorum exclusion
  - id: L8   # pack-lint-seat-rules
    host: pro
    status: in_flight
    pr: null
    scope: A1 — closed seat-token vocabulary in evidence_pack_lint.py, replacing the prose classifier
  - id: L9   # seat-mix-report
    host: pro
    status: in_flight
    pr: null
    scope: A7/E5/R12 — scripts/seat_mix_report.py, the daily scoreboard this mandate's kill criterion reads
  - id: L10  # spark-jules
    host: pro
    status: in_flight
    pr: null
    scope: R6-R7 — chore-queue + Jules dispatcher, Spark harvester repair
  - id: L11  # pr-4733
    host: pro
    status: in_flight
    pr: null
    scope: merge the finished memory-budget-gate cure after a GraphQL mergeability re-check — do not re-solve it
  - id: L12  # capture
    host: pro
    status: in_flight
    pr: null
    scope: this mandate + research/operations/2026-08-26-retro-fleet-sessions-25-26.md + AMENDMENTS entry + fleet memory
  - id: L13  # floor-size-term
    host: pro
    status: in_flight
    pr: null
    scope: S1 — blast-radius (numstat) term ahead of compute_floor, p90-measured threshold
  - id: L14  # base-protected-check
    host: pro
    status: in_flight
    pr: null
    scope: S5 check-half only — CI reads github.base_ref, fails a feature/* base with no covering ruleset (the arm-half is owner decision 6, operator[control-plane])

  # Day 30-90, not yet dispatched
  - id: pkg2-lying-guards
    host: null
    status: planned
    pr: null
    scope: [A2 (after A1/L8) — mandatory cross-family review lane on Gear>=2, X5 — roster<->dispatch-path lint, S5 arm-half — pending owner decision 6]
  - id: pkg3-instrument-ourselves
    host: null
    status: planned
    pr: null
    scope: [A4 — coverage-asserted door ping, F5 — ledger ratchet at PR base-date, S6 — pending PII-consent owner decision 8]
  - id: pkg4-finish
    host: null
    status: planned
    pr: null
    scope: [F4 — Corrects: depth counter, S2 — auto-enqueue breaker (after S3/L2), F2 — lane-debt gate in NOTICE, S7 — red-first proof reformed, F6 — mandate burndown on one real mandate]
```

`pr: null` on every Day-0 lane is the honest state at dispatch time, not a placeholder to forget:
this mandate's own receptor (once L9 lands) is what will fill these fields in, mechanically, instead
of a session hand-editing them later.

## 3. Gates

- **G-DAY0**: `Q0` (L1) lint (`scripts/tests/test_skills_canonical.py`) is green — `.agents` no
  longer routes any external seat to Fable. Blocking: every other lane's external-seat calls are
  reading the wrong doctrine until this closes.
- **G-DAY30**: S3's disposable-session proof passes (≤10 injections); `X2` shows Dependabot PRs
  draining one at a time; `#4733` is merged; `K1`'s undecided-tool-call counter exists and reports a
  real number (not zero-by-construction).
- **G-DAY60**: `A1`'s guilt+innocence proof passes (§1 above); `S1`'s floor recomputation shows a
  measured p90 threshold, not a placeholder; `L14`'s check-half is red on at least one real
  unprotected `feature/*` base before it is fixed (a check that has never fired red has not been
  proven).
- **G-DAY90**: `seat_mix_report.py` (L9) has run daily for two consecutive weeks with non-zero,
  moving deltas in at least three of the R1-R12 metrics from the research doc's §7 table.

Each gate is a **shadow period before it is a required check** (X3's own rule, `docs/factory/
ASSEMBLY-LINE.md` gate-lifecycle section): NOTICE for 7 days minimum, FAIL only after. A gate that
records zero denials across 30 days of being armed is a candidate for retirement, not evidence it is
unnecessary — X3's own ledger is what tells the two apart.

## 4. 30 / 60 / 90

See research doc §8 for the full narrative mapping (it is not repeated here — this mandate is the
YAML; that document is the reasoning). In one line each:

- **0-30**: silence and closure — L1-L14 above land, `S-OC` objective-card ships in SHADOW.
- **31-60**: the guards that lie — `pkg2-lying-guards`, `S-OC` moves SHADOW → ENFORCE, `S7+` reform.
- **61-90**: instrument ourselves, then finish — `pkg3-instrument-ourselves`, `pkg4-finish`, `A3+`
  receipt provenance, `X1+` branch quota/reaper, `F4+` review-loop stop, `L-FIN` terminal-state
  finalizer.

## 5. Owner switchboard — nothing here blocks L1-L14; build against the draft, collect signatures

Full text and rationale: research doc §6. Nine items — the eight from the plan's own §5 plus one new
one the blind-seat pass raised:

| #   | decision                                                                                                                                      | blocks                                                                    |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| 1   | The topic cap, actually — unit, per-machine vs per-session, is 2 literal                                                                      | any future admission-cap trick (F1/S8 stay PARKED until this is answered) |
| 2   | Conductor: build (Gear-3 adapter project) or delete the 77 profiles                                                                           | `pkg2`/A6 (already PARKED regardless)                                     |
| 3   | Fable 5 on M5, ~13% of M5's own traffic — Zero at the keyboard or drift                                                                       | nothing here; a compliance question                                       |
| 4   | Research OS — dead, deferred, or superseded                                                                                                   | nothing here; separate program                                            |
| 5   | Gate budget this quarter (a number, not "some")                                                                                               | how aggressively `pkg2-4` get staffed                                     |
| 6   | `feature/*` ruleset creation (`operator[control-plane]`)                                                                                      | `pkg2-lying-guards`' S5 arm-half                                          |
| 7   | Dependabot: serialize (already shipping as L3/X2) or close in bulk                                                                            | confirms L3's shape                                                       |
| 8   | PII consent for S6 (aggregate-only transcript extraction, local on Mini)                                                                      | `pkg3-instrument-ourselves`' S6                                           |
| 9   | **New**: admission lease fail-closed on Redis-down (new objectives only) — reads against the letter of `CLAUDE.md` §7, not against its intent | any lease-based admission control past L1-L14                             |

## 6. Enforced LLM-level rules

The twelve rules (R1-R12), their enforcers (E1-E7), and the per-rule A7 metric are the research
doc's §7 — by reference, not restated here, per this mandate's own opening principle ("an artifact
exists only if a gate consumes it": duplicating a table two places is exactly the drift class
`AMENDMENTS.md` 2026-07-25 already caught once, in the model-roster context). Read
`research/operations/2026-08-26-retro-fleet-sessions-25-26.md` §7 for the full table before staffing
`pkg2-4`.

## 7. Definition of done, and stopping

**A lane is current when** its enforcer exits red on a guilt fixture and green on an innocence
fixture, its A7 metric is non-zero and moving, and `pr:` in §2's YAML names a merged PR — not when a
session reports it finished in prose. **The mandate is current when the kill criterion (§1) has
held for 14 consecutive days.**

**Stopping**: Agent PR Contract rule 8 applies per-lane, not just per-PR — three reds on the same
cause on the same lane SUSPENDS that lane with one PENDING-ARMS line, branch left alive, and the
orchestrator moves to the next lane rather than a fourth round. A lane that finds a defect outside
its own scope writes a ledger row and does not chase it. Business decisions are §5, Zero's alone.
