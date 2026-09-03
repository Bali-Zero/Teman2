# LANE F — CI and merge-queue truth: make "armed" mean armed

**Machine:** Mini (GitHub-side; no local build; may run as headless ticks ≤ every 4 h with an
isolated `CLAUDE_CONFIG_DIR`). **Corner:** `.claude/skills/pipeline-ship/SKILL.md`,
`docs/runbooks/merge-queue-discipline.md`, memory `MEMORY_MERGE_QUEUE_TRAPS.md`.
**Contract:** `README.md` here.

Every item below is a mechanism that reports green while doing nothing. Fix the mechanism, add
the guilt test that would have caught it, never widen an exemption.

## F1 — Auto-merge arming has been inert since the queue (#5578)

- `auto-merge-whitelist.yml`'s `Enable auto-merge` step is inert; the workflow declines to ARM on a
  protected-path match but never DISARMS an auto-merge armed before a later push;
  `scripts/tests/test_auto_merge_whitelist.py` is named by no workflow and 26 of its tests are red
  on main; #5576's evidence pack states the opposite of the measured world. Fix in this order:
  wire the test → make it green → fix arming → add disarm-on-push → re-arm with proof
  (`autoMergeRequest` read via GraphQL on a throwaway PR).

## F2 — Dependabot lock carve-out is believed, not observed

- `exclude-paths` on the two uv-compiled locks: observe one Dependabot run; security updates ignore
  it (line-1 comment lies). The four born-dead PRs (#5564, #5565, #5453, #5452 — check #5566) get
  closed with the reason, not merged. A lock-only diff without its paired manifest must FAIL a
  check (ledger 2026-09-02: "a comment is not a control").

## F3 — `Harness floor recompute` is red on #5569, #5158, #5526, #5337 — cause unknown

- Diagnose ONCE on #5569 (council roster, ARMED): is it the base having moved (repoint with
  `bash scripts/mq.sh requeue`), a stale merge ref (W111), or the floor's own read-set? Then apply
  the same cure to the other three. If the floor is wrong, fix the floor, not the PRs.

## F4 — `scripts/codex-spalla.sh` exits 0 when codex never ran

- `--full-auto` was removed in codex-cli 0.149.1; every "clean" second opinion since is
  un-judged. Cure: pass `--sandbox read-only`, propagate the real rc, guilt test with a fake
  `codex` on PATH that exits 2.

## F5 — Checks that run and do not block

- `collision-matrix-case-folding` (#5497) and `merah-putih-day-contrast.yml` are jobs, not required
  contexts: add them to `infra/required.d/contexts.json` once green (B1 owns making the second
  green). `Visa Oracle fullstack smoke (advisory)`: never green since #4709 — fix or delete.

## F6 — Conflicting PRs

- #5155, #5072, #5028, #4815 are `CONFLICTING/DIRTY`. For each: if the branch's content is on main
  (compare by CONTENT, `git diff` against `origin/main`, never SHA-ancestor), close with the
  reason; else rebase onto fresh main in a NEW PR and close the old one.

## F7 — Instrumentation debt (small, one PR each)

- `scripts/tp1_call.py`: persist the raw body on JSONDecodeError; collect latency samples so
  `SILENCE_TIMEOUT_SECONDS=300` becomes a measured number.
- `gh` secondary rate limit invisible to the usual probe (ledger 2026-08-31): add the header read.
- `check-ledger-no-silent-loss` goes blind past `--depth=200`: fetch by merge-base.

## Guards

- Never rerun a check without knowing WHY it is red (rule 3): `gh run rerun` replays a stale merge
  ref; a `workflow_dispatch` run never enters the PR's rollup.
- Count check-runs with `gh api --paginate`; three checks means the battery never started.
- BLOCKED with zero red checks = a MISSING required check (concurrency cancel before job 1).

## LIVE STATE (update before ending the session)

- 2026-09-03: nothing done; F3 first (it blocks three armed PRs), then F1, F4, F6, F2, F5, F7.
