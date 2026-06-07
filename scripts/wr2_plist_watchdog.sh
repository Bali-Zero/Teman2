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
WR2_RETIRED_PLIST_LABELS="${WR2_RETIRED_PLIST_LABELS:-com.balizero.wr2.canva-renderer}"

if [[ -f "${SECRETS_FILE}" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "${SECRETS_FILE}"
    set +a
fi

UID_VAL="$(id -u)"
DOMAIN="gui/${UID_VAL}"
RECOVERIES=()
ERRORS=()

_plist_label() {
    local plist="$1"
    local parsed=""
    if command -v plutil >/dev/null 2>&1; then
        parsed="$(plutil -extract Label raw -o - "${plist}" 2>/dev/null || true)"
    fi
    if [[ -z "${parsed}" && -x /usr/libexec/PlistBuddy ]]; then
        parsed="$(/usr/libexec/PlistBuddy -c "Print :Label" "${plist}" 2>/dev/null || true)"
    fi
    if [[ -n "${parsed}" ]]; then
        printf '%s\n' "${parsed}"
    else
        basename "${plist}" .plist
    fi
}

_is_retired_label() {
    local candidate="$1"
    local retired=""
    for retired in ${WR2_RETIRED_PLIST_LABELS}; do
        if [[ "${candidate}" == "${retired}" ]]; then
            return 0
        fi
    done
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

# Only protect WR2 family (com.balizero.wr2.*). Other plists in
# infra/launchagents/ are out of scope — their respective owners can
# write their own watchdog if they need one.
shopt -s nullglob
for source_plist in "${SOURCE_DIR}"/com.balizero.wr2.*.plist; do
    source_name="$(basename "${source_plist}" .plist)"
    label="$(_plist_label "${source_plist}")"
    target_plist="${TARGET_DIR}/${source_name}.plist"

    if _is_retired_label "${label}"; then
        continue
    fi

    if [[ ! -f "${target_plist}" ]]; then
        echo "[wr2-plist-watchdog] ${label}: missing on disk, restoring..."
        if cp "${source_plist}" "${target_plist}" 2>/dev/null && chmod 0444 "${target_plist}" 2>/dev/null; then
            if launchctl bootstrap "${DOMAIN}" "${target_plist}" 2>/dev/null; then
                RECOVERIES+=("${label} (restored from git + bootstrapped)")
            else
                ERRORS+=("${label} (file restored, bootstrap failed)")
            fi
        else
            ERRORS+=("${label} (could not write to ${target_plist})")
        fi
        continue
    fi

    # File exists — check launchctl knows about it.
    if ! launchctl print "${DOMAIN}/${label}" >/dev/null 2>&1; then
        echo "[wr2-plist-watchdog] ${label}: file present but not loaded, bootstrapping..."
        if launchctl bootstrap "${DOMAIN}" "${target_plist}" 2>/dev/null; then
            RECOVERIES+=("${label} (bootstrapped, file was already present)")
        else
            ERRORS+=("${label} (bootstrap failed; file present, launchctl unloaded)")
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
