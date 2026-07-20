#!/bin/zsh
# launchd-liveness-detector cron wrapper.
# Invoked by com.nuzantara.launchd-liveness-detector.daily.plist.
#
# WHAT / WHY (liveness-detector-arm-0717): scripts/launchd_liveness_detector.py
# (PR #1518, cicatrix W84) has 4 test suites and correctly cross-references
# launchd's exit-code against the actual LOG CONTENT to catch the "green-but-
# TCC-dead" vector — but until this wrapper+plist, nothing ever scheduled it.
# The sensor for dead daemons was itself never armed (cicatrix superscar #2,
# "Esiste ≠ Armato"). This wrapper closes that loop:
#   1. W84 trampoline fail-fast (shared lib — defense-in-depth even though the
#      repo itself moved out of ~/Desktop on 2026-07-16; the detector's own
#      raison d'etre is "don't trust that a past fix stays fixed").
#   2. Runs the detector --json (read-only: launchctl list/print + log tails,
#      no writes to launchd state, no kickstart/bootout/load).
#   3. Writes an organism heartbeat sidecar so THIS sensor's own liveness is
#      provable, not just assumed — ~/.organism/last_seen/pro.launchd_liveness.json.
#   4. On real alarms (DEAD-GREEN / DEAD-NONZERO / ARMED-TO-NOTHING / NOT-LOADED)
#      sends ONE P0 via the already-wired tg_notify.py gateway — no new channel
#      invented; this is the SAME `--tier p0` path every other sane wrapper in
#      this directory (matagaruda-redis-split-brain-check.sh, audit-launchd
#      digest tier) already uses.
#   5. Honors LAUNCHD_LIVENESS_DETECTOR_ENABLED=false as a kill switch
#      (G5_kill_switch, organ-conformance gate): the operator can stop this
#      organ without uninstalling the plist; a final "disabled" heartbeat
#      keeps the healer from resurrecting an intentionally-stopped run — same
#      idiom as pro-git-pull-main.sh / mini-fleet-watch.sh / wr2-worktree-gc-run.sh.
#
# Cadence: daily, one-shot (see the paired .daily.plist: KeepAlive=false,
# StartCalendarInterval). This is deliberately NOT a persistent daemon —
# KeepAlive=true on a one-shot script is exactly cicatrix superscar #7
# (daemon-vs-cron misconfig: every exit read as "died", restart-storm).
#
# Exit code: propagates the detector's own exit (1 if any alarms found) rather
# than swallowing it to 0 — matching the fleet's established "HONEST-nonzero-
# by-design" pattern (e.g. matagaruda-redis-split-brain-check.sh: "We do NOT
# translate exit 1 -> 0 here. launchctl `last exit code` should reflect the
# real finding for operator visibility."). This job auditing ITSELF (its own
# label matches OURS_RE) will therefore show verdict=FAILING-HONESTLY on days
# it found real alarms elsewhere in the fleet — which is the correct,
# non-cry-wolf classification, not a bug.

set -uo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a

mkdir -p "$HOME/logs"
LOG="$HOME/logs/launchd-liveness-detector.log"
REPO_ROOT="${HOME}/nuzantara"

# --- organism heartbeat sidecar (scripts/lib/heartbeat.{sh,py} convention) ---
# Resolved early (before the kill switch / trampoline below) so a disabled
# run can still prove a "disabled" liveness signal. Resolution order mirrors
# regulatory-watcher-run.sh: prefer a HOME-forked copy outside the repo, fall
# back to repo canon (works both pre- and post-install of the HOME-fork pair).
if [ -n "${ORGANISM_HEARTBEAT_LIB:-}" ]; then
    HEARTBEAT_LIB="$ORGANISM_HEARTBEAT_LIB"
elif [ -r "$HOME/scripts/lib/heartbeat.sh" ]; then
    HEARTBEAT_LIB="$HOME/scripts/lib/heartbeat.sh"
else
    HEARTBEAT_LIB="$REPO_ROOT/scripts/lib/heartbeat.sh"
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ. Checked before
# the trampoline so a disabled organ never pays the TCC-probe/ssh-reexec cost.
if [ "${LAUNCHD_LIVENESS_DETECTOR_ENABLED:-true}" = "false" ]; then
    echo "[$(date)] kill switch LAUNCHD_LIVENESS_DETECTOR_ENABLED=false — exiting" >> "$LOG"
    [ -f "$HEARTBEAT_LIB" ] && bash "$HEARTBEAT_LIB" "pro.launchd_liveness" "disabled" "kill switch"
    exit 0
