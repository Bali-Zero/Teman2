# Codex Spark Sentinel Recovery Runbook

Date: 2026-05-20
Scope: `com.nuzantara.codex-spark-loop`, `com.nuzantara.codex-spark-alarm`,
`com.nuzantara.codex-spark-harvester`, and the overnight queue handoff.

This runbook exists because Spark scout reports can correctly identify a noisy
cluster while still being wrong about the live root cause. Treat scout output as
a triage seed, then verify the live launchd, state, queue, and log surfaces
before restarting anything.

## Verified Baseline From This Intervention

Current task source:

- Spark report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260520_003830.md`
- Spark prompt: `/Users/nuzantara/logs/codex-spark-loop/scout-20260520_003830.prompt.md`
- Spark JSONL: `/Users/nuzantara/logs/codex-spark-loop/scout-20260520_003830.jsonl`
- Runtime worktree:
  `/Users/nuzantara/Desktop/nuzantara/.worktrees/codex-overnight-runner-runs/spark-alarm-20260520_010704-spark-dispatch-20260520_003830-scout-2cce49097c53-20260520_010706`

Live checks on 2026-05-20 01:08-01:12 WITA showed:

- `com.nuzantara.codex-spark-loop` was loaded and `state = running` with PID
  `70536`, despite `last terminating signal = Terminated: 15`.
- The loop state file was fresh and unhealthy:
  `/Users/nuzantara/.agent/decisions/state/codex_com_nuzantara_codex_spark_loop.state.json`
  had `action=failed`, `message="Spark loop failed scout: exit 124"`.
- `com.nuzantara.codex-spark-alarm` was loaded but not running between
  intervals, with `last exit code = 1`; its state file had
  `action=spark_unhealthy`, `message="blocked_state action=failed"`.
- `com.nuzantara.codex-spark-harvester` was loaded, interval-based, and its
  latest state was `action=runner_active`.
- The useful cluster was not "Spark loop stopped". It was "running Spark loop
  with fresh failed scout timeout state, plus alarm escalation and repeated
  partial overnight tasks".

## Do Not Use These As Sole Evidence

Do not restart or patch solely because of any one of these signals:

- `launchctl list` shows `last_exit=-15` for `com.nuzantara.codex-spark-loop`.
  A loaded KeepAlive service can be running now while retaining the previous
  SIGTERM as its last terminating signal.
- `com.nuzantara.codex-spark-alarm` or `com.nuzantara.codex-spark-harvester`
  show `- 0` in `launchctl list`. They are interval jobs and are normally not
  running between ticks.
- A Spark report says `status: actionable`. The report is produced from a small
  snapshot and can be stale within minutes.
- The overnight failed directory contains old partial tasks. Use mtime and the
  active queue/backlog count before treating them as current failures.

## Required Diagnostic Commands

Run these from Pro before any remediation:

```bash
echo "Machine: $(whoami)@$(hostname)"
launchctl print gui/$(id -u)/com.nuzantara.codex-spark-loop | sed -n '1,180p'
launchctl print gui/$(id -u)/com.nuzantara.codex-spark-alarm | sed -n '1,160p'
launchctl print gui/$(id -u)/com.nuzantara.codex-spark-harvester | sed -n '1,160p'
```

Inspect state freshness and content:

```bash
for f in \
  ~/.agent/decisions/state/codex_com_nuzantara_codex_spark_loop.state.json \
  ~/.agent/decisions/state/codex_com_nuzantara_codex_spark_alarm.state.json \
  ~/.agent/decisions/state/codex_com_nuzantara_codex_spark_harvester.state.json
do
  echo "--- $f"
  stat -f 'mtime=%Sm size=%z' -t '%Y-%m-%dT%H:%M:%S%z' "$f" 2>&1
  sed -n '1,220p' "$f" 2>&1
