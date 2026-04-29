# kakuro-S4 — P0-3 LaunchAgents audit + auto-restart compliance

> Single-file prompt for one Claude Code Max x20 session.
> Macchina: **Pro** (`nuzantara@Nuzantara`). Worktree: `wt/p0-3-launchagents`.
> Session command: in your tmux pane, simply type:
>
>     leggi kakuro-S4 e esegui

---

## Mission

Implementa **P0-3** dal piano audit zero-crash 2026-04-29: mass audit dei 53 LaunchAgents Pro per enforce VADEMECUM §11 (KeepAlive=true sui daemon, EnvironmentVariables sempre, log fuori da `/tmp/`). Aggiungi PreToolUse hook per regression prevention.

**Tempo stimato: 3-4h.**

## Context

- Repo: `/Users/nuzantara/Desktop/nuzantara`, branch `main`
- Brainstorm dedicato (READ FIRST): [`11_brainstorms/P0-3_launchagents_audit.md`](../../11_brainstorms/P0-3_launchagents_audit.md)
- Cicatrice STRUCTURAL aperta: `.claude/rules/cicatrix-scars.md` — entry "53 LaunchAgents Pro, only 7 (13%) have KeepAlive=true (2026-04-29)"
- Codex empirical findings (audit master): 53 plist totali, 7 KeepAlive=true, 11 senza KeepAlive del tutto, 5 senza EnvironmentVariables, 6 logano in `/tmp/`

## Files to touch

1. `scripts/lint_launchagents.sh` (NEW) — VADEMECUM §11 enforcer
2. `scripts/patch_launchagents.sh` (NEW) — auto-fixer with --dry-run
3. `scripts/sync_job_registry.py` (NEW) — registry sync helper
4. `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist` — 53 plist (mass patch)
5. `~/.claude/settings.json` — add PreToolUse hook
6. `~/.agent/decisions/job_registry.json` — add daemon entries

## Files NOT to touch

- Plist NOT prefixed `com.{nuzantara,balizero,cell}` (those are user/system plist, off-scope)
- `.claude/rules/cicatrix-scars.md` (will be updated automatically by audit verify scripts)

## Workflow

### Phase 1 — Cross-LLM brainstorm

```bash
cd /Users/nuzantara/Desktop/nuzantara
source docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

cat > /tmp/kakuro-S4-brief.txt <<'BRIEF'
You are giving an independent strategy for auditing macOS LaunchAgents.

CONTEXT: Pro Mac has 53 plist files in ~/Library/LaunchAgents/ matching
com.{nuzantara,balizero,cell}.*.plist. Empirical scan shows:
- 7/53 (13%) have <key>KeepAlive</key><true/>
- 11/53 (21%) have NO KeepAlive directive at all
- 5/53 (9%) missing <key>EnvironmentVariables</key>
- 6/53 (11%) logging StandardOutPath/StandardErrorPath to /tmp/
  (lost on reboot, breaks Sentinel which reads ~/logs/)

VADEMECUM §11 rules:
- Daemon (no schedule directive) must have KeepAlive=true
- Cron-style (StartInterval or StartCalendarInterval set) must have KeepAlive=false explicit
- All plist must have EnvironmentVariables (PATH minimum, HOME recommended)
- Logs must go to ~/logs/, NEVER /tmp/
- Each daemon entry should be in ~/.agent/decisions/job_registry.json

EXAMPLES:
- com.cell.organism.plist → DAEMON (no schedule = KeepAlive=true)
- com.balizero.intel.nightly → CRON (StartCalendarInterval set = KeepAlive=false)
- com.balizero.nlm-bridge → DAEMON (no schedule = KeepAlive=true)
- com.balizero.indexing-sweep → CRON (likely StartCalendarInterval daily)

YOUR TASK: Propose:
1. Bash script lint_launchagents.sh that detects all violations and exits non-zero
   - Use plutil to read keys (handles binary plist transparently)
   - Classify daemon vs cron based on presence of StartInterval/StartCalendarInterval
   - Report each violation with the specific rule violated
2. Bash script patch_launchagents.sh --dry-run|--apply that auto-fixes:
   - Add KeepAlive=true to daemon plist missing it
   - Add EnvironmentVariables (PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:~/.pyenv/...)
   - Add HOME=$HOME
   - Replace /tmp/ log paths with ~/logs/
   - Backup each plist as .pre-vademecum-audit
   - launchctl unload && load to apply
3. PreToolUse hook in ~/.claude/settings.json that runs lint on plist edits
4. Edge cases:
   - RunAtLoad=true + no schedule → ambiguous (daemon? one-shot?). How to decide?
   - Plist with KeepAlive as conditional dict (e.g. NetworkState=true) — keep or simplify?
   - Plist that's actually disabled (Disabled=true in plist or in launchctl override) — skip lint?
5. Test plan to verify a daemon actually respawns after kill -9

CONSTRAINTS:
- macOS launchd-only (no systemd)
- plutil command available (no third-party tool)
- launchctl load/unload required after edit
- ~/.agent/decisions/job_registry.json schema documented in VADEMECUM §11
BRIEF

mkdir -p /tmp/kakuro-S4-brainstorms
coord_brainstorm "P0-3 LaunchAgents audit strategy" /tmp/kakuro-S4-brief.txt /tmp/kakuro-S4-brainstorms

for llm in codex gemini deepseek notebooklm; do
    echo "=== $llm ==="; head -150 /tmp/kakuro-S4-brainstorms/$llm.md
done
```

