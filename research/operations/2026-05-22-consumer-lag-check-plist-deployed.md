---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W10 W5 follow-up consumer-lag.check plist
sources: 3
---

# Consumer-lag.check plist deployed — W5 follow-up closed

## Context

Loop iteration 10 of NB-automations hardening. W5 cicatrix (commit
`063945e1e`) shipped `scripts/check_consumer_lag.py` + `health_tools`
helpers but explicitly deferred the LaunchAgent plist:

> Follow-up: a launchd plist `com.matagaruda.consumer-lag.check.plist`
> that runs this script every 30min and pipes stderr to
> ~/logs/matagaruda-consumer-lag.error.log will give us 24h coverage.

W10 closes that follow-up.

## Empirical state pre-deploy (2026-05-22 07:52 WITA)

`check_consumer_lag.py` manual run shows 6 active alerts:

| Stream | Group | Lag | Pending |
|---|---|---|---|
| garuda:raw | nexus-bridge | 2279 | 0 |
| garuda:raw | normalizer | 858 | 9 |
| garuda:enriched | classifier | 1230 | 7 |
| garuda:enriched | ner | 1530 | 110 |
| garuda:enriched | nlm_feeder | 1035 | 82 |
| garuda:enriched | scorer | 927 | 0 |

Without the plist, these alerts surface only when an operator manually
runs the script — invisible in the launchd dashboard, invisible in any
log file. Defeats the entire point of W5.

## Fix shipped

1. **Wrapper** `~/scripts/matagaruda-consumer-lag-check.sh` (24 lines,
   `set -e`, TCC-safe). NO flock — script runs in <1s and is idempotent
   (read-only). NO exit-code translation — propagates the script's
   exit 1 on alert so launchd's `last exit code` reflects active alerts.
2. **LaunchAgent** `~/Library/LaunchAgents/com.matagaruda.consumer-lag.check.plist`,
   `StartInterval=1800` (30min). Bootstrapped via `launchctl bootstrap`.
3. **Cross-tree sync**: `apps/mata-garuda/scripts/check_consumer_lag.py` +
   `mata_garuda/tools/health_tools.py` (W5 code) synced from worktree to
   main tree so the live cron working-directory can find the entry point
   before the worktree branch merges (same lesson as W9).

## Verification (2026-05-22 07:52 WITA)

```bash
# Bootstrap
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.matagaruda.consumer-lag.check.plist
# → state = not running, last exit = (never exited), run interval = 1800 seconds

# Force kickstart
launchctl kickstart -k "gui/$(id -u)/com.matagaruda.consumer-lag.check"

# Post-kickstart
# → matagaruda-consumer-lag.error.log size = 960 bytes (6 JSON alert lines)
# → matagaruda-consumer-lag.log size = 0 bytes (no stdout — silent success path)
# → launchctl last exit code = 1 (correctly reflects "alerts active")
```

## Operator runbook

```bash
# Live tail alerts
tail -f ~/logs/matagaruda-consumer-lag.error.log

# Check launchctl health
launchctl print "gui/$(id -u)/com.matagaruda.consumer-lag.check" | grep -E "state|last exit|launched"
# last exit = 1 → alerts active (look at error log)
# last exit = 0 → all clean (silent)

# Manual force run
launchctl kickstart -k "gui/$(id -u)/com.matagaruda.consumer-lag.check"
```

## Sources

1. W5 cicatrix (commit `063945e1e`) — `scripts/check_consumer_lag.py` source
2. `~/Library/LaunchAgents/com.matagaruda.ner.adaptive.plist` — pattern reference
3. Empirical 6-alert state at 07:52 WITA from live `check_consumer_lag.py` run
