#!/bin/bash
# wr2_plist_watchdog.sh — guardrail against the "LaunchAgent plist disappears
# between sessions" cicatrix scar (2026-04-29 P0-3 incident).
#
# Mechanism:
# 1. For each plist in infra/launchagents/com.balizero.wr2.*, check if a
#    matching file exists in ~/Library/LaunchAgents/ AND launchctl knows
#    about it.
# 2. If absent or unloaded, copy the git-tracked source-of-truth to
#    ~/Library/LaunchAgents/, chmod 0444, bootstrap with launchctl.
# 3. Telegram-alert on every recovery so we have a paper trail when the
#    unknown writer (still unidentified per cicatrix) hits again.
#
# Designed to be invoked from a watchdog plist on a 5-min schedule, OR
# manually after a session reboot.
#
# Idempotent. Safe to run unconditionally.

set -euo pipefail

REPO_ROOT="${WR2_REPO_ROOT:-${HOME}/Desktop/nuzantara-deploy}"
SOURCE_DIR="${REPO_ROOT}/infra/launchagents"
TARGET_DIR="${HOME}/Library/LaunchAgents"
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"

if [[ -f "${SECRETS_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${SECRETS_FILE}"
    set +a
fi

UID_VAL="$(id -u)"
DOMAIN="gui/${UID_VAL}"
LAUNCHCTL_TIMEOUT_SEC="${WR2_LAUNCHCTL_TIMEOUT_SEC:-6}"
LAUNCHCTL_TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"
RECOVERIES=()
ERRORS=()

_with_timeout() {
    if [[ -n "${LAUNCHCTL_TIMEOUT_BIN}" ]]; then
        "${LAUNCHCTL_TIMEOUT_BIN}" "${LAUNCHCTL_TIMEOUT_SEC}s" "$@"
    else
        "$@"
    fi
}

_plist_label() {
    local plist="$1"
    local label

    label="$(/usr/libexec/PlistBuddy -c 'Print :Label' "${plist}" 2>/dev/null || true)"
    if [[ -z "${label}" ]]; then
        label="$(basename "${plist}" .plist)"
    fi

    printf '%s\n' "${label}"
}

_is_disabled() {
    local label="$1"
    grep -F "\"${label}\" => disabled" <<<"${DISABLED_SERVICES}" >/dev/null
}

_bootstrap() {
    local label="$1"
    local target_plist="$2"
    local output
    local status

    if output="$(_with_timeout launchctl bootstrap "${DOMAIN}" "${target_plist}" 2>&1)"; then
        return 0
    fi

    status=$?
    if [[ "${status}" -eq 124 ]]; then
        output="timeout after ${LAUNCHCTL_TIMEOUT_SEC}s"
    fi
    output="${output//$'\n'/ }"
    if [[ -z "${output}" ]]; then
        output="exit ${status}"
    fi
    ERRORS+=("${label} (bootstrap failed: ${output})")
    return 1
}

_telegram() {
    local text="$1"
    local token="${TELEGRAM_BOT_TOKEN:-}"
    local chat="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
    if [[ -z "${token}" ]]; then
        return 0
    fi
    curl -fsS -m 10 \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=${text}" \
        "https://api.telegram.org/bot${token}/sendMessage" \
        >/dev/null 2>&1 || true
}

if [[ ! -d "${SOURCE_DIR}" ]]; then
    echo "[wr2-plist-watchdog] source dir missing: ${SOURCE_DIR}" >&2
    exit 0
fi

DISABLED_SERVICES="$(_with_timeout launchctl print-disabled "${DOMAIN}" 2>/dev/null || true)"

# Only protect WR2 family (com.balizero.wr2.*). Other plists in
# infra/launchagents/ are out of scope — their respective owners can
# write their own watchdog if they need one.
shopt -s nullglob
for source_plist in "${SOURCE_DIR}"/com.balizero.wr2.*.plist; do
    target_plist="${TARGET_DIR}/$(basename "${source_plist}")"
    label="$(_plist_label "${source_plist}")"
    if [[ -f "${target_plist}" ]]; then
        label="$(_plist_label "${target_plist}")"
    fi

    if [[ ! -f "${target_plist}" ]]; then
        echo "[wr2-plist-watchdog] ${label}: missing on disk, restoring..."
        if cp "${source_plist}" "${target_plist}" 2>/dev/null && chmod 0444 "${target_plist}" 2>/dev/null; then
            if _is_disabled "${label}"; then
                RECOVERIES+=("${label} (restored from git; launchd disabled, not bootstrapped)")
            elif _bootstrap "${label}" "${target_plist}"; then
                RECOVERIES+=("${label} (restored from git + bootstrapped)")
            fi
        else
            ERRORS+=("${label} (could not write to ${target_plist})")
        fi
        continue
    fi

    # File exists — check launchctl knows about it.
    if ! _with_timeout launchctl print "${DOMAIN}/${label}" >/dev/null 2>&1; then
        if _is_disabled "${label}"; then
            continue
        fi

        echo "[wr2-plist-watchdog] ${label}: file present but not loaded, bootstrapping..."
        if _bootstrap "${label}" "${target_plist}"; then
            RECOVERIES+=("${label} (bootstrapped, file was already present)")
        fi
    fi
done
shopt -u nullglob

if [[ ${#RECOVERIES[@]} -gt 0 ]] || [[ ${#ERRORS[@]} -gt 0 ]]; then
    msg="WR2 plist watchdog: action taken on $(date -u +%FT%TZ)"
    if [[ ${#RECOVERIES[@]} -gt 0 ]]; then
        for r in "${RECOVERIES[@]}"; do
            msg="${msg}"$'\n'"  ✓ ${r}"
        done
    fi
    if [[ ${#ERRORS[@]} -gt 0 ]]; then
        for e in "${ERRORS[@]}"; do
            msg="${msg}"$'\n'"  ✗ ${e}"
        done
    fi
    echo "${msg}"
    _telegram "${msg}"
fi

if [[ ${#ERRORS[@]} -gt 0 ]]; then
    exit 1
fi
exit 0