Synthesize. Particularly attentive to:
- How each LLM handles ambiguous `RunAtLoad=true + no schedule` case
- Whether anyone suggests a different daemon-vs-cron heuristic
- Edge case for conditional KeepAlive dict

### Phase 2 — Worktree

```bash
cd /Users/nuzantara/Desktop/nuzantara
git fetch origin
git worktree add -b feat/p0-3-launchagents ../nuzantara-wt/p0-3 origin/main
cd ../nuzantara-wt/p0-3
mkdir -p ~/logs  # ensure logs dir exists
```

### Phase 3 — Implement lint script

`scripts/lint_launchagents.sh`:

```bash
#!/usr/bin/env bash
# Lint all project LaunchAgents against VADEMECUM §11.
# Exit code = number of violations found.

set -u
PLIST_DIR="$HOME/Library/LaunchAgents"
VIOLATIONS=0

shopt -s nullglob
for plist in "$PLIST_DIR"/com.nuzantara.*.plist \
             "$PLIST_DIR"/com.balizero.*.plist \
             "$PLIST_DIR"/com.cell.*.plist; do
    label=$(plutil -extract Label raw -- "$plist" 2>/dev/null || echo "$(basename "$plist" .plist)")

    # Detect schedule presence
    has_interval=""
    has_calendar=""
    plutil -extract StartInterval raw -- "$plist" >/dev/null 2>&1 && has_interval=1
    plutil -extract StartCalendarInterval json -- "$plist" >/dev/null 2>&1 && has_calendar=1

    is_cron=false
    [ -n "$has_interval" ] || [ -n "$has_calendar" ] && is_cron=true

    # Detect KeepAlive
    has_keepalive_true=$(plutil -extract KeepAlive raw -- "$plist" 2>/dev/null || echo "")

    # Daemon must have KeepAlive=true
    if ! $is_cron; then
        if [ "$has_keepalive_true" != "true" ]; then
            echo "[VIOLATION] $label: daemon (no schedule) requires KeepAlive=true (got: '$has_keepalive_true')"
            ((VIOLATIONS++))
        fi
    fi

    # All must have EnvironmentVariables
    if ! plutil -extract EnvironmentVariables json -- "$plist" >/dev/null 2>&1; then
        echo "[VIOLATION] $label: missing EnvironmentVariables (PATH+HOME mandatory per VADEMECUM §11)"
        ((VIOLATIONS++))
    fi

    # Logs must NOT be in /tmp/
    out=$(plutil -extract StandardOutPath raw -- "$plist" 2>/dev/null || echo "")
    err=$(plutil -extract StandardErrorPath raw -- "$plist" 2>/dev/null || echo "")
    if [[ "$out" == /tmp/* ]] || [[ "$err" == /tmp/* ]]; then
        echo "[VIOLATION] $label: logs to /tmp/ (out=$out err=$err) — must use ~/logs/"
        ((VIOLATIONS++))
    fi

    # Daemon must be in job_registry.json
    if ! $is_cron && [ -f ~/.agent/decisions/job_registry.json ]; then
        if ! jq -e --arg lbl "$label" '.jobs[$lbl] // .[] | select(. == $lbl)' ~/.agent/decisions/job_registry.json >/dev/null 2>&1; then
            echo "[VIOLATION] $label: daemon not in ~/.agent/decisions/job_registry.json"
            ((VIOLATIONS++))
        fi
    fi
done

echo ""
echo "Total violations: $VIOLATIONS"
exit $((VIOLATIONS > 255 ? 255 : VIOLATIONS))
```

