#!/bin/zsh
# queue-baseline.sh — Merge-OS v2 Wave 1 baseline organ wrapper (MEASURE ONLY).
#
# Invoked nightly (03:40 WITA, StartCalendarInterval) by
# com.nuzantara.queue-baseline.plist — a TEMPLATE at this commit, NOT installed by
# this PR. Arming on Pro is a separate ALIGN-FLEET step (scar family #2 "esiste !=
# armato" — built != armed; tracked in .claude/skills/modus/PENDING-ARMS.md).
#
# Runs scripts/queue_baseline_probe.py for "yesterday" UTC, which writes the daily
# record to ~/.nuzantara-mq/baseline/YYYY-MM-DD.json, then alerts (Telegram DIGEST
# tier — informative, not actionable-now) only when the probe reports failure.
#
# Scar discipline this wrapper obeys (research/operations/2026-08-10-merge-os-v2-
# submission-system.md is the spec; the wrapper rules below are this repo's own
# blood-bought lessons, cicatrix-superscar.md families #2/#7):
#
#   - W108 "twentieth wrapper" (2026-07-28): the alarm must NOT share the failure
#     mode of the thing it reports. `SYSTEM_PY` — the interpreter used ONLY for the
#     Telegram notifier — is resolved via `command -v` at the very top of this
#     script, BEFORE secrets/venv sourcing can shadow PATH. It is a separate
#     variable from `VENV_PY` (used for the probe itself): if the repo venv is the
#     thing that's broken, the alert about that breakage must not run through it.
#   - W108 (16 of 20 wrappers, same date): the probe call runs under `set +e` with
#     its rc captured into a variable and judged explicitly afterward — never a
#     bare pipeline under `set -e`/`pipefail` where the capture is dead code on the
#     only path it exists for (W101).
#   - W108 (1 of 20 wrappers): `[ -f X ] && source X`, never `source X || true` —
#     under `set -e` bash treats a failed `source` as a special builtin and EXITS;
#     the `||` never runs.
#   - W104 (2026-07-25): `tg_notify.py` always returns rc=0 (spool-best-effort
#     contract, "NEVER fail the caller") — the verdict is read from its printed
#     status line, never from `$?`.
#   - Absolute interpreter for the PROBE itself, resolved from the repo venv WITH
#     an existence check; falls back to system python3 if the venv is missing —
#     the probe is stdlib-only (see its own module docstring), so this fallback is
#     safe rather than a silent behavior change.

set -uo pipefail

# --- W108 twentieth-wrapper fix: resolve the ALARM's interpreter FIRST, before any
# venv/secrets sourcing below can shadow PATH. Deliberately separate from VENV_PY.
SYSTEM_PY="$(command -v python3 2>/dev/null || echo /usr/bin/python3)"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

REPO_ROOT="${QUEUE_BASELINE_REPO_ROOT:-$HOME/nuzantara}"
REPO_SLUG="${QUEUE_BASELINE_REPO_SLUG:-Bali-Zero/Teman2}"
PROBE_SCRIPT="$REPO_ROOT/scripts/queue_baseline_probe.py"
STATE_DIR="$HOME/.nuzantara-mq/baseline"
RECEIPT_DIR="$HOME/.agent/decisions"
LOG="$HOME/logs/queue-baseline.log"

mkdir -p "$STATE_DIR" "$RECEIPT_DIR" "$HOME/logs"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] [queue-baseline] $*" >> "$LOG"; }

