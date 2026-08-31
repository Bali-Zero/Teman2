---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "01 — Intake, triage & specification"
source_report: research/operations/2026-08-28-beyond-sota-intake-triage-specification.md (PR #5177 branch)
status: SPEC-FINAL
---

# L01 — Intake, triage & specification

## Mission

The organism's gear-triage classifier (CI-recomputed floor + ceiling) is ahead of everything
surveyed, but every measured disaster in this lane's report lives on the other side: a
**declared-but-unbound commitment**. Falsifying numbers measured by the panel: 27 of the last
200 commits merged on main in a 3-day window (2026-08-20..22) existed only to correct a prior
commit's claim (13.5%); one "cut waste" mandate ran 44h / 8.6M output tokens / ~10 business
commits with the full loop armed; of the last 30 commits touching `evidence/pack.yml`, **0**
carry a `gear_override:` line, so the ceiling mechanism's actual binding rate is unmeasured;
the fixed-path `evidence/brief.yml` + `evidence/pack.yml` collide across concurrent PRs (W125),
confirmed live today: PRs #5054 and #5049 are both DIRTY specifically on
`scripts/evidence_pack_lint.py` + its test (cross-machine fleet-watch observation, 2026-08-27,
NOT re-verified by this session — re-verify with `gh pr view` before touching either branch).
This lane's three PRs lint the artifact at the one door that already exists
(`evidence_pack_lint.py` + `harness-floor.yml`), never adding new ceremony.

## Ground to load (orchestrator first reads)

- `scripts/evidence_pack_lint.py` [exists, 141 KB, `.claude/rules`-adjacent — the pack linter;
  has `--selftest` (embedded guilt+innocence corpus, exits 0/1), `--print-floor`,
  `--print-floor-source`; `compute_ceiling()` at line 680; `gear_override` handling at lines
  672-790, 1125, 2213-2406]
- `scripts/tests/test_evidence_pack_lint.py` [exists, 105 KB — pytest wrapper around the
  selftest corpus, e.g. `test_receipts_guilt_*`, `test_dissent_guilt_*`, `test_pii_scan_*`]
- `docs/factory/ASSEMBLY-LINE.md` [exists, 18 KB — RULED 2026-08-24 product-tier governance;
  target for the one-paragraph additions in PR-1/PR-2]
- `.claude/skills/modus/SKILL.md` [exists, 66 KB — STAGE 0 TRIAGE at lines ~33-68; target for
  the PR-3 appetite paragraph]
- `evidence/brief.yml`, `evidence/pack.yml` [exist at fixed root paths — read the live
  visa-retention-scope brief as the "practiced genre at its best" reference before writing
  fixtures]
- `.github/workflows/harness-floor.yml` [exists, 68 KB — CI-recomputes the gear floor
  unconditionally via `scripts/evidence_pack_lint.py --print-floor`]
- `.claude/rules/cicatrix-superscar.md` families #2 (esiste≠armato — ceiling never exercised)
  and #3 (guard-over-match — EARS/probe rules need guilt+innocence fixtures per
  `infra/guard-conformance/`)
- CI reads the **origin/main** version of `evidence_pack_lint.py`, not the working tree; dissent
  statuses must be CONFIRMED / PLAUSIBLE / RETRACTED, matching `pack.yml`'s `dissent:` block

- **First act, before any edit**: `gh pr view 5054 5049 --json state,title,mergeable,files` and
  reconcile. Both are reported DIRTY on exactly the two files PR-1/PR-2 also touch
  (`scripts/evidence_pack_lint.py`, `scripts/tests/test_evidence_pack_lint.py`). If either is
  still open and unresolved, rebase PR-1 on top of the resolution or sequence after it — never
  open a third conflicting branch on the same two files.

## PR-1: `feat(evidence): acceptance-as-probe lint (notice mode) + baseline report`

**Files**: `scripts/evidence_pack_lint.py` [exists], `scripts/tests/test_evidence_pack_lint.py`
[exists], one paragraph in `docs/factory/ASSEMBLY-LINE.md` [exists]
**Gear**: 2
**Build**:

