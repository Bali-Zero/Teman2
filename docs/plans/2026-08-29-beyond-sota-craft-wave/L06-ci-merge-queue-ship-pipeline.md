---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "06 — CI, merge queue & the ship pipeline"
source_report: research/operations/2026-08-28-beyond-sota-ci-merge-queue-ship-pipeline.md (PR #5177 branch)
status: SPEC-FINAL
---

# L06 — CI, merge queue & the ship pipeline

## Mission

Correctness is AT/AHEAD of SOTA — ALLGREEN queue live since 2026-07-27, evidence-driven required-
check curation (27→9→11 demote/reinstate-by-catch), a queue-trap corpus
(`MEMORY_MERGE_QUEUE_TRAPS.md`, ~19 measured traps) nobody surveyed publishes. Economics and
structural-conflict management are BEHIND: `min_entries_to_merge: 1` means the queue never batches,
Backend Tests executes ~2.5x per merged PR, and **39% of open PRs (12/31) sit DIRTY today** on fixed
shared files (`evidence/brief.yml`+`evidence/pack.yml`, `PENDING-ARMS.md`, `organs_registry.yaml`,
mdx batches). Median open→merge is 61 minutes — "one 30-minute job run twice, back to back." This
lane cures queue-state observability and structural-conflict prediction; it does NOT flip the
batching knob — the adversarial review found the audit had already measured 85% re-entry for size-3
batches and said "do not flip."

## Ground to load (orchestrator first reads)

- `MEMORY_MERGE_QUEUE_TRAPS.md` [exists, 167 lines] — 11 numbered traps + `roll-up-28/8`; trap #1 (no
  single field answers "is this armed?"), #9 (merge_group checks are DIFFERENT runs than the PR's),
  #10 (encoding a known-ambiguous field into a sentinel makes the sentinel lie), #11 (only add/add
  hunks in overlapping windows force serialization) are what PR-2/PR-3 build on.
- `docs/runbooks/merge-queue-discipline.md` [exists] — §2bis reinstatement, §6bis HEADGREEN rejection.
- `scripts/mq.sh` [exists] — verbs confirmed: `status`, `why-red`, `arm`, `watch`, `requeue`,
  `dequeue`, `handoff`; PR-2 adds `state`.
- `.github/workflows/immune-enforcement.yml` [exists] — triggers on both `pull_request` and
  `merge_group`; the sentinel host for PR-1's lint.
- `.github/workflows/hot-zone-pr-gate.yml` [exists], `scripts/ci/hotzone_changed_files.sh` [exists]
  — the W102 merge-base-anchoring antidote.
- `scripts/lint_scar_number_collision.py` [exists] — the claim-set technique PR-3 generalizes.
- `.github/CODEOWNERS` [exists] — Tier-1 on `/.github/workflows/`, CODEOWNERS, dependabot.yml.
- `.github/workflows/auto-merge-whitelist.yml` [exists], `scripts/tests/test_auto_merge_whitelist.py`
  [exists] — measured 24/73 red on clean `origin/main`, no workflow executes it (open, needs-ruling).
- `evidence/brief.yml`, `evidence/pack.yml` [both exist] — the collision-by-construction case.
- `scripts/ci/evidence_paths.py` [exists] — deprecation FAIL date 2026-09-05 for root-path writes.
- `scripts/queue_ejection_attribution.py`, `queue_shepherd.py`, `queue_unstick.py`,
  `probe_merge_gate_integrity.py`, `merge_train.py`, `queue_doctor.py` [all exist] — support organs
  not modified here. Superscar families #9 (state read via proxy) and #2 (exists≠armed).
- **Live fleet state, informational only**: unsolicited cross-machine `queue_unstick` notices arrived
  during Ground-gathering (2026-08-27/28) naming open PRs DIRTY on `evidence/*.yml` and
  `organs_registry.yaml` — confirms this report's 39%/hot-file figures, not a task for these PRs.

## PR-1: ci(queue): trigger-symmetry lint — pull_request and merge_group path filters must match

