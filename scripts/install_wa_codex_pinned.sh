#!/bin/bash
# install_wa_codex_pinned.sh — pin a DEDICATED, root-owned codex CLI binary
# for the wa-codex-broker daemon, decoupled from the shared Homebrew
# @openai/codex install any other seat on Pro may upgrade (chaos-table row
# 8, docs/runbooks/wa-broker-chaos-table.md).
#
# Supersedes PR #7313 (agent/air-m5/ops/wa-codex-dedicated-bin), which took
# two cross-family security BLOCKs building a privileged admin-verb surface
# (a NOPASSWD sudoers drop-in with `status`/`bump` verbs). The goal is only
# "a seat upgrading the shared Homebrew codex can never stop the bot
# again" — a dedicated binary that NOTHING auto-upgrades already achieves
# that. So this script has NO sudoers drop-in, NO NOPASSWD grant, NO admin
# verbs: the operator runs it by hand, with their own sudo password, as a
# rare deliberate action:
#
#     sudo bash scripts/install_wa_codex_pinned.sh <semver, e.g. 0.156.1>
#
# Root never reads, writes or executes anything `zantara-codex` (the
# daemon's own identity) or any other seat can influence: this script
# parses no daemon-writable file, executes no daemon-writable binary as
# root, and never touches /Users/zantara-codex.
#
# TESTING: there is no env-var or flag test-mode branch anywhere below —
# scripts/tests/test_install_wa_codex_pinned.py instead copies this FILE
# and `sed`-rewrites the plain path/identity CONSTANTS (ROOT_PREFIX,
# TRUST_OWNER, TRUST_GROUP, BROKER_USER, the *_BIN tool paths) into a
# scratch tree, the same source-level transformation of a COPY used by the
# superseded PR's own test suite. ROOT_PREFIX="" in the installed artifact,
# ALWAYS — ROOT_PREFIX also gates the root check below, so a sed-patched
# copy naturally runs unprivileged against its own scratch tree without a
# separate toggle anywhere.
set -euo pipefail

usage() { printf 'usage: %s <semver X.Y.Z>\n' "${0##*/}" >&2; }

