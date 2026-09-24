#!/bin/bash
# wa-codex-broker-admin.sh — root-owned admin verb for the WA codex broker's
# OWN dedicated codex binary, decoupled from the shared Homebrew
# @openai/codex install any other seat on Pro may upgrade.
#
# ROUND 1 (this file) after PR #7313's cross-family security BLOCK on round 0.
# The round-0 shape let `nuzantara`'s NOPASSWD grant turn into full root:
# python3 imported from the inherited cwd, `status` executed a
# daemon-writable WA_CODEX_BIN as root, and the daemon-owned env file gave a
# symlink/TOCTOU path to arbitrary root reads/writes. The PRINCIPLE this
# round is built on: root never reads, writes or executes anything that
# `zantara-codex` or `nuzantara` can influence; anything that executes the
# downloaded artifact runs as `zantara-codex`, never as root. Concretely:
#   - No interpreter at all (D1): JSON is parsed with `plutil`, not python3.
#     `cd /` happens before anything else, so no subprocess this script
#     spawns can pick up a cwd-relative import/config file.
#   - Pin + binary path live in a NEW root-owned config
#     (/usr/local/lib/wa-codex-broker/codex-pin.env, root:wheel 0644) — this
#     script never opens/reads/writes/chowns/chmods anything under
#     /Users/zantara-codex (D2). The broker wrapper sources this file AFTER
#     the daemon's own env file, so these values win.
#   - `status` never executes a daemon-chosen binary as root: it validates
#     WA_CODEX_BIN against an exact pattern AND every path component's
#     ownership/mode/symlink status, then drops privilege
#     (`sudo -u zantara-codex`) before running `--version` (D3).
#   - `bump` fetches over an HTTPS-pinned, host-allowlisted curl, verifies
#     sha512, rejects any symlink/hardlink in the archive BEFORE extracting,
#     normalizes ownership/permissions on the extracted tree, and probes the
#     staged binary as `zantara-codex` too — never as root (D4).
#   - Rollback (bump <old>) re-verifies the SAME ownership/mode/symlink
#     chain plus a recorded sha256 manifest before trusting a reused
#     directory (D5).
#   - The config write + kickstart is a transaction: a failed kickstart, or
#     a daemon that does not report running within a timeout, rolls the
#     config back to what it was and re-kickstarts (D6).
#
# Installed root:wheel 0755 at /usr/local/libexec/wa-codex-broker-admin.sh
# by scripts/install_wa_codex_admin.sh (also wired into
# scripts/provision_zantara_codex.sh). Callable passwordless by the
# `nuzantara` interactive user via the sudoers drop-in
# infra/sudoers/wa-codex-broker-admin (env_reset + NOSETENV — the sudoers
# wildcard on `bump *` is NOT the security boundary, this script's own
# strict argument validation is).
#
# Verbs:
#   status        — pin, dedicated binary path (validated, privilege-dropped
#                   --version), launchd state
#   bump <semver> — fetch/verify/install the darwin-arm64 codex build for
#                   <semver>, pin it, kickstart the daemon onto it
#
# TESTING (D8): there is NO env-var test mode anywhere in this file — no
# environment variable changes this script's behaviour at all, closing the
# round-0 class of bug where a sudoers env leak could have flipped a branch
# here. scripts/tests/test_wa_codex_broker_admin.py instead copies this
# FILE and `sed`-rewrites the plain constants below (ROOT_PREFIX and the
# *_BIN tool paths) into a scratch tree + logging stub binaries — a
# source-level transformation of a COPY, never a runtime toggle of the
# installed artifact. Privileged syscalls that only mean something as real
# root (chown to root:wheel, `sudo -u zantara-codex`) are gated on
# `[ "$(id -u)" -eq 0 ]`, which is false for every test run regardless of
# ROOT_PREFIX, so they are inert there without needing their own stubs.
set -euo pipefail

# --- path constants — sed-patchable by tests, otherwise literal and fixed.
# ROOT_PREFIX="" in the installed artifact, ALWAYS. Every other path below
# is built from it, so patching this one constant redirects the whole
# script into a scratch tree without touching any conditional logic.
ROOT_PREFIX=""
CURL_BIN=/usr/bin/curl
TAR_BIN=/usr/bin/tar
OPENSSL_BIN=/usr/bin/openssl
PLUTIL_BIN=/usr/bin/plutil
CHOWN_BIN=/usr/sbin/chown
CHMOD_BIN=/bin/chmod
MV_BIN=/bin/mv
RM_BIN=/bin/rm
MKDIR_BIN=/bin/mkdir
MKTEMP_BIN=/usr/bin/mktemp
STAT_BIN=/usr/bin/stat
GREP_BIN=/usr/bin/grep
AWK_BIN=/usr/bin/awk
SLEEP_BIN=/bin/sleep
LAUNCHCTL_BIN=/bin/launchctl
SUDO_BIN=/usr/bin/sudo

