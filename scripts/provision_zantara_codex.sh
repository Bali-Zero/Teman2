#!/bin/bash
# provision_zantara_codex.sh — one-shot, IDEMPOTENT host preparation for the
# WA codex broker daemon on Pro (BOT-V4 S2 PR-6; spec §4.1/§4.3,
# research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md).
#
# Run ON PRO, with sudo:   sudo bash scripts/provision_zantara_codex.sh
#
# Layout (fw-guard precedent 2026-08-14 — a launchd system-domain payload
# never executes from a user-writable $HOME; the daemon RUNS as
# zantara-codex, so root-owned code denies a compromised identity
# PERSISTENCE across restarts, not privilege it already lacks):
#   /usr/local/libexec/wa-codex-broker-wrapper.sh   root:wheel 0755
#   /usr/local/lib/wa-codex-broker/                 root:wheel (code + venv)
#   /Users/zantara-codex/                           0700 — env file, logs,
#                                                   CODEX_HOME, sidecar,
#                                                   canary files ONLY
#
# What it does (each step logs DONE/SKIP; re-running is safe):
#   1. Creates the login-less, hidden user `zantara-codex`.
#   2. Creates its home skeleton (logs/ .codex/), 0700.
#   3. Installs the daemon runtime (wa_codex_daemon.py + codex_exec_client.py
#      as a minimal root-owned `backend` package — the user holds NO repo
#      checkout by design) and the wrapper under /usr/local.
#   4. Builds the root-owned venv and installs httpx.
#   5. Writes the env-file PLACEHOLDER (0600, user-owned) if absent — the
#      operator fills WA_BROKER_KEY and WA_CODEX_CLI_VERSION_PIN.
#   6. Plants canary FILES in the sandbox (spec §4.3 leak tripwires) and
#      records their values in a root-only file; the SAME values must reach
#      Fly as WA_CODEX_CANARY_TOKENS (via `fly secrets import` reading the
#      file on stdin — the values never touch argv or shell history).
#   7. Installs the LaunchDAEMON plist (login-less user => LaunchDaemon with
#      UserName, never a LaunchAgent) and bootstraps it ONLY when the env
#      file has no placeholders left — half-configured is refused, not
#      half-armed (superscar #2).
#
# What it deliberately does NOT do (spec §Solo-operatore — operator actions):
#   - `codex login` as zantara-codex (one-time device-code flow):
#         sudo -u zantara-codex CODEX_HOME=/Users/zantara-codex/.codex codex login
#   - Filling WA_BROKER_KEY / WA_CODEX_CLI_VERSION_PIN in the env file.
#   - `fly secrets import` of the canary record on nuzantara-rag.
#
# Interpreter note (declared): the venv is built from whatever `python3`
# resolves to for root at run time (Pro measured 3.11.15, 2026-08-19). The
# daemon needs only stdlib + httpx; pin the interpreter here if that ever
# stops being true.

set -euo pipefail

BROKER_USER="zantara-codex"
BROKER_HOME="/Users/${BROKER_USER}"
RUNTIME_DIR="/usr/local/lib/wa-codex-broker"
WRAPPER_DST="/usr/local/libexec/wa-codex-broker-wrapper.sh"
ENV_FILE="${BROKER_HOME}/.wa-codex-broker.env"
CANARY_RECORD="/var/root/wa-codex-canaries.txt"
PLIST_LABEL="com.balizero.wa-codex-broker"
PLIST_DST="/Library/LaunchDaemons/${PLIST_LABEL}.plist"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_SRC="${REPO_ROOT}/apps/backend-rag/backend"
WRAPPER_SRC="${REPO_ROOT}/infra/launchagents/wrappers/wa-codex-broker-wrapper.sh"
PLIST_SRC="${REPO_ROOT}/infra/launchagents/${PLIST_LABEL}.plist"

log() { echo "[provision-zantara-codex] $*"; }

if [ "$(id -u)" -ne 0 ]; then
    log "ERROR: must run as root (sudo bash scripts/provision_zantara_codex.sh)"
    exit 1
