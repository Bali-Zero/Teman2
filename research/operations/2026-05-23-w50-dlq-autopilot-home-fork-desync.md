---
date: 2026-05-23
domain: operations
loop: NB-automations-hardening W50
status: shipped (commit dfdfe3607); daemon reloaded; verification pending next cron tick (~30min)
---

# W50 — `dlq_autopilot` wrapper exec'd HOME fork instead of repo copy

## TL;DR

`docs/infra/launchagents/launch_dlq_autopilot.sh` exec'd `$HOME/scripts/dlq_autopilot.py`
(a stale May-11 fork) instead of `$HOME/Desktop/nuzantara/scripts/dlq_autopilot.py` (repo
copy with 2026-05-19 ops-hardening fix). Production ran stale code 4 days post-fix.
9500+ INFO lines/day still polluting `dlq_autopilot.error.log`. Fix: wrapper now exec's
REPO copy with existence check.

## Empirical evidence

```
$ ls -la ~/scripts/dlq_autopilot.py /Users/nuzantara/Desktop/nuzantara/scripts/dlq_autopilot.py
-rwxr-xr-x  ... 27103 May 19 21:49 /Users/nuzantara/Desktop/nuzantara/scripts/dlq_autopilot.py
-rwxr-xr-x  ... 28905 May 11 19:06 /Users/nuzantara/scripts/dlq_autopilot.py
$ diff -q ~/scripts/dlq_autopilot.py ~/Desktop/nuzantara/scripts/dlq_autopilot.py
Files differ
$ grep -n "StreamHandler" ~/scripts/dlq_autopilot.py
29:        logging.StreamHandler(),         # ← stale, routes to stderr
$ grep -n "StreamHandler" ~/Desktop/nuzantara/scripts/dlq_autopilot.py
31:        logging.StreamHandler(sys.stdout),  # ← fix
```

Repo `scripts/dlq_autopilot.py:25-31` contains its own cicatrix comment:

```python
# ops-hardening fix 2026-05-19: explicit sys.stdout.
# Default StreamHandler() routes to sys.stderr, which sent
# 62 INFO "status=TERMINAL — skipping" lines per run to
# the plist StandardErrorPath (12.7 MB/day error.log).
logging.StreamHandler(sys.stdout),
```

But production never picked it up because the wrapper exec'd the wrong file.

## Empirical impact

```
$ ls -la ~/logs/dlq_autopilot.error.log
-rw-r--r--  1 nuzantara  staff  1615969 May 23 15:11 ...
$ wc -l ~/logs/dlq_autopilot.error.log
13378
$ awk '/^\[DLQAutopilot 1[0-5]:|^\[DLQAutopilot 0[0-9]:/' ~/logs/dlq_autopilot.error.log | wc -l
9500
```

9500 lines today (71% of lifetime accumulation), all INFO-level "status=TERMINAL — skipping"
for the same 63 dead jobs. Cron runs every 30min (StartInterval=1800), so ~63 jobs × ~48
runs/day ≈ 3024 lines/day expected; actual 9500 suggests run frequency higher OR job count
bigger over the day.

## Root cause

Classic deploy-path desync:

1. May 11: `~/scripts/dlq_autopilot.py` was the canonical script. Wrapper at
   `docs/infra/launchagents/launch_dlq_autopilot.sh:17` hardcoded that path.
2. May 19: ops-hardening wave moved script ownership into repo at
   `~/Desktop/nuzantara/scripts/dlq_autopilot.py`, added the StreamHandler fix.
3. Wrapper was never updated. HOME copy was never deleted, never sync'd.
4. Production silently kept running May-11 code from May 19 onwards.

The fix HAD landed in repo and tests would have validated it — but the runtime never saw
that code path because the wrapper boundary was the silent SSOT.

## Fix shipped

`docs/infra/launchagents/launch_dlq_autopilot.sh` (commit `dfdfe3607`):

```bash
REPO_DIR="$HOME/Desktop/nuzantara"
SCRIPT="$REPO_DIR/scripts/dlq_autopilot.py"

if [ ! -f "$SCRIPT" ]; then
    echo "FATAL: Missing $SCRIPT (repo path)" >&2
    exit 1
fi

export PATH="..."
exec "$HOME/.pyenv/versions/3.11.11/bin/python3" "$SCRIPT"
```

Daemon reloaded via `launchctl bootout/bootstrap` immediately post-commit. Next cron tick
(~30min from reload) will run REPO code.

## Verification plan

**Behavioral (next 30min)**:

```bash
ls -la ~/logs/dlq_autopilot.error.log  # baseline byte count
# wait 35min
ls -la ~/logs/dlq_autopilot.error.log  # should grow MUCH less or zero
```

Expected: zero new INFO "status=TERMINAL — skipping" lines in `.error.log` post-reload.
WARNING lines (e.g. `max attempts reached → TERMINAL` first-time promotion) may still
appear and are legitimate.

**Strong signal (next 24h)**:

```
grep -c "status=TERMINAL — skipping" ~/logs/dlq_autopilot.error.log
# Pre-W50: ~9500/day
# Post-W50: should freeze at lifetime count, no new ones
```

## Deferred W51+ candidates

1. **HOME fork cleanup**: `~/scripts/dlq_autopilot.py` should be DELETED to prevent
   accidental future drift. Risk: any other script importing it would break. Audit before
   deletion.
2. **Audit all other wrappers in `docs/infra/launchagents/*.sh`** for the same pattern
   (exec'ing HOME copies). Grep `\$HOME/scripts/` in wrapper dir = candidates.
3. **CI lint**: detect wrapper scripts that exec paths outside `$HOME/Desktop/nuzantara/`.
   Generalize wrapper boundary as SSOT enforcement.

## Lessons

- **Wrapper scripts are silent SSOT for deploy path**. Repo CI tests are meaningless if the
  wrapper never executes the tested code. Always verify wrapper boundary at PR review.
- **HOME forks are legacy**. Pre-Repo era of script hosting (~/scripts/ as canonical) is
  obsolete; any HOME copy of a repo script is technical debt to be either deleted or
  symlinked.
- **Log file naming lies**: `.error.log` is just where stderr goes. Default
  `logging.StreamHandler()` routes to stderr regardless of severity. INFO can flood
  `.error.log` if not explicitly routed to stdout.
- **Existence check in wrapper is cheap defense-in-depth**: a malformed REPO_DIR or
  missing script now produces clean FATAL with explicit message instead of cryptic
  `bash: line 1: ... : command not found`.
- **Family**: deploy-path desync. Future watch for: any LaunchAgent wrapper hardcoding
  `$HOME/scripts/` or other paths outside the repo SSOT.

## Reference

- Commit: `dfdfe3607`
- File: `docs/infra/launchagents/launch_dlq_autopilot.sh`
- Repo script (now exec'd): `scripts/dlq_autopilot.py:25-31` (carries its own self-doc comment)
- Plist: `~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist` (unchanged)
- HOME fork (legacy, candidate for deletion W51+): `~/scripts/dlq_autopilot.py` (May-11)
