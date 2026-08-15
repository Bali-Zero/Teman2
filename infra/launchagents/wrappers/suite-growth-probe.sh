#!/bin/zsh
# suite-growth-probe.sh — Merge-OS v3 step 3 slice 1 telemetry organ wrapper
# (MEASUREMENT ONLY, no gate-semantics change).
#
# Invoked nightly (03:57 WITA, StartCalendarInterval) by
# com.nuzantara.suite-growth-probe.plist — a TEMPLATE at this commit, NOT
# installed by this PR. Arming on Pro is a separate ALIGN-FLEET step (scar
# family #2 "esiste != armato" — built != armed; tracked in
# .claude/skills/modus/PENDING-ARMS.md).
#
# Runs scripts/suite_growth_probe.py over the last 7 days of tests.yml gate
# runs (push:main + merge_group), which writes its record to
# ~/.nuzantara-mq/suite-growth/<timestamp>.json. The probe itself dispatches
# any near-timeout/weekly-growth alert directly through scripts/tg_notify.py
# (module docstring "ALARM") — this wrapper's OWN alert below fires only when
# the PROBE ITSELF failed to collect data (a distinct condition from "the
# probe ran clean and found a growth problem", which is not a wrapper-level
# failure and must not be conflated with one, scar family #2).
#
# Scar discipline this wrapper obeys — copied byte-for-byte in structure from
# infra/launchagents/wrappers/queue-baseline.sh (research/operations/
# 2026-08-14-merge-os-v3-research-council.md §6 step 3 names that pattern as
# the one to model):
#
#   - W108 "twentieth wrapper" (2026-07-28): the ALARM's interpreter
#     (`SYSTEM_PY`) is resolved via `command -v` at the very top of this
#     script, BEFORE secrets/venv sourcing can shadow PATH — a separate
#     variable from `VENV_PY` (used for the probe itself), so an alert about
#     a broken venv never has to run through that same broken venv.
#   - W108 (16 of 20 wrappers): the probe call runs under `set +e` with its
#     rc captured into a variable and judged explicitly afterward — never a
#     bare pipeline under `set -e`/`pipefail` where the capture is dead code
#     on the only path it exists for (W101).
#   - W108 (1 of 20 wrappers): `[ -f X ] && source X`, never `source X ||
#     true` — under `set -e` bash treats a failed `source` as a special
#     builtin and EXITS; the `||` never runs.
#   - W104 (2026-07-25): `tg_notify.py` always returns rc=0 (spool-best-effort
#     contract) — the verdict is read from its printed status line, never
#     from `$?`.
#
# DIFFERS from queue-baseline.sh in one declared way: this probe is NOT
# stdlib-only (scripts/suite_growth_probe.py module docstring — it best-effort
# imports PyYAML to read tests.yml's own timeout-minutes). The repo venv is
# therefore preferred over a bare `set -e` fallback to system python3 unless
# PyYAML is independently confirmed there too; the probe itself degrades
# gracefully (declared error in errors[], never a crash) if PyYAML is missing
# under either interpreter, so this wrapper does not hard-fail on that case —
# it is visible in the record, not in this wrapper's own exit code.

set -uo pipefail

# --- W108 twentieth-wrapper fix: resolve the ALARM's interpreter FIRST, before
# any venv/secrets sourcing below can shadow PATH. Deliberately separate from
# VENV_PY.
SYSTEM_PY="$(command -v python3 2>/dev/null || echo /usr/bin/python3)"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

REPO_ROOT="${SUITE_GROWTH_REPO_ROOT:-$HOME/nuzantara}"
REPO_SLUG="${SUITE_GROWTH_REPO_SLUG:-Bali-Zero/Teman2}"
WORKFLOW="${SUITE_GROWTH_WORKFLOW:-tests.yml}"
PROBE_SCRIPT="$REPO_ROOT/scripts/suite_growth_probe.py"
STATE_DIR="$HOME/.nuzantara-mq/suite-growth"
RECEIPT_DIR="$HOME/.agent/decisions"
LOG="$HOME/logs/suite-growth-probe.log"

mkdir -p "$STATE_DIR" "$RECEIPT_DIR" "$HOME/logs"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] [suite-growth-probe] $*" >> "$LOG"; }

