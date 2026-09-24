#!/bin/bash
# wa-codex-broker-admin.sh — root-owned admin verb for the WA codex broker's
# OWN dedicated codex binary, decoupled from the shared Homebrew
# @openai/codex install any other seat on Pro may upgrade.
#
# Fixes the "pin drift" outage class (W136, docs/scars/cicatrix-scars.md):
# the daemon (apps/backend-rag/backend/services/integrations/wa_codex_daemon.py)
# refuses to claim once `codex --version` stops matching
# `WA_CODEX_CLI_VERSION_PIN` — twice now (2026-08-20/23, 2026-09-25) that
# mismatch was caused by an UNRELATED seat running `brew upgrade` /
# `npm i -g @openai/codex` against the ONE shared install at
# /opt/homebrew/lib/node_modules/@openai/codex. Once `bump` has run once,
# the daemon's WA_CODEX_BIN points at a version-namespaced copy under
# /usr/local/lib/wa-codex-broker/codex/<ver>/ that nothing else on the
# machine ever touches, so a shared-package upgrade can no longer pause it.
# `WA_CODEX_BIN` is read directly by the daemon (`codex_bin=os.environ.get(
# "WA_CODEX_BIN") or None`, wa_codex_daemon.py ~l.200) — no daemon code
# change needed, only the env file + a dedicated binary tree.
#
# Installed root:wheel 0755 at /usr/local/libexec/wa-codex-broker-admin.sh
# by scripts/install_wa_codex_admin.sh (also wired into
# scripts/provision_zantara_codex.sh so a re-provision keeps it current —
# a merge alone never updates the live copy, superscar #1 / W107). Callable
# passwordless by the `nuzantara` interactive user via the sudoers drop-in
# infra/sudoers/wa-codex-broker-admin — see that file's own comment: the
# sudoers wildcard on `bump *` is NOT the security boundary (glob `*`
# matches whitespace too, per `man sudoers`), the strict argument
# validation BELOW is.
#
# Verbs:
#   status        — pin, dedicated binary path + its --version, launchd state
#   bump <semver> — fetch/verify/install the darwin-arm64 codex build for
#                   <semver> straight from the npm registry (no node/npm
#                   needed), pin it, kickstart the daemon onto it
#
# Hardening (cicatrix-superscar #3 Guard-over/under-match, #4 Secret-clear,
# lesson: a script that executes on ANY unknown flag is itself a scar —
# lesson_a_rollback_script_that_executes_on_any_unknown_flag):
#   - set -euo pipefail, absolute paths, umask 077, PATH reset before any
#     verb runs (outside test mode — see below).
#   - Every verb/argument is validated BEFORE anything executes; unknown
#     verbs and any extra argument are a hard refusal, not a warning.
#   - No `eval`, no argument is ever built into a shell string and handed to
#     `sh -c`; every external command is invoked with a literal argv.
#   - The env file (`.wa-codex-broker.env`, 0600, holds WA_BROKER_KEY) is
#     never echoed or catted in full — only the two specific keys this verb
#     needs are grepped by name, and only the two specific keys are ever
#     rewritten (temp file in the same directory, then `mv`, preserving
#     owner zantara-codex:staff and mode 0600).
set -euo pipefail
umask 077

