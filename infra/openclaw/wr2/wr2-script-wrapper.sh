#!/bin/bash
# wr2-script-wrapper.sh — runs a standalone scripts/wr2_*.py script
# (not a backend module). Complements wr2-cron-wrapper.sh (which is for
# `python -m backend.xxx` modules).
#
# Usage (from a plist):
#   <array>
#     <string>/Users/nuzantara/.openclaw/bin/wr2/wr2-script-wrapper.sh</string>
#     <string>scripts/wr2_image_generator.py</string>
#     <string>--arg1</string>
#   </array>
#
# Responsibilities:
#   1. Source ~/.nuzantara-secrets.env for Telegram + AWS Tigris + misc
#   2. Resolve DATABASE_URL from DATABASE_URL_LOCAL (requires pg-proxy)
#   3. cd into repo root, activate apps/backend-rag/.venv, exec python <script>
#
# Fails loud (non-zero exit) on any missing piece.

set -euo pipefail

# ── Voice: alert on ANY non-zero exit (2026-08-06) ──────────────────────────
# The sibling `wr2-cron-wrapper.sh` got this on 2026-08-06 and this file did
# not, which is W107 with the names swapped: curing one wrapper of a pair does
# not cut the risk, it only moves which cohort dies quietly. Measured before
# writing this: eight LaunchAgents run through here — daily-metrics,
# draft-generator, fact-checker, fact-extractor, image-generator, supervisor,
# supervisor-watchdog, topic-selector — against nine on the cured sibling. The
# smaller half was the one with a voice.
#
# Two independent mechanisms kept these eight mute:
#
#   1. EIGHT silent exits — usage 64, DATABASE_URL_LOCAL unset 74, pg-proxy
#      unreachable 74, script not found 66 (armed-at-nothing, W81), and four
#      distinct `exit 75` in the venv auto-heal. None said anything to anyone.
#
#   2. The final `exec` REPLACED this shell, so the script's own failure never
#      returned here at all. That is the one that matters most: it is the
#      normal way these jobs fail.
#
# The pre-existing Telegram call is folded in here rather than left beside it.
# It was a raw `curl … || true` reachable only from the venv-missing branch,
# so it bypassed tier, budget and dedup entirely, and in launchd's token-poor
# environment it did nothing AND left no trace of doing nothing (W108). It
# also carried its own 1h cooldown state file, duplicating — worse — what the
# gateway's repeat ladder already does. Routing it through the gateway is a
# reduction in message volume, not an addition: two of these eight
# (supervisor, supervisor-watchdog) restart on failure, and a flapping job now
# collapses to ONE alert per 6/24/72/168h window instead of one per restart.
#
# The interpreter is ABSOLUTE and system, never "$VENV_PY" and never a bare
# `python3`. W108: this wrapper's whole job is to find and repair a venv, so a
# PATH-resolved python3 could be the very interpreter whose breakage it must
# report on. An alarm that shares the failure mode of what it reports is not
# an alarm.
#
# Fail-open by construction: the exit code is the contract this wrapper exists
# to preserve. The trap re-exits with the code it was handed, never its own.
WR2_STAGE="startup"
SCRIPT_ID="<none>"
_wr2_alerted=0

# Gateway resolution lives in ONE function, consulted by both the failure trap
# and the venv notice. Two callers that must agree on "where is the gateway"
# do not get to invent two answers (W106b: the asymmetry between twins is what
# hides the defect in one of them).
#
# WR2_REPO_ROOT leads the list on purpose. The first draft started at
# $REPO_ROOT, which is assigned ~30 lines BELOW — so on the usage exit, the
# earliest failure there is, the trap resolved nothing and stayed mute. The
# corpus caught it. A trap can fire from anywhere and must not depend on how
# far execution got; every input it reads has to be available at line one.
_wr2_gateway() {
    local root
    for root in "${WR2_REPO_ROOT:-}" "${REPO_ROOT:-}" "$HOME/nuzantara-deploy" "$HOME/nuzantara"; do
        [[ -n "$root" && -f "$root/scripts/tg_notify.py" ]] || continue
        printf '%s' "$root/scripts/tg_notify.py"
        return 0
    done
    return 1
}

_wr2_alert_exit() {
    local rc="$1"
    [[ "$rc" -eq 0 ]] && return 0
    [[ "${WR2_CRON_ALERT:-true}" == "false" ]] && return 0
    [[ "$_wr2_alerted" -eq 1 ]] && return 0   # a trap must not re-enter itself
    _wr2_alerted=1
    local gateway py key
    gateway="$(_wr2_gateway)" || return 0
    # The key names the CONDITION (script + stage), never a measurement: an
    # exit code or a duration in the key would mint a fresh one per failure
    # and defeat every window — the defect #3677 cured at the sentinel.
    key="cron-fail:wr2.${SCRIPT_ID}.${WR2_STAGE}"
    for py in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        [[ -x "$py" ]] || continue
        "$py" "$gateway" \
            --tier p0 \
            --source "wr2:${SCRIPT_ID}" \
            --dedup-key "$key" \
            -- "CRON FAIL $(hostname -s 2>/dev/null || echo '?')
Job: wr2 ${SCRIPT_ID}
Stage: ${WR2_STAGE}
Exit: ${rc}
Script: ${FULL_SCRIPT:-${SCRIPT_PATH:-<unresolved>}}" >/dev/null 2>&1 || true
        return 0
    done
    return 0
}
trap '_wr2_alert_exit $?' EXIT

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <script-relative-path> [args...]" >&2
    exit 64
