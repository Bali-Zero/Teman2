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
    # PROVE THE BINDINGS TOOK — round 7, and the defect it closes is the one the
    # prefix convention above was believed to have solved.
    #
    # In bash, `local X` on a name the CALLER declared `readonly` prints an
    # error, returns non-zero, and leaves the CALLER'S value visible under that
    # name. The `( … ) || :` wrapper keeps the caller alive — that is its whole
    # job — so execution simply carries on with someone else's data. Measured:
    # `readonly _organism_hb_id=x` before a call for `probe.real` published
    # `x.json`. That is a heartbeat under the WRONG ORGAN'S NAME — organ `x`
    # reported alive on the strength of organ `probe.real` having run, which is
    # precisely the fabricated liveness the rest of this file exists to prevent,
    # and the same shadow on `_organism_hb_status` would publish `ok` for a
    # caller reporting `error`. zsh binds correctly here (measured, both), so in
    # practice this fires only on bash.
    #
    # The `_organism_hb_` prefix makes the collision unlikely. Unlikely is not a
    # verdict: the earlier corpus asserted only that the caller SURVIVED such a
    # call and deliberately discarded the sidecar, so the misdirection had a
    # test walking straight past it. Silence is the right answer here — the
    # writer cannot know which value was meant.
    if [ "$_organism_hb_id" != "${1:-}" ] ||
        [ "$_organism_hb_status" != "${2:-ok}" ] ||
        [ "$_organism_hb_note" != "${3:-}" ] ||
        [ "$_organism_hb_dir" != "${ORGANISM_LAST_SEEN_DIR:-${HOME}/.organism/last_seen}" ]; then
        printf 'organism_heartbeat: a caller-readonly name shadowed this writer%s\n' \
            "'s own variables — nothing written" >&2
        return 0
    fi

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
    # `disabled` IS PASSED THROUGH — corrected 2026-07-29, adversarial round 6.
    #
    # This arm used to rewrite it to "ok", justified by a comment claiming
    # "disabled is not in the reader's vocabulary, so passing it through makes
    # the organ read DEAD and the healer would resurrect what an operator
    # intentionally stopped". I wrote that claim on 2026-07-29 WITHOUT READING
    # EITHER READER. Measured:
    #
    #   healer_receptor_registry.py: EXEMPT_STATUSES = {"disabled"} — since
    #     2026-07-06 (#2027), three weeks before the comment asserting it did
    #     not exist. The reader had already learned the word.
    #   sentinel-aggregate.py: `disabled` is a status it already renders, and
    #     _ESCALATE_STATUSES is ("dead", "starved") — so it does not page.
    #
    # The old mapping's cost was a #2-family lie: an organ an operator had
    # deliberately stopped was indistinguishable from a healthy one, on every
    # surface, forever. The sentinel's CLASSIFIER needed one arm to complete the
    # cure (a status it did not recognise fell to `else: dead`) — landed in the
    # same commit, because a writer emitting a word no reader classifies is how
    # this file got the false green in the first place.
    #
    # `running` maps to `ok` for the mirror reason: the healer counts `running`
    # among HEALTHY_STATUSES while the sentinel does not, so passing it through
    # would have one reader call the organ healthy and the other call it DEAD.
    # `ok` is the only spelling both agree on, and it is not a lie — an organ
    # reporting `running` is running.
    #
    # THE RULE THIS LEAVES: never map a status by what a reader is imagined to
    # know. Read the reader in the same turn. Both vocabularies are pinned by
    # test_the_writers_vocabulary_matches_its_readers, which imports them.
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
    # Separators are not part of the word. Round 7: the list matched `timeout`
    # but not `timed_out`, which is a failure conclusion this repository already
    # writes (`scripts/ci/queue_rearm_classify.sh`), so the same verdict softened
    # to `warning` purely on how the caller spelled it. Case was already handled;
    # SHAPE was not, and it is the same axis. Whole-string `case` patterns, so
    # stripping `_` and `-` can only ever make a word match one of the listed
    # ones — never widen a pattern to catch something else. Done before the
    # match, in place, because every arm below assigns a canonical value anyway.
    _organism_hb_status="${_organism_hb_status//_/}"
    _organism_hb_status="${_organism_hb_status//-/}"
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
        | [Tt][Ii][Mm][Ee][Dd][Oo][Uu][Tt] \
        | [Dd][Oo][Ww][Nn] | [Pp][Aa][Nn][Ii][Cc] | [Kk][Ii][Ll][Ll][Ee][Dd] \
        | [Aa][Bb][Oo][Rr][Tt][Ee][Dd] | [Ee][Xx][Cc][Ee][Pp][Tt][Ii][Oo][Nn] \
        | [Uu][Nn][Hh][Ee][Aa][Ll][Tt][Hh][Yy]) _organism_hb_status="error" ;;
        [Dd][Ii][Ss][Aa][Bb][Ll][Ee][Dd]) _organism_hb_status="disabled" ;;
        [Rr][Uu][Nn][Nn][Ii][Nn][Gg]) _organism_hb_status="ok" ;;
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
    # The SAME binding proof as the one on the argument locals above, because
    # the earlier one could not reach here — and that gap was not theoretical,
    # it was measured in this repository's own working tree. This corpus
    # parametrises `readonly` over every name the function declares, including
    # these two; with `_organism_hb_path` shadowed the write went to a
    # CALLER-CHOSEN relative path, so `pytest` had been quietly depositing a
    # `caller-sentinel/` directory of orphaned `.tmp.<pid>` files into the
    # checkout for weeks. Nobody noticed, because the test asserts only that the
    # caller SURVIVED. Two consequences, and the second is the serious one: the
    # real organ's sidecar is never written, so a live organ ages into `dead`.
    #
    # Refusing to write is the only honest answer — the writer cannot know which
    # value was meant, and guessing is what publishes fiction.
    if [ "$_organism_hb_path" != "${_organism_hb_dir}/${_organism_hb_id}.json" ] ||
        [ "$_organism_hb_tmp" != "${_organism_hb_path}.tmp.$$" ]; then
        printf 'organism_heartbeat: %s: a caller-readonly name shadowed the sidecar path — nothing written\n' \
            "$_organism_hb_id" >&2
        return 0
    fi
    # A DIRECTORY where the sidecar belongs makes `mv` a SUCCESS with the wrong
    # meaning: it moves the file INSIDE and exits 0, so the cleanup below finds
    # nothing at the old name, every reader still sees no sidecar, and the organ
    # ages into dead on a write that reported success. Observed for real — the
    # `caller-sentinel/` residue above is exactly this, a directory left by one
    # parametrisation swallowing the tmp file of the next.
    if [ -d "$_organism_hb_path" ]; then
        printf 'organism_heartbeat: %s: %s is a directory, not a sidecar — nothing written\n' \
            "$_organism_hb_id" "$_organism_hb_path" >&2
        return 0
    fi
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
    #
    # THE SHAPE IS NOT THE VALIDITY — round 6. The pattern below used to check
    # only that the digits were digits, so `9999-99-99T99:99:99Z` passed. Both
    # readers then fail to parse it: `sentinel-aggregate` scores the organ
    # `unknown`, `healer_receptor_registry` skips it and it ages into dead. That
    # is a DEAD fabricated on a healthy organ — the same lie as the corrupt `ts`
    # this check was added to stop, wearing a well-formed mask. The field ranges
    # are therefore checked too, still with bracket patterns and still without a
    # single external command (round 3: the verdict path must contain nothing
    # that can fail).
    # The verdict goes in a SEPARATE flag rather than blanking `ts` in place: the
    # diagnostic below prints what `date` actually said, and a validator that
    # erases its own evidence leaves the operator with "clock unavailable
    # (date gave nothing)" for a clock that answered something very specific.
    # ROUND 7 tightened three residual holes, and the rule that closed them is
    # the only one that ever mattered here: THE WRITER MAY NOT EMIT WHAT ITS
    # READERS CANNOT READ. Both readers parse with `datetime.fromisoformat`
    # (`healer_receptor_registry`, `sentinel-aggregate`), so anything it rejects
    # is a heartbeat that reads as malformed and lands the organ in `dead` —
    # the fabricated death this whole check exists to prevent. Round 6 checked
    # each field's range in isolation, which still let through a date no
    # calendar has.
    local _organism_hb_tsok=no
    case "$_organism_hb_ts" in
        # Year floor 1000, not 0000: `fromisoformat` accepts year 1 but a
        # four-digit-with-leading-zero year is a broken clock, never a real one,
        # and the floor also keeps the leap arithmetic below out of shell octal.
        [1-9][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9]Z)
            _organism_hb_tsok=yes
            case "${_organism_hb_ts#????-}" in
                0[1-9]-* | 1[0-2]-*) ;;
                *) _organism_hb_tsok=no ;;
            esac
            case "${_organism_hb_ts#????-??-}" in
                0[1-9]T* | [12][0-9]T* | 3[01]T*) ;;
                *) _organism_hb_tsok=no ;;
            esac
            case "${_organism_hb_ts#????-??-??T}" in
                [01][0-9]:* | 2[0-3]:*) ;;
                *) _organism_hb_tsok=no ;;
            esac
            # Seconds no longer allow 60. Round 6 allowed it reasoning that a
            # leap second is a valid UTC timestamp — true, and irrelevant:
            # `fromisoformat` refuses `:60`, so publishing one hands both
            # readers an unparseable heartbeat. A leap second is refused (and
            # said out loud below) rather than written unreadable.
            case "${_organism_hb_ts#????-??-??T??:??:}" in
                [0-5][0-9]Z) ;;
                *) _organism_hb_tsok=no ;;
            esac
            # The day-of-month range is not the day-of-month VALIDITY: 31 is in
            # range for every month, so `2026-02-31` and `2025-02-29` passed
            # field-by-field while no calendar contains them. Checked against
            # the month, with the leap rule spelled out — `[ ]` and `$(( ))` are
            # builtins in both shells, so the verdict path still contains
            # nothing that can fail (round 3's constraint).
            local _organism_hb_yy _organism_hb_md
            _organism_hb_yy="${_organism_hb_ts%%-*}"
            _organism_hb_md="${_organism_hb_ts%T*}"
            _organism_hb_md="${_organism_hb_md#*-}"
            case "$_organism_hb_md" in
                02-3[01] | 0[469]-31 | 11-31) _organism_hb_tsok=no ;;
                02-29)
                    if [ "$((_organism_hb_yy % 4))" -ne 0 ] ||
                        { [ "$((_organism_hb_yy % 100))" -eq 0 ] &&
                            [ "$((_organism_hb_yy % 400))" -ne 0 ]; }; then
                        _organism_hb_tsok=no
                    fi
                    ;;
            esac
            ;;
    esac
    case "$_organism_hb_tsok" in
        yes) ;;
        *)
            # Say it. The previous version returned 0 in silence, which left the
            # caller, launchd and the operator with an ordinary success and the
            # organ drifting stale for a fault that was never the organ's.
            printf 'organism_heartbeat: %s: clock unusable (date gave %s) — no heartbeat written, previous one kept\n' \
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
    #
    # DECLARED LIMIT (round 7, and deliberately not "fixed"). Neither proof sees
    # INTERIOR corruption: a caller-defined `tr` that SUBSTITUTES rather than
    # drops — `tr(){ sed 's/A/Z/'; }` — turns `ABX` into `ZBX`, which has the
    # right length and the right last byte, and `ZB` is published. That is the
    # note's declared contract, not a hole to plug: the note is best-effort by
    # design (the two paragraphs above say so, and it is why `tr` lives here and
    # not in the status path), while a caller who can shadow `tr` can equally
    # shadow `date`, `mkdir` and `mv`. The obvious guard — a `case` allow-listing
    # the byte range — would decide with a bracket RANGE whose membership is the
    # caller's collation, i.e. the exact class of defect (#3) this library keeps
    # re-learning, traded for a field the readers never act on. Refused, written
    # down, and ledgered instead.
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