fi

# --- W84 trampoline (shared lib; see infra/launchagents/wrappers/lib/trampoline.sh) ---
TRAMPOLINE_LIB="$HOME/scripts/lib/trampoline.sh"
[ -f "$TRAMPOLINE_LIB" ] || TRAMPOLINE_LIB="$(dirname "$0")/lib/trampoline.sh"
if [ -f "$TRAMPOLINE_LIB" ]; then
    source "$TRAMPOLINE_LIB"
    w84_trampoline_or_die "$LOG" "$0"
fi

DETECTOR="$REPO_ROOT/scripts/launchd_liveness_detector.py"

if [ ! -f "$DETECTOR" ]; then
    echo "[$(date)] FATAL: detector script missing at $DETECTOR" >> "$LOG"
    exit 66  # EX_NOINPUT
fi

PYBIN="$(command -v python3 || echo /usr/bin/python3)"

TMPOUT=$(mktemp)
"$PYBIN" "$DETECTOR" --json > "$TMPOUT" 2>>"$LOG"
DETECTOR_EXIT=$?

ALARMS=$("$PYBIN" -c "
import json, sys
try:
    d = json.load(open('$TMPOUT'))
    print(d.get('alarms', -1))
except Exception:
    print(-1)
" 2>>"$LOG")
case "$ALARMS" in
    ''|*[!0-9-]*) ALARMS=-1 ;;  # non-numeric output is itself a failure signal
esac

if [ "$ALARMS" -lt 0 ] 2>/dev/null; then
    HB_STATUS="error"
    HB_NOTE="rc=${DETECTOR_EXIT} unreadable JSON output"
elif [ "$ALARMS" -gt 0 ]; then
    HB_STATUS="degraded"
    HB_NOTE="${ALARMS} alarm(s) — see ${LOG}"
else
    HB_STATUS="ok"
    HB_NOTE="0 alarms"
fi

if [ -f "$HEARTBEAT_LIB" ]; then
    bash "$HEARTBEAT_LIB" "pro.launchd_liveness" "$HB_STATUS" "$HB_NOTE" || true
fi

echo "[$(date)] launchd-liveness-detector run: detector_exit=${DETECTOR_EXIT} alarms=${ALARMS}" >> "$LOG"
cat "$TMPOUT" >> "$LOG"

# --- alert on real findings via the already-wired gateway (no new channel) ---
if [ "$ALARMS" -gt 0 ] 2>/dev/null; then
    SUMMARY=$("$PYBIN" -c "
import json
d = json.load(open('$TMPOUT'))
alarm_verdicts = {'DEAD-GREEN', 'DEAD-NONZERO', 'ARMED-TO-NOTHING', 'NOT-LOADED'}
lines = [f\"{f['verdict']}: {f['label']} (exit={f['last_exit']})\" for f in d['findings'] if f['verdict'] in alarm_verdicts]
print('\n'.join(lines[:15]))
" 2>>"$LOG")
    MSG="launchd liveness detector — ${ALARMS} alarm(s) on $(hostname -s)

${SUMMARY}

DEAD-GREEN = launchd exit 0 but the log proves the worker never ran (W84 TCC vector).
Full log: ${LOG}"
    GATEWAY="$(dirname "$0")/tg_notify.py"
    [ -f "$GATEWAY" ] || GATEWAY="$REPO_ROOT/scripts/tg_notify.py"
    "$PYBIN" "$GATEWAY" --tier p0 --source launchd-liveness-detector \
        --dedup-key "launchd-liveness:$(hostname -s)" -- "$MSG" > /dev/null 2>&1 || true
fi

rm -f "$TMPOUT"

# Fail visibly if we couldn't even parse the detector's own output — don't
# let a broken sensor report itself healthy (the exact disease this detector
# exists to cure, applied reflexively to itself).
if [ "$ALARMS" -lt 0 ] 2>/dev/null; then
    exit 1
fi
exit "$DETECTOR_EXIT"
