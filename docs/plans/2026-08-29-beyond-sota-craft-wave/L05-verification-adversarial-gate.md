---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "05 — Verification, adversarial review & the final gate"
source_report: research/operations/2026-08-28-beyond-sota-verification-adversarial-gate.md (PR #5177 branch)
status: SPEC-FINAL
---

# L05 — Verification, adversarial review & the final gate

## Mission

The doctrine layer here is ahead of surveyed SOTA — executable generator≠grader
(`infra/workflows/verify-template.js`), hard family-exclusion backed by the W100 measurement
(same-family review certified 7-of-8 false-clean), guilt+innocence guard conformance (38/38
registered guards carry both proofs), a never-cascading final gate on a CI-recomputed gear floor. The
trust layer underneath is behind: **nothing verifies the verifiers' continued discriminative power**.
Measured: `infra/scar-gates/MANIFEST.json` declares 66 scar gates, 2 armed, 64 prose-only; 24 stated
HARD invariants → 6 enforced nowhere + 1 phantom; `test_auto_merge_whitelist.py` is 24/73 red on
clean `origin/main` with **no workflow executing it**; W121 proved a mutation cycle's kill-count was
produced by poisoned bytecode, not the corpus, for an unknown period. Two independent correction-tax
measurements (27/200, 13.5%, 2026-08-20..22; 106/866, ~12.2%, this session) land near 1-in-8 of the
commit stream being claim-repair. Meta-pattern: "a verifier, once written, keeps verifying" is false.

## Ground to load (orchestrator first reads)

- `.claude/commands/verify.md` [exists] — L0 personal empiricism.
- `.claude/skills/final-gate-discipline/SKILL.md` [exists] — five questions before declaring done.
- `infra/workflows/verify-template.js` [exists] — gather→adversarial-refute→synthesize.
- `.claude/commands/codex-second-opinion.md` [exists] — standing Codex "spalla".
- `.claude/skills/modus/SKILL.md` [exists, 280 lines] — §Arsenal, family-exclusion rule.
- `infra/guard-conformance/check_guard_conformance.py` + `registry.json` [exist] — C1-C4 checker.
- `.github/workflows/guard-conformance.yml`, `hook-innocence-gate.yml`, `verify-the-verifiers.yml`,
  `adversarial-review-gate.yml`, `p1s2-mutation-incremental.yml`, `harness-floor.yml` [all exist].
- `scripts/evidence_pack_lint.py` [exists], `evidence/pack.yml` [exists].
- `apps/backend-rag/backend/tests/test_data_invariant_tripwires.py` [exists, 9 tests].
- `infra/scar-gates/MANIFEST.json` [exists] — 66 declared scar gates.
- `scripts/launch_worker_plane_review_panel.py` [exists] — PR-3's target: docstring still names
  Fable 5 as the final gate, 8+ days after the 2026-08-20 ruling moved every gate seat to Opus 5.
- `MEMORY_VERIFICATION_RULES.md` [exists] — "la prova può essere vuota", the field-measured taxonomy.
- Superscar families #6 (phantom citations, W65→W90→W100→W113) and #2 (exists≠armed).

## PR-1: feat(verify): hermetic verification runner + W121 census

**Files**: `scripts/hermetic_verify.sh` [proposed], `.github/workflows/p1s2-mutation-incremental.yml`
[exists — edited], `scripts/tests/test_hermetic_census.py` [proposed]

**Gear**: 1-2

**Build**: a wrapper every measurement instrument (mutation cycles, guard-fuzz, tripwires, future
grader-bench) must run under — `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, clean
`__pycache__` assertion; a **self-canary** that flips one byte before reporting and asserts the
instrument notices (the direct W121 antidote — the number in the PR body was produced by the
filesystem, not the corpus); adopt in `p1s2-mutation-incremental.yml` first; a CI census that fails
any workflow invoking a measurement instrument outside the wrapper. ≤200 net lines.

**Acceptance**: guilt — self-canary run flips a byte, harness goes red; guilt — a deliberately-bare
invocation fixture (calls Python directly, bypasses the wrapper) fails the census; innocence — a
wrapped invocation passes. `bash scripts/hermetic_verify.sh -- <instrument-cmd>` exits non-zero on
canary failure, zero otherwise.

**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6 (non-Anthropic); final gate =
orchestrator (Opus 5 xhigh).

**Arming / prove-live**: armed = every mutation run in `p1s2-mutation-incremental.yml` goes through
the wrapper and the census is itself CI-enforced. Probe: recreate W121's shape (poison bytecode,
preserve byte-length, restore within the same second) and confirm the self-canary fires.

**Conflicts / order**: edits `.github/workflows/p1s2-mutation-incremental.yml` → CODEOWNERS-tier hot
zone; auto-merge OFF, session merges manually after gates; `pre-commit lease-check` applies. **Order
(LANE NOTES, binding)**: runs AFTER L06's PR-1 and the separate L00 R9-defuse PR — all three touch
`.github/workflows/`; serialize in one track to avoid a DIRTY collision.

## PR-2: feat(verify): correction-tax KPI

**Files**: `scripts/correction_tax.py` [proposed], ledger append [proposed], SessionStart line
[appended to existing hook output]

**Gear**: 1

**Build**: weekly job computing correction-shaped commit-stream share via a **versioned** heuristic
(this session's: `recidiv|actually|was wrong|wrongly|false.positive|false.green|mislabel|mente|
lied|stale claim|correct(s|ed|ion)|retract|W1[0-9][0-9]|claim`); publish trend at SessionStart as one
line; baseline 106/866 (~12.2%) on this session's window, cross-checked against 27/200 (13.5%,
2026-08-20..22). **Mandatory (adversarial review, HIGH, survives)**: report only, never target — do
not wire into any gate or council-composition decision; if two heuristic revisions move the number
more than real change does, stop publishing until stabilized. ≤150 net lines.

**Acceptance**: reproduces 106/866 on the frozen window, pinned with BOTH bounds
(`--since 2026-08-14 --until 2026-08-28 --heuristic v1`) — the exact closed window that produced
106/866 must be recorded at first run and then frozen in the test, never left open-ended; a
weekly ledger row with window/count/denominator/heuristic-version; SessionStart shows a trend delta
vs. the prior week.

**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final gate = orchestrator
(Opus 5 xhigh).

**Arming / prove-live**: armed = the weekly job runs unattended, SessionStart reflects the latest run
without manual invocation. Probe: run once, confirm ledger row + SessionStart line; force a second
dated run, confirm a delta appears.

**Conflicts / order**: read-only against git log; no hot-zone paths; parallel with PR-1 and PR-3.

## PR-3: fix(council): launcher docstring names the ruled gate seat

**Files**: `scripts/launch_worker_plane_review_panel.py` [exists — 1-line fix], a new
doctrine-conformance grep test [proposed]

**Gear**: 1

**Build**: fix the docstring ("invokes Fable 5 as the only sequential final gate" → Opus 5 xhigh per
the 2026-08-20 ruling) — verify no runtime code path actually routes to Fable before touching
anything beyond the string; if it does, escalate that separately, don't fold it into this 1-line PR.
Add a conformance test that reads the ruled gate seat from the doctrine source and asserts the
docstring names the same seat, so the next ruling can't drift silently for 8+ days again. ≤40 net
lines.

**Acceptance**: guilt — revert the fix (or compare against a hardcoded "Fable 5" string) → new test
fails; innocence — fix applied, doctrine unchanged → test passes. Must fail specifically when
docstring and doctrine **disagree**, not merely when the docstring is edited at all.

**Seats**: implementer = Sonnet 5 (Haiku 4.5 acceptable for the docstring edit alone, Sonnet 5 for
the conformance test); refuter = Kimi K3 or Codex GPT-5.6; final gate = orchestrator (Opus 5 xhigh) —
even a 1-line gate-seat fix goes through the full gate.

**Arming / prove-live**: armed = the conformance test runs in CI on any PR touching the launcher or
the doctrine source. Probe: grep the live docstring for "Fable" post-merge (must return nothing); run
the test standalone, confirm exit 0.

**Conflicts / order**: no workflow file touched unless the implementer wires the test into an
existing trigger list — if so, treat as hot-zone and apply PR-1's serialization rule. Otherwise
parallel with PR-1 and PR-2.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

The source report framed R1-R7 as non-business-decisions; the adversarial review overturned that for
three (HIGH, accepted) — carry as real open items:

1. **Council composition changes from a grader scorecard** (R1, wave 2, not in this spec).
2. **Any new required merge gate from dual-path census or verifier re-qualification** (R3/R5, wave
   2/3, not in this spec) — a required-check flip is `operator[GUI]`.
3. **Correction-tax KPI status**: PR-2 above is scoped "measured, never targeted" by design; any
   future proposal to wire it into a gate needs its own ruling.
4. **Receipt spot-re-execution safety** (R2, wave 2, not in this spec): adversarial review (HIGH,
   survives) — re-executing contributor-controlled commands inside a credentialed gate is unsafe as
   framed; needs a sandboxing ruling before any implementation runs anything.

## Suspend & ledger rules

Rule 8: three reds for the SAME cause → SUSPEND, one PENDING-ARMS line naming the cause, branch left
alive. Fix-of-a-fix stops at depth 1 — a broken PR-3 conformance test means the surface is
under-specified, write the spec, don't open a third PR. Every built-but-not-armed step gets its own
PENDING-ARMS row.

## Out of scope

R1 (grader scorecards), R2 (receipt re-execution), R3 (dual-path census), R5 (re-qualification
calendar), R6 (debate round), R7 (correction-tax as a targeted KPI) — all wave 2/3, not authorized
here beyond PR-2's measured-only script. Any change to review-council composition or to which checks
are `required`. Re-executing any receipt or credentialed-gate action.