# --- S1: argv validation FIRST, pure bash builtins — no external command
# runs before this check, not even `dirname`.
if [ $# -ne 1 ] || [[ ! "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    usage
    exit 2
fi
VERSION="$1"

# sed-patchable by tests only (see TESTING note above) — literal "" here,
# always, in the shipped artifact.
ROOT_PREFIX=""

if [ -z "$ROOT_PREFIX" ] && [ "${EUID}" -ne 0 ]; then
    echo "ERROR: must run as root (sudo bash $0 ${VERSION})" >&2
    exit 1
fi

# Absolute repo root, resolved from BASH_SOURCE via builtins only (`cd`,
# `pwd` — no external `dirname`) BEFORE `cd /` below makes a relative
# invocation path meaningless.
REPO_ROOT="$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)"

cd /
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
umask 022

# --- constants — sed-patchable by tests, literal and fixed in the shipped
# artifact.
TRUST_OWNER="root"
TRUST_GROUP="wheel"
BROKER_USER="zantara-codex"
RUNTIME_DIR="${ROOT_PREFIX}/usr/local/lib/wa-codex-broker"
CODEX_DIR="${RUNTIME_DIR}/codex"
CODEX_PIN_FILE="${RUNTIME_DIR}/codex-pin.env"
PLIST_LABEL="com.balizero.wa-codex-broker"
WRAPPER_SRC="${REPO_ROOT}/infra/launchagents/wrappers/wa-codex-broker-wrapper.sh"
WRAPPER_DST="${ROOT_PREFIX}/usr/local/libexec/wa-codex-broker-wrapper.sh"
REGISTRY_BASE="https://registry.npmjs.org/@openai%2fcodex"

STAT_BIN=/usr/bin/stat
CURL_BIN=/usr/bin/curl
TAR_BIN=/usr/bin/tar
OPENSSL_BIN=/usr/bin/openssl
PLUTIL_BIN=/usr/bin/plutil
AWK_BIN=/usr/bin/awk
MKTEMP_BIN=/usr/bin/mktemp
CHOWN_BIN=/usr/sbin/chown
CHMOD_BIN=/bin/chmod
MV_BIN=/bin/mv
RM_BIN=/bin/rm
MKDIR_BIN=/bin/mkdir
FIND_BIN=/usr/bin/find
SUDO_BIN=/usr/bin/sudo
LAUNCHCTL_BIN=/bin/launchctl
SLEEP_BIN=/bin/sleep
INSTALL_BIN=/usr/bin/install

TAG="install-wa-codex-pinned"
log() { echo "[${TAG}] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# --- S6 (cleanup trap): removes staging + temp pin file on ANY exit -------
_STAGING_DIR=""
_PIN_TMP=""
_cleanup() {
    if [ -n "$_STAGING_DIR" ] && [ -d "$_STAGING_DIR" ]; then
        "$RM_BIN" -rf "$_STAGING_DIR"
    fi
    if [ -n "$_PIN_TMP" ] && [ -f "$_PIN_TMP" ]; then
        "$RM_BIN" -f "$_PIN_TMP"
    fi
    return 0
}
trap _cleanup EXIT

# --- S2: trust root ---------------------------------------------------------
# Refuses a symlink, a missing path, wrong owner/group, or anything
# group/other-writable. Called on RUNTIME_DIR (must pre-exist — planted by
# scripts/provision_zantara_codex.sh) and on every directory this script
# itself creates.
_verify_root_owned_dir() { # $1 path, $2 label
    local path="$1" label="$2" owner group mode
    [ -L "$path" ] && die "${label} (${path}) is a symlink — refusing"
    [ -d "$path" ] || die "${label} (${path}) does not exist"
    owner="$("$STAT_BIN" -f '%Su' "$path")"
    group="$("$STAT_BIN" -f '%Sg' "$path")"
    mode="$("$STAT_BIN" -f '%Lp' "$path")"
    [ "$owner" = "$TRUST_OWNER" ] || die "${label} (${path}) not owned by ${TRUST_OWNER} (owner=${owner})"
    [ "$group" = "$TRUST_GROUP" ] || die "${label} (${path}) not group ${TRUST_GROUP} (group=${group})"
    if [ $(( 8#${mode} & 8#022 )) -ne 0 ]; then
        die "${label} (${path}) is group/other writable (mode=${mode})"
    fi
}

_verify_root_owned_dir "$RUNTIME_DIR" "trust root"

# A single new root-owned 0755 dir directly under an already-trusted
# parent — never `mkdir -p` through an unverified path, refuse a symlink
# race, re-verify (not silently trust) a pre-existing one.
_ensure_dir() { # $1 path, $2 label
    local path="$1" label="$2"
    if [ -L "$path" ]; then
        die "${label} (${path}) exists as a symlink — refusing"
    fi
    if [ -d "$path" ]; then
        _verify_root_owned_dir "$path" "$label"
        return 0
    fi
    "$MKDIR_BIN" -m 0755 "$path"
    "$CHOWN_BIN" "${TRUST_OWNER}:${TRUST_GROUP}" "$path"
    _verify_root_owned_dir "$path" "$label"
}

_ensure_dir "$CODEX_DIR" "codex dir"

# --- S3: staging + download -------------------------------------------------
_curl_https() { # $1 url $2 dest
    local url="$1" dest="$2"
    case "$url" in
        https://registry.npmjs.org/*) : ;;
        *) die "refusing non-allowlisted URL: ${url}" ;;
    esac
    "$CURL_BIN" -q -f -sS --proto '=https' --proto-redir '=https' --max-redirs 3 "$url" -o "$dest"
}

_STAGING_DIR="$("$MKTEMP_BIN" -d "${RUNTIME_DIR}/.staging.XXXXXX")" \
    || die "mktemp -d failed under ${RUNTIME_DIR}"
"$CHMOD_BIN" 0755 "$_STAGING_DIR"

log "resolving darwin-arm64 build for ${VERSION} from the npm registry"
BASE_JSON="${_STAGING_DIR}/.base.json"
_curl_https "${REGISTRY_BASE}/${VERSION}" "$BASE_JSON" \
    || die "npm registry lookup failed for @openai/codex@${VERSION}"

ALIAS="$("$PLUTIL_BIN" -extract 'optionalDependencies.@openai/codex-darwin-arm64' raw -o - "$BASE_JSON" 2>/dev/null || true)"
[ -n "$ALIAS" ] || die "no @openai/codex-darwin-arm64 optionalDependency alias for ${VERSION}"
PLATFORM_VER="${ALIAS##*@}"
[ -n "$PLATFORM_VER" ] || die "empty darwin-arm64 platform version for ${VERSION}"

PLATFORM_JSON="${_STAGING_DIR}/.platform.json"
_curl_https "${REGISTRY_BASE}/${PLATFORM_VER}" "$PLATFORM_JSON" \
    || die "npm registry lookup failed for @openai/codex@${PLATFORM_VER}"

TARBALL="$("$PLUTIL_BIN" -extract dist.tarball raw -o - "$PLATFORM_JSON" 2>/dev/null || true)"
INTEGRITY="$("$PLUTIL_BIN" -extract dist.integrity raw -o - "$PLATFORM_JSON" 2>/dev/null || true)"
[ -n "$TARBALL" ] || die "empty dist.tarball for ${PLATFORM_VER}"
case "$TARBALL" in
    https://registry.npmjs.org/*) : ;;
    *) die "tarball host is not registry.npmjs.org: ${TARBALL}" ;;
esac
case "$INTEGRITY" in
    sha512-*) : ;;
    *) die "dist.integrity for ${PLATFORM_VER} is not sha512: '${INTEGRITY}'" ;;
esac

TGZ="${_STAGING_DIR}/.codex.tgz"
_curl_https "$TARBALL" "$TGZ" || die "tarball download failed: ${TARBALL}"

WANT_B64="${INTEGRITY#sha512-}"
GOT_B64="$("$OPENSSL_BIN" dgst -sha512 -binary "$TGZ" | "$OPENSSL_BIN" base64 -A)"
[ "$GOT_B64" = "$WANT_B64" ] || die "integrity mismatch for ${TARBALL}"
log "sha512 integrity OK"

# --- S4: archive listing check, fail CLOSED ---------------------------------
# Full `tar -tvzf` listing to a FILE first (tar's own exit status is
# checked), then ONE awk pass over the WHOLE file — never a `grep -q` in a
# pipeline: a `-q` reader exits on its first match and closes the pipe
# early, which SIGPIPEs the writer — under `pipefail` an archive with
# 20,000 regular entries and ONE trailing symlink was wrongly ACCEPTED
# this way (PR #7313 round-2 finding). LC_ALL=C pins the date field count
# the parser below assumes (month, day, time-or-year — always 3 tokens).
LISTING="${_STAGING_DIR}/.listing.txt"
if ! LC_ALL=C "$TAR_BIN" -tvzf "$TGZ" > "$LISTING"; then
    die "tar -tvzf listing failed for ${TGZ}"
fi
if ! "$AWK_BIN" '
    {
        type = substr($0, 1, 1)
        if (type != "-" && type != "d") {
            print "unsafe entry (type=" type "): " $0
            bad = 1
            next
        }
        name = ""
        for (i = 9; i <= NF; i++) name = name (i > 9 ? " " : "") $i
        if (name ~ /^\// || name ~ /(^|\/)\.\.(\/|$)/) {
            print "unsafe path: " name
            bad = 1
        }
    }
    END { exit bad ? 1 : 0 }
' "$LISTING"; then
    die "archive ${TGZ} contains a symlink/hardlink/absolute-path/.. entry — refusing to extract"
fi
log "archive listing OK ($("$AWK_BIN" 'END{print NR}' "$LISTING") entries)"

# --- S5: extract, normalize, verify, probe ----------------------------------
_verify_extracted_tree() { # $1 dir, $2 expected version substring
    local dir="$1" want="$2" probe bad
    [ -L "$dir" ] && die "tree ${dir} is a symlink — refusing"
    bad="$("$FIND_BIN" "$dir" \( ! -user "${TRUST_OWNER}" -o ! -group "${TRUST_GROUP}" -o -perm -022 -o -type l \) -print)"
    [ -z "$bad" ] || die "tree ${dir} failed the post-normalize find check:
${bad}"
    [ -x "${dir}/bin/codex" ] || die "tree ${dir} has no executable bin/codex"
    probe="$("$SUDO_BIN" -u "$BROKER_USER" -H /usr/bin/env -i "${dir}/bin/codex" --version)" \
        || die "binary in ${dir} failed --version as ${BROKER_USER}"
    case "$probe" in
        *"$want"*) : ;;
        *) die "binary in ${dir} --version does not report ${want}: ${probe}" ;;
    esac
    log "verified ${dir} (as ${BROKER_USER}): ${probe}"
}

