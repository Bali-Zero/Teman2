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
#   8. Installs the S3 seat-probe pair (Piece A of the seat sentinel,
#      research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md):
#      /usr/local/var/wa-codex-broker (shared state dir), the probe wrapper
#      + script (root-owned, same fresh-copy-every-run discipline as step
#      3), and its own LaunchDAEMON. Bootstrapped UNCONDITIONALLY — unlike
#      the broker, the probe needs no WA_BROKER_KEY (it only reads
#      WA_CODEX_BIN/CODEX_HOME from the same env file), so it is useful
#      even before the operator fills the placeholders.
#
# What it deliberately does NOT do (spec §Solo-operatore — operator actions):
#   - `codex login` as zantara-codex (one-time device-code flow):
#         sudo -u zantara-codex CODEX_HOME=/Users/zantara-codex/.codex codex login
#   - Filling WA_BROKER_KEY / WA_CODEX_CLI_VERSION_PIN in the env file.
#   - `fly secrets import` of the canary record on nuzantara-rag.
#
# Interpreter note (declared): the venv is built from whatever `python3`
# resolves to for root at run time (Pro measured 3.11.15 on 2026-08-19; the
# live 2026-08-20 provisioning run built on 3.14.6 — the resolution moves
# between runs). The daemon needs only stdlib + httpx; pin the interpreter
# here if that ever stops being true.

set -euo pipefail

BROKER_USER="zantara-codex"
BROKER_HOME="/Users/${BROKER_USER}"
RUNTIME_DIR="/usr/local/lib/wa-codex-broker"
STATE_DIR="/usr/local/var/wa-codex-broker"
WRAPPER_DST="/usr/local/libexec/wa-codex-broker-wrapper.sh"
ENV_FILE="${BROKER_HOME}/.wa-codex-broker.env"
CANARY_RECORD="/var/root/wa-codex-canaries.txt"
PLIST_LABEL="com.balizero.wa-codex-broker"
PLIST_DST="/Library/LaunchDaemons/${PLIST_LABEL}.plist"

# S3 seat-probe pair (Piece A of the seat sentinel — step 8 below).
PROBE_WRAPPER_DST="/usr/local/libexec/wa-codex-seat-probe-wrapper.sh"
PROBE_SCRIPT_DST="${RUNTIME_DIR}/seat_probe.py"
PROBE_PLIST_LABEL="com.balizero.wa-codex-seat-probe"
PROBE_PLIST_DST="/Library/LaunchDaemons/${PROBE_PLIST_LABEL}.plist"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_SRC="${REPO_ROOT}/apps/backend-rag/backend"
WRAPPER_SRC="${REPO_ROOT}/infra/launchagents/wrappers/wa-codex-broker-wrapper.sh"
PLIST_SRC="${REPO_ROOT}/infra/launchagents/${PLIST_LABEL}.plist"
PROBE_SCRIPT_SRC="${REPO_ROOT}/scripts/wa_codex_seat_probe.py"
PROBE_WRAPPER_SRC="${REPO_ROOT}/infra/launchagents/wrappers/wa-codex-seat-probe-wrapper.sh"
PROBE_PLIST_SRC="${REPO_ROOT}/infra/launchagents/${PROBE_PLIST_LABEL}.plist"

log() { echo "[provision-zantara-codex] $*"; }

if [ "$(id -u)" -ne 0 ]; then
    log "ERROR: must run as root (sudo bash scripts/provision_zantara_codex.sh)"
    exit 1
fi
for src in "${BACKEND_SRC}/services/integrations/wa_codex_daemon.py" \
    "${BACKEND_SRC}/llm/codex_exec_client.py" "${WRAPPER_SRC}" "${PLIST_SRC}" \
    "${PROBE_SCRIPT_SRC}" "${PROBE_WRAPPER_SRC}" "${PROBE_PLIST_SRC}"; do
    if [ ! -f "$src" ]; then
        log "ERROR: source file missing: $src (run from a current repo checkout)"
        exit 1
    fi
