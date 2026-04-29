# infra/launchd — versioned LaunchAgent plists

This directory holds **versioned, repo-tracked** copies of the LaunchAgent
plist files that run on Pro (and selectively on Air). The actual plists that
`launchd` loads live in `~/Library/LaunchAgents/` — these files are the
canonical source the agents copy from.

VADEMECUM §11 conventions enforced for every plist here:

- `EnvironmentVariables` MUST include `HOME` and `PATH`.
- `StandardOutPath` / `StandardErrorPath` MUST point under `~/logs/` (not
  `/tmp/` — that is wiped on reboot and breaks Sentinel forensics).
- `RunAtLoad` MUST be set explicitly (`false` for cron-style jobs,
  `true` for daemon-on-boot).
- `StartCalendarInterval` schedules use the user's **LOCAL time zone**
  (Bali Zero = `Asia/Makassar` = WITA = UTC+8).

## Current plists

| File | Purpose | Schedule |
| ---- | ------- | -------- |
| `com.nuzantara.escalations-prune.plist` | P1-8 — prune resolved escalations >30d, archive unresolved >90d from `~/.agent/decisions/escalations.sqlite` | Daily 03:00 WITA |

## Install

After merging a new/updated plist here, install on the target machine:

```bash
# Pro (or Air, if applicable)
cp infra/launchd/com.nuzantara.escalations-prune.plist ~/Library/LaunchAgents/
plutil -lint ~/Library/LaunchAgents/com.nuzantara.escalations-prune.plist  # must print "OK"
launchctl unload -w ~/Library/LaunchAgents/com.nuzantara.escalations-prune.plist 2>/dev/null || true
launchctl load   -w ~/Library/LaunchAgents/com.nuzantara.escalations-prune.plist
launchctl list | grep com.nuzantara.escalations-prune
```

## P1-8 first-run on Pro

After installing the plist for the first time, also run the one-shot import
to backfill the SQLite mirror from the existing JSONL:

```bash
mkdir -p ~/.agent/decisions ~/logs/cron-agent
python3 ~/Desktop/nuzantara/scripts/migrate_escalations_to_sqlite.py import
sqlite3 ~/.agent/decisions/escalations.sqlite \
    "SELECT COUNT(*) AS total, SUM(resolved_at IS NULL) AS active FROM escalations"
```

The cron then keeps the DB bounded automatically.
