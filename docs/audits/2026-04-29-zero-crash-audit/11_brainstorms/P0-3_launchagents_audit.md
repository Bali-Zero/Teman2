# P0-3 Brainstorm — LaunchAgents audit (53 plist, 7 KeepAlive, 5 missing env)

**Goal:** Mass audit of all 53 project LaunchAgents to enforce VADEMECUM §11. Make Cell/Organism and other daemons survive crashes via launchd KeepAlive.
**Effort:** 3-4 hours
**Dependencies:** P0-0 (so we can SEE if KeepAlive=true actually works)

---

## Strategy options

### Option A: Mass automated patch via plutil

Single script that for each plist:
1. Detects daemon-vs-cron based on `<key>StartInterval</key>` presence (cron) vs absence (daemon)
2. Sets `KeepAlive=true` for daemons
3. Adds `EnvironmentVariables` if missing (PATH + HOME minimum)
4. Rewrites StandardOutPath/StandardErrorPath from `/tmp/` to `~/logs/`

**Pros:**
- Fast — one script processes all 53 in ~minutes
- Idempotent — re-run safe
- Auditable — produces a diff per plist

**Cons:**
- Daemon-vs-cron classification heuristic might be wrong for some plist
- Mass change higher risk than incremental

**Effort:** 2 hours including testing.

### Option B: Manual review + patch each plist

Open each plist in editor, decide daemon-vs-cron manually, patch.

**Pros:**
- Zero misclassification risk
- Owner reviews each one

**Cons:**
- 53 × 5 min = ~4 hours
- Risk of human error on tedious task
- Doesn't generate the lint script for future regression prevention

**Effort:** 4-5 hours.

### Option C: Hybrid — script + per-plist confirmation

Script proposes patches, owner accepts/rejects each via prompt.

**Pros:**
- Speed of automation + safety of review
- Catches edge cases

**Cons:**
- Requires interactive session (not L2-friendly)

**Effort:** 3 hours.

**Recommendation:** **Option A** with proper classification heuristic and dry-run mode + git diff review before commit. L2-friendly, fast, regression-proof.

---

## Implementation plan (Option A)

### Step 1: Lint script

```bash
#!/usr/bin/env bash
# File: scripts/lint_launchagents.sh
# Validate all project plist against VADEMECUM §11 requirements.
set -e
PLIST_DIR=~/Library/LaunchAgents
PROJECT_GLOB="com.{nuzantara,balizero,cell}.*.plist"
VIOLATIONS=0

shopt -s nullglob
for plist in "$PLIST_DIR"/com.nuzantara.*.plist "$PLIST_DIR"/com.balizero.*.plist "$PLIST_DIR"/com.cell.*.plist; do
    label=$(plutil -extract Label raw -- "$plist" 2>/dev/null || basename "$plist" .plist)

    # Classify: daemon vs cron-style
    has_interval=$(plutil -extract StartInterval raw -- "$plist" 2>/dev/null || echo "")
    has_calendar=$(plutil -extract StartCalendarInterval json -- "$plist" 2>/dev/null || echo "")
    has_keepalive=$(plutil -extract KeepAlive json -- "$plist" 2>/dev/null || echo "")

    is_cron=false
    [ -n "$has_interval" ] || [ -n "$has_calendar" ] && is_cron=true

    # Daemon must have KeepAlive=true
    if ! $is_cron; then
        if [ -z "$has_keepalive" ]; then
            echo "[VIOLATION] $label: daemon (no schedule) but no KeepAlive directive"
            ((VIOLATIONS++))
        elif [[ "$has_keepalive" != *"true"* ]] && [[ "$has_keepalive" != *"NetworkState"* ]]; then
            echo "[VIOLATION] $label: daemon but KeepAlive is not 'true' or conditional"
            ((VIOLATIONS++))
        fi
    fi

    # All must have EnvironmentVariables (especially PATH and HOME)
    has_env=$(plutil -extract EnvironmentVariables json -- "$plist" 2>/dev/null || echo "")
    if [ -z "$has_env" ]; then
        echo "[VIOLATION] $label: missing EnvironmentVariables (PATH+HOME mandatory per VADEMECUM §11)"
        ((VIOLATIONS++))
    fi

    # Logs must NOT be in /tmp/
    out=$(plutil -extract StandardOutPath raw -- "$plist" 2>/dev/null || echo "")
    err=$(plutil -extract StandardErrorPath raw -- "$plist" 2>/dev/null || echo "")
    if [[ "$out" == /tmp/* ]] || [[ "$err" == /tmp/* ]]; then
        echo "[VIOLATION] $label: logs to /tmp/ (lost on reboot, breaks Sentinel)"
        ((VIOLATIONS++))
    fi

    # Check job_registry.json entry exists for daemons
    if ! $is_cron && [ -f ~/.agent/decisions/job_registry.json ]; then
        registered=$(jq -r --arg label "$label" '.jobs[$label] // empty' ~/.agent/decisions/job_registry.json 2>/dev/null)
        if [ -z "$registered" ]; then
            echo "[VIOLATION] $label: daemon not registered in ~/.agent/decisions/job_registry.json"
            ((VIOLATIONS++))
        fi
    fi
done

echo ""
echo "Total violations: $VIOLATIONS"
[ $VIOLATIONS -gt 0 ] && exit 1 || exit 0
```

