---
date: 2026-05-29
domain: operations
status: ready-for-owner-triage
source_dispatch: spark-alarm-20260529_164915-spark-dispatch-20260529_164804-scout-1cd68c06dd7f
scope: main checkout dirty-state triage
---

# Main Dirty Worktree Triage — 2026-05-29

## Finding

Spark's actionable signal is valid, but narrow: `/Users/nuzantara/Desktop/nuzantara`
is dirty at `3a9011c19 chore(wr2): cutover canva-apply LaunchAgent to headless
actuator (#933)`.

The Spark lifecycle signal is not actionable. Live `launchctl print` on 2026-05-29
showed:

| Job | Live state | Last exit | Interpretation |
| --- | --- | --- | --- |
| `com.nuzantara.codex-spark-loop` | running, pid `28682` | 0 | healthy |
| `com.nuzantara.codex-spark-alarm` | not running, interval 120s | 0 | healthy timer idle |
| `com.nuzantara.codex-spark-harvester` | not running, interval 180s | 0 | healthy timer idle |
| `com.nuzantara.codex-overnight-runner` | running, pid `45157` | 0 | this run |

Codex decision-state files for Spark and overnight were fresh during this run, so
there is no direct stale-state proof to remediate.

## Dirty Files

| Path | Git state | Modified WITA | Size | Likely owner/intent | Plan |
| --- | --- | ---: | ---: | --- | --- |
| `research/visa/2026-05-26-c5a-content-creator-deep-research.md` | modified | 2026-05-29 08:50 | 101358 | Visa research correction; C7A/C7B/C7C taxonomy updated from Kepmen M.IP-08 evidence | Keep candidate. Owner should verify cited source path and commit as a research correction if source exists. |
| `shared/escalations_pro.jsonl` | modified | 2026-05-29 04:32 | 1171251 | Runtime DLQ append for `nlm_nb1_daily_refresh` | Do not include in feature/research commits. Preserve as runtime state or rotate through the escalation workflow. |
| `research/nb-health/2026-05-29-health.md` | untracked | 2026-05-29 04:31 | 15965 | NB curator daily health report | Keep candidate. Commit under an NB-health/report scope after owner confirms the P1 AIResearch source-drop alarm should be tracked. |
| `research/operations/2026-05-29-flow-tier1p5-veo-model-mapping.md` | untracked | 2026-05-29 06:29 | 10816 | FlowKit/TIER1P5 research capture | Keep candidate. Commit as research only; do not implement model guesses until live request sniffing verifies `videoModelKey`. |
| `research/regulatory/2026-05-29-delta.json` | untracked | 2026-05-29 07:06 | 3141 | Regulatory watcher daily delta output | Keep candidate if daily regulatory snapshots are versioned. Mark partial because NB UUIDs are stale and sources include WAF gaps. |
| `scripts/wr3_gatekeeper_check.py` | untracked | 2026-05-29 05:37 | 6064 | WR3 deterministic pre-render gatekeeper prototype | Owner-review only. Do not commit as-is: uses `print`, sync file I/O, untyped functions, local inline rules, and no tests. |
| `scripts/wr3_render_episode.py` | untracked | 2026-05-29 05:38 | 4568 | WR3 FlowKit render driver prototype | Owner-review only. Do not commit as-is: uses `print`, sync `urllib`, path mutation/import of `wr3_flowkit_client`, broad exception catch, and no tests. |

## Recommended Reconciliation Order

1. Isolate runtime state first:
   `shared/escalations_pro.jsonl` should not ride with any research or script commit.
2. Commit low-risk research artifacts separately:
   NB health report, Flow/TIER1P5 research, and regulatory delta can each be reviewed
   as standalone data/research commits.
3. Review the visa correction against
   `research/legal/2026-05-26-kepmen-visa-taxonomy/01-raw-extraction.md` before
   committing it.
4. Treat the two WR3 scripts as prototypes. Before promotion, refactor to repo
   standards: typed functions, logger instead of `print`, no ad hoc `sys.path`
   mutation, no sync HTTP, and focused tests/fixtures.

## Suggested Commands

```bash
git -C /Users/nuzantara/Desktop/nuzantara diff --stat
git -C /Users/nuzantara/Desktop/nuzantara diff -- research/visa/2026-05-26-c5a-content-creator-deep-research.md
tail -1 /Users/nuzantara/Desktop/nuzantara/shared/escalations_pro.jsonl
cd /Users/nuzantara/Desktop/nuzantara
source .venv/bin/activate
python -m json.tool research/regulatory/2026-05-29-delta.json
```

No destructive cleanup is recommended from an unattended runner. The safe handoff is
to leave the dirty main checkout untouched and use this file as the owner triage map.
