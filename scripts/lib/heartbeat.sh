#!/usr/bin/env bash
# heartbeat.sh — minimal heartbeat writer for the Innervation Genoma.
#
# Writes a single-line JSON to ~/.organism/last_seen/<organ_id>.json.
# Atomic via write-to-tmp + mv. Idempotent (overwrites previous).
#
# Source pattern (bash):
#   source ~/nuzantara/scripts/lib/heartbeat.sh
#   organism_heartbeat "pro.my_organ" "ok"
#   organism_heartbeat "pro.my_organ" "error" "rc=42 timeout"
#
# CLI pattern (any shell that can't source):
#   ~/nuzantara/scripts/lib/heartbeat.sh pro.my_organ ok
#   ~/nuzantara/scripts/lib/heartbeat.sh pro.my_organ error "rc=42"

set -o pipefail

_organism_hb_dir="${ORGANISM_LAST_SEEN_DIR:-${HOME}/.organism/last_seen}"

# organism_heartbeat <organ_id> <status> [note]
# - <organ_id> matches the `id` field in organs_registry.yaml (e.g. pro.cpu_monitor)
# - <status> is one of: ok | error | warning | starting | degraded
# - [note] free-form short string, embedded as "note" key
organism_heartbeat() {
    local id="${1:?heartbeat: organ_id required}"
    # NOT `local status`: in zsh `status` is a READ-ONLY special parameter (an
    # alias for `?`), so that assignment aborted the function with `read-only
    # variable: status` and no sidecar was ever written — while the CLI-mode
    # guard on the last line goes out of its way to make `source` from zsh
    # work. The trap was latent, not live: all four sourcing call-sites in the
    # repo are `#!/bin/bash` and the one `#!/bin/zsh` wrapper uses the CLI form
    # below — but the Source pattern in the header above invited the next zsh
    # caller straight onto it. Pinned by test_gene_g2_heartbeat_fires.py.
    local hb_status="${2:-ok}"
    local note="${3:-}"

    # Strict whitelist on organ_id to prevent path traversal / shell metachars.
    # Registry id convention: [a-z][a-z0-9_]+(\.[a-z0-9_]+)*  (e.g. pro.cpu_monitor)
    if ! [[ "$id" =~ ^[a-zA-Z][a-zA-Z0-9_.]{0,80}$ ]] || [[ "$id" == *..* ]]; then
        return 0  # silently refuse — never break the caller
    fi
    # Whitelist status to known set.
    case "$hb_status" in
        ok|error|warning|starting|degraded|fail|success|healthy) ;;
        *) hb_status="ok" ;;
    esac

    mkdir -p "$_organism_hb_dir" 2>/dev/null || return 0

    # NOT `local path` either, and this one is the worse of the two: in zsh
    # `path` is the ARRAY tied to $PATH, so declaring it local replaced PATH
    # with a one-element list holding this sidecar's filename — for the rest of
    # the function. `date` and `mv` then silently became "command not found"
    # (mv's complaint swallowed by its own 2>/dev/null), so the tmp file was
    # written and never renamed: a heartbeat directory accumulating
    # `<organ>.json.tmp.<pid>` and never the file any reader looks for.
    # Measured, not reasoned: of this function's six locals, `zsh -c 'echo
    # ${(t)v}'` reports exactly two as special — `status`
    # (integer-readonly-special) and `path` (array-tied-special). id, note,
    # tmp and ts are ordinary and keep their names.
    local hb_path="${_organism_hb_dir}/${id}.json"
    local tmp="${hb_path}.tmp.$$"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # Escape JSON-unsafe chars in note: backslash, quote, newline, tab, CR.
    note="${note//\\/\\\\}"
    note="${note//\"/\\\"}"
    note="${note//$'\n'/\\n}"
    note="${note//$'\r'/\\r}"
    note="${note//$'\t'/\\t}"
    # Truncate to 500 chars to avoid bloated heartbeat files.
    note="${note:0:500}"

    {
        printf '{"ts":"%s","status":"%s","note":"%s"}\n' "$ts" "$hb_status" "$note"
    } > "$tmp" 2>/dev/null && mv "$tmp" "$hb_path" 2>/dev/null

    return 0  # heartbeat MUST never break the caller
}

# CLI mode if invoked directly.
if [[ "${BASH_SOURCE[0]:-$0}" == "$0" && "${ZSH_EVAL_CONTEXT:-toplevel}" != *file* ]]; then
    organism_heartbeat "$@"
fi