### Phase 4 — Implement patch script

`scripts/patch_launchagents.sh` — see brainstorm Phase 1 synthesis. Key features:
- `--dry-run` mode prints proposed changes without applying
- `--apply` actually patches
- Backup `.pre-vademecum-audit` per plist
- launchctl unload + load after each apply

### Phase 5 — Run lint to baseline

```bash
bash scripts/lint_launchagents.sh 2>&1 | tee /tmp/p0-3-lint-before.txt
# Expected: ~22 violations total (per Codex empirical)
```

### Phase 6 — Run patch dry-run

```bash
bash scripts/patch_launchagents.sh --dry-run 2>&1 | tee /tmp/p0-3-patch-dryrun.txt
# Review every proposed change
```

**REVIEW CHECKPOINT:** Before applying, verify the dry-run output. For each plist proposed change:
- Daemon classification correct? (look for `RunAtLoad=true + no schedule + has Program` → likely daemon)
- KeepAlive=true added only to daemons?
- EnvironmentVariables addition uses correct PATH for Pro?
- Log path rewrite from /tmp/ to ~/logs/ preserves filename?

If anything looks wrong, fix `patch_launchagents.sh` and re-run dry-run.

### Phase 7 — Apply patches

```bash
bash scripts/patch_launchagents.sh --apply 2>&1 | tee /tmp/p0-3-patch-apply.txt
# Each plist: backup, edit, launchctl unload, launchctl load
```

### Phase 8 — Verify lint passes now

```bash
bash scripts/lint_launchagents.sh 2>&1 | tee /tmp/p0-3-lint-after.txt
# Expected: Total violations: 0
```

If non-zero violations remain, those are likely ambiguous cases (RunAtLoad+no schedule). Manual classification required:

```bash
diff /tmp/p0-3-lint-before.txt /tmp/p0-3-lint-after.txt
```

### Phase 9 — Test daemon respawn (critical functional verification)

Pick a daemon that was patched (e.g. com.cell.organism if it was missing KeepAlive):

```bash
PID_BEFORE=$(launchctl list com.cell.organism 2>/dev/null | jq -r .PID 2>/dev/null || echo "0")
[ "$PID_BEFORE" = "0" ] && echo "WARN: com.cell.organism not running" || echo "Cell PID before: $PID_BEFORE"

kill -9 $PID_BEFORE
sleep 15
PID_AFTER=$(launchctl list com.cell.organism 2>/dev/null | jq -r .PID 2>/dev/null || echo "0")
echo "Cell PID after: $PID_AFTER"

if [ "$PID_AFTER" != "0" ] && [ "$PID_AFTER" != "$PID_BEFORE" ]; then
    echo "PASS: launchd auto-respawned Cell (PID $PID_BEFORE → $PID_AFTER)"
else
    echo "FAIL: launchd did NOT auto-respawn (KeepAlive=true patch ineffective?)"
fi
```

