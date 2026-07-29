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
# (Its one pipeline, in the note sanitiser, is guarded on its own.) CLI mode sets
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
    # THE CONTRACT IS THIS WRAPPER, not the `return 0` at the bottom of the
    # implementation. Four rounds of adversarial review each found another way
    # for the body to kill its caller before reaching that line, and each fix
    # cured the instance: `${1:?}` exited the shell; a bare `ts="$(date …)"`
    # carried date's status into errexit; `local _rest` died on a caller's
    # `readonly _rest` — and after every internal name was namespaced, round 5
    # showed `readonly _organism_hb_id` doing it again, because ANY name can be
    # made readonly by someone. A namespace lowers the odds; it cannot close the
    # class. Neither can enumerating the statements: the `&& mv` at the end of
    # the writer is an AND-list whose failure trips errexit too.
    #
    # So the guarantee stops depending on the body being careful. Whatever the
    # implementation does — a readonly collision, a failed rename, a `local` on
    # a name we have not thought of — it is absorbed here and the caller sees 0.
    # stderr is deliberately NOT swallowed: a heartbeat that cannot be written
    # must still be able to say so (that is finding 4 of the same round — a
    # silent success is the exact "green that lies" this organ exists to fight).
    # A SUBSHELL, not a plain call, and the difference is not stylistic. `|| :`
    # absorbs an exit STATUS; it cannot absorb a shell that has exited. When a
    # caller has made one of our names readonly, the failing `local` is only the
    # first act: execution continues to a plain ASSIGNMENT to that same name,
    # and a variable-assignment error in a non-interactive shell is FATAL — bash
    # leaves the shell there and nothing downstream of the call ever runs.
    # Measured on three of the eight names. Inside `( … )` that fatality is
    # confined to the subshell and the caller comes back alive with 0.
    ( _organism_heartbeat_write "$@" ) || :
    return 0
}

