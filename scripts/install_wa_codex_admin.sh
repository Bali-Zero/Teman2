#!/bin/bash
# install_wa_codex_admin.sh — the ONE command the owner runs, once, with
# sudo, on Pro, to install the WA codex broker's dedicated-binary admin
# verb (W136 pin-drift cure, round 1 after PR #7313's security BLOCK).
# Idempotent: safe to re-run, and wired into
# scripts/provision_zantara_codex.sh so a re-provision keeps it current.
#
# Run ON PRO, with sudo:   sudo bash scripts/install_wa_codex_admin.sh
#
# D7 hardening (round 1): NO argument is accepted at all — `--help` or any
# other flag is rejected BEFORE anything runs, closing the round-0 gap
# where `sudo bash ... --help` silently installed anyway. Every source
# file (admin script AND sudoers drop-in) is fully preflighted — existence
# AND, for the sudoers file, `visudo -cf` — BEFORE either one is installed,
# so a bad sudoers file can no longer leave the admin script installed
# while itself failing. Both installs are temp-file-in-the-same-directory
# + `mv`, never a direct write to the live path.
#
# What it does (each step logs DONE/SKIP; re-running is safe):
#   1. Preflight: both source files exist; the sudoers drop-in parses
#      clean under `visudo -cf` in a throwaway temp file. Nothing is
#      installed yet.
#   2. Installs infra/launchagents/wrappers/wa-codex-broker-admin.sh to
#      /usr/local/libexec/wa-codex-broker-admin.sh (root:wheel 0755) —
#      fresh copy every run (a merge alone never updates a live copy,
#      superscar #1 / W107 delivery gotcha).
#   3. Installs the ALREADY-validated sudoers drop-in, 0440 root:wheel.
#   4. If the daemon's OWN env file still carries a real
#      WA_CODEX_CLI_VERSION_PIN (not the __FILL_ME__ placeholder) — the
#      only place that value has ever lived before this feature —
#      migrates it by running `bump <that pin>` once, so the daemon moves
#      onto its dedicated binary and the NEW root-owned codex-pin.env
#      IMMEDIATELY. This is a READ of the daemon's env file for migration
#      only (never a write — wa-codex-broker-admin.sh itself never touches
#      that file at all, D2). On a host where provisioning has not filled
#      the pin yet, this step logs SKIP (not an error).
set -euo pipefail
umask 022
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

log() { echo "[install-wa-codex-admin] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# D7 — reject ANY argument before anything else runs.
[ $# -eq 0 ] || die "takes no arguments (got: $*) — run exactly: sudo bash scripts/install_wa_codex_admin.sh"

[ "$(id -u)" -eq 0 ] || die "must run as root (sudo bash scripts/install_wa_codex_admin.sh)"

# --- 1. preflight — nothing installed yet past this point if anything fails
[ -f "$ADMIN_SRC" ] || die "source file missing: $ADMIN_SRC (run from a current repo checkout)"
[ -f "$SUDOERS_SRC" ] || die "source file missing: $SUDOERS_SRC (run from a current repo checkout)"

sudoers_tmp="$(mktemp "${TMPDIR:-/tmp}/wa-codex-admin-sudoers.XXXXXX")"
cp "$SUDOERS_SRC" "$sudoers_tmp"
if ! visudo -cf "$sudoers_tmp"; then
    rm -f "$sudoers_tmp"
    die "sudoers drop-in failed visudo -cf — refusing to install anything"
fi
log "preflight: DONE (sources present, sudoers drop-in visudo -cf clean)"

# --- atomic install: temp file IN THE TARGET DIRECTORY, owner/mode set
# BEFORE the rename, so the live path never exists with the wrong owner
# or mode even for an instant.
_atomic_install() { # $1 src, $2 dst, $3 mode
    local src="$1" dst="$2" mode="$3" dstdir tmp
    dstdir="$(dirname "$dst")"
    install -d -o root -g wheel -m 0755 "$dstdir"
    tmp="$(mktemp "${dstdir}/.$(basename "$dst").XXXXXX")"
    cp "$src" "$tmp"
    chown root:wheel "$tmp"
    chmod "$mode" "$tmp"
    mv "$tmp" "$dst"
}

# --- 2. admin script --------------------------------------------------------
_atomic_install "$ADMIN_SRC" "$ADMIN_DST" 0755
log "admin script: DONE -> ${ADMIN_DST}"

# --- 3. sudoers drop-in (already visudo -cf'd above) -----------------------
_atomic_install "$sudoers_tmp" "$SUDOERS_DST" 0440
rm -f "$sudoers_tmp"
log "sudoers drop-in: DONE -> ${SUDOERS_DST}"

# --- 4. migrate the pin onto the dedicated binary, if one already exists --
if [ ! -f "$ENV_FILE" ]; then
    log "bump: SKIP (no daemon env file yet — run provisioning first)"
elif ! current_pin="$(grep -m1 '^WA_CODEX_CLI_VERSION_PIN=' "$ENV_FILE" | cut -d= -f2-)" || [ -z "$current_pin" ]; then
    log "bump: SKIP (daemon env file has no WA_CODEX_CLI_VERSION_PIN line yet)"
elif [ "$current_pin" = "__FILL_ME__" ]; then
    log "bump: SKIP (daemon env file pin is still the __FILL_ME__ placeholder)"
    log "  fill it, then run:  sudo ${ADMIN_DST} bump <version>"
else
    log "bump: migrating the daemon onto its dedicated binary for pin ${current_pin}"
    "$ADMIN_DST" bump "$current_pin"
    log "bump: DONE"
fi

log "---- verify ----"
log "  sudo ${ADMIN_DST} status"
