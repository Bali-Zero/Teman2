---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "00 — R9 harness-floor defuse (P0, deadline 2026-09-02)"
source_report: memory discovery_harness_floor_ci_copies_only_pack_and_brief_so_council_run_journal_never_resolves_2026_08_29 + X1 lane (M5 panel)
status: SPEC-FINAL
---

# L00 — R9 harness-floor defuse

## Mission

`.github/workflows/harness-floor.yml` stages ONLY `pack.yml` + `brief.yml` into
`/tmp/evidence-check/evidence/` (lines ~849-945 on origin/main, verified 2026-08-29), then lints
there. `evidence_pack_lint.py::_read_council_journal_seats(pack_dir, council_run)` resolves
`council_run:` relative to the pack's own directory and refuses anything outside it — so a
perfectly valid `journal.jsonl` sitting next to the pack in the repo is INVISIBLE in CI.
Today this is a NOTICE; **the R9 grace ends 2026-09-02**, after which every Gear-3 PR fails a
required check on a rule that cannot be satisfied. This lane MUST merge on main before that date.
Side effect: it is the environment change that legitimately unblocks PR #5177 (suspended per
Rule 8 on this exact red).

## Ground to load (orchestrator first reads)

- `.github/workflows/harness-floor.yml` [exists] — the staging block near lines 849-945.
- `scripts/evidence_pack_lint.py` [exists] — `_read_council_journal_seats` + the R9 flip date;
  ALWAYS lint with the origin/main version (`git show origin/main:scripts/evidence_pack_lint.py`).
- Memory: `discovery_harness_floor_ci_copies_only_pack_and_brief_so_council_run_journal_never_resolves_2026_08_29`
  (holds the exact local CI-reproduction recipe — "Fact 3").
- `scripts/ci/evidence_paths.py` [exists] — per-branch pack dir convention.

## PR-1: `fix(ci): harness-floor stages the pack journal so council_run can resolve`

**Files**: `.github/workflows/harness-floor.yml` [exists] (workflow-only cure — do NOT touch
`scripts/evidence_pack_lint.py`: that file is a live conflict hotspot owned by lane L01).
**Gear**: 2 (hot zone: CODEOWNERS-tier-1 workflow — floor may recompute higher; accept it).
**Build**:

- After the existing `git show "$HEAD_SHA:${PACK_PATH}" > /tmp/evidence-check/evidence/pack.yml`,
  parse the pack's OWN `council_run:` value (packs on main use different names —
  `council-journal.jsonl` exists today, `journal.jsonl` elsewhere; never hardcode one) and stage
  THAT file from the SAME commit, preserving its relative name:
  `CR=$(grep -E '^council_run:' /tmp/evidence-check/evidence/pack.yml | awk '{print $2}')` then
  `[ -n "$CR" ] && git show "$HEAD_SHA:$(dirname "$PACK_PATH")/$CR" > "/tmp/evidence-check/evidence/$CR" || true`
  — path-confined to the pack dir (reject any `CR` containing `/` or `..`); tolerate absence:
  a pack that declares no `council_run` must keep passing without a journal.
- Stage any other file the pack's dir carries that the lint may resolve relative to the pack
  (journal only, unless the lint on origin/main names others — re-grep `_read_council_journal_seats`
  and siblings THIS turn before deciding).
- Do not widen the lint's resolution rules and do not move the check dir — smallest diff wins.
- The staged-journal `|| true` is a RECORDED exception (absence-tolerance for an OPTIONAL
  artifact), not a verification step being silenced — L12-PR3's no-`|| true` doctrine targets
  verification steps in restore-drill. State this in the PR body so no future lint rediscovers it.
  **Acceptance**:
- Guilt (old behavior must be shown cured): local reproduction per the memory's Fact-3 recipe with
  a pack declaring `council_run: journal.jsonl` and a valid 2-seat journal next to it → BEFORE the
  fix the origin/main invocation prints the R9 NOTICE; AFTER, staged the new way, it prints none.
- Innocence-1: a pack with NO `council_run` and no journal → lint output byte-identical pre/post.
- Innocence-2: a pack declaring `council_run` with a MISSING journal → still NOTICEs/FAILs (the
  rule itself must keep teeth).
- CI proof: one fixture-shaped test PR (or the first real Gear-3 PR after merge) shows the
  `Harness floor recompute` check green with a journal-carrying pack.
  **Seats**: implementer = Sonnet 5 subagent; refuter = Codex GPT-5.6 sol (xhigh) — a workflow diff
  on a required check is security-adjacent; final on-disk gate = orchestrator (Opus 5 xhigh).
  **Arming / prove-live**: merged on main BEFORE 2026-09-02; then `gh pr update-branch 5177` and
  re-run its `pull_request` harness-floor run (W111: repoint, never blind-rerun a stale merge ref);
  #5177's rollup shows the check green or a DIFFERENT cause (which re-opens it legitimately).
  **Conflicts / order**: `.github/workflows/` is auto-merge-OFF class — the CONDUCTOR merges on
  gates-green evidence posted in the squad ledger, never `--auto`; pre-commit lease-check applies. This PR precedes every other
  workflow-touching PR of the wave (L06, L05, L04-PR3, L12-PR3): Squad W serializes them all.

## Needs-ruling carried (Zero only)

- None. (The R9 flip DATE itself is already law in the lint; this lane does not move it.)

## Suspend & ledger rules

Rule 8: three reds for the same cause → SUSPEND with a PENDING-ARMS line, branch alive. If this
lane suspends, the wave's Gear-3 capacity dies on 2026-09-02 — the conductor must escalate to
Zero the same day, not queue silently.

## Out of scope

`scripts/evidence_pack_lint.py` (L01's surface), the R9 flip date, D3 seat-diversity rule,
every other workflow.