### Step 2: Auto-patch script (dry-run capable)

```bash
#!/usr/bin/env bash
# File: scripts/patch_launchagents.sh [--dry-run]
# Auto-fix plist violations per VADEMECUM §11 rules.
set -e
DRY_RUN=false
[ "$1" = "--dry-run" ] && DRY_RUN=true

PLIST_DIR=~/Library/LaunchAgents
LOGS_DIR=~/logs
mkdir -p "$LOGS_DIR"

for plist in "$PLIST_DIR"/com.nuzantara.*.plist "$PLIST_DIR"/com.balizero.*.plist "$PLIST_DIR"/com.cell.*.plist; do
    label=$(plutil -extract Label raw -- "$plist" 2>/dev/null)
    backup="${plist}.pre-vademecum-audit"
    [ -f "$backup" ] || cp "$plist" "$backup"  # one-time backup

    has_interval=$(plutil -extract StartInterval raw -- "$plist" 2>/dev/null || echo "")
    has_calendar=$(plutil -extract StartCalendarInterval json -- "$plist" 2>/dev/null || echo "")
    is_cron=false
    [ -n "$has_interval" ] || [ -n "$has_calendar" ] && is_cron=true

    # 1. Add KeepAlive=true for daemons
    if ! $is_cron; then
        existing=$(plutil -extract KeepAlive json -- "$plist" 2>/dev/null || echo "")
        if [ -z "$existing" ]; then
            cmd="plutil -insert KeepAlive -bool true -- '$plist'"
            $DRY_RUN && echo "[DRY] $label: $cmd" || eval "$cmd" && echo "[PATCHED] $label: KeepAlive=true added"
        fi
    fi

    # 2. Add EnvironmentVariables if missing
    has_env=$(plutil -extract EnvironmentVariables json -- "$plist" 2>/dev/null || echo "")
    if [ -z "$has_env" ]; then
        cmd_env="plutil -insert EnvironmentVariables -dictionary -- '$plist'"
        cmd_path="plutil -insert EnvironmentVariables.PATH -string '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin' -- '$plist'"
        cmd_home="plutil -insert EnvironmentVariables.HOME -string '/Users/nuzantara' -- '$plist'"
        if $DRY_RUN; then
            echo "[DRY] $label: + EnvironmentVariables (PATH, HOME)"
        else
            eval "$cmd_env" && eval "$cmd_path" && eval "$cmd_home"
            echo "[PATCHED] $label: EnvironmentVariables added"
        fi
    fi

    # 3. Rewrite log paths
    for key in StandardOutPath StandardErrorPath; do
        old=$(plutil -extract "$key" raw -- "$plist" 2>/dev/null || echo "")
        if [[ "$old" == /tmp/* ]]; then
            base=$(basename "$old")
            new="$LOGS_DIR/$base"
            cmd="plutil -replace $key -string '$new' -- '$plist'"
            if $DRY_RUN; then
                echo "[DRY] $label: $key $old → $new"
            else
                eval "$cmd"
                echo "[PATCHED] $label: $key → $new"
            fi
        fi
    done

    # 4. Reload plist
    if ! $DRY_RUN; then
        launchctl unload "$plist" 2>/dev/null || true
        launchctl load "$plist"
    fi
done

echo ""
echo "Audit complete. Run lint_launchagents.sh to verify."
```

### Step 3: PreToolUse hook (regression prevention)

Add to `~/.claude/settings.json`:

