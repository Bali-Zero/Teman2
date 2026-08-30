#!/bin/sh
# seat_state.sh — sourced, not executed (a direct-run debug entrypoint lives
# at the bottom of this file, but the normal path is `. seat_state.sh`).
#
# The seat-state ledger: "is this Claude OAuth seat (or non-Anthropic seat)
# LIVE, EXHAUSTED, or UNKNOWN right now, and why". Consumed by
# infra/launchagents/wrappers/claude-cascade.sh as a pre-dispatch check so a
# known-exhausted seat is skipped WITHOUT spending a live probe on it — see
# `docs/plans/2026-08-29-beyond-sota-craft-wave/L09-multi-agent-orchestration-fleet-routing.md`
# PR-1.
#
# CREDENTIAL SAFETY (load-bearing, not decorative): this library NEVER reads,
# prints, or logs a credential value — only seat identifiers (account emails,
# arsenal seat names), states (LIVE/EXHAUSTED/UNKNOWN) and reasons (percentages,
# statuses, staleness ages). Nothing here ever touches an OAuth token, an API
# key, or the contents of any Keychain entry. If you are tempted to add a
# field to make debugging easier, ask first whether that field could ever
# hold a secret — the two report files this reads are usage TELEMETRY, not
# credential stores, and it must stay that way on the reading side too.
#
# POSIX-sh in the function bodies on purpose: this file is sourced by BOTH a
# bash test harness (scripts/tests/test_seat_state.sh) and a zsh production
# wrapper (claude-cascade.sh, `#!/bin/zsh`). No `[[ ]]`, no arrays, no
# `${var,,}`, no `local -a` — `[ ]`, `case`, and plain `local` only (bash and
# zsh both support plain `local`, even though it is not itself POSIX).
#
# --- Data sources (env-overridable, read-only) -----------------------------
#
#   SEAT_STATE_REPORT          default $HOME/.claude/seat-quota.json
#     {"generated_at_epoch": <epoch>, "seats": [{"account": "...",
#      "session_pct": <num|null>, "weekly_pct": <num|null>, ...}]}
#
#   SEAT_STATE_ARSENAL_REPORT  default $HOME/.organism/arsenal/last.json
#     {"ts": "<ISO-8601>", "seats": [{"seat": "...", "status": "LIVE"
#      | "QUOTA_DEAD" | ..., ...}]}
#
# Staleness note, measured live on this fleet 2026-08-30: the quota report on
# disk right now is 5 days old against a default 6h cutoff — the stale path
# below is the NORMAL path on a real machine, not a corner case to special-case
# away. Never soften the cutoff to make today's report look fresh.
#
# --- Tunables ----------------------------------------------------------
#
#   SEAT_STATE_MAX_AGE_S       default 21600 (6h) — report staleness cutoff.
#   SEAT_STATE_EXHAUSTED_PCT   default 100 — quota %% at/above which a seat
#                               counts as exhausted.
#   SEAT_STATE_PROBE_CMD       default empty — if set, run once (never twice,
#                               never recursively) to refresh the reports when
#                               the first read comes back UNKNOWN.

# --- Python bridge -----------------------------------------------------
#
# JSON parsing is not hand-rolled in shell. One `python3 -c` invocation, fed
# a source string built once at source-time (below), takes (kind, path,
# seat-key, max-age-s, exhausted-pct) and prints exactly one line:
#   STATE<TAB>REASON<TAB>TERMINAL
# TERMINAL=1 means "this report answered for this seat, stop here" (row
# found, whatever its verdict); TERMINAL=0 means "this report could not
# answer (missing/unparseable/stale/seat-absent), try the next source".
# Every exit path is an explicit emit() — a catch-all at the bottom turns any
# unexpected exception into UNKNOWN/internal-error rather than a traceback
# that might echo file contents onto stderr.
_SEAT_STATE_PY="$(cat <<'SEAT_STATE_PY'
import json, sys, datetime

# Clock skew between two fleet machines is normal and small; a report dated
# meaningfully in the future is not. 300s absorbs ordinary NTP drift without
# absorbing a broken writer.
#
# EDITING NOTE, measured not theorised: this heredoc body is nested inside a
# command substitution, so bash SCANS it even though it is quote-delimited.
# A comment here containing a dollar-paren sequence, a backtick, or an
# unbalanced quote makes bash reject the WHOLE FILE with
# 'unexpected EOF while looking for matching quote' - and the reported line
# number is the end of the file, nowhere near the offending comment. Keep
# prose in here free of shell metacharacters.
_FUTURE_TOLERANCE_S = 300