fi
for src in "${BACKEND_SRC}/services/integrations/wa_codex_daemon.py" \
    "${BACKEND_SRC}/llm/codex_exec_client.py" "${WRAPPER_SRC}" "${PLIST_SRC}"; do
    if [ ! -f "$src" ]; then
        log "ERROR: source file missing: $src (run from a current repo checkout)"
        exit 1
    fi
done

# --- 1. user -----------------------------------------------------------
if id "${BROKER_USER}" >/dev/null 2>&1; then
    log "user ${BROKER_USER}: SKIP (exists)"
else
    sysadminctl -addUser "${BROKER_USER}" \
        -fullName "Zantara Codex Broker" \
        -home "${BROKER_HOME}" \
        -shell /usr/bin/false
    dscl . -create "/Users/${BROKER_USER}" IsHidden 1
    log "user ${BROKER_USER}: DONE (login-less, hidden)"
fi
if [ ! -d "${BROKER_HOME}" ]; then
    createhomedir -c -u "${BROKER_USER}" >/dev/null
    log "homedir: DONE"
fi

# --- 2. home skeleton (user-writable state ONLY) --------------------------
for dir in logs .codex; do
    install -d -o "${BROKER_USER}" -g staff -m 0700 "${BROKER_HOME}/${dir}"
done
chmod 0700 "${BROKER_HOME}"
log "home skeleton: DONE"

# --- 3. runtime code + wrapper — ROOT-OWNED, fresh copy every run (the ---
# --- merge alone never updates a live copy — superscar #1)             ---
PKG="${RUNTIME_DIR}/backend"
install -d -o root -g wheel -m 0755 /usr/local/libexec "${RUNTIME_DIR}" \
    "${PKG}" "${PKG}/llm" "${PKG}/services" "${PKG}/services/integrations"
for init in "${PKG}/__init__.py" "${PKG}/llm/__init__.py" \
    "${PKG}/services/__init__.py" "${PKG}/services/integrations/__init__.py"; do
    [ -f "$init" ] || { touch "$init"; chown root:wheel "$init"; chmod 0644 "$init"; }
done
install -o root -g wheel -m 0644 \
    "${BACKEND_SRC}/llm/codex_exec_client.py" "${PKG}/llm/codex_exec_client.py"
install -o root -g wheel -m 0644 \
    "${BACKEND_SRC}/services/integrations/wa_codex_daemon.py" \
    "${PKG}/services/integrations/wa_codex_daemon.py"
install -o root -g wheel -m 0755 "${WRAPPER_SRC}" "${WRAPPER_DST}"
log "runtime code + wrapper: DONE (root-owned, from repo @ $(cd "${REPO_ROOT}" && git rev-parse --short HEAD 2>/dev/null || echo 'no-git'))"

# --- 4. venv (root-owned; the user only executes it) -----------------------
VENV="${RUNTIME_DIR}/.venv"
if [ -x "${VENV}/bin/python3" ]; then
    log "venv: SKIP (exists)"
else
    python3 -m venv "${VENV}"
    log "venv: DONE"
fi
set +e
"${VENV}/bin/pip" install --quiet "httpx>=0.27"
PIP_RC=$?
set -e
if [ "${PIP_RC}" -ne 0 ]; then
    log "ERROR: pip install httpx failed (rc=${PIP_RC}) — daemon cannot run without it"
    exit 1
fi
log "venv deps (httpx): DONE"

# --- 5. env file placeholder ---------------------------------------------
if [ -f "${ENV_FILE}" ]; then
    log "env file: SKIP (exists — never overwritten)"
else
    umask 077
    cat > "${ENV_FILE}" <<'ENVEOF'
