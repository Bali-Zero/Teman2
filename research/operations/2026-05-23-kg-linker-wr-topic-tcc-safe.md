---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W20 TCC-safe wrappers for kg-linker + wr-topic (W19 follow-up)
sources: 4
---

# W20: kg-linker + wr-topic plists — TCC-safe wrapper rebuild + generic template

## Context

Loop iteration 20 survey of cron error logs (W19 follow-up) flagged
TWO more matagaruda plists using `/bin/bash -lc` with similar TCC
pollution:

- `~/logs/matagaruda-kg-linker.error.log`: **73 lines** of `/bin/bash:
.venv/bin/activate: Operation not permitted` over hourly runs
- `~/logs/matagaruda-wr-topic.error.log`: **2 lines** of the same
  (twice-weekly schedule, less accumulation)

Both plists used `/bin/bash -lc "set -a; source secrets.env; set +a;
export PATH=...; cd .../mata-garuda && .venv/bin/python entry.py >> ..."`.
The `-l` flag sources `.bashrc`/`.profile` which contains an attempt to
`source .venv/bin/activate` from CWD before the explicit `cd`. Under
launchd's TCC sandbox: EPERM on the relative path → 75 lines false-noise.

Python ran successfully (`last exit code = 0`, both crons emit
healthy JSON output to stdout). But W8 violation: non-actionable
noise routed to .error.log masks real errors.

## Generic wrapper (refactored from W19 single-purpose)

W19 shipped `~/scripts/matagaruda-nlm-feeder-stream.sh` (single
purpose). W20 introduces `~/scripts/matagaruda-cron-tcc-safe.sh`
that accepts entry script + log label as args:

```bash
#!/bin/zsh
# Usage: matagaruda-cron-tcc-safe.sh <entry_script_abs_path> [log_label]
set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

ENTRY="$1"
LABEL="${2:-$(basename "$ENTRY" .py)}"

REPO_ROOT="${REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"
APP_ROOT="$REPO_ROOT/apps/mata-garuda"
VENV_PY="$APP_ROOT/.venv/bin/python"
LOG="$HOME/logs/matagaruda-${LABEL}.log"

[ -f "$HOME/.nuzantara-secrets.env" ] && {
    set -a; . "$HOME/.nuzantara-secrets.env"; set +a;
}

export GARUDA_REDIS_HOST="${GARUDA_REDIS_HOST:-100.93.236.6}"
export PYTHONPATH="${PYTHONPATH:-$APP_ROOT}"

[ -x "$VENV_PY" ] || { echo "[ERROR] venv python missing" >&2; exit 2; }
[ -f "$ENTRY" ] || { echo "[ERROR] entry script missing" >&2; exit 2; }

cd "$APP_ROOT"
exec "$VENV_PY" "$ENTRY" >> "$LOG" 2>&1
```

Future cron migrations reuse this template — only the plist
ProgramArguments needs to change. Reduces W21+ work surface
significantly.

## Plist rebuilds

Both plists now use the same shape:

```xml
<key>ProgramArguments</key>
<array>
    <string>/Users/nuzantara/scripts/matagaruda-cron-tcc-safe.sh</string>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_kg_linker.py</string>
    <string>kg-linker</string>  <!-- log label -->
</array>
```

vs old:

```xml
<key>ProgramArguments</key>
<array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>set -a; ...; cd .../mata-garuda &amp;&amp; .venv/bin/python ...</string>
</array>
```

Old plists archived under `~/Library/LaunchAgents/.archive-2026-05-22/`
with `.pre-w20` suffix.

## Empirical verification

```bash
# Truncate + reload + kickstart both
$ > ~/logs/matagaruda-kg-linker.error.log
$ > ~/logs/matagaruda-wr-topic.error.log
$ launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.matagaruda.{kg-linker,wr-topic}.plist
$ launchctl kickstart -k "gui/$(id -u)/com.matagaruda.kg-linker"
$ launchctl kickstart -k "gui/$(id -u)/com.matagaruda.wr-topic"

# Wait for completion (kg-linker runs ~60s)
$ launchctl print "gui/$(id -u)/com.matagaruda.kg-linker" | grep "last exit"
        last exit code = 0
$ launchctl print "gui/$(id -u)/com.matagaruda.wr-topic" | grep "last exit"
        last exit code = 0

# Verify zero noise
$ wc -l ~/logs/matagaruda-kg-linker.error.log
       0
$ wc -l ~/logs/matagaruda-wr-topic.error.log
       0
```

75 lines of false-noise → 0. Clean exit on both. Existing functionality
preserved (kg-linker still emits kg_observations 956; wr-topic still
emits candidates/chars/tg_ok JSON).

## Remaining plist candidates (W21+ survey)

Other matagaruda plists with `/bin/zsh -lc` or `/bin/bash -lc`:

- `com.matagaruda.daily-briefing.plist`
- `com.matagaruda.kita-feed.daily.plist`
- `com.matagaruda.nlm-expander.weekly.plist`
- `com.matagaruda.public-channel.plist`
- `com.matagaruda.reg-alert.30min.plist`
- `com.matagaruda.sentinel.hourly.plist`
- `com.matagaruda.weekly-digest.plist`
- `com.matagaruda.wr2-bridge.hourly.plist`

Plus balizero/\* plists. Survey before migration: check the .error.log
size first — small files may have legitimate WARN/ERROR signal that
shouldn't be touched. Generic wrapper handles all uniformly.

## Sources

1. W19 nlm-feeder-stream cicatrix (commit `35896d406`) — reference
   pattern, single-purpose wrapper
2. W8 cicatrix outbox-drain stderr noise — same anti-pattern (W19+W20
   both fix instances of it)
3. CLAUDE.md §6 mata-garuda TCC note — venv python direct under launchd
4. Empirical kickstart 2026-05-22 23:58 WITA — 0 lines error.log,
   exit code 0 both crons