def _reject_const(_name):
    raise ValueError("non-strict JSON constant")


def _clean(v):
    # Report values are unvalidated input. They must never carry a tab or a
    # newline into the field-separated line this bridge prints, and must never
    # be unbounded. Cosmetic today, but it is untrusted content reaching output.
    t = str(v).replace("\t", " ").replace("\r", " ").replace("\n", " ")
    return t[:80]


def emit(state, reason, terminal):
    print(state + "\t" + reason + "\t" + ("1" if terminal else "0"))
    raise SystemExit(0)

def main():
    kind, path, seat_key, max_age_raw, exhausted_pct_raw = sys.argv[1:6]
    try:
        max_age_s = float(max_age_raw)
        exhausted_pct = float(exhausted_pct_raw)
    except ValueError:
        emit("UNKNOWN", "bad-config", False)

    try:
        with open(path, "r") as fh:
            # Reject the non-strict JSON constants Python accepts by default.
            # Measured: a report carrying weekly_pct as Infinity produced
            # EXHAUSTED and SKIPPED the seat - a strictly-invalid report forcing
            # the one decision that costs a live seat. Unparseable must be UNKNOWN.
            data = json.load(fh, parse_constant=_reject_const)
    except FileNotFoundError:
        emit("UNKNOWN", "missing-report", False)
    except (OSError, ValueError):
        emit("UNKNOWN", "unparseable-report", False)

    if not isinstance(data, dict):
        emit("UNKNOWN", "unparseable-report", False)

    if kind == "quota":
        try:
            ts_epoch = float(data.get("generated_at_epoch"))
        except (TypeError, ValueError):
            emit("UNKNOWN", "unparseable-timestamp", False)
    else:
        ts_raw = data.get("ts")
        if not isinstance(ts_raw, str) or not ts_raw:
            emit("UNKNOWN", "unparseable-timestamp", False)
        try:
            _dt = datetime.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            emit("UNKNOWN", "unparseable-timestamp", False)
        # A timestamp with NO timezone is refused, never guessed. Python reads
        # a naive datetime in LOCAL time, so a writer emitting naive UTC is read
        # here shifted by the reading machine local offset. Measured on Mini
        # (UTC+8): a naive-UTC arsenal report written THAT SECOND reported
        # stale age=28800s, exactly the offset. West of UTC the same bug runs
        # the other way and yields a negative age, i.e. fresh forever. We cannot
        # know which zone the writer meant, so we decline rather than invent one.
        if _dt.tzinfo is None or _dt.tzinfo.utcoffset(_dt) is None:
            emit("UNKNOWN", "timestamp-without-timezone", False)
        ts_epoch = _dt.timestamp()

    age = datetime.datetime.now(datetime.timezone.utc).timestamp() - ts_epoch
    # A report dated in the FUTURE is not fresh, it is untrustworthy. Only the
    # `age > max_age_s` side was checked before, so a negative age (clock skew,
    # a writer bug, a hand-edited fixture) sailed through as fresh FOREVER.
    # Measured: a report dated 11.5 days ahead carrying weekly_pct=100 made the
    # library report EXHAUSTED and SKIP a seat that may have been perfectly
    # live. That is the dangerous polarity - a wrong SKIP, not a wrong dispatch.
    if age < -_FUTURE_TOLERANCE_S:
        emit("UNKNOWN", "timestamp-in-future by=" + str(int(-age)) + "s", False)
    if age > max_age_s:
        emit("UNKNOWN", "stale age=" + str(int(age)) + "s", False)

    seats = data.get("seats")
    if not isinstance(seats, list):
        emit("UNKNOWN", "malformed-seats", False)

    key_field = "account" if kind == "quota" else "seat"
    row = None
    for s in seats:
        if isinstance(s, dict) and s.get(key_field) == seat_key:
            row = s
            break
    if row is None:
        emit("UNKNOWN", "seat-absent", False)

    if kind == "quota":
        weekly = row.get("weekly_pct")
        session = row.get("session_pct")
        weekly_num = isinstance(weekly, (int, float)) and not isinstance(weekly, bool)
        session_num = isinstance(session, (int, float)) and not isinstance(session, bool)
        if not weekly_num and not session_num:
            emit("UNKNOWN", "no-usage-figures", True)
        if weekly_num and weekly >= exhausted_pct:
            emit("EXHAUSTED", "weekly_pct=" + _clean(weekly), True)
        if session_num and session >= exhausted_pct:
            emit("EXHAUSTED", "session_pct=" + _clean(session), True)
        emit("LIVE", "weekly_pct=" + _clean(weekly) + " session_pct=" + _clean(session), True)
    else:
        status = row.get("status")
        if status == "QUOTA_DEAD":
            emit("EXHAUSTED", "status=QUOTA_DEAD", True)
        if status == "LIVE":
            emit("LIVE", "status=LIVE", True)
        emit("UNKNOWN", "status=" + _clean(status), True)