```json
{
  "hooks": [
    {
      "matcher": "Edit|Write",
      "matcher_args": ["**/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist"],
      "type": "command",
      "command": "bash ~/Desktop/nuzantara/scripts/lint_launchagents.sh"
    }
  ]
}
```

### Step 4: Job registry sync

For each daemon, ensure entry in `~/.agent/decisions/job_registry.json`:

```python
# scripts/sync_job_registry.py
import json
import subprocess
from pathlib import Path

REGISTRY = Path.home() / ".agent/decisions/job_registry.json"
PLIST_DIR = Path.home() / "Library/LaunchAgents"

reg = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"jobs": {}}

for plist in PLIST_DIR.glob("com.{nuzantara,balizero,cell}.*.plist"):
    label = subprocess.check_output(
        ["plutil", "-extract", "Label", "raw", "--", str(plist)]
    ).decode().strip()
    if label not in reg["jobs"]:
        reg["jobs"][label] = {
            "host": "pro",
            "type": "launchagent",
            "plist": str(plist),
            "schedule_seconds": None,  # daemon
            "staleness_threshold_s": 600,  # 10 min
            "restart_cmd": f"launchctl kickstart -k gui/$(id -u)/{label}",
            "repair_scope": "self_repair",
            "critical": False  # owner adjusts
        }

REGISTRY.write_text(json.dumps(reg, indent=2))
```

---

## Special-case plist that need owner attention

After Codex empirical audit, these plist need individual classification (daemon vs one-shot):

- `com.cell.organism.plist` → **DAEMON** — KeepAlive=true required
- `com.balizero.nlm-bridge` → **DAEMON** (cron-launched but stays running)
- `com.balizero.intel.nightly` → **CRON** — KeepAlive=false
- `com.balizero.indexing-sweep` → **CRON** — KeepAlive=false
- `com.balizero.post-publish-poller` → **DAEMON** — KeepAlive=true
- `com.balizero.client-value-predictor` → **CRON** (likely)
- `com.balizero.renewal-alerts` → **CRON**
- `com.balizero.intel-radar-daily-digest` → **CRON**
- `com.balizero.sota.m13-*` → **CRON** (multiple)

The lint script's heuristic (StartInterval/StartCalendarInterval presence = cron) is correct for these. **Special review:** any plist where `RunAtLoad=true` AND no schedule = ambiguous (could be daemon-on-boot or one-shot-on-load).

---

## Dependencies

- **Before:** P0-0 (so when respawned daemon comes up healthy, it's actually visible)
- **After:** Cell sensor for `daemon_keepalive_compliance` (count of plist with KeepAlive=true / total daemons)

## Rollback plan

Each plist has `.pre-vademecum-audit` backup. Restore:

```bash
for backup in ~/Library/LaunchAgents/*.pre-vademecum-audit; do
    plist="${backup%.pre-vademecum-audit}"
    cp "$backup" "$plist"
    launchctl unload "$plist" 2>/dev/null || true
    launchctl load "$plist"
done
```

## L2 autonomy decision

**Auto-implementable: YES** with caveat. Lint script + auto-patch + hook are mechanical. Daemon classification heuristic could misclassify ~5% of plist — recommend running with `--dry-run` first, reviewing diff, then applying.

## Verification

```bash
# 1. Dry run
bash scripts/patch_launchagents.sh --dry-run | tee /tmp/plist_patch_proposal.txt

# 2. Review proposal, owner can intervene per-plist if needed

# 3. Apply
bash scripts/patch_launchagents.sh

# 4. Lint
bash scripts/lint_launchagents.sh
# Expected: Total violations: 0

# 5. Test daemon respawn
PID=$(launchctl list com.cell.organism | jq -r .PID)
kill -9 $PID
sleep 15
NEW_PID=$(launchctl list com.cell.organism | jq -r .PID)
[ "$NEW_PID" != "$PID" ] && [ -n "$NEW_PID" ] && echo "PASS: Cell respawned"

# 6. Cell heartbeat resumes
tail -f ~/logs/cell_pulse.log | grep -m 1 "pulse"
# Expected: new pulse entry within 30s
```

Numbers:
- Before: 7/53 KeepAlive=true (13%)
- After audit: ~25-30/53 KeepAlive=true (proper daemon classification, rest cron-style explicitly KeepAlive=false)
- Before: 5/53 missing EnvironmentVariables
- After: 0
- Before: 6/53 logs to /tmp/
- After: 0
