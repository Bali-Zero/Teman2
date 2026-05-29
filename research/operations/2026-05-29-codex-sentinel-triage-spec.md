# Codex Sentinel Triage Spec - 2026-05-29

## Scope

This spec captures the live triage for Spark dispatch `4bada30028ad`
(`repo-dirty-plus-codex-state-triage`). It is intentionally limited to
classification and safe follow-up rules. It does not authorize cleanup,
deletion, staging, or committing of the dirty files in the main checkout.

## Live Verification

Run date: 2026-05-29 14:23-14:35 WITA on Pro
(`nuzantara@Nuzantara`).

Peer state:

- `ssh mini` reached `nuzantara@mini-pro2`.
- Local and peer HEAD matched:
  `3a9011c19 chore(wr2): cutover canva-apply LaunchAgent to headless actuator (#933)`.

Spark launchd state:

- `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 28682`,
  `last exit code = 0`.
- `com.nuzantara.codex-spark-alarm`: `state = not running`,
  `run interval = 120 seconds`, `last exit code = 0`.
- `com.nuzantara.codex-spark-harvester`: `state = not running`,
  `run interval = 180 seconds`, `last exit code = 0`.

Decision-state freshness:

- `codex_com_nuzantara_codex_spark_loop.state.json` was updated at dispatch
  time with `action=dispatched` and the expected backlog path.
- `codex_com_nuzantara_codex_spark_alarm.state.json` was updated one tick later
  with `action=promoted` and the expected overnight queue path.
- `codex_com_nuzantara_codex_spark_harvester.state.json` observed the backlog
  waiting before promotion. This is consistent with interval timing, not stale
  state.
- `codex_com_nuzantara_codex_overnight_runner.state.json` was updated with
  this run's dedicated branch/worktree.

Log findings:

- Latest Spark loop ticks completed successfully after a short earlier timeout
  cluster: exit `124` occurred around 11:39-12:06 WITA, then subsequent ticks
  returned to exit `0`.
- Spark alarm promoted this dispatch and requested runner kickstart.
- Spark harvester reported queue/backlog state as expected.
- `codex-autofix-ci` logs contain repeated older
  `cd: .../.worktrees/codex-autofix-ci-runtime: No such file or directory`
  lines, followed by worktree creation output. Current state is
  `action=daily_cap`, `outcome=skipped`, so the missing-runtime signal is not a
  current Spark blocker.

## Main Checkout Dirt Classification

The main checkout `/Users/nuzantara/Desktop/nuzantara` was dirty. These files
were inspected read-only and left untouched:

| Path | Status | Classification | Evidence |
| --- | --- | --- | --- |
| `research/visa/2026-05-26-c5a-content-creator-deep-research.md` | modified | intentional research correction | six-line taxonomy/citation correction for C7A/C7B/C7C, mtime 2026-05-29 08:50 WITA |
| `shared/escalations_pro.jsonl` | modified | runtime escalation append | one JSONL row for `nlm_nb1_daily_refresh`, mtime 2026-05-29 04:32 WITA |
| `research/nb-health/2026-05-29-health.md` | untracked | generated NB health report | read-only daily report, mtime 2026-05-29 04:31 WITA |
| `research/operations/2026-05-29-flow-tier1p5-veo-model-mapping.md` | untracked | intentional operations research capture | FlowKit/Veo tier mapping research, mtime 2026-05-29 06:29 WITA |
| `research/regulatory/2026-05-29-delta.json` | untracked | generated regulatory delta artifact | partial daily JSON result, mtime 2026-05-29 07:06 WITA |
| `scripts/wr3_gatekeeper_check.py` | untracked | WIP operational helper | WR3 pre-render gatekeeper script, mtime 2026-05-29 05:37 WITA |
| `scripts/wr3_render_episode.py` | untracked | WIP operational helper | WR3 FlowKit render driver, mtime 2026-05-29 05:38 WITA |

## Decision Rules

1. Do not treat Spark alarm or harvester `not running` as failure when
   `last exit code = 0` and a StartInterval is configured.
2. Treat Spark loop timeout clusters as watch-level unless they persist across
   three or more recent ticks and the latest state/log remains non-zero.
3. Treat `shared/escalations_pro.jsonl` as runtime output. Do not fold it into
   unrelated feature or research commits.
4. Treat untracked dated research files under `research/**/2026-05-29-*` as
   likely intentional capture until an owner-specific cleanup pass says
   otherwise.
5. Treat untracked executable scripts under `scripts/` as WIP until their
   imports, dependencies, and expected CLI contract are validated in a dedicated
   WR3 pass.
6. For `codex-autofix-ci`, only remediate the runtime worktree if both are true:
   the latest state is not `daily_cap`/`skipped`, and the runtime worktree is
   still missing in `git worktree list`.

## Minimal Remediation

No destructive cleanup is supported by the evidence. The safe remediation is
this spec: it records live verification, classifies the dirty surfaces, and
prevents future sentinel passes from escalating healthy Spark timer semantics or
accidentally absorbing unrelated WIP.

## Next Step

Schedule a separate WR3 owner pass for the two untracked scripts if they need to
be productized. Otherwise leave the main checkout dirt untouched until the owner
or originating automation commits, archives, or removes each artifact.