fi

SCRIPT_PATH="$1"
shift

# Identity for the alert: the script's basename without .py, so
# `scripts/wr2_image_generator.py` reports as `wr2_image_generator`. Derived
# once, here, rather than at the alert site — the trap can fire from anywhere
# below and must never depend on how far execution got.
SCRIPT_ID="$(basename "$SCRIPT_PATH" .py)"

# 2026-05-06: switched from ~/nuzantara (multi-agent collision zone)
# to dedicated git worktree ~/nuzantara-deploy on branch deploy/main.
# The main repo at ~/nuzantara is shared by 3+ Claude/Codex sessions
# that toggle branches every 1-3 min — production cron must read from a stable
# worktree pinned to origin/main, never feature branches.
# To update: `cd ~/nuzantara-deploy && git pull origin main`.
REPO_ROOT="${WR2_REPO_ROOT:-${HOME}/nuzantara-deploy}"
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"

# 0. PATH — launchd hands this wrapper a minimal PATH (no /opt/homebrew/bin).
# wr2_image_generator.py's Codex lane execs CODEX_BIN="/opt/homebrew/bin/codex"
# directly (absolute path, so it launches), but that file's shebang is
# `#!/usr/bin/env node` — `env` resolves `node` via PATH, which launchd never
# populates with Homebrew's prefix. Result: "codex exit=127: env: node: No
# such file or directory", indistinguishable from a Codex quota-exhaust
# failure unless you inspect the exact error text. Same signature already
# cured in scripts/auth_sentinel_cron.sh (2026-07-12) but never propagated to
# this sibling wrapper — found 2026-07-22 diagnosing a stuck WR2 cover image.
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