TAG="wa-codex-broker-admin"
log() { echo "[${TAG}] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# --- test-mode carve-out (ONLY this exact var flips it) --------------------
# scripts/tests/test_wa_codex_broker_admin.py sets both of these to redirect
# every path this script touches under a scratch dir and to let a stub
# curl/tar/openssl sit ahead of the real ones on PATH — never touching
# /usr/local, /etc, real root, or launchctl. Production invocation (the
# sudoers drop-in) never sets WA_CODEX_ADMIN_TEST_MODE, so this branch is
# dead in prod by construction, not by convention.
if [ "${WA_CODEX_ADMIN_TEST_MODE:-}" = "1" ]; then
    ROOT_PREFIX="${WA_CODEX_ADMIN_ROOT_PREFIX:-}"
    log "TEST MODE — root check skipped, paths prefixed with '${ROOT_PREFIX}'"
else
    ROOT_PREFIX=""
    PATH=/usr/bin:/bin:/usr/sbin:/sbin
    export PATH
    [ "$(id -u)" -eq 0 ] || die "must run as root"
fi

BROKER_USER="zantara-codex"
BROKER_HOME="${ROOT_PREFIX}/Users/${BROKER_USER}"
ENV_FILE="${BROKER_HOME}/.wa-codex-broker.env"
RUNTIME_DIR="${ROOT_PREFIX}/usr/local/lib/wa-codex-broker"
CODEX_DIR="${RUNTIME_DIR}/codex"
PLIST_LABEL="com.balizero.wa-codex-broker"
REGISTRY_BASE="https://registry.npmjs.org/@openai%2fcodex"
SEMVER_RE='^[0-9]+\.[0-9]+\.[0-9]+$'

# --- verb dispatch — validated BEFORE anything executes ---------------------
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

cmd_status() {
    local pin bin
    # `|| true`: under `set -o pipefail` a no-match grep (exit 1, e.g. an
    # env file with no WA_CODEX_BIN= line yet) would fail the whole pipe
    # and — outside any if/elif condition — silently kill the script under
    # `set -e` before it prints anything (caught live: `status` exited with
    # empty stdout and no error).
    pin="$(grep -m1 '^WA_CODEX_CLI_VERSION_PIN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
    bin="$(grep -m1 '^WA_CODEX_BIN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
    echo "pin: ${pin:-<unset>}"
    if [ -n "$bin" ] && [ -x "$bin" ]; then
        echo "dedicated binary: ${bin}"
        echo "dedicated binary --version: $("$bin" --version 2>&1 || true)"
    else
        echo "dedicated binary: <unset or missing — daemon falls back to PATH-resolved 'codex'>"
    fi
    echo "launchd:"
    if out="$(launchctl print "system/${PLIST_LABEL}" 2>&1)"; then
        printf '%s\n' "$out" | grep -E '^\s*state = ' || echo "  (loaded, state line not found)"
    else
        echo "  (launchctl print failed — not loaded, or not running as root)"
    fi
}

cmd_bump() {
    local ver="$1" dest bin_path
    # `tmpdir` is deliberately NOT `local`: the EXIT trap below fires after
    # this function returns, when a local's scope is already gone — under
    # `set -u` that read back as "tmpdir: unbound variable" (caught live on
    # M5, bash 3.2). A trailing cleanup failure must never mask a bump that
    # otherwise fully succeeded.
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/wa-codex-admin-bump.XXXXXX")"
    trap 'rm -rf "${tmpdir:-}"' EXIT

    dest="${CODEX_DIR}/${ver}"
    bin_path="${dest}/bin/codex"

    if [ -x "$bin_path" ] && "$bin_path" --version 2>/dev/null | grep -qF "$ver"; then
        log "fetch/extract: SKIP (${dest} already present and verified — reused, e.g. a rollback)"
    else
        # --- fetch: resolve the darwin-arm64 alias from the base package's
        # own metadata (no node/npm needed — plain registry reads) ---------
        log "fetch: resolving darwin-arm64 build for ${ver} from the npm registry"
        curl -fsSL "${REGISTRY_BASE}/${ver}" -o "${tmpdir}/base.json" \
            || die "npm registry lookup failed for @openai/codex@${ver} — does that version exist?"

        local platform_ver
        if ! platform_ver="$(python3 - "${tmpdir}/base.json" <<'PY'
import json, sys
with open(sys.argv[1]) as fh:
    data = json.load(fh)
alias = (data.get("optionalDependencies") or {}).get("@openai/codex-darwin-arm64")
if not alias or not alias.startswith("npm:@openai/codex@"):
    sys.exit("no @openai/codex-darwin-arm64 optionalDependency alias in package metadata")
print(alias.rsplit("@", 1)[-1])
PY
        )"; then
            die "could not resolve the darwin-arm64 platform version for ${ver} (see above)"
        fi
        [ -n "$platform_ver" ] || die "empty darwin-arm64 platform version for ${ver}"

        curl -fsSL "${REGISTRY_BASE}/${platform_ver}" -o "${tmpdir}/platform.json" \
            || die "npm registry lookup failed for @openai/codex@${platform_ver}"

        # bash 3.2 on macOS (M5 and Pro both measured) has no mapfile/
        # readarray (bash 4+ only) — two `read`s off one process
        # substitution instead.
        local tarball="" integrity=""
        {
            IFS= read -r tarball
            IFS= read -r integrity
        } < <(python3 - "${tmpdir}/platform.json" <<'PY'
import json, sys
with open(sys.argv[1]) as fh:
    d = json.load(fh)
dist = d.get("dist") or {}
tarball = dist.get("tarball") or ""
integrity = dist.get("integrity") or ""
if not tarball or not integrity.startswith("sha512-"):
    sys.exit("dist.tarball/dist.integrity missing or not sha512 in platform metadata")
print(tarball)
print(integrity)
PY
        ) || die "could not parse tarball/integrity from platform metadata (see above)"
        [ -n "$tarball" ] && [ -n "$integrity" ] || die "empty tarball/integrity for ${platform_ver}"

        log "fetch: downloading ${tarball}"
        curl -fsSL "$tarball" -o "${tmpdir}/codex.tgz" || die "tarball download failed: ${tarball}"

        # --- verify: sha512 must match dist.integrity exactly ---------------
        local want_b64 got_b64
        want_b64="${integrity#sha512-}"
        got_b64="$(openssl dgst -sha512 -binary "${tmpdir}/codex.tgz" | openssl base64 -A)"
        [ "$got_b64" = "$want_b64" ] \
            || die "integrity mismatch for ${tarball}: expected ${want_b64}, got ${got_b64} — refusing to install"
        log "verify: sha512 integrity OK"

        # --- extract: the darwin-arm64 tarball ships
        # package/vendor/aarch64-apple-darwin/{bin,codex-path,codex-resources}
        # — stripped to land at <dest>/{bin,codex-path,codex-resources},
        # same relative layout the upstream JS launcher itself resolves
        # (bin/codex.js: vendorRoot/<target-triple>/bin/codex), so the
        # native binary finds its sibling rg/zsh/voice resources unchanged.
        rm -rf "${dest}.partial"
        mkdir -p "${dest}.partial"
        tar -xzf "${tmpdir}/codex.tgz" -C "${dest}.partial" \
            --strip-components=3 "package/vendor/aarch64-apple-darwin" \
            || die "tar extract failed"
        [ -x "${dest}.partial/bin/codex" ] || die "extracted tree has no bin/codex"
        "${dest}.partial/bin/codex" --version 2>/dev/null | grep -qF "$ver" \
            || die "extracted binary does not report version ${ver}"
        if [ "${WA_CODEX_ADMIN_TEST_MODE:-}" != "1" ]; then
            chown -R root:wheel "${dest}.partial"
        fi
        rm -rf "$dest"
        mkdir -p "$(dirname "$dest")"
        mv "${dest}.partial" "$dest"
        log "extract: DONE -> ${dest}"
    fi

    # --- pin: rewrite ONLY the two keys, never the whole file -------------
    local envtmp
    envtmp="$(mktemp "${ENV_FILE}.XXXXXX")"
    awk -v pin="$ver" -v binp="$bin_path" '
        BEGIN { seen_pin = 0; seen_bin = 0 }
        /^WA_CODEX_CLI_VERSION_PIN=/ { print "WA_CODEX_CLI_VERSION_PIN=" pin; seen_pin = 1; next }
        /^WA_CODEX_BIN=/            { print "WA_CODEX_BIN=" binp;            seen_bin = 1; next }
        { print }
        END {
            if (!seen_pin) print "WA_CODEX_CLI_VERSION_PIN=" pin
            if (!seen_bin) print "WA_CODEX_BIN=" binp
        }
    ' "$ENV_FILE" > "$envtmp"
    if [ "${WA_CODEX_ADMIN_TEST_MODE:-}" != "1" ]; then
        chown "${BROKER_USER}:staff" "$envtmp"
    fi
    chmod 0600 "$envtmp"
    mv "$envtmp" "$ENV_FILE"
    log "pin: WA_CODEX_CLI_VERSION_PIN=${ver}, WA_CODEX_BIN=${bin_path}"

    if [ "${WA_CODEX_ADMIN_TEST_MODE:-}" = "1" ]; then
        log "TEST MODE — skipping launchctl kickstart"
        return 0
    fi
    launchctl kickstart -k "system/${PLIST_LABEL}" || die "launchctl kickstart failed"
    log "kickstart: DONE (system/${PLIST_LABEL})"
}

case "$VERB" in
status) cmd_status ;;
bump) cmd_bump "$VERSION" ;;
esac
