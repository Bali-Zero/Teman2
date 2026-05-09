#!/usr/bin/env bash
# heartbeat.sh — minimal heartbeat writer for the Innervation Genoma.
#
# Writes a single-line JSON to ~/.organism/last_seen/<organ_id>.json.
# Atomic via write-to-tmp + mv. Idempotent (overwrites previous).
#
# Source pattern (bash):
#   source ~/Desktop/nuzantara/scripts/lib/heartbeat.sh
#   organism_heartbeat "pro.my_organ" "ok"
#   organism_heartbeat "pro.my_organ" "error" "rc=42 timeout"
#
# CLI pattern (any shell that can't source):
#   ~/Desktop/nuzantara/scripts/lib/heartbeat.sh pro.my_organ ok
#   ~/Desktop/nuzantara/scripts/lib/heartbeat.sh pro.my_organ error "rc=42"

set -o pipefail

_organism_hb_dir="${ORGANISM_LAST_SEEN_DIR:-${HOME}/.organism/last_seen}"

# organism_heartbeat <organ_id> <status> [note]
# - <organ_id> matches the `id` field in organs_registry.yaml (e.g. pro.cpu_monitor)
# - <status> is one of: ok | error | warning | starting | degraded
# - [note] free-form short string, embedded as "note" key
organism_heartbeat() {
    local id="${1:?heartbeat: organ_id required}"
    local status="${2:-ok}"
    local note="${3:-}"

    mkdir -p "$_organism_hb_dir" 2>/dev/null || return 0  # never fail caller

    local path="${_organism_hb_dir}/${id}.json"
    local tmp="${path}.tmp.$$"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # Escape only the bare minimum: backslash + double-quote inside note.
    note="${note//\\/\\\\}"
    note="${note//\"/\\\"}"

    {
        printf '{"ts":"%s","status":"%s","note":"%s"}\n' "$ts" "$status" "$note"
    } > "$tmp" 2>/dev/null && mv "$tmp" "$path" 2>/dev/null

    return 0  # heartbeat MUST never break the caller
}

# CLI mode if invoked directly.
if [[ "${BASH_SOURCE[0]:-$0}" == "$0" && "${ZSH_EVAL_CONTEXT:-toplevel}" != *file* ]]; then
    organism_heartbeat "$@"
fi