- Require every Gear≥2 `acceptance:` bullet in `evidence/brief.yml` to pair with a `probe:`
  field (a command, test id, or check name); require `pack.yml`'s `receipts:` block to carry
  each probe's observed outcome
- Ship as a lint **NOTICE**, not a fail, in this wave — "new checks at existing doors, never
  new ceremony" (2026-08-26 lesson); EARS-shape the bullet text (WHEN/SHALL) as its own NOTICE
- Per adversarial finding (survives, both source reports): a stored `receipts:` outcome is
  **forgeable** unless a CI step actually executes the probe — this PR may only lint the
  FIELD'S PRESENCE and must say so in the ASSEMBLY-LINE.md paragraph; do not claim "mechanically
  bound acceptance" until a follow-up wires real CI execution
- Build the guilt+innocence fixture pair inside the existing `--selftest` corpus, following the
  pattern at `test_receipts_guilt_missing_field_rejected` / `test_receipts_innocence_*`
- Baseline: measure probe-coverage of `acceptance:` bullets across the last 30 Gear≥2 packs;
  report the number in the PR body (expected near-zero — the mechanism does not exist yet)
  **Acceptance**: `python scripts/evidence_pack_lint.py --selftest` exits 0 with the new
  guilt+innocence pair included; guilt fixture = a synthetic Gear-2 pack with a probe-less
  acceptance bullet (must emit a NOTICE); innocence fixture = the live visa-retention-scope
  pack's acceptance shape (must stay silent)
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6 (non-Anthropic,
  generator≠grader); final on-disk gate = orchestrator (Opus 5 xhigh)
  **Arming / prove-live**: armed when live on `origin/main` and `test_evidence_pack_lint.py` runs
  it in CI; probe = re-run `--selftest` on `origin/main`'s copy (CI never reads the local checkout)
  **Conflicts / order**: STRICTLY before PR-2 and PR-3 (same files, same lint module — sequential,
  not parallel). Must reconcile with #5054/#5049 first (see Ground). L03-PR-3 (`council` block in
  `pack.yml`) touches the same linter surface and may only start after this lane's three PRs are
  fully merged.

## PR-2: `feat(evidence): assumptions register block + lint notice`

**Files**: same as PR-1 (`scripts/evidence_pack_lint.py`, `scripts/tests/test_evidence_pack_lint.py`)
**Gear**: 2
**Build**:

- Add a structured `assumptions:` block to `evidence/brief.yml`: each entry carries `text`,
  `status: verified|unverified`, and `probe` (the check that would settle it)
- Lint emits a NOTICE (never a fail) naming every `unverified` assumption in the pack — mirror
  the existing `seat_diversity_note` UX pattern already in the linter
- Zero-assumption brief passes silently — no notice when the block is empty or absent
- Kill-criterion for the PR body: if the block degenerates to boilerplate ("no assumptions") in
  > 80% of briefs by day 60, log it as a day-60 review item — do not build auto-removal now
  > **Acceptance**: `--selftest` guilt fixture = a pack with ≥1 `unverified` assumption (must emit
  > a NOTICE naming it); innocence fixture = a pack with an empty/absent `assumptions:` block (must
  > stay silent)
  > **Seats**: implementer = Sonnet 5 subagent; refuter = Kimi K3 or Codex GPT-5.6; final on-disk
  > gate = orchestrator (Opus 5 xhigh)
  > **Arming / prove-live**: same mechanism as PR-1 — `--selftest` against `origin/main`
  > **Conflicts / order**: after PR-1 merges (same files). Wave 1.

## PR-3: `feat(evidence): appetite block + appetite_exceeded acknowledgment rule`

**Files**: `scripts/evidence_pack_lint.py`, `scripts/tests/test_evidence_pack_lint.py`, one
TRIAGE paragraph in `.claude/skills/modus/SKILL.md` [exists]
**Gear**: 2 (note: touching `SKILL.md` may recompute the CI floor to Gear 3 as a doctrine-path
hot zone — if `harness-floor.yml` recomputes 3, honor it, do not override)
**Build**:

- Add an `appetite:` block to `evidence/brief.yml`, declared at TRIAGE: wall-clock ceiling,
  adversarial-round ceiling, optional token ceiling