**Files**: `scripts/ci/lint_trigger_symmetry.py` [proposed], `scripts/tests/test_lint_trigger_symmetry.py`
[proposed], `.github/workflows/immune-enforcement.yml` [exists — hook added]

**Gear**: 2

**Build**: assert every path-filtered workflow has identical path semantics on `pull_request` and
`merge_group` — trap #9's shape (head-green/queue-red split from divergent filters); a workflow with
`paths:` under one trigger absent/narrower/differently-shaped under the other fails; current
asymmetries on the live tree (106 workflows) reported as a **dated, shrink-only allowlist** (no new
entries ever added); hook into `immune-enforcement.yml`'s always-runs sentinel pattern (avoids the
W69 pending-forever trap). ≤150 net lines.

**Acceptance**: guilt — synthetic workflow with `paths:[a/**]` on `pull_request` vs `paths:[b/**]` (or
none) on `merge_group` → exit 1; innocence — identical filters on both, or no filter at all → exit 0;
live-tree run reports current asymmetries into the dated allowlist without failing this PR's own merge.

**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final gate = orchestrator
(Opus 5 xhigh).

**Arming / prove-live**: armed = lint runs on every PR via `immune-enforcement.yml`, blocks a newly-
introduced asymmetry (allowlist never grows). Probe: open a throwaway PR adding a `merge_group`-only
filter and confirm the block; confirm an identical-filter edit passes.

**Conflicts / order**: edits `.github/workflows/immune-enforcement.yml` → CODEOWNERS-tier hot zone;
auto-merge OFF, session merges manually after gates; `pre-commit lease-check` applies. **Order
(LANE NOTES, binding)**: L00's R9-defuse PR merges FIRST, then this PR, then PR-2 (parallel-OK,
scripts-only), then PR-3 (wave 2). L05's PR-1 is ordered after this one — serialize all
`.github/workflows/` diffs across L00/L05/L06 in one track.

## PR-2: feat(mq): mq state — the queue-state oracle

**Files**: `scripts/mq.sh` [exists — new `state` verb], `scripts/tests/test_mq_state_oracle.sh`
[proposed], `.github/workflows/immune-enforcement.yml` [proposed wiring — hook that runs the
companion lint; the workflow-file edit itself is executed by Squad W per the battle plan, this
lane builds only the lint + test]

**Gear**: 2

**Build**: one `mq state <N>` verb using only reliable signals in the trap corpus's attestation
order — (1) `gh pr merge --auto`'s refusal text ("already queued") only when arming is intended;
(2) terminal states (`mergedAt`/`CLOSED`); (3) existence of `gh-readonly-queue/main/pr-<N>-*` runs;
(4) GraphQL `mergeQueueEntry`+`autoMergeRequest` read jointly, labeled non-probative for "not armed"
(trap #10's window: a null+absent joint read proves nothing); plus rollup-vs-required-count and
CANCELLED-bucket handling. A companion lint **bans raw `autoMergeRequest`/`isInMergeQueue` reads
outside `mq.sh`**. The oracle is read-only, never auto-arms. ≤300 net lines.

**Acceptance**: fixtures from traps #1/#10 and the CANCELLED/rollup roll-up rows each yield the
verdict that trap's postmortem says was true (trap #10 fixture must resolve "indeterminate", never
"not armed"); a raw-field-read fixture fails the companion lint. `bash
scripts/tests/test_mq_state_oracle.sh` exits 0 only when every fixture matches ground truth.

**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final gate = orchestrator
(Opus 5 xhigh).

