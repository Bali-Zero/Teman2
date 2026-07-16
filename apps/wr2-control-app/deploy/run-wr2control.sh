#!/bin/bash
# run-wr2control.sh — launchd wrapper for the WR2 Control ambient app.
# Genes: G2_heartbeat, G5_kill_switch, G9_fail_visible (audit §6/D2 vendoring, 2026-07-14).
# Canon: apps/wr2-control-app/deploy/run-wr2control.sh (tracked in-repo; the plist
# ProgramArguments point at THIS path, which lives under nuzantara/ — no
# HOME-fork declared-pair required, per infra/organ-conformance's own exemption
# for repo-checkout-resident payloads).
#
# The app itself is a long-lived GUI daemon with no built-in liveness sidecar
# (it was vendored from a pre-genome Desktop copy, audit §6/D2) — this wrapper
# is the minimal honest instrumentation possible without touching the Swift
# source: it proves launch-attempt liveness and honors a kill switch, then
# execs the real binary so launchd's own KeepAlive/SuccessfulExit semantics
# keep tracking the actual app process (not this wrapper).
set -u

ORGAN_ID="${WR2CONTROL_ORGAN_ID:-wr2_control_app}"
SIDECAR_DIR="$HOME/.organism/last_seen"

heartbeat() { # $1 status $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ.
if [ "${WR2CONTROL_ENABLED:-true}" = "false" ]; then
    heartbeat "disabled" "kill switch"
    exit 0
fi

APP_BIN="${1:-}"
shift || true
if [ -z "$APP_BIN" ] || [ ! -x "$APP_BIN" ]; then
    heartbeat "error" "app binary not found or not executable: ${APP_BIN:-<empty>}"
    exit 1
fi

heartbeat "ok" "launching $APP_BIN"
exec "$APP_BIN" "$@"