done

# --- 1. user -----------------------------------------------------------
if id "${BROKER_USER}" >/dev/null 2>&1; then
    log "user ${BROKER_USER}: SKIP (exists)"
else
    # -password gets a random THROWAWAY (Kimi round-2 L4): some macOS
    # versions prompt interactively without it, which hangs a sudo script.
    # The value protects nothing — the shell is /usr/bin/false, login is
    # impossible, and it is never used again — so its brief argv exposure
    # is noise, not a secret (the argv ban guards secrets).
    # Measured on the live 2026-08-20 Pro run (macOS 27): sysadminctl printed
    # its "No clear text password" warning ANYWAY, did not hang, and created
    # the account with NO AuthenticationAuthority at all — a safer outcome
    # than designed (no hash = nothing to authenticate against). The flag
    # stays for the older macOS versions the hang was reported on.
    sysadminctl -addUser "${BROKER_USER}" \
        -fullName "Zantara Codex Broker" \
        -home "${BROKER_HOME}" \
        -shell /usr/bin/false \
        -password "$(head -c16 /dev/urandom | xxd -p)"
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
elif [ -f "${CANARY_FILE_A}" ] || [ -f "${CANARY_FILE_B}" ] || [ -f "${CANARY_RECORD}" ]; then
    # Partial state (Kimi round-2 L2): regenerating here would overwrite
    # planted values while the Fly secret still scans for the old ones —
    # the tripwire silently disarmed in both directions. Refuse loudly;
    # planted values are never overwritten. The operator reconciles by
    # hand: the surviving 0600 files/record hold the truth (readable as
    # root), or delete ALL THREE to intentionally re-plant + re-import.
    log "ERROR: canary state is PARTIAL — refusing to regenerate:"
    for f in "${CANARY_FILE_A}" "${CANARY_FILE_B}" "${CANARY_RECORD}"; do
        log "  $([ -f "$f" ] && echo present || echo MISSING): $f"
    done
    log "  Reconcile manually (or remove all three to re-plant), then re-run."
    exit 1
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
elif launchctl print "system/${PLIST_LABEL}" >/dev/null 2>&1; then
    # Loaded-state is checked EXPLICITLY (Kimi r1 M2): the old pattern read
    # ANY bootstrap failure as "already loaded" (2>/dev/null + rc), so a
    # malformed plist or a permission error green-ticked as armed — the
    # installer itself reproducing superscar #2. And kickstart -k does NOT
    # re-read a changed plist; only bootout+bootstrap does.
    log "bootstrap: SKIP (already loaded). A CHANGED plist needs a reload:"
    log "    sudo launchctl bootout system/${PLIST_LABEL} && sudo launchctl bootstrap system ${PLIST_DST}"
    log "  (kickstart -k restarts the job but does NOT re-read the plist)"
else
    set +e
    BOOT_ERR="$(launchctl bootstrap system "${PLIST_DST}" 2>&1)"
    BOOT_RC=$?
    set -e
    if [ "${BOOT_RC}" -eq 0 ]; then
        log "bootstrap: DONE (daemon armed)"
    elif printf '%s' "${BOOT_ERR}" | grep -qi "already loaded\|already bootstrapped\|service already"; then
        # Kimi r2 #1: launchctl print can transiently fail while the service
        # IS loaded — then bootstrap answers "already loaded". That state is
        # ARMED, not broken: hard-failing here would page on a healthy daemon.
        log "bootstrap: SKIP (bootstrap says already loaded — print missed it)"
    else
        log "ERROR: bootstrap FAILED (rc=${BOOT_RC}): ${BOOT_ERR}"
        exit 1
    fi
fi

