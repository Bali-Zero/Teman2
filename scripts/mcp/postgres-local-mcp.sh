#!/bin/bash
# postgres-local-mcp.sh — launcher for the `postgres-nuzantara-local` MCP server.
#
# WHY THIS EXISTS. On 2026-08-26 this MCP returned `Command failed with no output`
# on three successive calls, including a bare `SELECT 1`, and the P05 Intel Lake
# lane recorded "no live counts anywhere" as a result. Measured afterwards: the
# database, the role, the Keychain entry and a direct psql connection were ALL
# healthy, and the failure could not be reproduced. The root cause is UNKNOWN and
# is deliberately NOT guessed at (an earlier guess — an npx cold start on a
# deprecated package — was refuted by measuring it: the package is cached and the
# server answers in ~2s).
#
# So this does not "fix the bug". It fixes what made the bug UNDIAGNOSABLE.
#
# STDOUT IS THE JSON-RPC CHANNEL. Never write to stdout here — one stray
# human-readable line corrupts the protocol. All diagnostics go to stderr + log.
#
# Exit codes: 70 keychain lookup failed · 71 keychain returned empty ·
#             72 keychain lookup TIMED OUT · 73 log dir unusable ·
#             78 refused: production-proxy port.

set -uo pipefail

# --- $HOME may be unset in a service-style invocation; `set -u` would kill us
# with bash's own generic message before any structured diagnostic exists.
HOME_DIR="${HOME:-}"
LOG_DIR="${NUZ_MCP_LOG_DIR:-${HOME_DIR:-/tmp}/logs}"
LOG="$LOG_DIR/mcp-postgres-local.log"

umask 077   # the log may carry connection errors; owner-only, set BEFORE creation

log() {
    printf '%s postgres-local-mcp: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
    printf '%s postgres-local-mcp: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG" 2>/dev/null || true
}

# Setup errors are REPORTED, not swallowed: the one fact that explains why the
# log is unusable is exactly the fact worth keeping. stderr still works even when
# the file does not, so this degrades rather than dies.
if ! MKDIR_ERR="$(mkdir -p "$LOG_DIR" 2>&1)"; then
    printf 'postgres-local-mcp: WARNING: log dir %s unusable: %s\n' "$LOG_DIR" "$MKDIR_ERR" >&2
fi
if ! TOUCH_ERR="$(: >>"$LOG" 2>&1)"; then
    printf 'postgres-local-mcp: WARNING: log file %s unwritable: %s\n' "$LOG" "$TOUCH_ERR" >&2
fi
chmod 600 "$LOG" 2>/dev/null || true

# If the log is unusable, fall back to /dev/null rather than carrying a path that
# breaks every `2>>"$LOG"` downstream. Measured: with an unwritable path, the
# REDIRECTION itself fails, so the credential fetch died with exit 1 before
# `security` ever ran — a broken log killed the launcher. Diagnostics still reach
# stderr (log() writes there first and unconditionally), so this degrades.
if ! : >>"$LOG" 2>/dev/null; then
    printf 'postgres-local-mcp: WARNING: %s unusable; diagnostics go to stderr only.\n' "$LOG" >&2
    LOG=/dev/null
fi

PKG_VERSION="${NUZ_PG_MCP_VERSION:-0.6.2}"
KEYCHAIN_SERVICE="nuzantara-dev-readonly"
KEYCHAIN_ACCOUNT="nuzantara_dev_readonly"
KEYCHAIN_TIMEOUT="${NUZ_KEYCHAIN_TIMEOUT:-10}"
# Absolute by default (a PATH-ahead `security` would hand back an attacker-chosen
# value that becomes PGPASSWORD). Overridable ONLY so the tests can stub it.
SECURITY_BIN="${NUZ_SECURITY_BIN:-/usr/bin/security}"
NPX_BIN="${NUZ_NPX_BIN:-npx}"   # npx location varies (brew/nvm); left on PATH

# 127.0.0.1:5432 is the LOCAL dev Postgres. 15432 is a flyctl proxy to PRODUCTION.
CONN="${NUZ_PG_MCP_CONN:-postgresql://nuzantara_dev_readonly@127.0.0.1:5432/nuzantara_dev?sslmode=disable}"

