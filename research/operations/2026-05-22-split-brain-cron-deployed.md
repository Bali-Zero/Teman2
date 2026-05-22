---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W17 wire W16 split-brain detector to launchd cron + Telegram alert
sources: 4
---

# W17: split-brain detector launchd cron + Telegram dedup alert

## Context

Loop iteration 17. W16 (commit `542bb2f19`) shipped
`check_redis_split_brain.py` detector that catches Pro<->Mini Redis
drift but did NOT wire it to a cron. The W16 deferred-list item §3
flagged: "W17 candidate: launchd plist for split-brain detector
(Telegram alert on stderr non-empty)."

The detector was already producing actionable signal — without cron,
that signal reaches operator only when someone happens to run the
script. Same failure pattern as W5/W10 (lag monitor shipped library
but no cron until W10 follow-up).

## Fix shipped

### Wrapper

`~/scripts/matagaruda-redis-split-brain-check.sh` (HOME, gitignored,
3.7KB):

- TCC-safe: calls venv python directly (no shell-init trap)
- Sources `~/.nuzantara-secrets.env` for `TELEGRAM_BOT_TOKEN` +
  `TELEGRAM_OWNER_CHAT_ID`
- Runs detector, captures stderr (JSON alerts) + exit code via
  `set +e/-e` block (avoids `|| true` exit masking)
- Re-emits alerts to launchd stderr for `launchctl print` visibility
- Telegram dedup: state file
  `~/.agent/decisions/matagaruda-split-brain-last.txt` stores
  `<epoch> <stream>|<stale_host>` combos. Suppress repeat alerts
  within 4h window. GC entries older than 4h on each run.

### LaunchAgent

`~/Library/LaunchAgents/com.matagaruda.redis-split-brain.check.plist`
(HOME, gitignored, 1KB):

- `StartInterval=1800` (30min cadence matching W10 lag-monitor)
- `RunAtLoad=false` (no init noise)
- `EnvironmentVariables`: PATH includes pyenv 3.11.11 for inline
  json parser; HOME set explicitly
- StandardOutPath/ErrorPath under `~/logs/matagaruda-redis-split-brain.*`

Bootstrapped via `launchctl bootstrap gui/$(id -u)`.

### Telegram dedup logic

```bash
# GC stale entries (>4h old)
awk '($1 + 14400) >= now' $STATE_FILE > $STATE_FILE.tmp

# For each alert line, extract stream+host combo, skip if already in state
COMBO=$(echo "$line" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(f'{d[\"stream\"]}|{d[\"stale_host\"]}')")
if ! grep -q " ${COMBO}$" $STATE_FILE; then
    echo "${NOW} ${COMBO}" >> $STATE_FILE
    NEW_ALERTS="${NEW_ALERTS}${line}\n"
fi

# Only send Telegram if NEW combos found
if [ -n "$NEW_ALERTS" ]; then
    curl -sS POST .../sendMessage -d "text=$MSG"
fi
```

Within 4h window: same split-brain combo only fires Telegram ONCE.
Suppresses notification fatigue while root-cause fix is pending.

## Empirical verification (2026-05-22 12:12 WITA)

```bash
$ launchctl bootstrap gui/$(id -u) com.matagaruda.redis-split-brain.check.plist
# OK

$ launchctl kickstart -k gui/$(id -u)/com.matagaruda.redis-split-brain.check

# Logs after first fire
$ ls -la ~/logs/matagaruda-redis-split-brain.*
-rw-r--r--  1 nuzantara  staff  501 May 22 12:12 .../error.log
-rw-r--r--  1 nuzantara  staff    0 May 22 12:12 .../log

# Stderr: 2 JSON alerts as expected
$ cat ~/logs/matagaruda-redis-split-brain.error.log
{"level":"WARNING","tag":"redis-split-brain","stream":"garuda:enriched","stale_host":"mini","fresh_host":"pro","drift_h":10.2,...}
{"level":"WARNING","tag":"redis-split-brain","stream":"garuda:alerts","stale_host":"pro","fresh_host":"mini","drift_h":210.1,...}

# Last exit code reflects split-brain active
$ launchctl print "gui/$(id -u)/com.matagaruda.redis-split-brain.check" | grep "last exit"
        last exit code = 1
```

## Exit-code gotcha caught pre-deploy

Initial wrapper used `ALERTS=$(...) || true; EXIT_CODE=$?` which
always set EXIT_CODE=0 because `|| true` is the last command before
$? captures. Fix:

```bash
# WRONG:
ALERTS=$(...) || true
EXIT_CODE=$?    # always 0

# RIGHT:
set +e
ALERTS=$(...)
EXIT_CODE=$?    # captures real exit
set -e
```

Smoke test caught this. Always test exit propagation explicitly when
mixing `set -e` + non-zero-tolerant subcommands.

## Operator runbook

```bash
# Live tail
tail -f ~/logs/matagaruda-redis-split-brain.error.log

# Force manual run (e.g. after fixing root cause to verify)
launchctl kickstart -k "gui/$(id -u)/com.matagaruda.redis-split-brain.check"

# Check current dedup state
cat ~/.agent/decisions/matagaruda-split-brain-last.txt

# Reset dedup (force next alert to fire) — useful after fixing one stream
rm ~/.agent/decisions/matagaruda-split-brain-last.txt

# Disable cron temporarily (if Antonello chose Option C replication + needs quiet)
launchctl bootout "gui/$(id -u)/com.matagaruda.redis-split-brain.check"
```

## Telegram alert format

```
🚨 *Mata Garuda Redis Split-Brain*

```

{"level":"WARNING","tag":"redis-split-brain","stream":"garuda:enriched",...}

```

Run manually:
`python3 ~/Desktop/nuzantara/apps/mata-garuda/scripts/check_redis_split_brain.py`
```

## Open questions (deferred)

- **W16 root-cause fix Option A/B/C/D**: still needs Antonello.
- **W17 Telegram alert verification**: dedup logic suppressed re-send
  in smoke (state file already had both combos from W16 manual run).
  First fire of TRUE NEW combo will be needed to verify Telegram
  end-to-end. To force-test: `rm
~/.agent/decisions/matagaruda-split-brain-last.txt` then kickstart.
- **Cron-of-crons risk**: 30min cadence + ~2s execution = negligible
  CPU. Telegram quota: max 6 messages every 4h even worst case.
- **W18 candidate**: bring same wire-to-cron treatment to any other
  diagnostics that exist but lack launchd (audit needed).
- **W13/W14/W15 deferred items**: still open.
- **Wave 17-commit branch PR readiness**: noted (17 commits accumulated).

## Sources

1. W16 cicatrix (commit `542bb2f19`) — open question §3
2. W10 cicatrix pattern reference
   (`~/scripts/matagaruda-consumer-lag-check.sh`)
3. Empirical kickstart 2026-05-22 12:12 WITA — stderr 501B, exit=1
4. Empirical Telegram suppression: 2nd wrapper run produced 0 new
   Telegram messages (state file already had both combos)