try:
    main()
except SystemExit:
    raise
except Exception:
    emit("UNKNOWN", "internal-error", False)
SEAT_STATE_PY
)"

_seat_state_probe() {
    # args: kind path seat_key max_age_s exhausted_pct
    python3 -c "$_SEAT_STATE_PY" "$1" "$2" "$3" "$4" "$5"
}

# _seat_state_resolve <seat-key>
# Sets SEAT_STATE_STATE / SEAT_STATE_REASON. Resolution order: quota report
# row first (terminal on row-found, whatever the verdict), else arsenal
# report row, else UNKNOWN naming both sub-reasons.
_seat_state_resolve() {
    local seat_key="$1"
    local tab out q_state q_reason q_terminal a_state a_reason a_terminal
    local quota_path arsenal_path max_age exhausted_pct

    if ! command -v python3 >/dev/null 2>&1; then
        SEAT_STATE_STATE="UNKNOWN"
        SEAT_STATE_REASON="no-python3"
        return
    fi

    quota_path="${SEAT_STATE_REPORT:-$HOME/.claude/seat-quota.json}"
    arsenal_path="${SEAT_STATE_ARSENAL_REPORT:-$HOME/.organism/arsenal/last.json}"
    max_age="${SEAT_STATE_MAX_AGE_S:-21600}"
    exhausted_pct="${SEAT_STATE_EXHAUSTED_PCT:-100}"
    tab="$(printf '\t')"

    out="$(_seat_state_probe quota "$quota_path" "$seat_key" "$max_age" "$exhausted_pct")"
    q_state="${out%%"$tab"*}"; out="${out#*"$tab"}"
    q_reason="${out%%"$tab"*}"; q_terminal="${out##*"$tab"}"
    if [ "$q_terminal" = "1" ]; then
        SEAT_STATE_STATE="$q_state"
        SEAT_STATE_REASON="$q_reason"
        return
    fi

    out="$(_seat_state_probe arsenal "$arsenal_path" "$seat_key" "$max_age" "$exhausted_pct")"
    a_state="${out%%"$tab"*}"; out="${out#*"$tab"}"
    a_reason="${out%%"$tab"*}"; a_terminal="${out##*"$tab"}"
    if [ "$a_terminal" = "1" ]; then
        SEAT_STATE_STATE="$a_state"
        SEAT_STATE_REASON="$a_reason"
        return
    fi

    SEAT_STATE_STATE="UNKNOWN"
    SEAT_STATE_REASON="quota=$q_reason; arsenal=$a_reason"
}

# seat_state_lookup <seat-key>
# Prints "STATE<TAB>reason" to stdout. Returns 0=LIVE, 1=EXHAUSTED, 2=UNKNOWN.
# UNKNOWN gets exactly one fresh probe (SEAT_STATE_PROBE_CMD) before being
# accepted as final — gated by the SEAT_STATE_PROBED env sentinel so the
# probe can never fire twice or recurse, across this call OR any later call
# in the same process (a probe typically refreshes the whole report, so one
# attempt per process is the right budget, not one per seat checked).
seat_state_lookup() {
    local seat_key="$1"

    _seat_state_resolve "$seat_key"

    if [ "$SEAT_STATE_STATE" = "UNKNOWN" ] && [ -n "${SEAT_STATE_PROBE_CMD:-}" ] \
        && [ "${SEAT_STATE_PROBED:-0}" != "1" ]; then
        # Deliberately NOT exported. The guarantee is one probe per PROCESS;
        # exporting made it one probe per process TREE, so every child the
        # cascade spawns inherited the already-probed flag and could never
        # refresh. A plain shell variable gives the stated guarantee already.
        SEAT_STATE_PROBED=1
        sh -c "$SEAT_STATE_PROBE_CMD" >/dev/null 2>&1
        _seat_state_resolve "$seat_key"
        if [ "$SEAT_STATE_STATE" = "UNKNOWN" ]; then
            SEAT_STATE_REASON="after-probe: $SEAT_STATE_REASON"
        fi
    fi

    printf '%s\t%s\n' "$SEAT_STATE_STATE" "$SEAT_STATE_REASON"

    case "$SEAT_STATE_STATE" in
        LIVE) return 0 ;;
        EXHAUSTED) return 1 ;;
        *) return 2 ;;
    esac
}