# A libpq URI may end the port with `/dbname`, with `?query`, or with nothing at
# all — `*:15432/*` alone matched only the first and let the other two through
# (found by adversarial review, reproduced live).
case "$CONN" in
    *:15432|*:15432/*|*:15432\?*)
        log "FATAL: connection string targets port 15432 (flyctl PRODUCTION proxy). Refusing."
        exit 78 ;;
esac

# --- credential fetch: status-checked AND time-boxed.
#
# Two distinct silent-failure modes are guarded here:
#   (a) EMPTY/FAILED: the old form `PGPASSWORD=$(security ...) exec npx ...` put the
#       substitution in an assignment PREFIX, which DISCARDS its exit status — a
#       failed lookup became an empty password and the shell carried on.
#   (b) HANG: `security` blocks indefinitely on a GUI keychain-authorization
#       prompt (ACL reset by an OS update, "Always Allow" lost). Execution freezes
#       BEFORE any diagnostic can be emitted — no stdout, no stderr, no exit code.
#       That is indistinguishable from the original incident, so a wrapper whose
#       whole purpose is loud failure MUST time-box it. Found by adversarial
#       review; the first version of this script had exactly this hole.
#
# The credential is fetched with a real TIMEOUT and a checked exit status, and it
# never touches disk: a plain command substitution keeps it in memory only.
#
# The time-box is `perl -e 'alarm shift; exec @ARGV'` — the alarm timer SURVIVES
# exec, so SIGALRM lands on `security` itself and the process dies (exit 142).
# perl is present on every macOS. A first attempt used a FIFO plus `read -t`;
# it was discarded after measuring it: `read` returned EOF (1), not a timeout
# (>128), so the timeout branch never fired and `wait` blocked forever — and
# killing the child left a grandchild holding the caller's stdout, which is the
# very silent hang this guard exists to prevent.
if [ -x /usr/bin/perl ]; then
    PW="$(/usr/bin/perl -e 'alarm shift; exec @ARGV' "$KEYCHAIN_TIMEOUT" \
        "$SECURITY_BIN" find-generic-password -s "$KEYCHAIN_SERVICE" -a "$KEYCHAIN_ACCOUNT" -w \
        2>>"$LOG")"
    RC=$?
else
    # No perl: still status-checked, just not time-boxed. Say so rather than
    # pretend the guarantee holds.
    log "WARNING: /usr/bin/perl absent — keychain lookup is NOT time-boxed."
    PW="$("$SECURITY_BIN" find-generic-password -s "$KEYCHAIN_SERVICE" -a "$KEYCHAIN_ACCOUNT" -w 2>>"$LOG")"
    RC=$?
fi

if [ "$RC" -eq 142 ]; then   # 128 + SIGALRM(14)
    log "FATAL: keychain lookup TIMED OUT after ${KEYCHAIN_TIMEOUT}s (service='$KEYCHAIN_SERVICE')."
    log "  Most likely a GUI keychain-authorization prompt nobody can answer in this context."
    log "  Fix: run the lookup once interactively and grant 'Always Allow', or unlock the login keychain."
    exit 72
fi
if [ "$RC" -ne 0 ]; then
    log "FATAL: keychain lookup failed (exit $RC) for service='$KEYCHAIN_SERVICE' account='$KEYCHAIN_ACCOUNT'. See $LOG."
    exit 70
fi
if [ -z "$PW" ]; then
    log "FATAL: keychain returned an EMPTY password (exit 0) — the case the old inline"
    log "  assignment could not see, because a substitution in an assignment prefix"
    log "  discards its exit status."
    exit 71
fi

log "starting: pkg=@modelcontextprotocol/server-postgres@$PKG_VERSION db=nuzantara_dev host=127.0.0.1:5432 (credential ok, ${#PW} chars)"

# NOTE (accepted, documented): PGPASSWORD is exported before exec, so the npx
# bootstrap inherits it, not only the final server process. macOS blocks reading
# another process's environment via ps (verified), so this is scoped exposure
# within our own process tree, not a local-user leak.
export PGPASSWORD="$PW"
unset PW
exec "$NPX_BIN" -y "@modelcontextprotocol/server-postgres@$PKG_VERSION" "$CONN" \
    2> >(tee -a "$LOG" >&2)
