#!/usr/bin/env bash
# Resolve WHICH fly credential is actually alive — by asking fly, never by assuming.
#
# WHY THIS EXISTS (2026-07-26)
# ---------------------------
# flyctl takes its credential from two places: `FLY_API_TOKEN`/`FLY_ACCESS_TOKEN`
# in the environment, or the token stored in `~/.fly/config.yml`. Env wins.
#
# On 2026-06-03 the env copy was STALE and shadowed a VALID config token, so
# every `fly` call answered "unauthorized" and the nightly Postgres backup died
# silently for five days. The fix shipped then was a bare `unset FLY_API_TOKEN`
# — correct for that day's world, and pinned to it.
#
# On 2026-07-26 the world inverted: the CONFIG token went dead ("no access token
# available") while the env token was valid. The 2026-06-03 cure was now the
# disease — it threw away the only working credential. The prod PG backup
# aborted on both nightly runs, and the error text it printed blamed the env
# token, which was in fact the one that worked. Cure and diagnosis were both
# pointing at yesterday's world.
#
# The bug is not "which token" — it is HARDCODING which token, in either
# direction. Either source can rot at any time and nothing announces it. So we
# probe: whichever source `fly auth whoami` accepts is the one we keep, and we
# LOG which one it was. A silent fallback is exactly how this stayed invisible
# for two runs.
#
# USAGE
#     source "$(dirname "$0")/lib/fly_credential.sh"
#     resolve_fly_credential "$FLY_BIN" || exit 1
#
# CONTRACT
#   - exit 0: exactly one credential source is active in the environment, and
#     the choice has been logged. Callers may run `fly` normally.
#   - exit 1: BOTH sources were refused. Nothing is left exported, and the
#     remedy for each source has been logged. The caller must abort — there is
#     no credential to work with.
#   - The caller may define `log()`; if it does, we use it, so the choice lands
#     in the same log stream as everything else. Otherwise we print to stderr.
#
# Overridable for tests: pass the binary as $1 (a stub that accepts/refuses on
# demand). See tests/test_fly_credential.sh — guilt AND innocence, both worlds.

_fly_cred_log() {
    if declare -F log >/dev/null 2>&1; then
        log "$@"
    else
        echo "[fly-credential] $*" >&2
    fi
}

# _fly_auth_ok <fly_bin> — does this binary authenticate with the CURRENT env?
_fly_auth_ok() {
    "$1" auth whoami >/dev/null 2>&1
}

resolve_fly_credential() {
    local fly_bin="${1:-${FLY_BIN:-/opt/homebrew/bin/fly}}"
    # Capture whatever the secrets file exported, then clear BOTH names so the
    # config-file probe is genuinely un-shadowed. FLY_ACCESS_TOKEN is checked
    # second only as a source of a value — flyctl honours either name.
    local env_token="${FLY_API_TOKEN:-}"
    [ -n "$env_token" ] || env_token="${FLY_ACCESS_TOKEN:-}"
    unset FLY_API_TOKEN FLY_ACCESS_TOKEN

    if _fly_auth_ok "$fly_bin"; then
        _fly_cred_log "fly auth: config-file token (~/.fly/config.yml) accepted"
        return 0
    fi

    if [ -z "$env_token" ]; then
        _fly_cred_log "ERROR: ~/.fly/config.yml token was REFUSED and no FLY_API_TOKEN is set."
        _fly_cred_log "ERROR: remedy: 'fly auth login' on this host, or add a fresh FLY_API_TOKEN to ~/.nuzantara-secrets.env."
        return 1
    fi

    export FLY_API_TOKEN="$env_token"
    if _fly_auth_ok "$fly_bin"; then
        _fly_cred_log "fly auth: config-file token REFUSED — using FLY_API_TOKEN from the secrets file instead."
        _fly_cred_log "NOTE: ~/.fly/config.yml has rotted; refresh it with 'fly auth login' when convenient."
        return 0
    fi

    unset FLY_API_TOKEN
    _fly_cred_log "ERROR: BOTH fly credentials were REFUSED (~/.fly/config.yml AND FLY_API_TOKEN)."
    _fly_cred_log "ERROR: remedy: 'fly auth login' on this host, and refresh FLY_API_TOKEN in ~/.nuzantara-secrets.env."
    return 1
}