### Phase 10 — Implement sync_job_registry.py

`scripts/sync_job_registry.py`:

```python
"""Sync ~/.agent/decisions/job_registry.json with current LaunchAgents.

Adds entries for daemon plist not yet registered.
Verifies existing entries point to existing plist.
"""

import json
import subprocess
from pathlib import Path

REGISTRY = Path.home() / ".agent/decisions/job_registry.json"
PLIST_DIR = Path.home() / "Library/LaunchAgents"


def get_label(plist_path: Path) -> str:
    return subprocess.check_output(
        ["plutil", "-extract", "Label", "raw", "--", str(plist_path)]
    ).decode().strip()


def is_daemon(plist_path: Path) -> bool:
    """Daemon = no schedule directive."""
    has_interval = subprocess.run(
        ["plutil", "-extract", "StartInterval", "raw", "--", str(plist_path)],
        capture_output=True
    ).returncode == 0
    has_calendar = subprocess.run(
        ["plutil", "-extract", "StartCalendarInterval", "json", "--", str(plist_path)],
        capture_output=True
    ).returncode == 0
    return not (has_interval or has_calendar)


def main():
    reg = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"jobs": {}}

    for plist in sorted(PLIST_DIR.glob("com.{nuzantara,balizero,cell}.*.plist")):
        try:
            label = get_label(plist)
        except subprocess.CalledProcessError:
            continue

        if label not in reg["jobs"]:
            reg["jobs"][label] = {
                "host": "pro",
                "type": "launchagent",
                "plist": str(plist),
                "schedule_seconds": None if is_daemon(plist) else "from-plist",
                "staleness_threshold_s": 600 if is_daemon(plist) else 86400,
                "restart_cmd": f"launchctl kickstart -k gui/$(id -u)/{label}",
                "repair_scope": "self_repair",
                "critical": False  # owner adjusts
            }
            print(f"+ added {label}")

    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=2))
    print(f"Registry updated: {len(reg['jobs'])} total jobs")


if __name__ == "__main__":
    main()
```

```bash
python3 scripts/sync_job_registry.py
# Output: + added com.cell.organism, + added com.balizero.nlm-bridge, ...
```

### Phase 11 — Add PreToolUse hook

Read `~/.claude/settings.json`, add hook to `hooks` array:

```json
{
  "hooks": [
    {
      "matcher": "Edit|Write",
      "matcher_args": ["**/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist"],
      "type": "command",
      "command": "bash /Users/nuzantara/Desktop/nuzantara/scripts/lint_launchagents.sh"
    }
  ]
}
```

This runs lint before any future edit/write to project plist.

### Phase 12 — Commit + Push (COORDINATED)

**Note:** Plist files in `~/Library/LaunchAgents/` are NOT in the repo. We commit only the scripts. The plist changes are local-only on Pro (Air has different plist).

