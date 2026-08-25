#!/bin/bash
# provision_team_bot_failoverd.sh — one-shot, IDEMPOTENT host preparation
# for team-bot-failoverd on Pro (F9, lane B5).
#
# Run ON PRO, with sudo:   sudo bash scripts/provision_team_bot_failoverd.sh
#
# Modeled directly on scripts/provision_zantara_codex.sh — same layout
# reasoning (fw-guard precedent 2026-08-14: a launchd system-domain
# payload never executes from a user-writable $HOME; the daemon RUNS as
# team-bot-failoverd, so root-owned code denies a compromised identity
# PERSISTENCE across restarts, not privilege it already lacks), scoped
# down: no seat-probe apparatus (that is specific to the codex broker's
# leak-detection design and has no equivalent here).
#
# Layout:
#   /usr/local/libexec/team-bot-failoverd-wrapper.sh   root:wheel 0755
#   /usr/local/lib/team-bot-failoverd/                 root:wheel (code + venv)
#   /Users/team-bot-failoverd/                         0700 — env file, logs ONLY
#
# What it does (each step logs DONE/SKIP; re-running is safe):
#   1. Creates the login-less, hidden user `team-bot-failoverd`.
#   2. Creates its home skeleton (logs/), 0700.
#   3. Installs the daemon runtime (a minimal root-owned `backend` package
#      containing only services/team_bot_ingress/ — the user holds NO
#      repo checkout by design) and the wrapper under /usr/local.
#   4. Builds the root-owned venv and installs httpx + asyncpg.
#   5. Writes the env-file PLACEHOLDER (0600, user-owned) if absent — the
#      operator fills TEAM_BOT_WABA_ACCESS_TOKEN, TEAM_BOT_WABA_ID,
#      TEAM_BOT_FAILOVER_CALLBACK_URI(+_SHA256), TEAM_BOT_WABA_VERIFY_TOKEN,
#      TEAM_BOT_FAILOVER_DATABASE_URL, TEAM_BOT_MINI_READYZ_URL,
#      TEAM_BOT_BACKEND_HEALTH_URL.
#   6. Installs the LaunchDAEMON plist (login-less user => LaunchDaemon
#      with UserName, never a LaunchAgent) and bootstraps it ONLY when
#      the env file has no placeholders left — half-configured is
#      refused, not half-armed (superscar family #2).
#
# What it deliberately does NOT do (operator actions):
#   - Filling any value in the env file (all secrets — Golden Rule #6).
#   - Setting TEAM_BOT_FAILOVER_AUTO_ENABLED=true (stays false/absent —
#     the daemon runs in shadow mode the moment it starts, and stays
#     there until an explicit operator decision, per F9 and
#     KILL-SWITCHES.md).

set -euo pipefail

DAEMON_USER="team-bot-failoverd"
DAEMON_HOME="/Users/${DAEMON_USER}"
RUNTIME_DIR="/usr/local/lib/team-bot-failoverd"
WRAPPER_DST="/usr/local/libexec/team-bot-failoverd-wrapper.sh"
ENV_FILE="${DAEMON_HOME}/.team-bot-failoverd.env"
PLIST_LABEL="com.balizero.team-bot-failoverd"
PLIST_DST="/Library/LaunchDaemons/${PLIST_LABEL}.plist"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_SRC="${REPO_ROOT}/apps/backend-rag/backend"
WRAPPER_SRC="${REPO_ROOT}/infra/launchagents/wrappers/team-bot-failoverd-wrapper.sh"
PLIST_SRC="${REPO_ROOT}/infra/launchagents/${PLIST_LABEL}.plist"

log() { echo "[provision-team-bot-failoverd] $*"; }

if [ "$(id -u)" -ne 0 ]; then
    log "ERROR: must run as root (sudo bash scripts/provision_team_bot_failoverd.sh)"
    exit 1
fi
for src in "${BACKEND_SRC}/services/team_bot_ingress/ingress_leader.py" \
    "${BACKEND_SRC}/services/team_bot_ingress/failoverd.py" "${WRAPPER_SRC}" "${PLIST_SRC}"; do
    if [ ! -f "${src}" ]; then
        log "ERROR: expected source file missing: ${src}"
        exit 1
    fi
done

# 1. login-less user
if id "${DAEMON_USER}" >/dev/null 2>&1; then
    log "user ${DAEMON_USER} already exists — SKIP"
