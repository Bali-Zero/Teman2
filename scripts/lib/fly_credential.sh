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
# probe: whichever source the probe accepts is the one we keep, and we LOG which
# one it was. A silent fallback is exactly how this stayed invisible for two
# runs.
#
# THE PROBE MUST MEASURE THE JOB (added after adversarial review, same day)
# ------------------------------------------------------------------------
# `fly auth whoami` only proves a credential IS a credential. A token scoped to
# one app passes it and then dies on `Could not find App "<other>"`. That is not
# hypothetical here: Pro's `FLY_API_TOKEN` is scoped to `nuzantara-postgres`
# ONLY (ledgered 2026-07-25), so a caller targeting `nuzantara-rag` that probed
# with `auth whoami` would be handed a credential that cannot do its work — the
# same silent-wrong-answer shape one stage later. Callers therefore pass the
# subcommand that stands for their real job; `auth whoami` is only the default
# for callers that genuinely need nothing app-scoped.
#
# USAGE
#     source "$(dirname "$0")/lib/fly_credential.sh"
#     resolve_fly_credential "$FLY_BIN" machine list --app "$FLY_APP" || exit 1
#     resolve_fly_credential "$FLY_BIN"            # defaults to: auth whoami
#
# CONTRACT
#   - exit 0: one credential source is active in the environment and has PASSED
#     the caller's probe; the choice has been logged. `FLY_CREDENTIAL_SOURCE` is
#     set to `config` or `env`, so a caller can report degradation.
#   - exit 1: every source was refused. Nothing is left exported, the remedy is
#     logged, and the probe's own stderr is echoed — otherwise "token rotted",
#     "wrong scope" and "network down" are indistinguishable to whoever reads it.
#   - When the config token wins, the env token stays UNSET on purpose. It is NOT
#     restored: flyctl reads the environment first, so putting it back would
#     re-shadow the credential we just chose — that is precisely the 2026-06-03
#     bug. "Non-destructive" here would mean re-introducing the disease.
#   - The caller may define `log()`; if it does, we use it, so the choice lands
#     in the same log stream as everything else. Otherwise we print to stderr.
#
# NOTE ON `set -e`: both callers invoke this as `resolve_fly_credential … || exit N`.
# Being part of a `||` list disables `-e` inside the whole function body, so a
# future unguarded fallible command here will NOT abort the way the caller's
# `set -euo pipefail` header suggests. Keep every fallible call explicitly tested.
#
# Overridable for tests: pass the binary as $1 (a stub that accepts/refuses on
# demand). See tests/test_fly_credential.sh — guilt AND innocence, both worlds.

# Set by resolve_fly_credential: "config" | "env" | "" (unresolved).
# Read by the SOURCING script (fly-pg-backup.sh's failure message names the
# accepted source) and by test_fly_credential.sh — shellcheck cannot see across
# the `source` boundary, hence the disable.
# shellcheck disable=SC2034
FLY_CREDENTIAL_SOURCE=""
# Last probe's stderr, so failures can say WHY rather than guess.
FLY_CREDENTIAL_PROBE_ERR=""

_fly_cred_log() {
    if declare -F log >/dev/null 2>&1; then
        log "$@"
    else
        echo "[fly-credential] $*" >&2
    fi
}

# _fly_probe <fly_bin> <probe-args...> — does fly accept the CURRENT environment?
# Captures stderr instead of shredding it: "no access token available",
# "Could not find App" and a dead network must not collapse into one message.
_fly_probe() {
    local bin="$1"; shift
    local err
    err="$("$bin" "$@" 2>&1 >/dev/null)"
    local rc=$?
    FLY_CREDENTIAL_PROBE_ERR="$err"
    return $rc
}

resolve_fly_credential() {
    local fly_bin="${1:-${FLY_BIN:-/opt/homebrew/bin/fly}}"
    shift 2>/dev/null || true
    local -a probe=("$@")
    [ ${#probe[@]} -gt 0 ] || probe=(auth whoami)

    # Collect every env-supplied credential BEFORE clearing, in flyctl's own
    # precedence order. Both names are tried: consulting FLY_ACCESS_TOKEN only
    # when FLY_API_TOKEN is *empty* (rather than when it is *refused*) would
    # destroy a valid token whenever a stale one sat next to it — a live shape,
    # since ad-hoc runs pass FLY_ACCESS_TOKEN while the secrets file exports
    # FLY_API_TOKEN.
    local -a candidates=()
    [ -n "${FLY_API_TOKEN:-}" ] && candidates+=("$FLY_API_TOKEN")
    if [ -n "${FLY_ACCESS_TOKEN:-}" ] && [ "${FLY_ACCESS_TOKEN:-}" != "${FLY_API_TOKEN:-}" ]; then
        candidates+=("$FLY_ACCESS_TOKEN")
    fi
    unset FLY_API_TOKEN FLY_ACCESS_TOKEN
    FLY_CREDENTIAL_SOURCE=""

    if _fly_probe "$fly_bin" "${probe[@]}"; then
        FLY_CREDENTIAL_SOURCE="config"
        _fly_cred_log "fly auth: config-file token (~/.fly/config.yml) accepted"
        return 0
    fi
    local config_err="$FLY_CREDENTIAL_PROBE_ERR"

    local idx=0
    for _tok in ${candidates[@]+"${candidates[@]}"}; do
        idx=$((idx + 1))
        export FLY_API_TOKEN="$_tok"
        if _fly_probe "$fly_bin" "${probe[@]}"; then
            FLY_CREDENTIAL_SOURCE="env"
            _fly_cred_log "fly auth: config-file token REFUSED — using FLY_API_TOKEN from the secrets file instead (candidate $idx/${#candidates[@]})."
            _fly_cred_log "NOTE: ~/.fly/config.yml has rotted; refresh it with 'fly auth login' when convenient."
            return 0
        fi
    done

    unset FLY_API_TOKEN
    if [ ${#candidates[@]} -eq 0 ]; then
        _fly_cred_log "ERROR: ~/.fly/config.yml token was REFUSED and no FLY_API_TOKEN is set."
    else
        _fly_cred_log "ERROR: every fly credential was REFUSED (~/.fly/config.yml AND ${#candidates[@]} env token(s))."
    fi
    # WHY it was refused, not just THAT it was — a wrong-scope token and a dead
    # network produce very different remedies and identical exit codes.
    [ -n "$config_err" ] && _fly_cred_log "ERROR: config-file probe said: ${config_err%%$'\n'*}"
    [ -n "$FLY_CREDENTIAL_PROBE_ERR" ] && [ "$FLY_CREDENTIAL_PROBE_ERR" != "$config_err" ] &&
        _fly_cred_log "ERROR: env-token probe said: ${FLY_CREDENTIAL_PROBE_ERR%%$'\n'*}"
    _fly_cred_log "ERROR: remedy: 'fly auth login' on this host, and/or refresh FLY_API_TOKEN in ~/.nuzantara-secrets.env."
    return 1
}