```bash
source /Users/nuzantara/Desktop/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

cd /Users/nuzantara/Desktop/nuzantara-wt/p0-3

git add scripts/lint_launchagents.sh
git add scripts/patch_launchagents.sh
git add scripts/sync_job_registry.py

# Optional: docs update if you want to record the count change
# git add docs/audits/2026-04-29-zero-crash-audit/_p0-3_completion_log.md (if you create one)

coord_commit "fix(p0-3): LaunchAgents VADEMECUM §11 enforcer + auto-patcher

P0-3 from zero-crash audit 2026-04-29.

- scripts/lint_launchagents.sh: validates all com.{nuzantara,balizero,cell}.*.plist
  against VADEMECUM §11 rules (KeepAlive=true on daemons, EnvironmentVariables
  mandatory, no /tmp/ logs, registry sync). Exit code = violations count.
- scripts/patch_launchagents.sh --dry-run|--apply: auto-fixes violations.
  Backs up each plist as .pre-vademecum-audit. Reloads via launchctl.
- scripts/sync_job_registry.py: ensures ~/.agent/decisions/job_registry.json
  has entries for all daemon plist (so Sentinel monitors them).

Pro audit results (post-apply):
- LaunchAgents project: 53
- KeepAlive=true (daemons only): 7 → ~25 (proper classification)
- Missing EnvironmentVariables: 5 → 0
- Logging to /tmp/: 6 → 0
- Daemon respawn verified via kill -9 + launchctl list

Pre-vademecum-audit backups in ~/Library/LaunchAgents/.

Cicatrix STRUCTURAL 2026-04-29 P0-3 resolved (Pro side).
Air-side audit pending separate session (different plist set)."

coord_push origin feat/p0-3-launchagents

gh pr create \
  --title "fix(p0-3): LaunchAgents VADEMECUM §11 enforcer + Pro auto-patch" \
  --body "Resolves cicatrix STRUCTURAL 2026-04-29 P0-3 (Pro side).

## Summary
- 3 new scripts (lint, patch, registry sync)
- Pro 53 plist patched: 22 violations → 0
- Daemon respawn verified end-to-end
- ~/.claude/settings.json PreToolUse hook prevents regression

## Test plan
- [x] lint_launchagents.sh exits 0 on Pro
- [x] kill -9 daemon → respawn within 15s
- [x] sync_job_registry.py adds missing daemon entries
- [ ] PreToolUse hook fires on next plist edit

Air-side audit (different plist set) pending separate session.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

gh pr merge --auto --squash

# No fly deploy needed — this is local Pro infra. The scripts get into repo,
# the plist changes are local-only.

PR_NUMBER=$(gh pr view --json number -q .number)
~/.claude/scripts/mem save decision "P0-3 LaunchAgents audit Pro completed — PR #$PR_NUMBER. lint+patch scripts committed. 22 violations → 0 on Pro. Daemon respawn verified. Hook prevents regression. Air audit deferred. Cicatrix STRUCTURAL 2026-04-29 P0-3 resolved (Pro)." 9
```

### Phase 13 — Cleanup

```bash
cd /Users/nuzantara/Desktop/nuzantara
git worktree remove ../nuzantara-wt/p0-3
```

## Reporting

```
[kakuro-S4 DONE] P0-3 merged in PR #<num>.
Pro 53 LaunchAgents audited: 22 violations → 0.
KeepAlive=true daemons: 7 → ~25 (proper classification).
Missing EnvironmentVariables: 5 → 0.
/tmp/ logs: 6 → 0.
Daemon respawn verified (kill -9 + launchctl auto-restart within 15s).
3 new scripts: lint_launchagents.sh, patch_launchagents.sh, sync_job_registry.py.
PreToolUse hook prevents regression.
Cicatrix STRUCTURAL 2026-04-29 P0-3 resolved (Pro).
Air-side TODO: separate session (different plist set).
Brainstorms saved in /tmp/kakuro-S4-brainstorms.
```

## Failure modes

- **Daemon does NOT respawn after kill -9**: KeepAlive=true didn't take. Check plutil read on plist after patch. Possible cause: launchctl unload failed silently. Force reload: `launchctl bootout gui/$(id -u)/LABEL && launchctl bootstrap gui/$(id -u) PLIST_PATH`.
- **patch_launchagents.sh --apply breaks a critical daemon**: backups in `.pre-vademecum-audit`. Restore: `cp PLIST.pre-vademecum-audit PLIST && launchctl unload PLIST && launchctl load PLIST`.
- **Ambiguous plist (RunAtLoad+no schedule)**: skip auto-classification. List them in commit message. Owner reviews each separately.
- **Coord lock stuck**: standard `coord_status` + manual break.

## Autonomy boundary

L2 autonomous EXCEPT for:
- Critical daemon (com.cell.organism, com.balizero.nlm-bridge, com.balizero.post-publish-poller) breaks after patch → revert to backup, escalate to Zero
- Ambiguous classification → log, leave unchanged, document for follow-up