# 1. Secrets — source primary then backend-specific (additive)
if [[ -f "$SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$SECRETS_FILE"
    set +a
fi

# 1b. Backend-specific secrets (JWT_SECRET_KEY, OPENAI_API_KEY, API_KEYS)
# These are required by apps/backend-rag/backend/app/core/config.py
# Pydantic Settings validators. Without them, scripts importing backend
# modules emit WARNINGs and fall back to noop config (no LLM cost
# recorder, no auth checks).
BACKEND_SECRETS_FILE="${HOME}/.nuzantara-backend-secrets.env"
if [[ -f "$BACKEND_SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$BACKEND_SECRETS_FILE"
    set +a
fi

# 2. DATABASE_URL — FORCE-override to LOCAL (pg-proxy on 127.0.0.1:15432).
# Why: ~/.nuzantara-secrets.env defines DATABASE_URL=postgres://...@nuzantara-postgres.flycast
# (Fly 6PN internal hostname — only resolves *inside* Fly). When sourced on Pro,
# DATABASE_URL is set but unusable; supervisor would emit "errno 8 nodename nor
# servname" forever. Always pin DATABASE_URL_LOCAL on Pro/Mini regardless of
# whatever the secrets file pre-set. Bug discovered 2026-05-06 (supervisor in
# reconnect-loop since 2026-04-30 17:31).
WR2_STAGE="guard"
if [[ -z "${DATABASE_URL_LOCAL:-}" ]]; then
    echo "[wr2-script-wrapper] ERROR: DATABASE_URL_LOCAL not set in $SECRETS_FILE" >&2
    exit 74
fi
DATABASE_URL="$DATABASE_URL_LOCAL"
export DATABASE_URL

# Sanity check: pg-proxy listening?
if ! nc -z 127.0.0.1 15432 2>/dev/null; then
    echo "[wr2-script-wrapper] ERROR: 127.0.0.1:15432 unreachable (is com.balizero.wr2.pg-proxy loaded?)" >&2
    exit 74
fi

# 3. Resolve script path
WR2_STAGE="script"
FULL_SCRIPT="$REPO_ROOT/$SCRIPT_PATH"
if [[ ! -f "$FULL_SCRIPT" ]]; then
    echo "[wr2-script-wrapper] ERROR: script not found: $FULL_SCRIPT" >&2
    exit 66
fi

# 4. Repo + venv + exec
cd "$REPO_ROOT"
VENV_DIR="$REPO_ROOT/apps/backend-rag/.venv"
VENV_PY="$VENV_DIR/bin/python"
REQ_FILE="$REPO_ROOT/apps/backend-rag/requirements-prod.txt"

# W81b (2026-06-23): the old preflight only checked that the venv PYTHON exists
# (`-x`). But a venv-SKELETON — python present, site-packages evaporated by a
# deploy-worktree re-add — passed that check and crashed at `import asyncpg`
# (ModuleNotFoundError, supervisor down ~3 days, 20→23 Jun). Probe the real import.
WR2_STAGE="venv"
VENV_BROKEN=0
if [[ -x "$VENV_PY" ]]; then
    "$VENV_PY" -c "import asyncpg" >/dev/null 2>&1 || VENV_BROKEN=1
fi

# Venv-preflight (Wave 1 fix 2026-05-19, 4-LLM panel synthesis 3/3 quorum):
# A missing venv on the deploy worktree caused the WR2 supervisor to
# crashloop silently for 84h (2026-05-16 03:32 → 2026-05-19 09:44),
# accumulating 27,227 error lines in `wr2_supervisor_watchdog.launchd.err.log`
# and 1.2 MB in `wr2_supervisor.launchd.err.log`. The events_outbox
# design saved us from data loss (7 missed `wr2_status_change` events
# auto-replayed on recovery), but 4 days of pipeline downtime are
# unacceptable for a solo-dev operation.
#
# Mitigation: auto-heal + Telegram alert IN THIS WRAPPER.
# Flow:
#   - If venv exists: fast-path exec (zero overhead).
#   - If venv missing: alert Telegram (cooldown 1h), attempt auto-heal
#     via `python -m venv` + `pip install -r requirements-prod.txt`
#     (3-5 min). If auto-heal fails: hard exit 75 (same as before,
#     preserves audit trail + KeepAlive restart cycle).
#
# Reference: research/operations/2026-05-19-wr2-intel-lake-fixes-panel.md
if [[ ! -x "$VENV_PY" || "$VENV_BROKEN" == "1" ]]; then
    NOW=$(date '+%Y-%m-%d %H:%M:%S WITA')
    echo "[wr2-script-wrapper] WARN ${NOW}: venv Python missing at $VENV_PY — attempting auto-heal" >&2

    # The venv-missing notice, on the gateway.
    #
    # It used to be a raw `curl … || true` behind a hand-rolled 1h cooldown
    # state file. Three things were wrong with that and all three are why the
    # cooldown is gone rather than kept: the curl needed TELEGRAM_BOT_TOKEN in
    # the environment, which launchd does not provide, so it silently did
    # nothing and left no record of having done nothing (W108); it bypassed
    # tier, p0 budget and the dedup ladder, so it could not be reasoned about
    # alongside every other alert; and its 1h window was both narrower and
    # dumber than the gateway's 6/24/72/168h escalation. Note this notice is
    # deliberately NOT the failure trap — the auto-heal may well succeed, so
    # this is `digest` tier, and only a FAILED heal exits non-zero and reaches
    # the p0 trap above.
    _wr2_venv_notice() {
        local gateway py
        gateway="$(_wr2_gateway)" || return 0
        for py in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
            [[ -x "$py" ]] || continue
            "$py" "$gateway" \
                --tier digest \
                --source "wr2:${SCRIPT_ID}" \
                --dedup-key "wr2-venv-missing.${SCRIPT_ID}" \
                -- "WR2 venv missing at ${VENV_DIR} — auto-heal attempted (${NOW})" \
                >/dev/null 2>&1 || true
            return 0
        done
        return 0
    }
    _wr2_venv_notice

    # Auto-heal: create venv + pip install
    PYENV_PY311="${HOME}/.pyenv/versions/3.11.11/bin/python"
    if [[ ! -x "$PYENV_PY311" ]]; then
        echo "[wr2-script-wrapper] ERROR: pyenv Python 3.11.11 not found at $PYENV_PY311" >&2
        exit 75
    fi

    if "$PYENV_PY311" -m venv "$VENV_DIR" 2>&1; then
        echo "[wr2-script-wrapper] auto-heal: venv created at $VENV_DIR" >&2
        if [[ ! -f "$REQ_FILE" ]]; then
            echo "[wr2-script-wrapper] ERROR: requirements-prod.txt not found at $REQ_FILE" >&2
            exit 75
        fi
        echo "[wr2-script-wrapper] auto-heal: installing $REQ_FILE (this may take 3-5 min)" >&2
        if "$VENV_PY" -m pip install --quiet --upgrade pip >&2 \
           && "$VENV_PY" -m pip install --quiet -r "$REQ_FILE" >&2; then
            echo "[wr2-script-wrapper] auto-heal: pip install completed, resuming exec" >&2
        else
            echo "[wr2-script-wrapper] ERROR: auto-heal pip install failed — manual fix required" >&2
            exit 75
        fi
    else
        echo "[wr2-script-wrapper] ERROR: auto-heal venv creation failed — manual fix required" >&2
        exit 75
    fi
fi

# Run-and-judge, not `exec`. This line used to be `exec "$VENV_PY" …`, which
# replaced this shell with the script — so the EXIT trap above could never
# fire for the way these jobs actually fail. errexit is disarmed around the
# run and the verdict is the CAPTURED code, never survival (W101/W108).
WR2_STAGE="job"
set +e
"$VENV_PY" "$FULL_SCRIPT" "$@"
SCRIPT_RC=$?
set -e
exit $SCRIPT_RC
