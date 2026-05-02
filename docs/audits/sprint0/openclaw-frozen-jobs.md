# OpenClaw 24 frozen jobs cleanup plan — Sprint 0 Track A5 (part 2)

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "Disabilitare 24 OpenClaw frozen jobs"

## TL;DR

`~/.openclaw/cron/jobs.json` on Pro contains **24 jobs** that are all
`status=null, lastRun=null, nextRun=null` since approximately 2026-04-30
(the OpenClaw scheduler froze for reasons not yet root-caused; likely
fixed in v2026.4.29 — see Track A4 upgrade plan).

All 24 overlap with the **`cron-agent-python` 19 strategies** that are LIVE
production runners today. Round 2 brainstorm 4/4 unanime: split clean
Opzione C → cron-agent-python wins these workloads, OpenClaw cron tool is
de-scoped.

→ **Disable the 24 OpenClaw cron jobs before the OpenClaw upgrade**, so
that when (if) the scheduler unfreezes after upgrade we don't get
double-execution against cron-agent-python.

## What's in the queue

From the round 1 audit transcript (06_openclaw_ecosystem_audit.md § 6):

```
Sample 5 named:
  - client-health-005
  - seo-guardian-weekly-001
  - conversation-cleanup-daily-001
  - tech-orchestrator-l2-002
  - system-doctor-001

19 more UUID-based jobs (full list requires reading ~/.openclaw/cron/jobs.json)
```

The named-prefix jobs map directly onto cron-agent-python strategies (see
Track D2 ownership matrix):

| Frozen OpenClaw job | cron-agent-python strategy | Active? |
|---|---|---|
| `client-health-005` | `client-health-monitor` | ✅ |
| `seo-guardian-weekly-001` | `seo-guardian-weekly` (cron strategy) | ✅ |
| `conversation-cleanup-daily-001` | `conversation-trainer` cleanup tier | ✅ |
| `tech-orchestrator-l2-002` | `tech-orchestrator` (Level 2) | ✅ |
| `system-doctor-001` | `system-doctor` | ✅ |

UUID-prefixed jobs likely fall in the same categories — full mapping in
Step 1 below.

## Recommended action: disable, don't delete

Per Symbiosis Law 5, deletion is destructive: if the scheduler unfreezes
post-upgrade and we discover a job that was actually carrying value
(e.g. a one-shot that wasn't meant to be in cron-agent-python), the
audit log is gone. Better: set each job's `enabled=false` in jobs.json
and leave the entries on disk.

## Application steps (manual on Pro)

### Step 1 — list all 24 with their full metadata (read-only)

```bash
ssh pro 'python3 -c "
import json
jobs = json.load(open(\"$HOME/.openclaw/cron/jobs.json\"))
for j in jobs:
    name = j.get(\"name\", j.get(\"id\", \"<no-id>\"))
    schedule = j.get(\"schedule\", \"<no-schedule>\")
    cmd = j.get(\"command\", \"<no-cmd>\")[:80]
    print(f\"{name:40s} {schedule:20s} {cmd}\")
"' > ~/openclaw-frozen-jobs-snapshot-2026-05-02.tsv
```

Expected: 24 rows. Verify count: `wc -l ~/openclaw-frozen-jobs-snapshot-2026-05-02.tsv`.

### Step 2 — backup + disable

```bash
ssh pro 'cp ~/.openclaw/cron/jobs.json ~/.openclaw/cron/jobs.json.pre-disable-2026-05-02'

ssh pro 'python3 -c "
import json
path = \"$HOME/.openclaw/cron/jobs.json\"
jobs = json.load(open(path))
for j in jobs:
    j[\"enabled\"] = False
    j[\"_disabled_at\"] = \"2026-05-02\"
    j[\"_disabled_by\"] = \"Sprint 0 Track A5 — split clean Opzione C\"
json.dump(jobs, open(path, \"w\"), indent=2)
print(f\"disabled {len(jobs)} jobs\")
"'
```

### Step 3 — hot-reload OpenClaw

```bash
ssh pro 'launchctl kickstart -k gui/501/ai.openclaw.gateway'
```

OpenClaw should re-read `jobs.json` on next reload (within ~500ms based on
hybrid-debounce config). Verify by running:

```bash
ssh pro 'sleep 30; cat ~/.openclaw/cron/jobs.json | python3 -c "
import json, sys
jobs = json.load(sys.stdin)
print(\"enabled:\", sum(1 for j in jobs if j.get(\"enabled\", True)))
print(\"disabled:\", sum(1 for j in jobs if not j.get(\"enabled\", True)))
"'
```

Expected: `enabled: 0, disabled: 24`.

### Step 4 — verify no double-execution

If/when OpenClaw upgrades to v2026.4.29 and the scheduler unfreezes:

```bash
ssh pro 'tail -F ~/.openclaw/logs/gateway.log | grep -iE "(cron|scheduler|job)"'
```

Expected: silence or `[cron] all jobs disabled`. NOT: `[cron] firing job X`.

If a job fires despite `enabled=false`, that's a bug in OpenClaw's
respect of the flag — file with the OpenClaw vendor. Roll back from
backup, leave at v2026.3.31 until the scheduler-config behaviour is
clarified.

## Repo helper script

`scripts/openclaw-frozen-jobs-disable.sh` — dry-run by default, uses jq to
batch-disable all jobs in `~/.openclaw/cron/jobs.json`. Usage:

```bash
# On Pro (or via ssh pro 'bash ...'):
bash scripts/openclaw-frozen-jobs-disable.sh --dry-run    # default
bash scripts/openclaw-frozen-jobs-disable.sh --apply
```

## Out-of-scope today

- Migrating any of the 24 jobs to cron-agent-python. The audit shows full
  overlap with existing strategies; nothing to migrate, only to disable.
  If a UUID job in Step 1 turns out to NOT match a known strategy, file
  it as an audit gap and bring it to Sprint 1 mapping.
- Removing the `cron` tool from OpenClaw `tools.alsoAllow` entirely. The
  Lobster workflows might invoke ad-hoc cron registration; safer to leave
  the tool available but the queue empty.

## References

- `~/.openclaw/cron/jobs.json` (24 frozen jobs)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/06_openclaw_ecosystem_audit.md` § 6
- `docs/audits/sprint0/openclaw-upgrade-plan.md` (Track A4 — upgrade procedure)
- `scripts/openclaw-frozen-jobs-disable.sh`