EXTRACT_DIR="${_STAGING_DIR}/tree"
"$MKDIR_BIN" -m 0755 "$EXTRACT_DIR"
"$TAR_BIN" -x --no-same-owner --no-same-permissions -f "$TGZ" -C "$EXTRACT_DIR" \
    --strip-components=3 "package/vendor/aarch64-apple-darwin" \
    || die "tar extract failed"
[ -x "${EXTRACT_DIR}/bin/codex" ] || die "extracted tree has no bin/codex"

"$CHOWN_BIN" -R "${TRUST_OWNER}:${TRUST_GROUP}" "$EXTRACT_DIR"
"$CHMOD_BIN" -R u=rwX,go=rX "$EXTRACT_DIR"
"$CHMOD_BIN" -R ug-s "$EXTRACT_DIR"

_verify_extracted_tree "$EXTRACT_DIR" "$VERSION"

# --- S6: install -------------------------------------------------------------
DEST="${CODEX_DIR}/${VERSION}"
if [ -e "$DEST" ] && [ ! -L "$DEST" ] && [ -d "$DEST" ]; then
    log "reuse: ${DEST} already present — re-verifying before reuse"
    _verify_extracted_tree "$DEST" "$VERSION"
    log "reuse: ${DEST} verified — discarding staged download"