# [ -f X ] && source X — never `source X || true` (W108: a failed source is a
# special builtin under `set -e` and EXITS before the `||` ever runs).
[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a

# Repo-venv interpreter for the probe itself (existence-checked). Unlike
# queue-baseline.sh's probe, this one is NOT guaranteed stdlib-only (see
# header) — the repo venv is where PyYAML has actually been measured present
# (module docstring), so prefer it strongly; system python3 is still a safe
# fallback because the probe degrades gracefully without PyYAML rather than
# crashing.
VENV_PY="$REPO_ROOT/apps/backend-rag/.venv/bin/python3"
if [ ! -x "$VENV_PY" ]; then
    VENV_PY="$REPO_ROOT/.venv/bin/python3"
fi
if [ ! -x "$VENV_PY" ]; then
    log "WARN: no repo venv python3 at either candidate path — falling back to system ($SYSTEM_PY); probe degrades gracefully without PyYAML but this is a real capability loss, not a false alarm"
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

# --- run the probe; rc captured then judged (W101 discipline: no bare
# pipeline under `set -e`, capture is never dead code) ---
set +e
"$VENV_PY" "$PROBE_SCRIPT" --repo "$REPO_SLUG" --workflow "$WORKFLOW" \
    --repo-root "$REPO_ROOT" --out-dir "$STATE_DIR" >> "$LOG" 2>&1
PROBE_RC=$?
set -e

# The probe writes .last-run-pointer.json naming what it just produced — read
# THAT instead of recomputing the same fact in shell (scar family #9: two
# independent computations of one derived fact drift).
POINTER_FILE="$STATE_DIR/.last-run-pointer.json"
RECORD_PATH="(unknown — pointer file missing)"
ERRORS_COUNT="-1"
ALERTS_COUNT="-1"
if [ -f "$POINTER_FILE" ]; then
    RECORD_PATH="$("$SYSTEM_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("record_path",""))' "$POINTER_FILE" 2>/dev/null)"
    ERRORS_COUNT="$("$SYSTEM_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("errors_count",-1))' "$POINTER_FILE" 2>/dev/null)"
    ALERTS_COUNT="$("$SYSTEM_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("alerts_sent_count",-1))' "$POINTER_FILE" 2>/dev/null)"
fi

# Wrapper's own execution receipt (distinct from the probe's DATA record
# above) — same convention as queue-baseline.sh.
RECEIPT_FILE="$RECEIPT_DIR/suite-growth-probe-last-receipt.json"
"$SYSTEM_PY" - "$RECEIPT_FILE" "$PROBE_RC" "$RECORD_PATH" "$ERRORS_COUNT" "$ALERTS_COUNT" <<'PY'
import json, os, sys, time
receipt_path, rc, record_path, errors_count, alerts_count = sys.argv[1:6]
json.dump({
    "job": "suite-growth-probe",
    "ran_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "probe_rc": int(rc),
    "record_path": record_path,
    "record_exists": bool(record_path) and os.path.exists(record_path),
    "errors_count": int(errors_count) if errors_count not in ("", "-1") else None,
    "alerts_sent_count": int(alerts_count) if alerts_count not in ("", "-1") else None,
    "status": "ok" if int(rc) == 0 else "failed",
}, open(receipt_path, "w"), indent=2)
PY

if [ "$PROBE_RC" -ne 0 ]; then
    log "probe FAILED rc=$PROBE_RC record=$RECORD_PATH errors=$ERRORS_COUNT — see $LOG for detail, alerting"

    MSG="suite-growth-probe FAILED to collect data (rc=$PROBE_RC) on $(hostname -s). errors=$ERRORS_COUNT record=$RECORD_PATH log=$LOG. NOTE: this is a data-collection failure, NOT a suite-growth finding — those alert directly from the probe itself."
    # Same lookup convention as the neighboring wrappers (queue-baseline.sh,
    # audit-launchd-daily.sh, cron-agent.sh): a live HOME deployment may keep
    # tg_notify.py alongside the wrapper itself; the repo canon is the fallback.
    GATEWAY="$(dirname "$0")/tg_notify.py"
    [ -f "$GATEWAY" ] || GATEWAY="$REPO_ROOT/scripts/tg_notify.py"
    if [ -f "$GATEWAY" ]; then
        # W104: tg_notify.py always returns rc=0 (spool-best-effort) — judge its
        # printed status line, never $?.
        REPLY="$("$SYSTEM_PY" "$GATEWAY" --tier digest --source suite-growth-probe \
            --dedup-key "suite-growth-probe:$(hostname -s):collection-failed" -- "$MSG" 2>&1)"
        log "tg_notify reply: $(printf '%s' "$REPLY" | tr '\n' ' ' | head -c 200)"
    else
        log "ALERT NOT SENT: tg_notify.py gateway missing (looked in $(dirname "$0") and $REPO_ROOT/scripts)"
    fi
else
    log "probe OK record=$RECORD_PATH errors=$ERRORS_COUNT alerts_sent=$ALERTS_COUNT"
fi

exit "$PROBE_RC"
