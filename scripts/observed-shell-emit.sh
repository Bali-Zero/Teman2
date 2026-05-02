#!/usr/bin/env bash
# observed-shell-emit.sh — Sprint 1 PR-1.2
#
# Bash wrapper around POST /api/observed-shell/emit, intended to be
# sourced from LaunchAgent + cron-agent-python shell jobs that record
# their lifecycle into the cell-core observed-shell tier without having
# to import Python.
#
# Usage:
#   source scripts/observed-shell-emit.sh
#   observed_shell_emit translate.hourly ok '{"items":42}' "trace-abc"
#
# Or one-shot:
#   bash scripts/observed-shell-emit.sh translate.hourly ok '{"items":42}'
#
# Required env:
#   OBSERVED_SHELL_API_URL   — base URL, default http://127.0.0.1:8080
#   OBSERVED_SHELL_API_KEY   — X-API-Key header value (set in ~/.nuzantara-secrets.env)
#
# Status taxonomy (must match VALID_STATUSES in observed_shell.py):
#   ok | error | warning | skipped
#
# Failure mode: this wrapper is BEST-EFFORT. If the curl POST fails (DNS,
# TCP refused, 5xx), the script logs to stderr and returns 0 — the parent
# automation MUST NOT fail because observability is unavailable. This
# mirrors ObservedShellBus.emit() never-raises invariant.
#
# Reference:
#   docs/cell-core/observed-shell-tier.md § "Bash (LaunchAgent / launchd cron jobs)"
#   apps/backend-rag/backend/app/routers/observed_shell.py

set -uo pipefail   # NOT -e: we want to swallow curl errors

OBSERVED_SHELL_API_URL="${OBSERVED_SHELL_API_URL:-http://127.0.0.1:8080}"
OBSERVED_SHELL_API_KEY="${OBSERVED_SHELL_API_KEY:-}"

observed_shell_emit() {
    local automation_name="${1:-}"
    local status="${2:-}"
    local payload_json="${3:-{}}"
    local trace_id="${4:-}"

    if [[ -z "$automation_name" || -z "$status" ]]; then
        echo "observed_shell_emit: usage: emit <automation_name> <status> [payload_json] [trace_id]" >&2
        return 0   # best-effort — never fail caller
    fi

    if [[ -z "$OBSERVED_SHELL_API_KEY" ]]; then
        echo "observed_shell_emit: OBSERVED_SHELL_API_KEY unset — skipping emit for $automation_name" >&2
        return 0
    fi

    # Build JSON safely: jq if available (atomic, escapes everything), fall
    # back to a printf-style template that the caller is responsible for.
    local body
    if command -v jq >/dev/null 2>&1; then
        body=$(jq -nc \
            --arg name "$automation_name" \
            --arg status "$status" \
            --argjson payload "$payload_json" \
            --arg trace "$trace_id" \
            '{automation_name: $name, status: $status, payload: $payload}
             + (if $trace == "" then {} else {trace_id: $trace} end)' 2>/dev/null) || {
            echo "observed_shell_emit: jq build failed for $automation_name — skipping" >&2
            return 0
        }
    else
        # Fallback: minimal JSON without payload escape safety. Callers
        # without jq SHOULD pass payload_json='{}' to avoid corruption.
        if [[ -n "$trace_id" ]]; then
            body=$(printf '{"automation_name":"%s","status":"%s","payload":%s,"trace_id":"%s"}' \
                "$automation_name" "$status" "$payload_json" "$trace_id")
        else
            body=$(printf '{"automation_name":"%s","status":"%s","payload":%s}' \
                "$automation_name" "$status" "$payload_json")
        fi
    fi

    # 5s connect + 10s total — observability MUST NOT block real work
    curl -fsS \
        --max-time 10 \
        --connect-timeout 5 \
        -X POST "${OBSERVED_SHELL_API_URL}/api/observed-shell/emit" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: ${OBSERVED_SHELL_API_KEY}" \
        -d "$body" \
        > /dev/null 2>&1 || \
        echo "observed_shell_emit: POST failed for $automation_name (status=$status) — non-fatal" >&2

    return 0
}

# Allow direct invocation: `bash observed-shell-emit.sh <name> <status> ...`
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    observed_shell_emit "$@"
fi