- Exceeding the declared appetite without an explicit `appetite_exceeded:` acknowledgment line
  in `evidence/pack.yml` is a lint **FAIL** — this mirrors the existing `gear_override:` pattern
  exactly (same mechanism, applied to spend instead of gear)
- Rounds are already countable via rule 8's red-count; wall-clock is derivable from PR/commit
  timestamps. Per adversarial finding (survives, both reports): those timestamps measure **PR
  lifetime**, not live session wall-clock runtime — label this check **ex-post / PR-lifetime
  accounting**, never an "in-flight breaker"; it makes overrun visible and requires
  acknowledgment after the fact, it does not interrupt a live 44h session
- Add the TRIAGE paragraph to `modus/SKILL.md` documenting appetite declaration as part of
  STAGE 0, alongside the existing gear declaration
- A pack with NO `appetite:` block PASSES silently — absence is never a failure; the rule only
  fires when a declared appetite is exceeded without acknowledgment
  **Acceptance**: `--selftest` guilt fixture = a pack whose recorded rounds/timestamps exceed its
  declared `appetite:` with no `appetite_exceeded:` line (must fail); innocence fixture = the same
  overrun WITH the acknowledgment line present (must pass); second innocence fixture = a pack with
  no `appetite:` block at all (must stay silent). Pre-merge compatibility requirement: run the new
  lint against the evidence packs of all in-flight craft-wave branches; zero new reds is part of
  acceptance.
  **Seats**: implementer = Sonnet 5 subagent; refuter = Kimi K3 or Codex GPT-5.6; final on-disk
  gate = orchestrator (Opus 5 xhigh)
  **Arming / prove-live**: `--selftest` against `origin/main`; additionally confirm the SKILL.md
  paragraph survives L03-PR-2's citation-integrity lint (no phantom cross-references introduced)
  **Conflicts / order**: after PR-2 merges. Wave 2. This is the PR most likely to trip the doctrine
  hot-zone floor — budget for a Gear-3 recompute.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

1. **Appetite auto-suspend default (R2)**: whether breaching a declared appetite may SUSPEND a
   mandate by default (rule-8 precedent) or only demand the `appetite_exceeded:` acknowledgment
   line. Report's recommendation: acknowledgment-only for 30 days, then Zero decides with the
   measured breach rate in hand. This spec builds acknowledgment-only (PR-3); auto-suspend is
   out of scope until ruled.
2. **Docs-only owner label** (ASSEMBLY-LINE.md enforcement backlog item 1): arming it requires
   an owner-initialed label mechanism only Zero can commit to supplying. Not part of this lane.
3. **Surfaced by adversarial review, not in the report's original §7 list**: the report's claim
   "nothing else in §5 requires a business decision" was itself flagged (HIGH) as wrong —
   appetite ceiling VALUES, any path-class exemption list, and invariant-zone selection are
   governance choices. This spec does not pick numbers or zones; PR-3's `appetite:` block ships
   with the field present and enforced, values set per-brief pending a Zero ruling on defaults.

## Suspend & ledger rules

Rule 8 (`CLAUDE.md` §2): a PR red three times for the SAME cause SUSPENDS — one PENDING-ARMS
line naming the cause, branch left alive, no fourth round. Fix-of-a-fix stops at depth 1: if the
correction to a correction is itself wrong, the surface is under-specified — write the spec, do
not open a third PR. Every BUILT-but-not-yet-ARMED step (e.g. a merged lint rule not yet
exercised by a live pack) gets one row in `.claude/skills/modus/PENDING-ARMS.md` naming the
artifact, the missing arming step, and a named owner (never a bare `operator`).

## Out of scope

- R3 (recidiva tripwire), R4 (invariant micro-specs), R6 (pre-TRIAGE receptor hook) — in the
  report's own roadmap but not part of this lane's three assigned PRs.
- Flipping PR-1's NOTICE to a FAIL (report's own Wave-2 plan) — a future PR, not PR-3.
- Any change to `harness-floor.yml`'s floor/ceiling computation logic — this lane only adds lint
  rules inside `evidence_pack_lint.py`.
- Seat/model routing decisions beyond the standard implementer/refuter/gate split above —
  `modus`/`FLEET_TOPOLOGY.json` territory.
