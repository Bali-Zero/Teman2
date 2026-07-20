#!/usr/bin/env bash
# verify_home_bridge_sync.sh — HOME-bridge sync antibody (cicatrix family W50/W51/W52).
#
# THE INVARIANT THIS GUARDS
# -------------------------
# The LIVE WhatsApp bridge does NOT run from the git checkout. It runs from a
# HOME copy:
#       ~/.openclaw/bin/openclaw_whatsapp_bridge.py     (prod, NOT git-tracked)
# launched by LaunchAgent  com.nuzantara.openclaw-whatsapp-bridge.
# The git-tracked source of truth is:
#       scripts/openclaw_whatsapp_bridge.py             (on origin/main)
#
# The two are supposed to be byte-identical. But nothing enforced that — they can
# diverge IN SILENCE. This bit us (the W50/W51/W52 scar family): a fix that
# touches only scripts/ is INVISIBLE to prod until someone re-copies it into HOME;
# and conversely a hand-patch applied to the HOME copy never lands in git, so the
# repo's "source of truth" is a lie.
#
# The danger is doubled because the WhatsApp safety guards
# (property-zoning / nominee / villa — commits F05 / F06 / F13) live in this file.
# If HOME drifts from tracked, then either:
#   - prod runs WITHOUT the guards the repo thinks are deployed, OR
#   - prod runs guards DIFFERENT from what the repo says is shipped.
# Both are dangerous, and both were until now completely undetectable.
#
# THIS SCRIPT is the antibody: it compares the git blob hash of the live HOME
# copy against the blob hash of scripts/openclaw_whatsapp_bridge.py ON ORIGIN/MAIN
# (origin/main is ground truth — deliberately NOT the local checkout, which can be
# stale by dozens of commits). If they match → healthy. If they diverge → exit 1,
# print both hashes + a diff summary, and (if Telegram creds are configured, same
# pattern as the other sentinel scripts) fire a DRIFT alert.
#
# DRIFT RESOLUTION IS ONE-DIRECTIONAL: origin/main -> HOME, NEVER the reverse.
# See docs/runbooks/home-bridge-sync.md.
#
# Usage:
#   verify_home_bridge_sync.sh           # check; exit 0 = sync, 1 = DRIFT, 0+WARN = no HOME copy
#   FORCE_ALERT=1 verify_home_bridge_sync.sh   # exercise the Telegram path (self-test)
#
# Kill switch: env HOME_BRIDGE_SYNC_OFF=1 → exits 0 immediately.
#
# Scheduling: meant to run via launchd ~every 30min. The plist is an OPERATOR
# step (this script does NOT install it) — see the runbook.

set -uo pipefail

# --- Kill switch -----------------------------------------------------------

if [[ "${HOME_BRIDGE_SYNC_OFF:-0}" == "1" ]]; then
    echo "verify_home_bridge_sync: disabled via HOME_BRIDGE_SYNC_OFF=1" >&2
    exit 0
fi

# --- launchd robustness: minimal PATH, absolute tool paths -----------------
# launchd hands us a bare environment. Resolve git with an absolute path and a
# sane PATH so the script behaves identically under cron/launchd and an
# interactive shell.
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:${PATH:-}"

GIT_BIN="/usr/bin/git"
[[ -x "$GIT_BIN" ]] || GIT_BIN="$(command -v git || echo git)"

# --- Configuration ---------------------------------------------------------

REPO_ROOT="${NUZ_REPO_ROOT:-$HOME/nuzantara}"
HOME_BRIDGE="$HOME/.openclaw/bin/openclaw_whatsapp_bridge.py"
TRACKED_PATH="scripts/openclaw_whatsapp_bridge.py"
GROUND_TRUTH_REF="origin/main"

LOG_FILE="$HOME/logs/home-bridge-sync.log"

# Source secrets (TELEGRAM_BOT_TOKEN + chat id). NEVER hardcode the token.
# Same pattern as scripts/cost_breaker_deadman.sh / disk_watchdog.sh.
if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${BALIZEROBOT_TOKEN:-}}"
TELEGRAM_CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ADMIN_CHAT_ID:-${TELEGRAM_CHAT_ID:-1125336968}}}"

# --- Helpers ---------------------------------------------------------------

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

log() {
    local msg
    msg="[$(date '+%Y-%m-%dT%H:%M:%S%z')] $*"
    echo "$msg"
    echo "$msg" >>"$LOG_FILE" 2>/dev/null || true
}

tg_alert() {
    local text="$1"
    if [[ -z "$TELEGRAM_BOT_TOKEN" || -z "$TELEGRAM_CHAT_ID" ]]; then
        log "telegram: missing creds (token or chat_id), skipping alert"
        return 1
    fi
    curl -sS -m 10 -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${text}" \
        -d "parse_mode=HTML" \
        -o /dev/null \
        || log "telegram: post failed"
}

