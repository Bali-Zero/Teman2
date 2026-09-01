---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "04 — Implementation craft (BUILD)"
source_report: research/operations/2026-08-28-beyond-sota-implementation-craft.md (PR #5177 branch)
status: SPEC-FINAL
---

# L04 — Implementation craft (BUILD)

## Mission

The organism believes isolating the git tree isolates the work. The worktree broker
(`scripts/agent_start.py`) makes `working_tree(w1) ∩ working_tree(w2) = ∅` true — ahead of every
surveyed system on tree isolation — but everything the tree does not contain is shared and
undeclared: environment (60/4,414 `apps/mouth` tests red in a worktree, green in CI, same commit),
machine (13 of 14 parallel `Agent` spawns died `ENXIO`), stop boundary (two headless `claude -p` runs
exited 0 with work undone; 5+ lanes "silent-idle before the last mile"), default model (SEAT-MIX:
Sonnet 85.8% of dispatches vs. the 2026-08-15 workhorse-first ruling). This spec cures the stop
boundary and the size/attribution meters — the hermetic-environment tier (R3) is out of scope, wave 2.

## Ground to load (orchestrator first reads)

- `scripts/agent_start.py` [exists, 1,814 lines] — the broker; `_refuse_if_nested`,
  `check_ram_admission`, `_worktree_has_wip`, `_content_subset_ok` guards.
- `docs/runbooks/agent-worktree-broker.md` [exists] — branch namespace `agent/<host>/<lane>/<task-id>`.
- `infra/claude-hooks/worktree_isolation.py` [exists, 1,435 lines], `infra/claude-hooks/README.md`
  [exists] — 17 scar-named regression tests convention.
- `infra/claude-hooks/subagent_stop_verify.py` [exists] — the surface PR-1 extends.
- `scripts/lint_test_reward_hacking.py` [exists] — guards PR-1's check command against tautologies.
- `docs/factory/SEAT-MIX.md` [exists] — L93 confirms `sonnet | 127 | 85.8%`.
- `.claude/skills/modus/PENDING-ARMS.md` [exists, 2.2 MB] — ledger for PR-1's auto-row.
- Superscar families #5 (sibling-race), #1 (HOME-fork), #2 (exists≠armed), #3 (guard-over-match).
- **Live-hooks divergence check**: LANE NOTES flag `/Users/nuzantara/.claude/hooks/worktree_isolation.py`
  as possibly diverged from `infra/claude-hooks/worktree_isolation.py`. Verified THIS session: the
  two are byte-identical (1,435 lines, empty diff) on this machine right now. Re-diff at execution
  time on every machine before overwriting — a fix may be stranded live between now and then.

## PR-1: feat(hooks): lane check contract — .lane-check.json gates the stop boundary

**Files**: `infra/claude-hooks/lane_check.py` [proposed], `infra/claude-hooks/subagent_stop_verify.py`
[exists — extended], `infra/claude-hooks/test_lane_check.py` [proposed]

**Gear**: 2

**Build**:

1. DESIGN emits `.lane-check.json` per worktree: `{command, expected_exit, timeout, scope_globs}`.
2. `lane_check.py` is consumed by all FOUR termination surfaces: interactive Stop hook (lives in
   `~/.claude/hooks/stop_verify.py`, HOME-fork — repo canon lands here first, live refresh is a
   separate ALIGN-FLEET step), `subagent_stop_verify.py`, headless `-p` report-file detector,
   PENDING-ARMS auto-row writer.
3. No `.lane-check.json` present → byte-identical behavior to today (innocence baseline, not an
   afterthought).
4. The check command itself gets guilt+innocence tests, guard-conformance style.
5. `lint_test_reward_hacking.py` must flag a bare `true` check command.
6. Scope globs bound the check; keep the matcher entity-based, not substring (family #3).
7. Deliberately BUILD-side only — generator≠grader still applies after it passes. ≤380 net lines.

**Acceptance**: guilt — failing check → stop blocked, stderr quoted; innocence — no
`.lane-check.json` → stop behavior byte-identical to pre-PR; guilt — tautological `true` command →
flagged by `lint_test_reward_hacking.py` or an equivalent assertion in `test_lane_check.py`.
`python infra/claude-hooks/test_lane_check.py -v` exits 0 only when all three fixtures pass.

**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6 (non-Anthropic); final gate =
orchestrator (Opus 5 xhigh).

**Arming / prove-live**: armed = all four surfaces import and honor `lane_check.py`. Probe: drop a
failing `.lane-check.json` in a throwaway worktree, trigger each of the four stop paths, confirm each
blocks quoting stderr; remove the file, confirm all four are silent (innocence).

**Conflicts / order**: `infra/claude-hooks/` is repo canon for the `~/.claude/hooks/` HOME-fork pairs
on all three machines — ALIGN-FLEET refreshes live copies only after a fresh diff on each machine. No
`.github/workflows/` touch, so no serialization needed against L05/L06's workflow edits.

## PR-2: feat(telemetry): lane_outcome_report — correction-chain, time-to-green, builder attribution

**Files**: `scripts/lane_outcome_report.py` [proposed], `scripts/tests/test_lane_outcome_report.py`
[proposed], `docs/factory/SEAT-MIX.md` [exists — appended]

**Gear**: 2

**Build**: correction-chain rate (a `fix`-prefixed commit/PR touching the same FILES, not just a
subject-prefix match, within 7 days); time-to-green; builder attribution from the
`agent/<host>/<lane>/<task-id>` namespace + claim commit. Mitigate Goodhart via file-overlap
detection, never prefix alone. Publish as a daily SEAT-MIX section (a metric nobody reads is
theater). ≤350 net lines.

**Acceptance**: reproduces the hand-measured **27-of-200** correction count within ±3 on the
2026-08-20..22 window; builder attribution ≥80% of merged PRs. **Carry forward, do not silently
fix**: the adversarial review on this report flagged that the automated heuristic and the hand
judgment measure different constructs — ±3 agreement is not validation of the heuristic; report the
number, don't claim it proves the method.

**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final gate = orchestrator
(Opus 5 xhigh).

**Arming / prove-live**: armed = script runs unattended, output lands in `SEAT-MIX.md` dated. Probe:
run against the frozen window, diff correction count against 27/200 (±3); run against last 48h,
confirm attribution ≥80%.

**Conflicts / order**: read-only against git history + branch namespace — no hot-zone paths; parallel
with PR-1 and PR-3.

## PR-3: feat(ci): pr_size_taxonomy — typed exceptions for the 400-line contract (advisory)

**Files**: `scripts/pr_size_taxonomy.py` [proposed], advisory workflow [proposed — new
`.github/workflows/*.yml`, report-only, never added to a required-check list], tests [proposed]

**Gear**: 2

**Build**: exception taxonomy by path-class + provenance (docs/design reports, named codemod output,
lockfiles, generated fixtures); split-recipe documentation (by-files, horizontal, vertical, stacked
child-PR); label every over-400-net-line merged PR `exempt(<class>)` or `split-required`;
report-only, zero gating in this PR. ≤300 net lines.

**Acceptance**: classifies the 26 measured over-400 merges (this session's baseline), assigning a
class to ≥20; workflow output is report-only, zero required-check entries. **Carry forward**: the
adversarial review found the 26/100 baseline itself includes exemptible docs/design drops — hitting
"≥20 classified" by relabeling alone proves nothing. Define the taxonomy BEFORE running the
classification; the metric that matters (non-exempt over-400 share, target 26/100→<10/100) is not
yet computed by this PR — flag as a known gap, don't claim the reduction.

**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final gate = orchestrator
(Opus 5 xhigh).

**Arming / prove-live**: armed = advisory workflow runs on every merged PR, appends a classification.
Probe: re-run over the last 100 merged PRs, confirm ≥20 of the 26 over-400 ones get a non-
`unclassified` label.

**Conflicts / order**: touches `.github/workflows/` → CODEOWNERS-tier hot zone; auto-merge OFF, the
session merges manually after gates (`docs/runbooks/merge-queue-discipline.md`); `pre-commit
lease-check` applies. Serialize against L05 PR-1 and L06 PR-1/PR-2, which also touch workflows.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

1. **Antigravity: arm or retire** (Legge 5, GUI-only surface). 2 mentions in a 2.2 MB ledger. Either
   Zero uses it on one real wave-2 task, or it is downgraded to archaeology.
2. **Disk headroom on Pro for hermetic caches** (physical resource, relevant only if wave-2 R3 is
   later greenlit): disk went 69%→93% with ~23 GB worktree bloat on 2026-07-12.
3. _Not_ needs-ruling, to prevent re-litigation: shifting implementer volume to non-Anthropic seats
   is already RULED (workhorse-first, 2026-08-15).
4. **Candidate for ruling, raised by this report's adversarial review** (not yet formal §7): an
   unreconciled tension between the 2026-08-14 ruling ("Sonnet 5 is the implementer default") and
   the 2026-08-15 workhorse-first ruling — the measured 85.8% Sonnet share may be compliant with the
   first and in violation of the second. This spec does not resolve which binds.

## Suspend & ledger rules

Rule 8: three reds for the SAME cause → SUSPEND with one PENDING-ARMS line naming the cause, branch
left alive, move to the next PR. Every built-but-not-armed step (e.g., PR-1 merged but the live-hook
refresh not yet done on all three machines) gets its own PENDING-ARMS row.

## Out of scope

R3 (hermetic lane tier), R5 (routing-loop scripts beyond the needs-ruling note above), R6
(guard-fuzz harness), R7 (army-feed from PENDING-ARMS) — all wave 2/3, not authorized here. Any
change to `worktree_isolation.py` itself. Gating PR-3's advisory workflow into a required check.