else
    log "creating login-less user ${DAEMON_USER}"
    NEXT_UID=$(dscl . -list /Users UniqueID | awk '{print $2}' | sort -n | tail -1 | awk '{print $1+1}')
    dscl . -create "/Users/${DAEMON_USER}"
    dscl . -create "/Users/${DAEMON_USER}" UserShell /usr/bin/false
    dscl . -create "/Users/${DAEMON_USER}" UniqueID "${NEXT_UID}"
    dscl . -create "/Users/${DAEMON_USER}" PrimaryGroupID 20
    dscl . -create "/Users/${DAEMON_USER}" NFSHomeDirectory "${DAEMON_HOME}"
    dscl . -create "/Users/${DAEMON_USER}" IsHidden 1
    log "DONE: user created (uid=${NEXT_UID})"
fi

# 2. home skeleton
mkdir -p "${DAEMON_HOME}/logs"
chown -R "${DAEMON_USER}:staff" "${DAEMON_HOME}"
chmod 700 "${DAEMON_HOME}"
log "DONE: home skeleton at ${DAEMON_HOME}"

# 3. runtime code (root-owned, fresh copy every run — never a symlink to
#    the repo, per superscar family #1: the daemon's payload must be a
#    declared, independently-updated copy, not a live link into a
#    developer's working tree)
mkdir -p "${RUNTIME_DIR}/backend/services/team_bot_ingress"
cp "${BACKEND_SRC}/services/team_bot_ingress/"*.py "${RUNTIME_DIR}/backend/services/team_bot_ingress/"
touch "${RUNTIME_DIR}/backend/__init__.py" "${RUNTIME_DIR}/backend/services/__init__.py"
chown -R root:wheel "${RUNTIME_DIR}"
install -m 0755 -o root -g wheel "${WRAPPER_SRC}" "${WRAPPER_DST}"
log "DONE: runtime + wrapper installed"

# 4. venv
if [ ! -x "${RUNTIME_DIR}/.venv/bin/python3" ]; then
    log "building venv at ${RUNTIME_DIR}/.venv"
    python3 -m venv "${RUNTIME_DIR}/.venv"
    "${RUNTIME_DIR}/.venv/bin/pip" install --quiet httpx asyncpg
    chown -R root:wheel "${RUNTIME_DIR}/.venv"
    log "DONE: venv built"
else
    log "venv already present — SKIP"
fi

# 5. env-file placeholder
if [ ! -f "${ENV_FILE}" ]; then
    log "writing env-file placeholder ${ENV_FILE}"
    cat > "${ENV_FILE}" <<'ENVEOF'
TEAM_BOT_FAILOVER_NODE_ID=pro
TEAM_BOT_WABA_ID=__FILL_ME__
TEAM_BOT_FAILOVER_CALLBACK_URI=__FILL_ME__
TEAM_BOT_FAILOVER_CALLBACK_URI_SHA256=__FILL_ME__
TEAM_BOT_WABA_VERIFY_TOKEN=__FILL_ME__
TEAM_BOT_WABA_ACCESS_TOKEN=__FILL_ME__
TEAM_BOT_FAILOVER_DATABASE_URL=__FILL_ME__
TEAM_BOT_MINI_READYZ_URL=__FILL_ME__
TEAM_BOT_MINI_TAILSCALE_HOSTNAME=Mini-Pro2
TEAM_BOT_BACKEND_HEALTH_URL=__FILL_ME__
TEAM_BOT_FUNNEL_LOCAL_URL=http://127.0.0.1:8765/livez
TEAM_BOT_FAILOVER_POLL_SECONDS=5.0
TEAM_BOT_FAILOVER_AUTO_ENABLED=false
TEAM_BOT_FAILOVERD_PROCESS_ENABLED=true
ENVEOF
    chown "${DAEMON_USER}:staff" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    log "DONE: env-file placeholder written — operator must fill __FILL_ME__ values"
else
    log "env file already present — SKIP (not overwriting operator-filled values)"
fi

# 6. LaunchDaemon — bootstrap ONLY when fully configured
install -m 0644 -o root -g wheel "${PLIST_SRC}" "${PLIST_DST}"
if grep -q "__FILL_ME__" "${ENV_FILE}"; then
    log "env file still has __FILL_ME__ placeholders — plist installed but NOT bootstrapped"
    log "fill the env file, then: sudo launchctl bootstrap system ${PLIST_DST}"
else
    log "env file fully configured — bootstrapping ${PLIST_LABEL}"
    launchctl bootstrap system "${PLIST_DST}" 2>/dev/null || log "already bootstrapped — SKIP"
    log "DONE: ${PLIST_LABEL} bootstrapped"
fi

log "provisioning complete. TEAM_BOT_FAILOVER_AUTO_ENABLED=false by default —"
log "the daemon runs in SHADOW mode until an explicit operator decision."
