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

# NOTE: no `set -o pipefail` at file scope. This file is DESIGNED to be sourced,
# and a shell option set at file scope is set on the CALLER — a library must not
# change the error semantics of a script that merely wanted a heartbeat writer.
# (The function below contains no pipeline, so it never needed it.) CLI mode sets
# it for itself, at the bottom.

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
    # Sourced from zsh, `[[ =~ ]]` below overwrites the caller's MATCH/MBEGIN/
    # MEND (zsh's regex specials) — a library must not clobber its caller's
    # variables. Declaring them local shadows them for the match's duration;
    # measured to leave the caller's values intact. Bash's BASH_REMATCH is NOT
    # protected this way (measured: `local BASH_REMATCH` still leaks on bash
    # 3.2) — a known, smaller residue, not a fixed one.
    local MATCH MBEGIN MEND

    # Strict whitelist on organ_id to prevent path traversal / shell metachars.
    # Registry id convention: [a-z][a-z0-9_]+(\.[a-z0-9_]+)*  (e.g. pro.cpu_monitor)
    if ! [[ "$id" =~ ^[a-zA-Z][a-zA-Z0-9_.]{0,80}$ ]] || [[ "$id" == *..* ]]; then
        return 0  # silently refuse — never break the caller
    fi
    # Whitelist status to the vocabulary the READER understands. This is not
    # cosmetic: `sentinel-aggregate.py` maps ok/success/healthy/starting -> ok,
    # degraded/warning -> warning, and EVERYTHING ELSE -> dead. So an
    # unrecognised value is not a formatting detail, it is a verdict.
    #
    # `warn` is normalised, not dropped: agent_worktree_cleanup_cron.sh passes
    # it (its own comment calls it "the heartbeat status=warn"), and the old
    # fallback rewrote it to "ok" — a WIP-skipped reaper reported as healthy.
    #
    # KNOWN AND DELIBERATELY NOT CHANGED HERE: launchd-liveness-detector.sh
    # passes "disabled" on its kill switch, which still falls through to "ok".
    # That IS a false green — but the naive cure is worse than the disease:
    # "disabled" is not in the reader's vocabulary, so passing it through makes
    # the organ read DEAD, and the healer would then resurrect precisely the
    # organ an operator intentionally stopped — the exact outcome that
    # wrapper's comment says the disabled heartbeat exists to prevent. Teaching
    # the READER a non-paging "disabled" state is the real fix and it is a
    # fleet-alarm change, not a shell-quoting one.
    case "$hb_status" in
        ok|error|warning|starting|degraded|fail|success|healthy) ;;
        warn) hb_status="warning" ;;
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

    # Truncate the RAW note FIRST, then escape. The other order cut escape
    # sequences in half: 499 'a' followed by a quote escaped to 501 chars, the
    # 500-char cut landed between the backslash and its quote, and the trailing
    # backslash then escaped the JSON's own closing quote — the whole sidecar
    # became unparseable, so the reader saw NOTHING rather than a long note.
    # Measured before the fix (json.loads raised on exactly that input).
    # Escaping after the cut can exceed 500 bytes; bounding the INFORMATION is
    # the point, and a note that survives is worth more than a round number.
    note="${note:0:500}"

    # Escape JSON-unsafe chars in note: backslash, quote, newline, tab, CR.
    # Backslash MUST stay first — it is the escape character for the rest.
    note="${note//\\/\\\\}"
    note="${note//\"/\\\"}"
    note="${note//$'\n'/\\n}"
    note="${note//$'\r'/\\r}"
    note="${note//$'\t'/\\t}"

    {
        printf '{"ts":"%s","status":"%s","note":"%s"}\n' "$ts" "$hb_status" "$note"
    } > "$tmp" 2>/dev/null && mv "$tmp" "$hb_path" 2>/dev/null

    return 0  # heartbeat MUST never break the caller
}

# CLI mode if invoked directly.
if [[ "${BASH_SOURCE[0]:-$0}" == "$0" && "${ZSH_EVAL_CONTEXT:-toplevel}" != *file* ]]; then
    set -o pipefail   # ours to set only when we ARE the script, never the caller's
    organism_heartbeat "$@"
fi
