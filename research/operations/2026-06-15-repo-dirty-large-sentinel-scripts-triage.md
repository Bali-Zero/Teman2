# 2026-06-15 Repo Dirty Large Sentinel Scripts Triage

Status: ready for heavier agent  
Source dispatch key: `repo-dirty-large-sentinel-scripts`  
Prepared by: Codex overnight runner  
Prepared at: 2026-06-15 04:52 Asia/Makassar

## Executive Decision

Spark itself is not the actionable failure. The actionable cluster is the broad
dirty main checkout at `/Users/nuzantara/Desktop/nuzantara`, especially two
staged runtime automation scripts plus large generated/untracked research and
output trees. Do not restart Spark or clean files blindly. Partition the dirty
work first, then promote or archive each partition with its own validation.

Minimal remediation applied by this runner: write this heavier-agent spec only.
No user dirty files in the main checkout were modified.

## Live Evidence Verified

- Machine: `nuzantara@Nuzantara` (Pro).
- Peer check: Mini was unreachable during the session-start SSH check, so
  Pro/Mini git sync is unverified.
- Intervention worktree:
  `codex-overnight/spark-alarm-20260615_045232-spark-dispatch-20260615_040041-scout-repo-dirty-large-sentinel-scripts-20260615_045232`
  started clean from `origin/main` at
  `0207c648a fix(mouth): improve a11y and semantic HTML in chat components (#1427)`.
- Main checkout `/Users/nuzantara/Desktop/nuzantara` is dirty and stale:
  `main...origin/main [ahead 2, behind 176]`.
- Main checkout has staged changes in:
  - `scripts/dlq_autopilot.py`
  - `scripts/nuzantara-sentinel.py`
- Staged automation diff size:
  `2 files changed, 205 insertions(+), 2 deletions(-)`.
