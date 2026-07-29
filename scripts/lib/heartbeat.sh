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

# NOTE: nothing is assigned at file scope either. An earlier version set
# `_organism_hb_dir` here, which meant merely SOURCING the library overwrote a
# caller variable of that name — the same class of leak as the shell options
# above, just quieter. Everything the function needs it now computes itself.

# organism_heartbeat <organ_id> <status> [note]
# - <organ_id> matches the `id` field in organs_registry.yaml (e.g. pro.cpu_monitor)
# - <status> is one of: ok | error | warning | starting | degraded
# - [note] free-form short string, embedded as "note" key
organism_heartbeat() {
    # NOT `${1:?...}`: in a non-interactive shell that construct EXITS the shell,
    # so a sourcing caller that mistyped the invocation was killed by its own
    # heartbeat writer — measured, bash returned 127 and zsh 1, and the line
    # after the call never ran. That directly contradicts this function's own
    # closing contract ("MUST never break the caller"), which is worth more than
    # the diagnostic.
    local id="${1:-}"
    [ -n "$id" ] || return 0
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
    local _organism_hb_dir="${ORGANISM_LAST_SEEN_DIR:-${HOME}/.organism/last_seen}"

    # Strict whitelist on organ_id to prevent path traversal / shell metachars.
    # Registry id convention: [a-z][a-z0-9_]+(\.[a-z0-9_]+)*  (e.g. pro.cpu_monitor)
    #
    # Done WITHOUT `[[ =~ ]]` on purpose. A regex match sets its shell's match
    # globals, and a sourced library that clobbers its caller's variables is a
    # bug however small: zsh's MATCH/MBEGIN/MEND could be shadowed with `local`,
    # but bash's BASH_REMATCH could NOT (measured: `local BASH_REMATCH` still
    # leaks on bash 3.2), so the previous version fixed one shell and left a
    # declared residue in the other. Substring deletion sets no globals in
    # either shell, so the asymmetry disappears instead of being documented.
# The character set is ENUMERATED, not a range. `[a-zA-Z]` is collation-based,
    # and bash 3.2 under a UTF-8 locale matches accented letters with it —
    # measured: `LC_ALL=it_IT.UTF-8 bash -c 'id=éa; echo "${id//[a-zA-Z0-9_.]/}"'`
    # prints nothing, i.e. `é` passed the whitelist, while zsh rejected it. A
    # path-safety whitelist whose meaning depends on the caller's locale is not a
    # whitelist. Enumerating costs a long line and buys locale-independence.
    #
    # No temporary local either: `local _rest` aborts a bash caller that happens
    # to have `readonly _rest` (measured: rc=1, "readonly variable"), and a
    # library must not be able to kill its caller over an internal name.
    case "$id" in
        [abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ]*) ;;
        *) return 0 ;;          # must start with an ASCII letter
    esac
    [ -z "${id//[abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.]/}" ] \
        || return 0             # no character outside the allowed ASCII set
    [ "${#id}" -le 81 ] || return 0
    case "$id" in
        *..*) return 0 ;;       # no traversal
    esac
    # Whitelist status to the vocabulary the READER understands. This is not
    # cosmetic: `sentinel-aggregate.py` maps ok/success/healthy/starting -> ok,
    # degraded/warning -> warning, and EVERYTHING ELSE -> dead. So an
    # unrecognised value is not a formatting detail, it is a verdict.
    #
    # `warn` is normalised, not dropped: agent_worktree_cleanup_cron.sh passes
    # it (its own comment calls it "the heartbeat status=warn"), and the old
    # fallback rewrote it to "ok" — a WIP-skipped reaper reported as healthy.
    #
    # DELIBERATE, and now an EXPLICIT arm rather than a fall-through:
    # launchd-liveness-detector.sh passes "disabled" on its kill switch and we
    # map it to "ok". That IS a false green — but the naive cure is worse than
    # the disease:
    # "disabled" is not in the reader's vocabulary, so passing it through makes
    # the organ read DEAD, and the healer would then resurrect precisely the
    # organ an operator intentionally stopped — the exact outcome that
    # wrapper's comment says the disabled heartbeat exists to prevent. Teaching
    # the READER a non-paging "disabled" state is the real fix and it is a
    # fleet-alarm change, not a shell-quoting one.
    #
    # THE FALLBACK USED TO BE `ok`, AND THAT WAS THE WHOLE BUG. Only the exact
    # lowercase spellings below were recognised, so `failed`, `ERROR`, `FAIL`,
    # `crash`, `timeout` — every near-miss a caller could plausibly write — fell
    # through to "ok". An organ whose entire job is to report that something died
    # was declaring healthy everything it did not recognise, and the comment
    # directly above it already said "an unrecognised value is not a formatting
    # detail, it is a verdict". Unknown now degrades to `warning`: visible, and
    # not the `dead` a raw pass-through would page for.
    #
    # THE VERDICT PATH RUNS NO EXTERNAL COMMAND, and that is not style. The first
    # version of this fix lowercased with `tr` — and adversarial round 3 showed the
    # cure catching the disease it was written for: with `tr` failing, `error`
    # became `warning`; with a `tr` that succeeded and printed nothing, `error`
    # became `ok`. Measured in both shells. A DEATH published as healthy, by the
    # code whose whole job was to stop deaths being published as healthy. Bracket
    # patterns do the same matching with nothing that can fail.
    case "$hb_status" in
        [Oo][Kk]) hb_status="ok" ;;
        [Ee][Rr][Rr][Oo][Rr]) hb_status="error" ;;
        [Ww][Aa][Rr][Nn][Ii][Nn][Gg]) hb_status="warning" ;;
        [Ss][Tt][Aa][Rr][Tt][Ii][Nn][Gg]) hb_status="starting" ;;
        [Dd][Ee][Gg][Rr][Aa][Dd][Ee][Dd]) hb_status="degraded" ;;
        [Ss][Uu][Cc][Cc][Ee][Ss][Ss]) hb_status="success" ;;
        [Hh][Ee][Aa][Ll][Tt][Hh][Yy]) hb_status="healthy" ;;
        [Ww][Aa][Rr][Nn]) hb_status="warning" ;;
        [Ff][Aa][Ii][Ll] | [Ff][Aa][Ii][Ll][Ee][Dd] | [Ff][Aa][Ii][Ll][Uu][Rr][Ee] \
        | [Ff][Aa][Tt][Aa][Ll] | [Cc][Rr][Aa][Ss][Hh] | [Cc][Rr][Aa][Ss][Hh][Ee][Dd] \
        | [Dd][Ee][Aa][Dd] | [Tt][Ii][Mm][Ee][Oo][Uu][Tt]) hb_status="error" ;;
        [Dd][Ii][Ss][Aa][Bb][Ll][Ee][Dd]) hb_status="ok" ;;  # deliberate, see above
        "") hb_status="ok" ;;         # caller passed nothing; the default is ok
        *) hb_status="warning" ;;
    esac

    mkdir -p "$_organism_hb_dir" 2>/dev/null || return 0

    # NOT `local path` either, and this one is the worse of the two: in zsh
    # `path` is the ARRAY tied to $PATH, so declaring it local replaced PATH
    # with a one-element list holding this sidecar's filename — for the rest of
    # the function. `date` and `mv` then silently became "command not found"
    # (mv's complaint swallowed by its own 2>/dev/null), so the tmp file was
    # written and never renamed: a heartbeat directory accumulating
    # `<organ>.json.tmp.<pid>` and never the file any reader looks for.
    # Measured, not reasoned: across every name this function declares, `zsh -c
    # 'echo ${(t)v}'` reports exactly two as special — `status`
    # (integer-readonly-special) and `path` (array-tied-special). Those two are
    # renamed to hb_status/hb_path; id, note, tmp and ts are ordinary and keep
    # their names.
    local hb_path="${_organism_hb_dir}/${id}.json"
    local tmp="${hb_path}.tmp.$$"
    # A bare `ts="$(date …)"` makes the ASSIGNMENT carry date's exit status, so
    # under a caller's `set -e` a failing date killed the caller — measured, rc=42
    # in both shells, with the line after the call never reached. That is not
    # hypothetical: `scripts/outbox-prune.sh` and `scripts/wr2-cron-wrapper.sh`
    # both run `set -euo pipefail` and call this function without `|| true`.
    #
    # The fallback is deliberately the EPOCH, not "now-ish". A heartbeat is judged
    # by freshness, so a timestamp we could not obtain must read as stale — the
    # direction that raises an alarm — never as fresh.
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf '')"
    [ -n "$ts" ] || ts="1970-01-01T00:00:00Z"

    # Three passes, in this order: SANITISE -> TRUNCATE -> ESCAPE. Every ordering
    # here is load-bearing, and two of the three were wrong at some point.
    #
    # 1. SANITISE to printable ASCII (plus \n \r \t). Two independent defects die
    #    here, and both produced a sidecar no reader could parse AT ALL:
    #    - Raw C0 control bytes went straight through. The escape chain below
    #      covers \n \r \t but not \b, \f, \v, NUL or anything else in
    #      U+0000-U+001F, and a note built from a command's stderr carries them
    #      routinely. A literal 0x08 inside a JSON string is not valid JSON.
    #    - The truncation below is BYTE-based under LC_ALL=C — the locale cron
    #      hands you — so a 500-byte cut could land inside a multibyte UTF-8
    #      character and leave a lone continuation byte. The file was then not
    #      even valid UTF-8, so reading it failed before parsing began.
    #    Restricting to single-byte printables makes the cut provably safe rather
    #    than argued-safe: after this pass one byte is one character, in every
    #    locale and both shells. The cost is declared, not hidden — an accented
    #    character in a note becomes a space. A heartbeat note is "rc=42 timeout",
    #    not prose. If tr is unavailable we drop the note rather than emit a
    #    sidecar nobody can read: the note is the least valuable field here, and
    #    the ts/status the reader acts on are worth more than it.
    #    The trailing `X` is a sentinel, stripped straight back off: command
    #    substitution eats ALL trailing newlines, so a note ending in one lost it
    #    silently even though `\12` is in the keep-set and the escape phase below
    #    handles it. `X` is inside the keep-set, so `tr` passes it through.
    #
    #    Note that `tr` stays here, in the NOTE path, and is gone from the status
    #    path above. That split is the point: the note is diagnostic and losing it
    #    is survivable, while the status is a VERDICT and must not depend on
    #    anything that can fail.
    note="$(printf '%sX' "$note" | LC_ALL=C tr -c '\11\12\15\40-\176' ' ' 2>/dev/null)" \
        || note="(note dropped: could not sanitise)X"
    note="${note%X}"

    # 2. TRUNCATE the sanitised-but-unescaped note. Escaping FIRST cut escape
    #    sequences in half: 499 'a' followed by a quote escaped to 501 chars, the
    #    500-char cut landed between the backslash and its quote, and the trailing
    #    backslash then escaped the JSON's own closing quote — the whole sidecar
    #    became unparseable, so the reader saw NOTHING rather than a long note.
    #    Measured before the fix (json.loads raised on exactly that input).
    #    Escaping after the cut can exceed 500 bytes; bounding the INFORMATION is
    #    the point, and a note that survives is worth more than a round number.
    note="${note:0:500}"

    # 3. Escape JSON-unsafe chars in note: backslash, quote, newline, tab, CR.
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