# seat_is_live <seat-key> — return 0 iff LIVE, else non-zero. No stdout.
seat_is_live() {
    seat_state_lookup "$1" >/dev/null
}

# seat_is_exhausted <seat-key> — return 0 iff EXHAUSTED, else non-zero. No stdout.
seat_is_exhausted() {
    local rc=0
    seat_state_lookup "$1" >/dev/null || rc=$?
    [ "$rc" -eq 1 ]
}

# seat_state_precheck_skip <cascade-label>
# The ONLY function the cascade calls. Returns 0 ("skip this seat") ONLY when
# the label resolves to a slot with a known account AND that account is
# EXHAUSTED. Everything else — unparseable label, unmapped slot, LIVE,
# UNKNOWN — returns 1 ("do not skip").
#
# Why there is no built-in slot->account table: ~/.claude/seat-quota.json is
# keyed by account e-mail and ~/.organism/arsenal/last.json carries a single
# "claude" row for the whole family — no machine-readable slot->account key
# exists anywhere on this fleet. CLAUDE.md states the slot<->account map is
# DOCUMENTAL, per-machine divergent, and NOT derivable from a token.
# Hardcoding it here would bake in a claim this library cannot verify. The
# map is therefore caller-supplied via CLAUDE_SEAT_ACCOUNT_<N> env vars, and
# the feature arms itself the moment those are declared.
#
# UNKNOWN must never cause a skip: skipping a seat we cannot identify would
# disarm the cascade, which is strictly worse than the status quo (a live
# probe that may fail anyway). The safe polarity is fail-open on the skip
# decision, never fail-closed.
seat_state_precheck_skip() {
    local label="$1"
    local rest slot account

    case "$label" in
        claude-token-[0-9]*)
            rest="${label#claude-token-}"
            slot="${rest%%-*}"
            ;;
        *)
            return 1
            ;;
    esac

    case "$slot" in
        ''|*[!0-9]*) return 1 ;;
    esac

    eval "account=\${CLAUDE_SEAT_ACCOUNT_${slot}:-}"
    [ -z "$account" ] && return 1

    seat_is_exhausted "$account"
}

# --- Direct-execution entrypoint (debug only) -------------------------
# A normal `. seat_state.sh` never reaches the block below. Best-effort
# detection only — see comments inline; guessing wrong here never causes an
# accidental `exit` of whoever sourced this file, only a CLI entrypoint that
# fails to fire under a shell we cannot introspect (plain POSIX sh/dash).
_seat_state_running_directly() {
    if [ -n "${BASH_SOURCE:-}" ]; then
        # bash: BASH_SOURCE[0] is always this file; $0 is the top-level
        # script/shell, differing from it unless this file was run directly.
        [ "$BASH_SOURCE" = "$0" ] && return 0 || return 1
    fi
    if [ -n "${ZSH_EVAL_CONTEXT:-}" ]; then
        # zsh: the context stack carries a "file" component when sourced via
        # `.`/`source` — but NOT necessarily as the last one: calling this
        # function from inside another function appends ":shfunc" AFTER it
        # (measured live: "cmdarg:file" -> "cmdarg:file:shfunc" the instant
        # you are one function deep). A suffix-only `*:file)` match misses
        # that and would `exit` the caller's shell mid-source. Wrap with
        # colons and match "file" as ANY component instead.
        case ":$ZSH_EVAL_CONTEXT:" in
            *:file:*) return 1 ;;
            *) return 0 ;;
        esac
    fi
    return 1
}

if _seat_state_running_directly; then
    seat_state_lookup "${1:-}"
    exit $?
fi