# D1 — cd / FIRST, before anything else runs: no subprocess spawned below
# can ever pick up a cwd-relative import, config file, or .curlrc-style
# lookup from wherever this script happened to be invoked from.
cd /

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
umask 022

TAG="wa-codex-broker-admin"
log() { echo "[${TAG}] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

BROKER_USER="zantara-codex"
RUNTIME_DIR="${ROOT_PREFIX}/usr/local/lib/wa-codex-broker"
CODEX_DIR="${RUNTIME_DIR}/codex"
STAGING_ROOT="${RUNTIME_DIR}/.staging"
LOCK_DIR="${RUNTIME_DIR}/.bump.lock"
CODEX_PIN_FILE="${RUNTIME_DIR}/codex-pin.env"
PLIST_LABEL="com.balizero.wa-codex-broker"
REGISTRY_BASE="https://registry.npmjs.org/@openai%2fcodex"
SEMVER_RE='^[0-9]+\.[0-9]+\.[0-9]+$'
_KICKSTART_VERIFY_TIMEOUT_S=5

# --- cleanup: one global trap, conditionally removes whatever got set ------
_STAGING_DIR=""
_LOCK_ACQUIRED=0
_cleanup() {
    if [ -n "$_STAGING_DIR" ] && [ -d "$_STAGING_DIR" ]; then
        $RM_BIN -rf "$_STAGING_DIR"
    fi
    if [ "$_LOCK_ACQUIRED" = "1" ]; then
        rmdir "$LOCK_DIR" 2>/dev/null || true
    fi
}
trap _cleanup EXIT

# --- small helpers -----------------------------------------------------

_ensure_dir() { # $1 path, $2 octal mode
    local d="$1" mode="$2"
    if [ ! -d "$d" ]; then
        $MKDIR_BIN -p -m "$mode" "$d" || die "could not create directory: $d"
    fi
    $CHMOD_BIN "$mode" "$d" || true
}

_acquire_lock() {
    _ensure_dir "$RUNTIME_DIR" 0755
    if ! $MKDIR_BIN "$LOCK_DIR" 2>/dev/null; then
        die "another bump is already in progress (lock held: ${LOCK_DIR}) — remove it manually only after confirming no wa-codex-broker-admin.sh process is running"
    fi
    _LOCK_ACQUIRED=1
}

# D3 — verify ONE path component: not a symlink, exists, owned by root
# (uid 0), and not group- or other-writable. Pure predicate, no execution.
_verify_component_safe() {
    local p="$1"
    if [ -L "$p" ]; then
        return 1
    fi
    if [ ! -e "$p" ]; then
        return 1
    fi
    local owner_uid perm
    owner_uid="$($STAT_BIN -f '%u' "$p" 2>/dev/null)" || return 1
    if [ "$owner_uid" != "0" ]; then
        return 1
    fi
    perm="$($STAT_BIN -f '%Lp' "$p" 2>/dev/null)" || return 1
    if [ -z "$perm" ]; then
        return 1
    fi
    if (( (8#$perm) & 8#022 )); then
        return 1
    fi
    return 0
}

# D3 — every path component from RUNTIME_DIR down to the binary itself.
_verify_trusted_chain() { # $1 version
    local ver="$1"
    local components=(
        "$RUNTIME_DIR"
        "$CODEX_DIR"
        "${CODEX_DIR}/${ver}"
        "${CODEX_DIR}/${ver}/bin"
        "${CODEX_DIR}/${ver}/bin/codex"
    )
    local c
    for c in "${components[@]}"; do
        _verify_component_safe "$c" || return 1
    done
    return 0
}

# D3 — WA_CODEX_BIN must match the EXACT pattern
# CODEX_DIR/<semver>/bin/codex, then pass the trust chain above.
_bin_matches_trusted_pattern() { # $1 candidate bin path
    local bin="$1" ver_part=""
    case "$bin" in
        "${CODEX_DIR}"/*/bin/codex) : ;;
        *) return 1 ;;
    esac
    ver_part="${bin#"${CODEX_DIR}"/}"
    ver_part="${ver_part%/bin/codex}"
    if [[ ! "$ver_part" =~ $SEMVER_RE ]]; then
        return 1
    fi
    _verify_trusted_chain "$ver_part"
}

# D5 — re-verify a promoted tree's sha256 manifest (guilt: tampered or
# missing file/manifest = false; only a byte-exact match is trusted).
_manifest_matches() { # $1 dest dir
    local dest="$1"
    local manifest="${dest}/.manifest.sha256"
    [ -f "$manifest" ] || return 1
    local line hash relpath actual
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        hash="${line%% *}"
        relpath="${line#*\*}"
        if [ ! -f "${dest}/${relpath}" ]; then
            return 1
        fi
        actual="$($OPENSSL_BIN dgst -sha256 -r "${dest}/${relpath}" 2>/dev/null | $AWK_BIN '{print $1}')"
        if [ "$actual" != "$hash" ]; then
            return 1
        fi
    done < "$manifest"
    return 0
}

# D3 — the ONLY place this script executes a codex binary: always through
# a privilege drop to $BROKER_USER, never directly as whatever this
# process's own uid is.
_probe_version_as_broker_user() { # $1 bin path
    local bin="$1"
    $SUDO_BIN -u "$BROKER_USER" -H /usr/bin/env -i "$bin" --version
}

# D4 — HTTPS-only, host-allowlisted, .curlrc-disabled fetch.
_curl_https() { # $1 url, $2 dest
    local url="$1" dest="$2"
    case "$url" in
        https://registry.npmjs.org/*) : ;;
        *) die "refusing non-allowlisted URL: ${url}" ;;
    esac
    $CURL_BIN -q -f -sS -L --proto '=https' --proto-redir '=https' "$url" -o "$dest"
}

# D4 — reject any archive entry that is not a plain file or directory
# (symlink, hardlink, device, fifo…) BEFORE extraction ever runs.
_reject_unsafe_archive_entries() { # $1 tgz path
    local tgz="$1" listing rc
    listing="$($TAR_BIN -tv -f "$tgz" 2>&1)"; rc=$?
    if [ "$rc" -ne 0 ]; then
        die "tar -tv listing failed (rc=${rc}): ${listing}"
    fi
    if printf '%s\n' "$listing" | $AWK_BIN '{print substr($1,1,1)}' | $GREP_BIN -qvE '^[-d]$'; then
        die "archive contains a non-regular-file entry (symlink/hardlink/device) — refusing to extract"
    fi
}

_write_manifest() { # $1 dir
    local dir="$1"
    local manifest="${dir}/.manifest.sha256"
    ( cd "$dir" && find . -type f ! -name '.manifest.sha256' -print0 | LC_ALL=C sort -z | xargs -0 "$OPENSSL_BIN" dgst -sha256 -r ) > "$manifest"
    $CHMOD_BIN 0644 "$manifest"
}

_daemon_running() {
    local out
    out="$($LAUNCHCTL_BIN print "system/${PLIST_LABEL}" 2>/dev/null)" || return 1
    printf '%s\n' "$out" | $GREP_BIN -qE '^[[:space:]]*state = running'
}

_wait_daemon_running() { # $1 timeout seconds
    local timeout="$1" waited=0
    while :; do
        _daemon_running && return 0
        waited=$((waited + 1))
        if [ "$waited" -gt "$timeout" ]; then
            return 1
        fi
        $SLEEP_BIN 1
    done
}

_ROLLBACK_VER=""
_PREV_CONFIG_BACKUP=""

# D6 — restore whatever codex-pin.env held before this bump, re-kickstart,
# and exit non-zero naming BOTH the failure and the rollback outcome.
_rollback_config() { # $1 reason
    local reason="$1"
    log "transaction failed (${reason}) — restoring previous config"
    if [ -n "$_PREV_CONFIG_BACKUP" ] && [ -f "$_PREV_CONFIG_BACKUP" ]; then
        local tmp
        tmp="$($MKTEMP_BIN "${CODEX_PIN_FILE}.XXXXXX")"
        cp "$_PREV_CONFIG_BACKUP" "$tmp"
        if [ "$(id -u)" -eq 0 ]; then $CHOWN_BIN root:wheel "$tmp"; fi
        $CHMOD_BIN 0644 "$tmp"
        $MV_BIN "$tmp" "$CODEX_PIN_FILE"
    else
        $RM_BIN -f "$CODEX_PIN_FILE"
    fi
    local rekick_note
    if $LAUNCHCTL_BIN kickstart -k "system/${PLIST_LABEL}" >/dev/null 2>&1; then
        rekick_note="re-kickstarted after rollback"
    else
        rekick_note="re-kickstart after rollback ALSO failed — manual intervention needed"
    fi
    die "bump to ${_ROLLBACK_VER:-<unknown>} FAILED (${reason}); config restored to its previous state and ${rekick_note}"
}

# D6 — write the new pin+bin config as a transaction, kickstart, verify.
_write_config_and_kickstart() { # $1 version, $2 bin path
    local ver="$1" bin_path="$2"
    _ensure_dir "$RUNTIME_DIR" 0755

    _PREV_CONFIG_BACKUP=""
    if [ -f "$CODEX_PIN_FILE" ]; then
        _PREV_CONFIG_BACKUP="$($MKTEMP_BIN "${RUNTIME_DIR}/.prev-config.XXXXXX")"
        cp "$CODEX_PIN_FILE" "$_PREV_CONFIG_BACKUP"
    fi

    local tmp
    tmp="$($MKTEMP_BIN "${CODEX_PIN_FILE}.XXXXXX")"
    {
        echo "WA_CODEX_CLI_VERSION_PIN=${ver}"
        echo "WA_CODEX_BIN=${bin_path}"
    } > "$tmp"
    if [ "$(id -u)" -eq 0 ]; then $CHOWN_BIN root:wheel "$tmp"; fi
    $CHMOD_BIN 0644 "$tmp"
    $MV_BIN "$tmp" "$CODEX_PIN_FILE"
    log "pin: WA_CODEX_CLI_VERSION_PIN=${ver}, WA_CODEX_BIN=${bin_path}"

    _ROLLBACK_VER="$ver"
    if ! $LAUNCHCTL_BIN kickstart -k "system/${PLIST_LABEL}"; then
        _rollback_config "kickstart command failed"
    fi
    if ! _wait_daemon_running "$_KICKSTART_VERIFY_TIMEOUT_S"; then
        _rollback_config "daemon not running within ${_KICKSTART_VERIFY_TIMEOUT_S}s of kickstart"
    fi
    log "kickstart: DONE, daemon confirmed running (system/${PLIST_LABEL})"

    if [ -n "$_PREV_CONFIG_BACKUP" ]; then
        $RM_BIN -f "$_PREV_CONFIG_BACKUP"
    fi
}

# --- verb bodies ------------------------------------------------------------

cmd_status() {
    local pin="" bin=""
    if [ -f "$CODEX_PIN_FILE" ]; then
        pin="$($GREP_BIN -m1 '^WA_CODEX_CLI_VERSION_PIN=' "$CODEX_PIN_FILE" 2>/dev/null | cut -d= -f2- || true)"
        bin="$($GREP_BIN -m1 '^WA_CODEX_BIN=' "$CODEX_PIN_FILE" 2>/dev/null | cut -d= -f2- || true)"
    fi
    echo "pin: ${pin:-<unset — no ${CODEX_PIN_FILE} yet>}"
    if [ -z "$bin" ]; then
        echo "dedicated binary: <unset>"
    elif ! _bin_matches_trusted_pattern "$bin"; then
        echo "dedicated binary: ${bin} — REFUSED (fails the pattern/ownership/mode/symlink trust chain) — not executed"
    else
        local out
        if out="$(_probe_version_as_broker_user "$bin" 2>&1)"; then
            echo "dedicated binary: ${bin}"
            echo "dedicated binary --version (run as ${BROKER_USER}): ${out}"
        else
            echo "dedicated binary: ${bin} — trusted, but --version failed (as ${BROKER_USER}): ${out}"
        fi
    fi
    echo "launchd:"
    local lc_out
    if lc_out="$($LAUNCHCTL_BIN print "system/${PLIST_LABEL}" 2>&1)"; then
        printf '%s\n' "$lc_out" | $GREP_BIN -E '^[[:space:]]*state = ' || echo "  (loaded, state line not found)"
    else
        echo "  (launchctl print failed — not loaded, or not running as root)"
    fi
}

# D4 — fetch, verify, extract, normalize, probe. Leaves the finished tree
# at "${_STAGING_DIR}/tree" for the caller to promote.
_fetch_and_stage_version() { # $1 version
    local ver="$1"
    _ensure_dir "$STAGING_ROOT" 0700
    _STAGING_DIR="$($MKTEMP_BIN -d "${STAGING_ROOT}/bump.XXXXXX")" || die "mktemp -d failed under ${STAGING_ROOT}"
    $CHMOD_BIN 0700 "$_STAGING_DIR"

    log "fetch: resolving darwin-arm64 build for ${ver} from the npm registry"
    local base_json="${_STAGING_DIR}/.base.json"
    _curl_https "${REGISTRY_BASE}/${ver}" "$base_json" \
        || die "npm registry lookup failed for @openai/codex@${ver}"

    local alias platform_ver
    alias="$($PLUTIL_BIN -extract 'optionalDependencies.@openai/codex-darwin-arm64' raw -o - "$base_json" 2>/dev/null || true)"
    [ -n "$alias" ] || die "no @openai/codex-darwin-arm64 optionalDependency alias in package metadata for ${ver}"
    platform_ver="${alias##*@}"
    [ -n "$platform_ver" ] || die "empty darwin-arm64 platform version for ${ver}"

    local platform_json="${_STAGING_DIR}/.platform.json"
    _curl_https "${REGISTRY_BASE}/${platform_ver}" "$platform_json" \
        || die "npm registry lookup failed for @openai/codex@${platform_ver}"

    local tarball integrity
    tarball="$($PLUTIL_BIN -extract dist.tarball raw -o - "$platform_json" 2>/dev/null || true)"
    integrity="$($PLUTIL_BIN -extract dist.integrity raw -o - "$platform_json" 2>/dev/null || true)"
    [ -n "$tarball" ] || die "empty dist.tarball for ${platform_ver}"
    case "$integrity" in
        sha512-*) : ;;
        *) die "dist.integrity for ${platform_ver} is not sha512: '${integrity}'" ;;
    esac

    local tgz="${_STAGING_DIR}/.codex.tgz"
    _curl_https "$tarball" "$tgz" || die "tarball download failed: ${tarball}"

    local want_b64 got_b64
    want_b64="${integrity#sha512-}"
    got_b64="$($OPENSSL_BIN dgst -sha512 -binary "$tgz" | $OPENSSL_BIN base64 -A)"
    [ "$got_b64" = "$want_b64" ] || die "integrity mismatch for ${tarball}: expected ${want_b64}, got ${got_b64}"
    log "verify: sha512 integrity OK"

    _reject_unsafe_archive_entries "$tgz"

    local extract_dir="${_STAGING_DIR}/tree"
    $MKDIR_BIN -m 0755 "$extract_dir"
    $TAR_BIN -x --no-same-owner --no-same-permissions -f "$tgz" -C "$extract_dir" \
        --strip-components=3 "package/vendor/aarch64-apple-darwin" \
        || die "tar extract failed"
    [ -x "${extract_dir}/bin/codex" ] || die "extracted tree has no bin/codex"

    if [ "$(id -u)" -eq 0 ]; then
        $CHOWN_BIN -R root:wheel "$extract_dir"
    fi
    $CHMOD_BIN -R u=rwX,go=rX "$extract_dir"

    local probe
    if ! probe="$(_probe_version_as_broker_user "${extract_dir}/bin/codex" 2>&1)"; then
        die "staged binary failed --version as ${BROKER_USER}: ${probe}"
    fi
    case "$probe" in
        *"$ver"*) : ;;
        *) die "staged binary --version (as ${BROKER_USER}) does not report ${ver}: ${probe}" ;;
    esac

    _write_manifest "$extract_dir"
    $RM_BIN -f "$base_json" "$platform_json" "$tgz"
}

cmd_bump() {
    local ver="$1"
    _acquire_lock

    local dest="${CODEX_DIR}/${ver}"
    local bin_path="${dest}/bin/codex"

    if _bin_matches_trusted_pattern "$bin_path" 2>/dev/null && _manifest_matches "$dest"; then
        log "reuse: ${dest} already present, trusted, and manifest-verified — skipping fetch/extract (e.g. a rollback)"
    else
        _fetch_and_stage_version "$ver"
        $RM_BIN -rf "$dest"
        _ensure_dir "$CODEX_DIR" 0755
        $MV_BIN "${_STAGING_DIR}/tree" "$dest"
    fi

    _write_config_and_kickstart "$ver" "$bin_path"
}

# --- verb dispatch — validated BEFORE anything else runs -------------------
[ $# -ge 1 ] || die "usage: $0 status|bump <semver>"
VERB="$1"
shift

case "$VERB" in
status)
    [ $# -eq 0 ] || die "status takes no arguments (got: $*)"
    ;;
bump)
    [ $# -eq 1 ] || die "bump requires exactly one argument: <semver> (got $#: $*)"
    VERSION="$1"
    if [[ ! "$VERSION" =~ $SEMVER_RE ]]; then
        die "invalid version '${VERSION}' — must be strict X.Y.Z (digits and dots only, no build/pre-release suffix)"
    fi
    ;;
*)
    die "unknown verb '${VERB}' (status|bump <semver>)"
    ;;
esac

if [ -z "$ROOT_PREFIX" ] && [ "$(id -u)" -ne 0 ]; then
    die "must run as root"
fi

case "$VERB" in
status) cmd_status ;;
bump) cmd_bump "$VERSION" ;;
esac
