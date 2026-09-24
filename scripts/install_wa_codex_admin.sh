#!/bin/bash
# install_wa_codex_admin.sh — the ONE command the owner runs, once, with
# sudo, on Pro, to install the WA codex broker's dedicated-binary admin
# verb (W136 pin-drift cure). Idempotent: safe to re-run, and wired into
# scripts/provision_zantara_codex.sh so a re-provision keeps it current.
#
# Run ON PRO, with sudo:   sudo bash scripts/install_wa_codex_admin.sh
#
# What it does (each step logs DONE/SKIP; re-running is safe):
#   1. Installs infra/launchagents/wrappers/wa-codex-broker-admin.sh to
#      /usr/local/libexec/wa-codex-broker-admin.sh (root:wheel 0755) —
#      fresh copy every run (a merge alone never updates a live copy,
#      superscar #1 / W107 delivery gotcha).
#   2. `visudo -cf`'s infra/sudoers/wa-codex-broker-admin in a TEMP file
#      BEFORE it ever lands in /etc/sudoers.d — a syntax error here must
#      fail this install, never land half-written on the live sudoers
#      tree — then installs it 0440 root:wheel.
#   3. If the daemon's env file already carries a real
#      WA_CODEX_CLI_VERSION_PIN (not the __FILL_ME__ placeholder), runs
#      `bump <that pin>` so the daemon moves onto its dedicated binary
#      IMMEDIATELY — no separate manual step. On a host where provisioning
#      has not filled the pin yet, this step logs SKIP (not an error) and
#      leaves it for the operator to run by hand once the pin is set.
set -euo pipefail
umask 077
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

BROKER_USER="zantara-codex"
BROKER_HOME="/Users/${BROKER_USER}"
ENV_FILE="${BROKER_HOME}/.wa-codex-broker.env"
ADMIN_DST="/usr/local/libexec/wa-codex-broker-admin.sh"
SUDOERS_DST="/etc/sudoers.d/wa-codex-broker-admin"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADMIN_SRC="${REPO_ROOT}/infra/launchagents/wrappers/wa-codex-broker-admin.sh"
SUDOERS_SRC="${REPO_ROOT}/infra/sudoers/wa-codex-broker-admin"

log() { echo "[install-wa-codex-admin] $*"; }
die() { log "ERROR: $*"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "must run as root (sudo bash scripts/install_wa_codex_admin.sh)"
[ -f "$ADMIN_SRC" ] || die "source file missing: $ADMIN_SRC (run from a current repo checkout)"
[ -f "$SUDOERS_SRC" ] || die "source file missing: $SUDOERS_SRC (run from a current repo checkout)"

# --- 1. admin script -------------------------------------------------------
install -d -o root -g wheel -m 0755 /usr/local/libexec
install -o root -g wheel -m 0755 "$ADMIN_SRC" "$ADMIN_DST"
log "admin script: DONE -> ${ADMIN_DST}"

# --- 2. sudoers drop-in — validated BEFORE it ever touches /etc -----------
sudoers_tmp="$(mktemp "${TMPDIR:-/tmp}/wa-codex-admin-sudoers.XXXXXX")"
cp "$SUDOERS_SRC" "$sudoers_tmp"
if ! visudo -cf "$sudoers_tmp"; then
    rm -f "$sudoers_tmp"
    die "sudoers drop-in failed visudo -cf — refusing to install (nothing written to /etc)"
fi
install -d -o root -g wheel -m 0755 /etc/sudoers.d
install -o root -g wheel -m 0440 "$sudoers_tmp" "$SUDOERS_DST"
rm -f "$sudoers_tmp"
log "sudoers drop-in: DONE -> ${SUDOERS_DST} (visudo -cf clean)"

# --- 3. bump onto the dedicated binary, if the pin is already real --------
if [ ! -f "$ENV_FILE" ]; then
    log "bump: SKIP (no env file yet — run provisioning first)"
elif ! current_pin="$(grep -m1 '^WA_CODEX_CLI_VERSION_PIN=' "$ENV_FILE" | cut -d= -f2-)" || [ -z "$current_pin" ]; then
    log "bump: SKIP (env file has no WA_CODEX_CLI_VERSION_PIN line yet)"
elif [ "$current_pin" = "__FILL_ME__" ]; then
    log "bump: SKIP (env file pin is still the __FILL_ME__ placeholder)"
    log "  fill it, then run:  sudo ${ADMIN_DST} bump <version>"
else
    log "bump: moving the daemon onto its dedicated binary for pin ${current_pin}"
    "$ADMIN_DST" bump "$current_pin"
    log "bump: DONE"
fi

log "---- verify ----"
log "  sudo ${ADMIN_DST} status"
