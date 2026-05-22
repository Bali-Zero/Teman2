---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W19 eliminate nlm-feeder error.log shell-init noise via TCC-safe wrapper
sources: 4
---

# W19: nlm-feeder-stream wrapper rebuild — TCC-safe, zero shell-init noise

## Context

Loop iteration 19 survey of cron error logs revealed
`matagaruda-nlm-feeder-stream.error.log` at **842 lines / 100KB**, the
biggest by far among Mata Garuda launchd error streams. Every line was
the same pair:

```
shell-init: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
job-working-directory: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
```

**100% noise, zero actionable signal** across ~3 weeks of hourly runs.

## Root cause

`com.matagaruda.nlm-feeder-stream.hourly.plist` used:

```xml
<key>ProgramArguments</key>
<array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda && source ~/.nuzantara-secrets.env 2>/dev/null; .venv/bin/python scripts/run_nlm_feeder_stream.py >> ...</string>
</array>
```

The `-l` flag makes zsh sources `.zshrc` (login profile). The zshrc
contains sub-shell commands (likely a prompt-rendering or pyenv hook)
that call `pwd` on parent directories. Under launchd's sandbox, parent
dirs of `~/Desktop/...` aren't readable (TCC permission denied) →
EPERM printed by every sub-command initialization.

Same scar family as 2026-05-06 cicatrix lessons_ssh_path_audit.md ("ssh
PATH minimale") and the historic launchd zsh EPERM episodes — workers
running under launchd should NEVER use `zsh -l`.

## Comparison to recently-shipped wrappers (W10, W17)

Both `matagaruda-consumer-lag-check.sh` (W10) and
`matagaruda-redis-split-brain-check.sh` (W17) use TCC-safe pattern:

- `#!/bin/zsh` shebang (no `-l`)
- Explicit `PATH=...:$PATH` export
- `if [ -f ~/.nuzantara-secrets.env ]; then set -a; . ...; set +a; fi`
- venv python invoked directly (`$VENV_PY entry.py`)

Their error logs: **0 lines of noise** despite running every 30min for
days. Definitive proof the pattern works.

## Fix shipped

### Wrapper `~/scripts/matagaruda-nlm-feeder-stream.sh` (~50 lines)

```bash
#!/bin/zsh
set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

REPO_ROOT="${REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"
APP_ROOT="$REPO_ROOT/apps/mata-garuda"
VENV_PY="$APP_ROOT/.venv/bin/python"
ENTRY="$APP_ROOT/scripts/run_nlm_feeder_stream.py"
LOG="$HOME/logs/matagaruda-nlm-feeder-stream.log"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    . "$HOME/.nuzantara-secrets.env"
    set +a
fi

export GARUDA_REDIS_HOST="${GARUDA_REDIS_HOST:-100.93.236.6}"

[ -x "$VENV_PY" ] || { echo "[ERROR] venv python missing: $VENV_PY" >&2; exit 2; }
[ -f "$ENTRY" ] || { echo "[ERROR] entry script missing: $ENTRY" >&2; exit 2; }

cd "$APP_ROOT"
exec "$VENV_PY" "$ENTRY" >> "$LOG" 2>&1
```

### Plist rebuild

`ProgramArguments` reduced to a single wrapper invocation. All env
state moved into `EnvironmentVariables`. Defense-in-depth: GARUDA_REDIS_HOST
set in BOTH plist and wrapper (Tailscale 100.93.236.6, fix from
2026-05-06 cicatrix Pro<->Mini Redis split-brain).

Old plist archived to `~/Library/LaunchAgents/.archive-2026-05-22/com.matagaruda.nlm-feeder-stream.hourly.plist.pre-w19`.

## Verification (2026-05-22 23:30 WITA)

```bash
$ launchctl bootout "gui/$(id -u)/com.matagaruda.nlm-feeder-stream.hourly"
$ launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.matagaruda.nlm-feeder-stream.hourly.plist
$ > ~/logs/matagaruda-nlm-feeder-stream.error.log
$ launchctl kickstart -k "gui/$(id -u)/com.matagaruda.nlm-feeder-stream.hourly"
$ sleep 30
$ wc -l ~/logs/matagaruda-nlm-feeder-stream.error.log
       0
$ launchctl print "gui/$(id -u)/com.matagaruda.nlm-feeder-stream.hourly" | grep "last exit"
        last exit code = 0
$ tail -1 ~/logs/matagaruda-nlm-feeder-stream.log
{"agent": "nlm_feeder_stream", "alerts": {"processed": 0, "fed": 0, "skipped": 0, "errors": 0}, "enriched": {"processed": 0, "fed": 0, "skipped": 0, "errors": 0}}
```

842 lines of noise → 0. Clean exit code. Python runs successfully.

## Open questions (deferred — out of scope for W19)

- `processed=0, fed=0` is the EXISTING split-brain behavior documented
  in W16 cicatrix (Pro hosts intel_scraper writes, Mini hosts feeder
  reader). W19 only de-noises the error log — the productivity gap
  remains until Antonello chooses Option A/B/C/D from W16.
- Other Mata Garuda plists may still use `zsh -lc`. Survey suggests:
  - `com.matagaruda.watcher.daily.plist` — already TCC-safe per CLAUDE.md §6
  - `com.matagaruda.nlm-expander.weekly.plist` — TBD W20 candidate
  - `com.matagaruda.sentinel.*.plist` — TBD audit
- No regression: lag dashboard probes Mini Redis identically post-fix.

## Sources

1. Empirical 842-line error.log audit 2026-05-22 23:20 WITA
2. W10 `matagaruda-consumer-lag-check.sh` reference template
3. W17 `matagaruda-redis-split-brain-check.sh` reference template
4. W7+CLAUDE.md §6 "TCC note" — venv python direct under launchd