- Spark launchd state is healthy enough to leave alone:
  - `com.nuzantara.codex-spark-loop`: PID `1212`, `state = running`,
    last exit `(never exited)`.
  - `com.nuzantara.codex-spark-alarm`: idle between intervals, last exit `0`,
    interval `120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: idle between intervals, last exit `0`,
    interval `180 seconds`.
- Non-Codex launchd failures still exist and are separate follow-up work:
  `com.nuzantara.cost-breaker`, `com.nuzantara.mcp-integrity`,
  `com.nuzantara.review-gate`, and `com.nuzantara.merge-train` all reported
  last exit `127`.
- Fresh Codex/Spark state files exist under
  `/Users/nuzantara/.agent/decisions/state`, including
  `codex_com_nuzantara_codex_spark_harvester.state.json`,
  `codex_com_nuzantara_codex_spark_alarm.state.json`, and
  `codex_com_nuzantara_codex_overnight_runner.state.json`.

Generated/untracked payload sizes observed in the main checkout:

| Path | Size |
| --- | ---: |
| `outputs/` | 40M |
| `research/nb-monitor/` | 20K |
| `apps/evaluator/nlm_deep_research/output/multimodal/` | 167M |
| `research/coherence-corpus/` | 44M |
| `research/commercial/` | 16K |

Notable generated files include `outputs/_b64chunks/*`,
`outputs/clients_all.csv`, `outputs/clients_master_clean.csv`, and
`research/nb-monitor/report-2026-W24.md`.

## Non-Goals

- Do not mutate `/Users/nuzantara/Desktop/nuzantara` during initial triage.
- Do not run `git reset`, `git checkout --`, `git clean`, or stash operations
  against the main checkout.
- Do not delete generated folders until ownership and archival value are clear.
- Do not edit `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`,
  `secrets/*`, or `backend/app/dependencies.py`.
- Do not deploy.
- Do not use `--no-verify`, force push, or bypass CI/review gates.

## Heavier-Agent Work Plan

### 1. Freeze And Inventory Without Mutating Main

Run only read-only capture commands first:

```bash
git -C /Users/nuzantara/Desktop/nuzantara status --short --branch
git -C /Users/nuzantara/Desktop/nuzantara diff --cached --stat
git -C /Users/nuzantara/Desktop/nuzantara diff --stat
git -C /Users/nuzantara/Desktop/nuzantara diff --cached -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py > /tmp/sentinel-dlq-staged.patch
git -C /Users/nuzantara/Desktop/nuzantara diff -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py > /tmp/sentinel-dlq-unstaged.patch
```

Acceptance:
- A timestamped inventory exists outside the repo.
- Staged script patch is preserved before any attempt to test, rebase, or split.
- Main checkout is still dirty in exactly the same way after inventory.

### 2. Partition Dirty Work Into Independent Buckets

Use separate worktrees or branches for each bucket; do not mix them into one PR.

| Bucket | Paths | Initial disposition |
| --- | --- | --- |
| Runtime automation logic | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Highest priority. Test in isolation before promotion. |
| NLM/evaluator code | `apps/evaluator/nlm_deep_research/*.py`, related configs | Separate PR with evaluator validation. |
| Generated research/output | `outputs/`, `research/nb-monitor/`, `research/regulatory/*-delta.json`, `apps/evaluator/nlm_deep_research/output/multimodal/`, `research/coherence-corpus/` | Classify as artifact, archive, or intentionally tracked content before committing. |
| Public content | New `apps/mouth/src/content/articles/**/*.mdx` | Separate editorial/content PR with frontend/content checks. |
| Docs/rules | `.claude/rules/*`, `docs/*`, `research/operations/*` | Separate docs PR if still relevant. |
| Launchd failures | `com.nuzantara.cost-breaker`, `mcp-integrity`, `review-gate`, `merge-train` | Diagnose as service failures, not Spark failures. |

Acceptance:
- Each bucket has an owner, validation command, and disposition:
  `promote`, `archive`, `ignore`, or `discard with explicit owner approval`.
- No bucket includes both runtime automation code and large generated artifacts.

### 3. Runtime Automation Script Review Focus

The staged script patch appears to implement W70 DLQ/sentinel recovery behavior:

- `scripts/dlq_autopilot.py`
  - Adds `requeue_terminal(job_id: str) -> int`.
  - Resets matching `TERMINAL` DLQ entries to active state.
  - Adds CLI usage `requeue <job_id>`.
- `scripts/nuzantara-sentinel.py`
  - Enriches bare `last_error` values from cron log tails.
  - Clears DLQ terminal entries when jobs recover.
  - Adds blind heal-loop detection and alerting.
  - Counts resurrected jobs as healing actions in the current cycle.

Review risks before promotion:

- Patch was staged on a main checkout that is `behind 176`; verify it still
  applies cleanly to current `origin/main`.
- `exit 127` launchd failures may be PATH/program resolution issues and should
  not be assumed fixed by sentinel/DLQ behavior.
- Confirm `clear_dlq_entry`, `check_escalation_cooldown`,
  `mark_escalation_sent`, and `send_alert` semantics before allowing automated
  terminal-entry mutation.
- Ensure blind-loop alerts cannot storm and that cooldown state is shared with
  the existing escalation mechanism.
- Confirm the `healing_actions_24h` field is not consumed elsewhere as a true
  24-hour aggregate, because the patched code still writes current-cycle
  retried/resurrected counts.

Suggested isolated validation:

```bash
WT=$(python scripts/agent_start.py --lane ops --task-id sentinel-dlq-w70-review | tail -1)
cd "$WT"
git apply --check /tmp/sentinel-dlq-staged.patch
git apply /tmp/sentinel-dlq-staged.patch
source venv/bin/activate
python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
python scripts/dlq_autopilot.py requeue __nonexistent_test_job__
```

If repository tests exist for these scripts, add or run focused tests before
promoting the patch. Do not validate by running the production LaunchAgents.

Acceptance:
- Patch applies to a current isolated worktree or is rebased explicitly.
- Syntax and focused behavior validation pass.
- Promotion PR contains only automation script code and tests/docs needed for
  those scripts.

### 4. Generated Output Disposition

The generated folders are too large and heterogeneous to commit by default:

- `apps/evaluator/nlm_deep_research/output/multimodal/` is 167M.
- `outputs/` contains base64 chunks and CRM-looking CSV exports.
- `research/coherence-corpus/` is 44M.

Required checks before any commit:

```bash
git -C /Users/nuzantara/Desktop/nuzantara check-ignore -v outputs research/nb-monitor apps/evaluator/nlm_deep_research/output/multimodal research/coherence-corpus
find /Users/nuzantara/Desktop/nuzantara/outputs -maxdepth 2 -type f | sed -n '1,120p'
find /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/output/multimodal -maxdepth 2 -type f | sed -n '1,120p'
```

Acceptance:
- Human-sensitive exports are not committed accidentally.
- Large binary/multimodal artifacts are either ignored, archived outside git, or
  represented by a small manifest.
- If new `.gitignore` rules are needed, propose them in a dedicated PR.

### 5. Launchd Exit 127 Follow-Up

Treat these as service command-resolution failures until logs prove otherwise:

- `com.nuzantara.cost-breaker`
- `com.nuzantara.mcp-integrity`
- `com.nuzantara.review-gate`
- `com.nuzantara.merge-train`

Read-only first pass:

```bash
for label in com.nuzantara.cost-breaker com.nuzantara.mcp-integrity com.nuzantara.review-gate com.nuzantara.merge-train; do
  launchctl print "gui/$(id -u)/$label"
done
```

Acceptance:
- Each failing label has the resolved program/arguments, stderr/stdout log path,
  and latest error text recorded.
- Any fix is separated from the dirty-worktree partition PR unless it directly
  depends on the same script patch.

## Done Criteria

- Main checkout user changes are preserved.
- Runtime script patch has a dedicated decision: promoted with validation,
  parked as patch, or rejected with a concrete reason.
- Generated outputs are not mixed into runtime code PRs.
- Spark lifecycle is left alone unless it becomes stale or exits non-zero in a
  fresh live check.
- The next status report says exactly which bucket moved and which bucket
  remains blocked.