done
```

Extract the recent loop timeline:

```bash
tail -n 180 ~/logs/codex-spark-loop/launchd.out.log
tail -n 80 ~/logs/codex-spark-loop/launchd.err.log
tail -n 180 ~/logs/codex-spark-alarm/launchd.out.log
tail -n 120 ~/logs/codex-spark-harvester/launchd.out.log
```

Check queue pressure and recent partials:

```bash
find ~/codex-overnight/queue -maxdepth 1 -type f -name '*.md' | sort
find ~/codex-overnight/backlog -maxdepth 1 -type f -name '*.md' | sort
ls -lt ~/codex-overnight/failed | sed -n '1,20p'
```

## Decision Matrix

### Healthy Or No-Op

Classify as no-op when all are true:

- `launchctl print ...codex-spark-loop` says `state = running` and has a PID.
- The loop state file mtime is newer than 2x `CODEX_SPARK_LOOP_INTERVAL`
  (default 10 minutes).
- The last loop log has a recent `Spark loop tick complete` line.
- The latest report has `codex_exit=0`, or a non-zero exit is isolated and
  followed by later successful reports.

Action: write status only. Do not kickstart.

### Scout Timeout Cluster

Classify as scout timeout when all are true:

- The loop is running.
- The loop state file is fresh.
- The loop state says `action=failed` and the message includes `exit 124`.
- The matching report says `codex_exit: 124` and `(no final message written)`.

Action:

1. Do not restart the LaunchAgent as the first move.
2. Inspect the matching prompt and JSONL.
3. If fewer than 3 consecutive timeout reports occurred, wait for the next tick
   or record a watch status.
4. If 3 or more consecutive timeout reports occurred, open a focused follow-up
   issue/PR to tune `CODEX_SPARK_LOOP_RUN_TIMEOUT`, reduce scout snapshot size,
   or add a timeout-specific state classification. Do not bundle watchdog or
   unrelated launchd exits.

### Stale State Or Dead Loop

Classify as stale/dead only when one of these is true:

- `launchctl print ...codex-spark-loop` reports the service is missing or not
  running, and the state file is older than 2x the loop interval.
- The lock directory exists and its PID is not running:
  `~/.agent/decisions/state/codex_spark_loop.lock.d/pid`.
- The loop log has no tick start or completion newer than 2x the loop interval.

Action:

```bash
launchctl kickstart -k gui/$(id -u)/com.nuzantara.codex-spark-loop
sleep 15
launchctl print gui/$(id -u)/com.nuzantara.codex-spark-loop | sed -n '1,120p'
tail -n 40 ~/logs/codex-spark-loop/launchd.out.log
```

Acceptance criteria after kickstart:

- `state = running`
- PID present
- state file mtime changes within one loop interval
- log shows a new tick

If these do not hold, stop and write a blocked status. Do not repeatedly
kickstart.

### Alarm Blocked State

Classify alarm as a reporter, not the root cause, when:

- `codex_spark_alarm.state.json` says `spark_unhealthy` or
  `blocked_state action=failed`.
- The loop state file independently confirms `action=failed`.

Action: fix or document the loop condition first. Alarm exit `1` is expected
when it intentionally reports unhealthy state.

### Harvester Runner Active

Classify harvester as healthy when:

- `codex_spark_harvester.state.json` says `runner_active`,
  `backlog_waiting`, or `idle` with fresh mtime.
- Its launchd job is loaded and interval-based.

Action: do not restart harvester unless its state is stale and queue/backlog
counts prove it stopped advancing handoffs.

## Minimal Remediation Policy

Use the smallest action that matches evidence:

1. Fresh timeout state: document and watch; do not restart.
2. Dead loop with stale state: one kickstart, then verify.
3. Repeated partial overnight failures: inspect the failed status files and
   runner logs before dispatching more work.
4. Watchdog `127` exits: keep out of the Spark loop root-cause cluster unless
   their stderr proves they block Spark scripts.

## Non-Goals

- Do not edit `backend/prompts/zantara_core.py`.
- Do not edit `fly.toml`, `.env*`, or secrets.
- Do not deploy.
- Do not force push or bypass hooks.
- Do not modify live scripts under `/Users/nuzantara/scripts/codex/` from an
  overnight worktree. Mirror a proposed patch into the repo first, validate it,
  and ship through PR unless a human explicitly asks for a local hotfix.

## Final Status Template

Use this shape in `/tmp/codex-overnight-<run-id>-status.md`:

```markdown
outcome: success|partial|failed

milestones_completed:
- live evidence baseline
- minimal remediation
- validation

files_changed:
- docs/operations/codex-spark-sentinel-recovery-2026-05-20.md

blockers:
- <none or exact command/error>

next_step:
- <one concrete recommendation>
```