# wa-codex-broker daemon config — read by wa-codex-broker-wrapper.sh.
# 0600, owner zantara-codex. WA_BROKER_KEY is a secret: never echo this
# file, never put the key on argv (superscar #4 / W115).
WA_BROKER_BASE_URL=https://nuzantara-rag.fly.dev
WA_BROKER_KEY=__FILL_ME__
# Bare semver the installed codex CLI must report (chaos row 8), e.g. 0.147.0
WA_CODEX_CLI_VERSION_PIN=__FILL_ME__
WA_CODEX_MODEL=gpt-5.6-terra
WA_BROKER_POLL_S=2.0
# Absorbs claim-response return transit AND completion margin — size against
# measured claim latency (see compute_budget_s docstring).
WA_BROKER_NET_MARGIN_S=1.0
CODEX_HOME=/Users/zantara-codex/.codex
# Kill switch: set to false for an operator stop without uninstall.
WA_CODEX_BROKER_ENABLED=true
ENVEOF
    chown "${BROKER_USER}:staff" "${ENV_FILE}"
    chmod 0600 "${ENV_FILE}"
    log "env file: DONE (placeholder — operator fills WA_BROKER_KEY + version pin)"
fi

# --- 6. canaries (spec §4.3) ----------------------------------------------
# Decoy files an injected agent hunting credentials would read; their values
# reach the Fly side as WA_CODEX_CANARY_TOKENS so the leg's egress scan can
# veto any answer carrying one. Never regenerated once planted (the Fly
# secret must keep matching the planted files).
CANARY_FILE_A="${BROKER_HOME}/.codex/backup_credentials.txt"
CANARY_FILE_B="${BROKER_HOME}/.aws-credentials"
if [ -f "${CANARY_FILE_A}" ] && [ -f "${CANARY_FILE_B}" ] && [ -f "${CANARY_RECORD}" ]; then
    log "canaries: SKIP (planted)"
else
    CANARY_A="bzcanary-$(head -c16 /dev/urandom | xxd -p)"
    CANARY_B="bzcanary-$(head -c16 /dev/urandom | xxd -p)"
    umask 077
    printf 'api_backup_token=%s\n' "${CANARY_A}" > "${CANARY_FILE_A}"
    printf '[default]\naws_secret_access_key = %s\n' "${CANARY_B}" > "${CANARY_FILE_B}"
    chown "${BROKER_USER}:staff" "${CANARY_FILE_A}" "${CANARY_FILE_B}"
    chmod 0600 "${CANARY_FILE_A}" "${CANARY_FILE_B}"
    printf 'WA_CODEX_CANARY_TOKENS=%s,%s\n' "${CANARY_A}" "${CANARY_B}" > "${CANARY_RECORD}"
    chmod 0600 "${CANARY_RECORD}"
    log "canaries: DONE — values recorded root-only in ${CANARY_RECORD};"
    log "          ship them to Fly WITHOUT argv/history exposure:"
    log "            fly secrets import -a nuzantara-rag < ${CANARY_RECORD}"
fi

# --- 7. LaunchDaemon --------------------------------------------------------
install -o root -g wheel -m 0644 "${PLIST_SRC}" "${PLIST_DST}"
log "plist installed: ${PLIST_DST}"
if grep -q "__FILL_ME__" "${ENV_FILE}"; then
    log "bootstrap: SKIP — env file still has __FILL_ME__ placeholders."
    log "  After filling it (and codex login), arm with:"
    log "    sudo launchctl bootstrap system ${PLIST_DST}"
else
    set +e
    launchctl bootstrap system "${PLIST_DST}" 2>/dev/null
    BOOT_RC=$?
    set -e
    if [ "${BOOT_RC}" -eq 0 ]; then
        log "bootstrap: DONE (daemon armed)"
    else
        log "bootstrap: already loaded (rc=${BOOT_RC}) — restart with:"
        log "    sudo launchctl kickstart -k system/${PLIST_LABEL}"
    fi
fi

log "---- remaining OPERATOR steps (spec §Solo-operatore) ----"
log "1) one-time seat login:"
log "     sudo -u ${BROKER_USER} CODEX_HOME=${BROKER_HOME}/.codex HOME=${BROKER_HOME} codex login"
log "2) fill ${ENV_FILE} (WA_BROKER_KEY, WA_CODEX_CLI_VERSION_PIN)"
log "3) fly secrets import -a nuzantara-rag < ${CANARY_RECORD}"
log "4) re-run this script (or launchctl bootstrap) to arm"
