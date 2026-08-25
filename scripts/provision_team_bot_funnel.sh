#!/bin/bash
# provision_team_bot_funnel.sh — idempotent Tailscale Funnel setup for the
# team-bot Meta webhook ingress (F9, lane B5).
#
# Run ON THE NODE that should be the current ingress front — Mini for the
# primary/default topology, or Pro AFTER a failover promotion
# (team-bot-failoverd calls the WABA override, not this script; this
# script only wires the LOCAL Funnel front, once, on whichever node is
# about to become the public ingress). Not sudo — `tailscale funnel` runs
# as the interactive Tailscale-authenticated user.
#
#   bash scripts/provision_team_bot_funnel.sh [--port PORT]
#
# Verified against the ACTUALLY INSTALLED Tailscale CLI (1.96.5, checked
# empirically on Mini 2026-08-25 via `tailscale serve --help` /
# `tailscale funnel --help`) — NOT copied from
# research/operations/2026-08-25-due-bot-7-lens-research.md's example
# commands (`tailscale serve --bg --set-path / 8000` /
# `tailscale funnel --bg 443 on`), which target an older/different CLI
# syntax this installed version's own --help does not accept. If you run
# this on a node with a materially different Tailscale version, verify
# `tailscale funnel --help` yourself before trusting this script's
# command shape.
#
# SAFETY GATE (the reason this script refuses by default rather than
# just running the two Tailscale commands): `tailscale funnel <port>`
# makes a PUBLIC HTTPS endpoint live IMMEDIATELY, even if nothing is
# listening on the target local port yet. Since apps/team-bot/ (B3's
# file ownership) may not exist or may not be running at the time this
# is invoked, this script REFUSES to enable Funnel unless it can first
# prove something is actually answering on the target port — never
# silently expose a dangling public endpoint.
#
# Idempotent: re-running with the same port is a no-op if Funnel is
# already configured for it (checked via `tailscale funnel status`
# before writing anything).

set -euo pipefail

TARGET_PORT="8765" # F9 §4.2: "local listener: http://127.0.0.1:8765/webhooks/team-wa"
LOCAL_HEALTH_PATH="/livez" # matches TEAM_BOT_FUNNEL_LOCAL_URL's default in failoverd.py

while [ $# -gt 0 ]; do
    case "$1" in
        --port)
            TARGET_PORT="$2"
            shift 2
            ;;
        *)
            echo "unknown argument: $1" >&2
            exit 64 # EX_USAGE
            ;;
    esac
done

log() { echo "[provision-team-bot-funnel] $*"; }

if ! command -v tailscale >/dev/null 2>&1; then
    log "ERROR: tailscale CLI not found on PATH"
    exit 1
fi

if ! tailscale status >/dev/null 2>&1; then
    log "ERROR: tailscale not authenticated on this node (run 'tailscale up' first — operator[gui]/[credential])"
    exit 1
fi

LOCAL_URL="http://127.0.0.1:${TARGET_PORT}${LOCAL_HEALTH_PATH}"
log "safety check: is anything actually listening at ${LOCAL_URL}?"
if ! curl -sf --max-time 5 "${LOCAL_URL}" >/dev/null 2>&1; then
    log "REFUSING: nothing answered ${LOCAL_URL}."
    log "This means apps/team-bot/ (B3) is not deployed/running here yet."
    log "Enabling Funnel now would expose a public HTTPS endpoint with"
    log "nothing behind it — every Meta probe would 502, and (worse) the"
    log "endpoint would sit there dark-but-live with no team-bot code"
    log "watching it. Deploy and start the team-bot app FIRST, then"
    log "re-run this script."
    exit 78 # EX_CONFIG
fi
log "OK — local service answered."

EXISTING_STATUS="$(tailscale funnel status 2>&1 || true)"
if echo "${EXISTING_STATUS}" | grep -q ":${TARGET_PORT}\b"; then
    log "Funnel already configured for port ${TARGET_PORT} — idempotent no-op."
else
    log "enabling Funnel: tailscale funnel --bg ${TARGET_PORT}"
    log "*** THIS MAKES A PUBLIC HTTPS ENDPOINT LIVE ON THE INTERNET NOW. ***"
    tailscale funnel --bg "${TARGET_PORT}"
fi

log "current funnel status:"
tailscale funnel status

FUNNEL_HOST="$(tailscale status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("Self",{}).get("DNSName","").rstrip("."))' 2>/dev/null || true)"
if [ -n "${FUNNEL_HOST}" ]; then
    log "public webhook URL (give this to Meta, owner switchboard item 1):"
    log "  https://${FUNNEL_HOST}/webhooks/team-wa"
else
    log "could not determine this node's DNSName — run 'tailscale status --json' manually to find it"
fi

log "REMAINING OPERATOR STEPS (this script does not, and cannot, do these):"
log "  1. Paste the URL above into Meta's WhatsApp webhook configuration"
log "     (owner switchboard item 1 — operator[gui])."
log "  2. On the Mini->Pro failover path specifically: this script wires"
log "     the LOCAL Funnel front only. The WABA callback override that"
log "     actually re-points Meta's traffic during a failover is"
log "     team-bot-failoverd's job (backend/services/team_bot_ingress/"
log "     failoverd.py), not this script — do not re-run this script as"
log "     part of a failover; it is a one-time-per-node setup step."
