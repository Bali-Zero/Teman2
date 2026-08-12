#!/usr/bin/env bash
# Install/verify/remove the Pro-only KBLI surface conformance LaunchAgent.
# This script is intentionally not run by the implementation step. The shipper
# uses it after merge, after first exercising the wrapper with a stub gateway.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LABEL="com.nuzantara.kbli-surface-conformance.daily"
PLIST_SRC="$REPO_ROOT/infra/launchagents/$LABEL.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/kbli-surface-conformance-run.sh"
RUNNER="$REPO_ROOT/scripts/cron-runner.sh"
DETECTOR="$REPO_ROOT/scripts/kbli_filiera/kbli_surface_conformance.py"
REGISTRY_FRAGMENT="$REPO_ROOT/infra/launchagents/job_registry.kbli_surface_conformance.json"
REGISTRY_FILE="$HOME/.agent/decisions/job_registry.json"
RECEIPT="$HOME/.agent/decisions/state/kbli_surface_conformance.last.json"
HEARTBEAT="$HOME/.organism/last_seen/pro.kbli_surface_conformance.json"
LOG_DIR="$HOME/logs/kbli-conformance"
UID_VAL="$(id -u)"
MODE="${1:-install}"

require_pro() {
    local current
    current="$(hostname -s 2>/dev/null || hostname)"
    if [ "$current" != "Nuzantara" ]; then
        echo "FATAL: $LABEL is Pro-only; current host=$current" >&2
        exit 69
    fi
}

lint_sources() {
    local path
    for path in "$PLIST_SRC" "$WRAPPER" "$RUNNER" "$DETECTOR" "$REGISTRY_FRAGMENT"; do
        [ -f "$path" ] || { echo "FATAL: required source missing: $path" >&2; return 1; }
    done
    /usr/bin/plutil -lint "$PLIST_SRC"
    /bin/bash -n "$WRAPPER"
    /usr/bin/python3 -m json.tool "$REGISTRY_FRAGMENT" >/dev/null
}

bootout() {
    if /bin/launchctl print "gui/$UID_VAL/$LABEL" >/dev/null 2>&1; then
        /bin/launchctl bootout "gui/$UID_VAL/$LABEL"
    fi
}

registry_update() {
    local action="$1"
    /usr/bin/python3 - "$REGISTRY_FILE" "$REGISTRY_FRAGMENT" "$action" <<'PY'
import hashlib
import json
import os
import stat
import sys
import time
from pathlib import Path

registry_path = Path(sys.argv[1])
fragment_path = Path(sys.argv[2])
action = sys.argv[3]

data = json.loads(registry_path.read_text(encoding="utf-8"))
jobs = data.get("jobs")
if not isinstance(jobs, dict):
    raise SystemExit("registry has no jobs mapping")

canonical = json.dumps(jobs, sort_keys=True, separators=(",", ":"))
actual = hashlib.sha256(canonical.encode()).hexdigest()
recorded = data.get("checksum")
if recorded and recorded != actual:
    raise SystemExit(f"registry checksum mismatch before update: recorded={recorded} actual={actual}")

fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
job = fragment["job"]
if action == "check":
    print(f"registry preflight clean; checksum={actual}")
    raise SystemExit(0)
elif action == "add":
    jobs[job] = fragment["entry"]
elif action == "remove":
    jobs.pop(job, None)
else:
    raise SystemExit(f"unknown registry action: {action}")

canonical = json.dumps(jobs, sort_keys=True, separators=(",", ":"))
data["checksum"] = hashlib.sha256(canonical.encode()).hexdigest()
data["_writer"] = "install_kbli_surface_conformance"

backup = registry_path.with_name(
    registry_path.name + f".pre-kbli-surface-conformance-{int(time.time())}"
)
backup.write_bytes(registry_path.read_bytes())
os.chmod(backup, stat.S_IRUSR | stat.S_IWUSR)
tmp = registry_path.with_name(registry_path.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
os.replace(tmp, registry_path)
print(f"registry {action}: {job}; checksum={data['checksum']}")
PY
}

verify_receipts() {
    local now path age
    now="$(date +%s)"
    for path in "$RECEIPT" "$HEARTBEAT"; do
        if [ ! -s "$path" ]; then
            echo "MISSING: $path"
            return 1
        fi
        /usr/bin/python3 -m json.tool "$path" >/dev/null
        age=$((now - $(/usr/bin/stat -f %m "$path")))
        echo "OK: $path age=${age}s"
        /bin/tail -n 1 "$path"
    done
}

case "$MODE" in
    --lint|lint)
        lint_sources
        echo "source lint clean: plist, wrapper, runner, detector, Sentinel fragment"
        ;;
    install|--install)
        require_pro
        lint_sources
        registry_update check
        /bin/mkdir -p "$(dirname "$PLIST_DEST")" "$LOG_DIR" "$(dirname "$RECEIPT")"
        /bin/chmod +x "$WRAPPER"
        if [ -f "$PLIST_DEST" ]; then
            backup="$PLIST_DEST.pre-install-$(date +%Y%m%d-%H%M%S)"
            /bin/cp "$PLIST_DEST" "$backup"
            /bin/chmod 0400 "$backup"
            echo "backed up $PLIST_DEST -> $backup"
        fi
        bootout
        /bin/cp "$PLIST_SRC" "$PLIST_DEST"
        /bin/chmod 0444 "$PLIST_DEST"
        /usr/bin/plutil -lint "$PLIST_DEST"
        /bin/launchctl bootstrap "gui/$UID_VAL" "$PLIST_DEST"
        registry_update add
        echo "installed $LABEL (not kickstarted)"
        echo "First run: invoke cron-runner manually with KBLI_SURFACE_CONFORMANCE_GATEWAY=<stub>, inspect report, then run: $0 --kickstart"
        ;;
    --kickstart|kickstart)
        require_pro
        /bin/launchctl kickstart -k "gui/$UID_VAL/$LABEL"
        echo "kickstarted $LABEL; after completion run: $0 --verify"
        ;;
    --verify|verify)
        require_pro
        lint_sources
        /bin/launchctl print "gui/$UID_VAL/$LABEL" | /usr/bin/grep -E "state =|runs =|last exit code|program =" || true
        verify_receipts
        /usr/bin/python3 - "$REGISTRY_FILE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
entry = d.get("jobs", {}).get("kbli_surface_conformance")
if not entry:
    raise SystemExit("MISSING: Sentinel registry entry kbli_surface_conformance")
print("OK: Sentinel registry entry", json.dumps(entry, sort_keys=True))
PY
        ;;
    --uninstall|uninstall)
        require_pro
        bootout
        if [ -f "$PLIST_DEST" ]; then
            /bin/chmod u+w "$PLIST_DEST"
            /bin/rm -f "$PLIST_DEST"
        fi
        registry_update remove
        echo "uninstalled $LABEL; receipts/logs retained for audit"
        ;;
    *)
        echo "Usage: $0 [--lint|install|--kickstart|--verify|--uninstall]" >&2
        exit 64
        ;;
esac