# --- Main ------------------------------------------------------------------

main() {
    if [[ ! -d "$REPO_ROOT/.git" && ! -f "$REPO_ROOT/.git" ]]; then
        log "ERROR: repo root not a git repo: $REPO_ROOT"
        exit 1
    fi

    # Case: HOME copy absent → this machine simply has no bridge installed
    # (e.g. Mini). That is NOT a drift — it is a non-event. Warn and pass.
    if [[ ! -f "$HOME_BRIDGE" ]]; then
        log "WARN: HOME bridge not present ($HOME_BRIDGE) — no bridge installed on this machine, nothing to sync"
        exit 0
    fi

    # Hash of the LIVE HOME copy (git blob hash — same algo git uses, so it is
    # directly comparable to a tracked blob hash).
    local home_hash
    home_hash="$("$GIT_BIN" hash-object "$HOME_BRIDGE" 2>/dev/null)"
    if [[ -z "$home_hash" ]]; then
        log "ERROR: could not hash HOME bridge ($HOME_BRIDGE)"
        exit 1
    fi

    # Ground-truth blob hash from origin/main (NOT the local checkout). Refresh
    # the remote ref first so we compare against what is actually on origin/main,
    # not a stale fetch. Failure to fetch is non-fatal — fall back to the cached
    # remote-tracking ref (better a slightly stale ground truth than none).
    "$GIT_BIN" -C "$REPO_ROOT" fetch origin main --quiet 2>/dev/null \
        || log "WARN: 'git fetch origin main' failed — comparing against cached $GROUND_TRUTH_REF ref"

    local tracked_hash
    tracked_hash="$("$GIT_BIN" -C "$REPO_ROOT" rev-parse "${GROUND_TRUTH_REF}:${TRACKED_PATH}" 2>/dev/null)"
    if [[ -z "$tracked_hash" ]]; then
        log "ERROR: could not resolve ${GROUND_TRUTH_REF}:${TRACKED_PATH} — is origin/main fetched?"
        exit 1
    fi

    # --- Verdict -----------------------------------------------------------

    if [[ "$home_hash" == "$tracked_hash" && "${FORCE_ALERT:-0}" != "1" ]]; then
        log "OK: HOME bridge in sync with ${GROUND_TRUTH_REF} (blob ${home_hash})"
        exit 0
    fi

    # DRIFT (or forced self-test). Compute a diff summary against the tracked
    # blob. We materialise the origin/main blob to a temp file and diff line
    # counts — purely informational, never mutating either side.
    local tmp diff_summary="(diff unavailable)"
    tmp="$(mktemp -t home_bridge_truth.XXXXXX 2>/dev/null || echo "")"
    if [[ -n "$tmp" ]] && "$GIT_BIN" -C "$REPO_ROOT" cat-file blob "$tracked_hash" >"$tmp" 2>/dev/null; then
        # diff exit code is 1 when files differ; capture changed-line count.
        local added removed
        added="$(diff "$tmp" "$HOME_BRIDGE" 2>/dev/null | grep -c '^>' || true)"
        removed="$(diff "$tmp" "$HOME_BRIDGE" 2>/dev/null | grep -c '^<' || true)"
        diff_summary="HOME has ${added} line(s) not in ${GROUND_TRUTH_REF}, missing ${removed} line(s) present in ${GROUND_TRUTH_REF}"
        rm -f "$tmp"
    fi

    if [[ "${FORCE_ALERT:-0}" == "1" && "$home_hash" == "$tracked_hash" ]]; then
        log "SELF-TEST (FORCE_ALERT=1): hashes actually MATCH (${home_hash}); exercising alert path only"
    fi

    log "DRIFT: HOME bridge != ${GROUND_TRUTH_REF}"
    log "  HOME blob    : ${home_hash}  ($HOME_BRIDGE)"
    log "  origin/main  : ${tracked_hash}  (${TRACKED_PATH})"
    log "  diff         : ${diff_summary}"
    log "  RESOLUTION   : re-copy ${GROUND_TRUTH_REF}:${TRACKED_PATH} -> HOME, then restart LaunchAgent com.nuzantara.openclaw-whatsapp-bridge (NEVER the reverse). See docs/runbooks/home-bridge-sync.md"

    tg_alert "⚠️ HOME bridge DRIFT vs origin/main
HOME blob: <code>${home_hash}</code>
origin/main: <code>${tracked_hash}</code>
${diff_summary}
Fix: re-copy origin/main:${TRACKED_PATH} → HOME + restart LaunchAgent (runbook: home-bridge-sync.md). NEVER copy HOME→repo."

    exit 1
}

main "$@"