# [ -f X ] && source X — never `source X || true` (W108: a failed source is a
# special builtin under `set -e` and EXITS before the `||` ever runs).
[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a

# Repo-venv interpreter for the probe itself (existence-checked). The probe is
# stdlib-only (module docstring / imports), so a missing venv degrades safely to
# system python3 rather than hard-failing the whole nightly run.
VENV_PY="$REPO_ROOT/apps/backend-rag/.venv/bin/python3"
if [ ! -x "$VENV_PY" ]; then
    VENV_PY="$REPO_ROOT/.venv/bin/python3"
fi
if [ ! -x "$VENV_PY" ]; then
    log "WARN: no repo venv python3 at either candidate path — falling back to system ($SYSTEM_PY); probe is stdlib-only so this is safe"
    VENV_PY="$SYSTEM_PY"
fi

if [ ! -f "$PROBE_SCRIPT" ]; then
    log "FATAL: probe script missing at $PROBE_SCRIPT — cannot run"
    exit 78
fi

if ! command -v gh >/dev/null 2>&1; then
    log "FATAL: gh CLI not on PATH — the probe cannot make a single API call without it"
    exit 78
fi

# --- run the probe; rc captured then judged (W101 discipline: no bare pipeline
# under `set -e`, capture is never dead code) ---
set +e
"$VENV_PY" "$PROBE_SCRIPT" --repo "$REPO_SLUG" --out-dir "$STATE_DIR" >> "$LOG" 2>&1
PROBE_RC=$?
set -e

# The probe itself writes .last-run-pointer.json naming the date/path it just
# produced — read THAT instead of recomputing "yesterday UTC" a second time in
# shell (scar family #9: two independent computations of one derived fact drift).
POINTER_FILE="$STATE_DIR/.last-run-pointer.json"
RECORD_PATH="(unknown — pointer file missing)"
RECORD_DATE="(unknown)"
ERRORS_COUNT="-1"
if [ -f "$POINTER_FILE" ]; then
    RECORD_PATH="$("$SYSTEM_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("record_path",""))' "$POINTER_FILE" 2>/dev/null)"
    RECORD_DATE="$("$SYSTEM_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("date",""))' "$POINTER_FILE" 2>/dev/null)"
    ERRORS_COUNT="$("$SYSTEM_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("errors_count",-1))' "$POINTER_FILE" 2>/dev/null)"
fi

# Wrapper's own execution receipt (distinct from the probe's DATA record above) —
# team direction: "receipt JSON written to the state dir".
RECEIPT_FILE="$RECEIPT_DIR/queue-baseline-last-receipt.json"
"$SYSTEM_PY" - "$RECEIPT_FILE" "$PROBE_RC" "$RECORD_PATH" "$RECORD_DATE" "$ERRORS_COUNT" <<'PY'
import json, os, sys, time
receipt_path, rc, record_path, record_date, errors_count = sys.argv[1:6]
json.dump({
    "job": "queue-baseline",
    "ran_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "probe_rc": int(rc),
    "record_date": record_date,
    "record_path": record_path,
    "record_exists": bool(record_path) and os.path.exists(record_path),
    "errors_count": int(errors_count) if errors_count not in ("", "-1") else None,
    "status": "ok" if int(rc) == 0 else "failed",
}, open(receipt_path, "w"), indent=2)
PY

if [ "$PROBE_RC" -ne 0 ]; then
    log "probe FAILED rc=$PROBE_RC date=$RECORD_DATE record=$RECORD_PATH errors=$ERRORS_COUNT — see $LOG for detail, alerting"

    MSG="queue-baseline probe FAILED (rc=$PROBE_RC) on $(hostname -s). date=$RECORD_DATE errors=$ERRORS_COUNT record=$RECORD_PATH log=$LOG"
    # Same lookup convention as the neighboring wrappers (audit-launchd-daily.sh,
    # cron-agent.sh, launchd-liveness-detector.sh): a live HOME deployment may keep
    # tg_notify.py alongside the wrapper itself; the repo canon is the fallback.
    GATEWAY="$(dirname "$0")/tg_notify.py"
    [ -f "$GATEWAY" ] || GATEWAY="$REPO_ROOT/scripts/tg_notify.py"
    if [ -f "$GATEWAY" ]; then
        # W104: tg_notify.py always returns rc=0 (spool-best-effort) — judge its
        # printed status line, never $?.
        REPLY="$("$SYSTEM_PY" "$GATEWAY" --tier digest --source queue-baseline \
            --dedup-key "queue-baseline:$(hostname -s):probe-failed" -- "$MSG" 2>&1)"
        log "tg_notify reply: $(printf '%s' "$REPLY" | tr '\n' ' ' | head -c 200)"
    else
        log "ALERT NOT SENT: tg_notify.py gateway missing (looked in $(dirname "$0") and $REPO_ROOT/scripts)"
    fi
else
    log "probe OK date=$RECORD_DATE record=$RECORD_PATH errors=$ERRORS_COUNT"
fi

exit "$PROBE_RC"
