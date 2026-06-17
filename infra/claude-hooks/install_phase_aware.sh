#!/bin/bash
# install_phase_aware.sh — install the phase-aware-guardrails layer into ~/.claude/hooks/
#
# Idempotent. Copies host_boundary.py + _phase.py + the 3 relaxed green gates
# (orchestrate_gate / dispatch_nudge / stadio_zero_nudge) from this repo dir into
# ~/.claude/hooks/, backs up any file it overwrites, and registers host_boundary
# as a PreToolUse matcher in ~/.claude/settings.json (if not already present).
#
# worktree_isolation.py is NOT installed here — it is managed by W79 and is NOT
# phase-relaxed (its scratch git-ops are already permitted without plan-mode;
# relaxing its main-checkout block would be a hole — see spec §10 correction).
#
# Run on each machine (M5 done in-session; Pro+Mini via this script after merge):
#   bash infra/claude-hooks/install_phase_aware.sh
#
# Kill switches after install: NUZ_PHASE_AWARE_OFF=1 (disable the switch),
# HOST_BOUNDARY_OFF=1 (disable host_boundary).
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="$HOME/.claude/hooks"
TS="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$DST"

install_file() {
    local name="$1"
    local src="$SRC/$name"
    local dst="$DST/$name"
    if [ ! -f "$src" ]; then
        echo "  SKIP $name (not in repo dir)"
        return
    fi
    if [ -f "$dst" ] && ! diff -q "$src" "$dst" >/dev/null 2>&1; then
        cp "$dst" "$dst.bak-pre-phaseaware-$TS"
        echo "  backed up existing $name -> $name.bak-pre-phaseaware-$TS"
    fi
    cp "$src" "$dst"
    chmod 700 "$dst"
    echo "  installed $name"
}

echo "== installing phase-aware hooks into $DST =="
install_file host_boundary.py
install_file _phase.py
install_file orchestrate_gate.py
install_file dispatch_nudge.py
install_file stadio_zero_nudge.py

echo "== registering host_boundary in settings.json =="
python3 - <<'PY'
import json, os, pathlib, shutil, time
p = pathlib.Path.home() / ".claude" / "settings.json"
if not p.exists():
    print("  WARN: settings.json missing — skip host_boundary registration")
    raise SystemExit(0)
s = json.loads(p.read_text())
pre = s.setdefault("hooks", {}).setdefault("PreToolUse", [])
cmd = "python3 ~/.claude/hooks/host_boundary.py"
if any(cmd in hh.get("command", "") for g in pre for hh in g.get("hooks", [])):
    print("  host_boundary already registered")
else:
    shutil.copy2(p, p.with_name(p.name + f".bak-pre-phaseaware-{time.strftime('%Y%m%d-%H%M%S')}"))
    pre.insert(0, {"matcher": "Bash|Edit|Write|MultiEdit",
                   "hooks": [{"type": "command", "command": cmd}]})
    p.write_text(json.dumps(s, indent=2))
    print("  host_boundary registered at top of PreToolUse")
PY

echo "== done. Reload hooks with /hooks (or restart the session). =="
echo "   Kill switches: NUZ_PHASE_AWARE_OFF=1 / HOST_BOUNDARY_OFF=1"
