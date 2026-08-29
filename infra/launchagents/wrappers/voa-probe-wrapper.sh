#!/bin/zsh
# voa-probe-wrapper.sh — cron wrapper for scripts/probes/voa_journey_probe.mjs
# LaunchAgent: com.nuzantara.voa-probe (StartInterval 900s / 15min)
#
# Mirrors infra/launchagents/wrappers/garuda-consumer.sh's shape (absolute
# interpreter, guarded payload, appended timestamped log), ported from python
# to node, plus the three traps this class of wrapper is written to avoid:
#
#   W101/W108 — never `set -e`. Under errexit a naked pipeline aborts ON the
#   pipeline itself, and any exit-code capture written after it becomes dead
#   code on the one path it exists for (measured: 16 of 20 NLM alert wrappers
#   had exactly this shape and never spoke). This script only ever sets
#   `-uo pipefail`; the node run's exit code is captured explicitly with
#   `|| RC=$?`, never inferred from "did the previous line survive".
#
#   W108 — the wrapper that reports on prod health must not itself depend on
#   an interpreter resolved by ambient PATH (a launchd job's PATH is not a
#   login shell's PATH, and a corrupted/absent interpreter is one of the
#   plausible reasons the job would need to alarm in the first place). Node
#   is resolved to an ABSOLUTE path: `/opt/homebrew/bin/node` first (the
#   Homebrew location on both fleet Macs), `command -v node` as fallback,
#   FATAL with a distinct exit code if neither resolves.
#
#   W104/superscar#2 — never redirect the probe's output to /dev/null. The
#   probe's own tri-state verdict (pass/dark/fail — see the .mjs header) and
#   its heartbeat JSON are the evidence a dead-man watcher and a human both
#   need; a wrapper that swallows them is cron-theater — green on the
#   outside, mute on the inside.
#
# Exit code: whatever the probe itself returned (0 = pass/dark, 1 = fail),
# or a distinct FATAL code (2/3) if this wrapper could not even start it.

set -uo pipefail

SCRIPT_PATH="${0:A}"
REPO_ROOT="$(cd "${SCRIPT_PATH:h}/../../.." && pwd)"
PROBE="$REPO_ROOT/scripts/probes/voa_journey_probe.mjs"
LOG="${HOME}/logs/voa-probe.log"

mkdir -p "$(dirname "$LOG")"

echo "" >> "$LOG"
echo "=== VOA Journey Probe — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

# Signature guard (W105 class): if the derived REPO_ROOT does not contain the
# probe, either the derivation is wrong or the probe was never deployed here
# — proceeding would mean invoking `node` on a nonexistent file and reporting
# a bare 127, not the FATAL/CANNOT-VERIFY this deserves.
if [ ! -f "$PROBE" ]; then
    echo "[voa-probe] FATAL: probe not found at $PROBE (REPO_ROOT derived: $REPO_ROOT)" >> "$LOG"
    exit 2
fi

if [ -x /opt/homebrew/bin/node ]; then
    NODE_BIN=/opt/homebrew/bin/node
else
    NODE_BIN="$(command -v node 2>/dev/null || true)"
fi

if [ -z "${NODE_BIN:-}" ] || [ ! -x "$NODE_BIN" ]; then
    echo "[voa-probe] FATAL: node interpreter not found (checked /opt/homebrew/bin/node and PATH)" >> "$LOG"
    exit 3
fi

echo "[voa-probe] node=$NODE_BIN probe=$PROBE" >> "$LOG"

RC=0
"$NODE_BIN" "$PROBE" "$@" >> "$LOG" 2>&1 || RC=$?

echo "[voa-probe] rc=$RC" >> "$LOG"
exit "$RC"