**Arming / prove-live**: armed = at least one existing sentinel (e.g. merge-queue-watch) calls `mq
state` instead of reading raw fields, and the lint would fail if it reverted, AND the companion
lint is actually wired as a hook in `.github/workflows/immune-enforcement.yml` (Squad W executes
that workflow edit; this PR is not armed until Squad W's wiring diff lands). Probe: run `mq state
<N>` on real PRs in three states (queued/not-yet-queued/just-merged), confirm verdict matches `gh pr
view <N>` at that moment.

**Conflicts / order**: scripts-only — no hot-zone touch by the verb itself; parallel with PR-1. If
the sentinel-migration arming step edits a workflow file, that edit follows PR-1's serialization rule.

## PR-3: ci(conflicts): open-PR add/add collision check (advisory)

**Files**: `scripts/ci/pr_collision_check.py` [proposed], tests [proposed], advisory workflow
[proposed — report-only, never a required check]

**Gear**: 2

**Build**: generalize `lint_scar_number_collision.py`'s claim-set technique from "W-number" to
"file+hunk-window" — merge-base-anchored added-hunks per opened PR, intersected against every other
open PR's diff; discriminator stays add/add-in-overlapping-window, never bare "same file" (trap #11:
modify/modify on disjoint lines must NOT flag); posted verdict naming the colliding PR+file plus a
table of known hot files (`evidence/*.yml` until 2026-09-05, `PENDING-ARMS.md`, `organs_registry.yaml`,
`infra/required.d/contexts.json`, mdx batches); advisory only, gates nothing. ≤350 net lines.

**Acceptance**: replay of the historical C1/W125 evidence-pack pair → flags serialize-the-second;
replay of the #4783/#4782 pair (trap #11: modify/modify, disjoint lines) → does NOT flag. Both
replays must match the trap corpus's documented verdict exactly, not merely "a" verdict.

**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final gate = orchestrator
(Opus 5 xhigh).

**Arming / prove-live**: armed = advisory workflow posts a verdict comment on every PR-open; two
clean advisory weeks is the report's own bar before any future reinstate-by-catch promotion (separate
PR, wave 2). Probe: open a throwaway PR that add/add-collides on `evidence/pack.yml` with an existing
open PR and confirm the comment names the correct PR number.

**Conflicts / order**: wave 2 per the authoritative index. Workflow file is a hot-zone touch — same
auto-merge-OFF rule as PR-1; serialize behind PR-1 and PR-2 landing.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

1. **R5 security-gate semantics** (advisory-DB snapshot in the blocking path, live-DB async) —
   changes security posture, Legge 5; report recommends GO with ≤24h bound. Not built in this spec.
2. **Detect Secrets diff-scoping** — same class. **Correction (adversarial review, accepted)**:
   reportedly already shipped in `security.yml` (diff-scoped on PR/merge_group, full scan scheduled
   separately) — re-verify current state before treating as gap or as done.
3. **Whitelist-vs-CODEOWNERS intent**: the 24/73-red `test_auto_merge_whitelist.py` presumes
   CODEOWNERS and whitelist eligibility must coincide, never established. One sentence settles
   fix/re-scope/delete — it then needs an executor either way.
4. **`min_entries_to_merge` batching flip** — ruled-against-for-now: adversarial review (HIGH,
   accepted) found the audit already measured 85% re-entry at size 3 and said "do not flip." Not one
   of this spec's PRs; a future proposal must re-derive the re-entry math first.
5. **Auto-quarantine of flaky tests (R4)** — flagged (HIGH, accepted) as weakening a gate without a
   ruling; needs the ruling plus safeguards (≥5 failures, ≥50 runs, 2% suite cap, expiry) before any
   auto-file mechanism runs. Not built here.

## Suspend & ledger rules

Rule 8: three reds for the SAME cause → SUSPEND, one PENDING-ARMS line naming the cause, branch left
alive. All three PRs touch or gate near `.github/workflows/` hot zones — a suspend caused by a
structural collision on `evidence/*.yml` or `PENDING-ARMS.md` is PR-3's target class; log it as
corpus evidence, not friction. Every built-but-not-armed step gets its own PENDING-ARMS row.

## Out of scope

R1 (batching flip, ruled against, #4 above). R4 (flakiness harvest/auto-quarantine, #5). R5
(world-vs-diff security split) and Detect Secrets scoping (#1-2). R6 (stacked lanes — an
"experiment" in the source report). Migrating required checks into the queue's ruleset layer
(`operator[GUI]`). Fixing `test_auto_merge_whitelist.py` directly (blocked on #3).
