#!/bin/bash
# mailbox_janitor_cron.sh — launchd wrapper for scripts/mailbox_janitor.py.
#
# The fleet mailbox (~/.nuzantara-mailbox) has a reader hook that RENAMES dead
# mail to `<name>.<tag>-<ts>` and appends `.broadcast_seen` markers, and a
# sender that only creates. Nothing deleted anything, so the root listing grew
# without bound (measured 2026-09-18: 957 entries on M5, 5,734 on Pro, 13 live
# messages between them). This wrapper is the ONLY deleter: it runs the janitor
# in --apply mode once a day, appends a JSON receipt line and writes the organ
# heartbeat with the outcome. Driven by
# infra/launchagents/com.nuzantara.mailbox-janitor.daily.plist on all
# three machines (each machine owns its own mailbox; no shared state, so no
# node guard).
#
# Exit codes: 0 = applied (or dry-run) with no deletion errors; 1 = janitor
# refused (root missing/symlink/not owned) — heartbeat error; 2 = env missing
# (python3/janitor) or kill switch; 3 = janitor reported deletion errors —
# heartbeat warning.

set -euo pipefail

# Hardcoded MAIN checkout — do NOT derive from $0 (a worktree copy of this
# wrapper must still run the canonical janitor). Env override for tests only.
REPO_ROOT="${MAILBOX_JANITOR_REPO_ROOT:-${HOME}/nuzantara}"
JANITOR="${REPO_ROOT}/scripts/mailbox_janitor.py"

LOG_DIR="${HOME}/logs"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/mailbox-janitor.log"
RECEIPTS="${MAILBOX_JANITOR_RECEIPTS:-${LOG_DIR}/mailbox-janitor.receipts.jsonl}"

# `|| true` on every tee: a full disk or an unwritable log dir must never
# kill the wrapper before the heartbeat (spalla review, superscar #2).
log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG" || true
}

# Heartbeat helper (no-op fallback if not present). bash 3.2 exits the whole
# script when `source` cannot find the file, so guard with an existence check.
if [ -f "${REPO_ROOT}/scripts/lib/heartbeat.sh" ]; then
    # shellcheck disable=SC1091
    source "${REPO_ROOT}/scripts/lib/heartbeat.sh" || true
fi
if ! declare -F organism_heartbeat >/dev/null 2>&1; then
    organism_heartbeat() { :; }
fi

# Machine-aware organ id: this cron runs on all three machines and a hardcoded
# prefix would forge a Pro-resident heartbeat from M5/Mini.
case "$(hostname -s | tr '[:upper:]' '[:lower:]')" in
    nuzantara)  _ORGAN_MACHINE="pro" ;;
    mini-pro2)  _ORGAN_MACHINE="mini" ;;
    air-m5)     _ORGAN_MACHINE="m5" ;;
    *)          _ORGAN_MACHINE="$(hostname -s | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '_')" ;;
esac
ORGAN_ID="${MAILBOX_JANITOR_ORGAN_ID:-${_ORGAN_MACHINE}.mailbox_janitor}"

# G5 kill switch: stop the organ without uninstalling it, visibly.
if [ "${MAILBOX_JANITOR_ENABLED:-true}" = "false" ]; then
    log "kill switch MAILBOX_JANITOR_ENABLED=false — exiting"
    organism_heartbeat "$ORGAN_ID" "disabled" "kill-switch" || true
    exit 2
fi

if [ ! -f "$JANITOR" ]; then
    log "ERROR: janitor not found at $JANITOR"
    organism_heartbeat "$ORGAN_ID" "error" "janitor missing" || true
    exit 2
fi

PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
    log "ERROR: python3 not on PATH ($PATH)"
    organism_heartbeat "$ORGAN_ID" "error" "python3 missing" || true
    exit 2
fi

MODE_FLAG="--apply"
if [ "${MAILBOX_JANITOR_DRY_RUN:-0}" = "1" ]; then
    MODE_FLAG=""
fi

log "running janitor ${MODE_FLAG:-DRY-RUN} (receipts=$RECEIPTS)"
set +e
# shellcheck disable=SC2086
OUTPUT="$("$PYTHON" "$JANITOR" $MODE_FLAG --receipt "$RECEIPTS" 2>&1)"
RC=$?
set -e

echo "$OUTPUT" | tee -a "$LOG" || true
# `|| true`: under pipefail a crashed janitor (traceback, no summary line)
# would otherwise kill this wrapper here, BEFORE the heartbeat below — the
# exact "silently dead cron" superscar #2 shape (codex council finding).
SUMMARY="$(echo "$OUTPUT" | grep -m1 '^mailbox-janitor:' | cut -c1-200 || true)"

case "$RC" in
    0)
        organism_heartbeat "$ORGAN_ID" "ok" "${SUMMARY:-applied}" || true
        exit 0
        ;;
    1)
        log "REFUSED: janitor rc=1 (root missing, symlink or not owned)"
        organism_heartbeat "$ORGAN_ID" "error" "refused: ${SUMMARY:-see log}" || true
        exit 1
        ;;
    2)
        log "WARN: janitor rc=2 (deletion errors, see log)"
        organism_heartbeat "$ORGAN_ID" "warning" "${SUMMARY:-deletion errors}" || true
        exit 3
        ;;
    *)
        log "ERROR: janitor rc=$RC"
        organism_heartbeat "$ORGAN_ID" "error" "rc=$RC" || true
        exit "$RC"
        ;;
esac