# --- 8. seat probe (S3, Piece A) ------------------------------------------
install -d -o "${BROKER_USER}" -g staff -m 0755 "${STATE_DIR}"
log "seat-probe state dir ${STATE_DIR}: DONE"

# Fresh copy every run, same reasoning as step 3: the merge alone never
# updates a live copy (superscar #1).
install -o root -g wheel -m 0644 "${PROBE_SCRIPT_SRC}" "${PROBE_SCRIPT_DST}"
install -o root -g wheel -m 0755 "${PROBE_WRAPPER_SRC}" "${PROBE_WRAPPER_DST}"
log "seat-probe script + wrapper: DONE (root-owned)"

install -o root -g wheel -m 0644 "${PROBE_PLIST_SRC}" "${PROBE_PLIST_DST}"
log "seat-probe plist installed: ${PROBE_PLIST_DST}"
# Unconditional bootstrap — the probe needs no WA_BROKER_KEY (only
# WA_CODEX_BIN/CODEX_HOME from the shared env file), so it is useful even
# while the broker's own env-file placeholders are still unfilled.
if launchctl print "system/${PROBE_PLIST_LABEL}" >/dev/null 2>&1; then
    # Same explicit loaded-check as the broker section above (Kimi r1 M2).
    log "seat-probe bootstrap: SKIP (already loaded). A CHANGED plist needs a reload:"
    log "    sudo launchctl bootout system/${PROBE_PLIST_LABEL} && sudo launchctl bootstrap system ${PROBE_PLIST_DST}"
    log "  (kickstart -k restarts the job but does NOT re-read the plist)"
else
    set +e
    PROBE_BOOT_ERR="$(launchctl bootstrap system "${PROBE_PLIST_DST}" 2>&1)"
    PROBE_BOOT_RC=$?
    set -e
    if [ "${PROBE_BOOT_RC}" -eq 0 ]; then
        log "seat-probe bootstrap: DONE (armed)"
    elif printf '%s' "${PROBE_BOOT_ERR}" | grep -qi "already loaded\|already bootstrapped\|service already"; then
        # Kimi r2 #1, symmetric with the broker section (W101-recidiva lesson:
        # a fix that covers only the phase that bit you is half a fix).
        log "seat-probe bootstrap: SKIP (bootstrap says already loaded — print missed it)"
    else
        log "ERROR: seat-probe bootstrap FAILED (rc=${PROBE_BOOT_RC}): ${PROBE_BOOT_ERR}"
        exit 1
    fi
fi

log "---- remaining OPERATOR steps (spec §Solo-operatore) ----"
log "1) one-time seat login:"
log "     sudo -u ${BROKER_USER} CODEX_HOME=${BROKER_HOME}/.codex HOME=${BROKER_HOME} codex login"
log "2) fill ${ENV_FILE} (WA_BROKER_KEY, WA_CODEX_CLI_VERSION_PIN)"
log "3) fly secrets import -a nuzantara-rag < ${CANARY_RECORD}"
log "4) re-run this script (or launchctl bootstrap) to arm"
log "5) arm Piece B (the reader — Kimi r1 M3: the probe writes a status file"
log "   NOBODY reads until this runs) as the NORMAL cron user, not root:"
log "   add a cron-runner crontab entry for"
log "     infra/launchagents/wrappers/wa-codex-seat-sentinel.sh"
log "   from this machine's MAIN checkout (~/nuzantara — NEVER a .worktrees/"
log "   lane path: lanes get reaped after merge and the cron would point at"
log "   nothing; Kimi r2 #4). Same pattern as the other cron-runner lines"
log "   in \`crontab -l\`, e.g. every 15 minutes."
log "NOTE (Kimi r2 #3): the probe bootstraps with RunAtLoad, so its FIRST run"
log "   fires NOW — before step 1's login — and records auth_death. Expect ONE"
log "   RED 'AUTH DEAD' page from the first sentinel run if it lands within"
log "   the probe's 6h cadence of your login; the next probe run clears it."