_organism_heartbeat_write() {
    # NOT `${1:?...}`: in a non-interactive shell that construct EXITS the shell,
    # so a sourcing caller that mistyped the invocation was killed by its own
    # heartbeat writer — measured, bash returned 127 and zsh 1, and the line
    # after the call never ran. That directly contradicts this function's own
    # closing contract ("MUST never break the caller"), which is worth more than
    # the diagnostic.
    local _organism_hb_id="${1:-}"
    [ -n "$_organism_hb_id" ] || return 0
    # NOT `local status`: in zsh `status` is a READ-ONLY special parameter (an
    # alias for `?`), so that assignment aborted the function with `read-only
    # variable: status` and no sidecar was ever written — while the CLI-mode
    # guard on the last line goes out of its way to make `source` from zsh
    # work. The trap was latent, not live: all four sourcing call-sites in the
    # repo are `#!/bin/bash` and the one `#!/bin/zsh` wrapper uses the CLI form
    # below — but the Source pattern in the header above invited the next zsh
    # caller straight onto it. Pinned by test_gene_g2_heartbeat_fires.py.
    local _organism_hb_status="${2:-ok}"
    local _organism_hb_note="${3:-}"
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
    # measured: `LC_ALL=it_IT.UTF-8 bash -c 'v=éa; echo "${v//[a-zA-Z0-9_.]/}"'`
    # prints nothing, i.e. `é` passed the whitelist, while zsh rejected it. A
    # path-safety whitelist whose meaning depends on the caller's locale is not a
    # whitelist. Enumerating costs a long line and buys locale-independence.
    #
    # No temporary local here either — but dropping ONE name was not the cure it
    # looked like. `local X` aborts a bash caller that has `readonly X`, so
    # removing `_rest` only moved the collision: `id`, `hb_status`, `note` and
    # `ts` each still killed a caller that had reserved that word (measured, all
    # four: rc=1 "readonly variable", with the line after the call never reached).
    # One name is an instance; the rule is the class. EVERY local this function
    # declares is therefore prefixed `_organism_hb_`, and the corpus fails on any
    # future `local` that is not — so the next name added cannot reopen this.
    case "$_organism_hb_id" in
        [abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ]*) ;;
        *) return 0 ;;          # must start with an ASCII letter
    esac
    [ -z "${_organism_hb_id//[abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.]/}" ] \
        || return 0             # no character outside the allowed ASCII set
    [ "${#_organism_hb_id}" -le 81 ] || return 0
    case "$_organism_hb_id" in
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
    case "$_organism_hb_status" in
        [Oo][Kk]) _organism_hb_status="ok" ;;
        [Ee][Rr][Rr][Oo][Rr]) _organism_hb_status="error" ;;
        [Ww][Aa][Rr][Nn][Ii][Nn][Gg]) _organism_hb_status="warning" ;;
        [Ss][Tt][Aa][Rr][Tt][Ii][Nn][Gg]) _organism_hb_status="starting" ;;
        [Dd][Ee][Gg][Rr][Aa][Dd][Ee][Dd]) _organism_hb_status="degraded" ;;
        [Ss][Uu][Cc][Cc][Ee][Ss][Ss]) _organism_hb_status="success" ;;
        [Hh][Ee][Aa][Ll][Tt][Hh][Yy]) _organism_hb_status="healthy" ;;
        [Ww][Aa][Rr][Nn]) _organism_hb_status="warning" ;;
        [Ff][Aa][Ii][Ll] | [Ff][Aa][Ii][Ll][Ee][Dd] | [Ff][Aa][Ii][Ll][Uu][Rr][Ee] \
        | [Ff][Aa][Tt][Aa][Ll] | [Cc][Rr][Aa][Ss][Hh] | [Cc][Rr][Aa][Ss][Hh][Ee][Dd] \
        | [Dd][Ee][Aa][Dd] | [Tt][Ii][Mm][Ee][Oo][Uu][Tt] \
        | [Dd][Oo][Ww][Nn] | [Pp][Aa][Nn][Ii][Cc] | [Kk][Ii][Ll][Ll][Ee][Dd] \
        | [Aa][Bb][Oo][Rr][Tt][Ee][Dd] | [Ee][Xx][Cc][Ee][Pp][Tt][Ii][Oo][Nn] \
        | [Uu][Nn][Hh][Ee][Aa][Ll][Tt][Hh][Yy]) _organism_hb_status="error" ;;
        [Dd][Ii][Ss][Aa][Bb][Ll][Ee][Dd]) _organism_hb_status="ok" ;;  # deliberate, see above
        # The six on the two lines above joined the list late, and the gap they
        # filled was arbitrary rather than principled: `fail`/`fatal`/`crash`/
        # `dead`/`timeout` mapped to error while `down`, `panic`, `killed`,
        # `aborted`, `exception` and — worst — `unhealthy` fell to the `*)` arm
        # and published as a mere warning. `unhealthy` is the direct negation of
        # `healthy`, which this same list accepts verbatim: a caller writing the
        # negative form of an accepted word had its verdict softened. Unknown
        # words still land on `warning` deliberately (an unrecognised string is
        # not evidence of death), but an unambiguous failure word must not.
        *) _organism_hb_status="warning" ;;
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
    # (integer-readonly-special) and `path` (array-tied-special). That was the
    # original reason to rename those two — but the shell's special names and the
    # caller's readonly names are one hazard, not two: a name this library does
    # not own. The `_organism_hb_` prefix on ALL of them subsumes both.
    local _organism_hb_path="${_organism_hb_dir}/${_organism_hb_id}.json"
    local _organism_hb_tmp="${_organism_hb_path}.tmp.$$"
    # A bare `ts="$(date …)"` makes the ASSIGNMENT carry date's exit status, so
    # under a caller's `set -e` a failing date killed the caller — measured, rc=42
    # in both shells, with the line after the call never reached. That is not
    # hypothetical: `scripts/outbox-prune.sh` and `scripts/wr2-cron-wrapper.sh`
    # both run `set -euo pipefail` and call this function without `|| true`.
    #
    # If the clock is unavailable we write NOTHING and return. The previous
    # version substituted the EPOCH, reasoning that a timestamp we could not
    # obtain should read as stale — the direction that alarms. Measured against
    # the real readers, that was worse than the disease on two counts:
    #   - sentinel-aggregate.py computes `age = now - ts` and compares it to
    #     expected_hb * DEAD_MULTIPLIER, so an EPOCH ts is an age of ~56 years:
    #     a confident, actionable DEAD verdict on an organ that is running fine.
    #   - healer_receptor_registry.py branches on the sidecar's EXISTENCE first
    #     (`never_armed` when absent). Writing the fake timestamp overwrites the
    #     last genuine heartbeat AND takes the organ out of the honest bucket.
    # So the alarm named the wrong thing: the fault is the clock, and the receipt
    # accused the organ. Not writing keeps the last true beat, and a truly dead
    # organ still goes stale on its own — the alarm survives, the lie does not.
    # `|| printf ''` does NOT clear what the command already wrote: a `date`
    # that prints something and THEN fails leaves that something in the
    # substitution, and the old emptiness test passed it straight through —
    # measured, `date(){ printf BROKEN; return 42; }` published `"ts":"BROKEN"`
    # over the last good heartbeat. Emptiness was a proxy for "the clock
    # answered"; the answer itself is the entity. So the shape is checked.
    local _organism_hb_ts
    _organism_hb_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" || _organism_hb_ts=""
    case "$_organism_hb_ts" in
        [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z) ;;
        *)
            # Say it. The previous version returned 0 in silence, which left the
            # caller, launchd and the operator with an ordinary success and the
            # organ drifting stale for a fault that was never the organ's.
            printf 'organism_heartbeat: %s: clock unavailable (date gave %s) — no heartbeat written, previous one kept\n' \
                "$_organism_hb_id" "${_organism_hb_ts:-nothing}" >&2
            return 0
            ;;
    esac

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
    local _organism_hb_len="${#_organism_hb_note}"
    _organism_hb_note="$(printf '%sX' "$_organism_hb_note" | LC_ALL=C tr -c '\11\12\15\40-\176' ' ' 2>/dev/null)" \
        || _organism_hb_note="(note dropped: could not sanitise)X"
    # Strip the sentinel only after proving it is the one we appended, and the
    # proof is LENGTH, not the character. A bare `%X` assumed that a `tr` which
    # exits zero preserves every byte — so a `tr` that succeeded while losing the
    # last one made this line eat a trailing `X` the CALLER wrote, publishing `A`
    # for a note of `AX`, silently. Testing `*X)` alone does not catch that: for
    # `AX` the sentinel makes `AXX`, dropping one byte leaves `AX`, which still
    # ends in `X` and is indistinguishable from a clean run.
    #
    # `tr -c <set> ' '` with a single replacement char SUBSTITUTES, never deletes
    # (no `-s`), so its output is byte-for-byte as long as its input. The input
    # was the note plus one sentinel, hence `out >= in + 1` always — and the
    # comparison is one-sided on purpose: under a UTF-8 locale a multibyte input
    # character counts as ONE in `${#...}` while `tr` turns each of its bytes into
    # a space, so a legitimate run can only ever come out LONGER. Shorter is not
    # ambiguous; it means bytes went missing.
    # TWO proofs, because each alone has a blind spot the other covers:
    #   - length: a `tr` that DROPS bytes leaves the output shorter than
    #     input+1. Catches `AX` -> `AXX` -> `AX`, which still ends in `X` and so
    #     looks clean to a suffix test.
    #   - identity: a `tr` that CORRUPTS the last byte at equal length leaves
    #     something else there. Catches `AB` -> `ABX` -> `ABY` under a
    #     `s/X$/Y/` sanitiser, which passes the length test and would publish
    #     the corrupted sentinel verbatim.
    # Both were demonstrated on this code, one round apart.
    case "$_organism_hb_note" in
        *X) ;;
        *) _organism_hb_note="(note dropped: could not sanitise)X" ;;
    esac
    if [ "${#_organism_hb_note}" -lt "$((_organism_hb_len + 1))" ]; then
        _organism_hb_note="(note dropped: could not sanitise)"
    else
        _organism_hb_note="${_organism_hb_note%X}"
    fi

    # 2. TRUNCATE the sanitised-but-unescaped note. Escaping FIRST cut escape
    #    sequences in half: 499 'a' followed by a quote escaped to 501 chars, the
    #    500-char cut landed between the backslash and its quote, and the trailing
    #    backslash then escaped the JSON's own closing quote — the whole sidecar
    #    became unparseable, so the reader saw NOTHING rather than a long note.
    #    Measured before the fix (json.loads raised on exactly that input).
    #    Escaping after the cut can exceed 500 bytes; bounding the INFORMATION is
    #    the point, and a note that survives is worth more than a round number.
    _organism_hb_note="${_organism_hb_note:0:500}"

    # 3. Escape JSON-unsafe chars in note: backslash, quote, newline, tab, CR.
    # Backslash MUST stay first — it is the escape character for the rest.
    _organism_hb_note="${_organism_hb_note//\\/\\\\}"
    _organism_hb_note="${_organism_hb_note//\"/\\\"}"
    _organism_hb_note="${_organism_hb_note//$'\n'/\\n}"
    _organism_hb_note="${_organism_hb_note//$'\r'/\\r}"
    _organism_hb_note="${_organism_hb_note//$'\t'/\\t}"

    {
        printf '{"ts":"%s","status":"%s","note":"%s"}\n' "$_organism_hb_ts" "$_organism_hb_status" "$_organism_hb_note"
    } > "$_organism_hb_tmp" 2>/dev/null && mv "$_organism_hb_tmp" "$_organism_hb_path" 2>/dev/null || :
    # `|| :` is load-bearing, not decoration: `set -e` does not spare the LAST
    # command of an `&&` list, so a failed `mv` (full disk, a directory in the
    # way, a racing sweeper) killed the caller one line before `return 0`.
    rm -f "$_organism_hb_tmp" 2>/dev/null || :   # never leave a `.tmp.<pid>` behind

    return 0  # heartbeat MUST never break the caller
}

# CLI mode if invoked directly.
if [[ "${BASH_SOURCE[0]:-$0}" == "$0" && "${ZSH_EVAL_CONTEXT:-toplevel}" != *file* ]]; then
    set -o pipefail   # ours to set only when we ARE the script, never the caller's
    organism_heartbeat "$@"
fi