elif [ -e "$DEST" ]; then
    die "${DEST} exists but is not a plain directory (symlink or other) — refusing"
else
    "$MV_BIN" "$EXTRACT_DIR" "$DEST"
    log "installed ${DEST}"
fi
FINAL_BIN="${DEST}/bin/codex"

# Pin file — root:wheel 0644, WA_CODEX_CLI_VERSION_PIN + WA_CODEX_BIN only,
# written atomically (temp file in the same dir, then mv).
_PIN_TMP="$("$MKTEMP_BIN" "${RUNTIME_DIR}/.codex-pin.env.XXXXXX")" \
    || die "mktemp failed for pin file"
{
    printf 'WA_CODEX_CLI_VERSION_PIN=%s\n' "$VERSION"
    printf 'WA_CODEX_BIN=%s\n' "$FINAL_BIN"
} > "$_PIN_TMP"
"$CHOWN_BIN" "${TRUST_OWNER}:${TRUST_GROUP}" "$_PIN_TMP"
"$CHMOD_BIN" 0644 "$_PIN_TMP"
"$MV_BIN" "$_PIN_TMP" "$CODEX_PIN_FILE"
_PIN_TMP=""
log "wrote ${CODEX_PIN_FILE} (pin=${VERSION}, bin=${FINAL_BIN})"

# --- S8: install wrapper + kickstart ----------------------------------------
# Same install(1) invocation shape as scripts/provision_zantara_codex.sh —
# root:wheel 0755, never under /Users/zantara-codex.
"$INSTALL_BIN" -o "${TRUST_OWNER}" -g "${TRUST_GROUP}" -m 0755 "$WRAPPER_SRC" "$WRAPPER_DST"
log "wrapper installed: ${WRAPPER_DST}"

"$LAUNCHCTL_BIN" kickstart -k "system/${PLIST_LABEL}" \
    || die "launchctl kickstart failed for system/${PLIST_LABEL}"
"$SLEEP_BIN" 2
STATE_LINE="$("$LAUNCHCTL_BIN" print "system/${PLIST_LABEL}" 2>&1 | "$AWK_BIN" '/state = /{print; exit}')"
log "daemon state: ${STATE_LINE:-<not found>}"
log "done: codex ${VERSION} pinned at ${FINAL_BIN}"
