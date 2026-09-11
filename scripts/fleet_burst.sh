#!/usr/bin/env bash
# fleet_burst.sh dispatches independently configured, headless Claude lanes.
#
# Refusal policy: if fewer verified-LIVE seats exist than requested lanes, refuse
# the whole burst rather than silently turning parallel work into a serial queue.
# The default concurrency ceiling is 3; a precaution, not a proven fix — W96's ENXIO occurred with 94% of ptys free and the cause is undetermined.
#
# Dry-run format is stable TSV: a PLAN row is followed by zero or more LANE
# rows.  LANE fields include lane, seat, config_dir, and output so callers can
# verify the isolation and one-seat-per-lane invariant without parsing prose.
#
# This dispatcher handles seat identifiers only.  It deliberately never reads,
# logs, prints, or interpolates credential values or Keychain content.

set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: fleet_burst.sh --lanes N --seat SEAT [--seat SEAT ...] [options]

Options:
  --seats A,B,C             Comma-separated alternative to repeated --seat.
  --model MODEL             Claude model (default: claude-sonnet-5).
  --max-concurrency N       Simultaneous Claude processes (default: 3).
  --run-dir DIR             Parent directory for sterile lane state/output.
  --prompt TEXT             Prompt supplied to every dispatched lane.
  --dry-run                 Print the TSV plan; do not create or spawn anything.
  --help                    Show this message.

FLEET_BURST_SEAT_STATE_LIB may override the sourced seat-state library.  It is
intended for hermetic tests; a missing library is always a hard failure.
USAGE
}

die() {
    printf 'fleet_burst: %s\n' "$*" >&2
    exit 1
}

is_positive_integer() {
    [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

# Every value that reaches a TSV row goes through here, and there is exactly one
# of these on purpose.
#
# The plan rows are tab-separated because a test has to be able to read them
# field by field. That makes a tab, newline or carriage return inside ANY
# interpolated value a parsing break, not a cosmetic issue: measured this turn,
# `--run-dir $'/tmp/x\ty'` makes the reader parse config_dir as "/tmp/x" -- the
# value is silently TRUNCATED and the plan reads as if it said something else.
#
# An earlier form of this script validated only the seat identifier, for exactly
# this reason, and then interpolated `model` and `run_dir` into the same rows
# unchecked -- the guard's own reasoning applied to one of its three call sites.
# Blind cross-family refutation (Kimi K3) caught it. Keep this shared: adding a
# fourth TSV-bound value and forgetting to validate it is the same defect again.
reject_control_chars() {
    local label="$1"
    local value="$2"
    [[ "$value" != *$'\t'* && "$value" != *$'\n'* && "$value" != *$'\r'* ]] \
        || die "${label} contains a tab, newline or carriage return, which would corrupt the plan rows"
}

wait_for_pid() {
    local pid="$1"

    # A failed lane must not prevent reaping the remaining children.
    if ! wait "$pid"; then
        return 1
    fi
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
seat_state_lib="${FLEET_BURST_SEAT_STATE_LIB:-${script_dir}/lib/seat_state.sh}"
lanes=""
model="claude-sonnet-5"
max_concurrency="3"
run_dir=""
prompt=""
dry_run=0
declare -a candidate_seats=()

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --lanes)
            [[ "$#" -ge 2 ]] || die "--lanes requires a value"
            lanes="$2"
            shift 2
            ;;
        --seat)
            [[ "$#" -ge 2 ]] || die "--seat requires a seat identifier"
            candidate_seats+=("$2")
            shift 2
            ;;
        --seats)
            [[ "$#" -ge 2 ]] || die "--seats requires a comma-separated list"
            IFS=',' read -r -a supplied_seats <<< "$2"
            candidate_seats+=("${supplied_seats[@]}")
            shift 2
            ;;
        --model)
            [[ "$#" -ge 2 ]] || die "--model requires a value"
            model="$2"
            shift 2
            ;;
        --max-concurrency)
            [[ "$#" -ge 2 ]] || die "--max-concurrency requires a value"
            max_concurrency="$2"
            shift 2
            ;;
        --run-dir)
            [[ "$#" -ge 2 ]] || die "--run-dir requires a path"
            run_dir="$2"
            shift 2
            ;;
        --prompt)
            [[ "$#" -ge 2 ]] || die "--prompt requires text"
            prompt="$2"
            shift 2
            ;;
        --dry-run)
            dry_run=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

is_positive_integer "$lanes" || die "--lanes must be a positive integer"
is_positive_integer "$max_concurrency" || die "--max-concurrency must be a positive integer"
[[ "${#candidate_seats[@]}" -gt 0 ]] || die "at least one --seat or --seats entry is required"

# Fable routing is a governance boundary, not a model availability check.
case "$model" in
    *[Ff][Aa][Bb][Ll][Ee]*)
        die "Fable is manual-only (CLAUDE.md section 5, RULED 2026-08-20); fleet_burst cannot auto-route to fable"
        ;;
esac

[[ -r "$seat_state_lib" ]] || die "seat state library is missing or unreadable: $seat_state_lib"
# shellcheck source=/dev/null
source "$seat_state_lib"
declare -F seat_state_lookup >/dev/null || die "seat state library does not provide seat_state_lookup"

# A caller-supplied --run-dir is the caller's business. The DEFAULT is ours, and
# it must not be guessable: `${TMPDIR:-/tmp}/fleet-burst-$$` is PID-derived, so in
# a shared /tmp another local user can pre-plant `fleet-burst-<pid>/lane-1` as a
# symlink and `mkdir -p` plus the output redirection then follow it, steering lane
# output (which carries seat identifiers) into a file of their choosing. mktemp -d
# creates an unguessable directory owned by us with 0700. Raised by blind
# cross-family refutation (Kimi K3); the test file already used mktemp for its own
# scratch, so the tool was held to a lower standard than its corpus.
#
# Only the dispatch path needs a real directory. --dry-run creates nothing at all,
# so it gets a clearly-labelled placeholder instead of a stray empty dir -- and the
# plan it prints is the path that mode would actually use, not a different one.
if [[ -z "$run_dir" ]]; then
    if [[ "$dry_run" -eq 1 ]]; then
        run_dir="${TMPDIR:-/tmp}/fleet-burst-<mktemp-at-dispatch>"
    else
        run_dir="$(mktemp -d "${TMPDIR:-/tmp}/fleet-burst-XXXXXX")" \
            || die "could not create a private run directory"
    fi
fi

# Both of these are interpolated into the plan rows, so both are TSV-bound.
reject_control_chars "--model" "$model"
reject_control_chars "--run-dir" "$run_dir"

declare -a unique_candidates=()
declare -a live_seats=()
for seat in "${candidate_seats[@]}"; do
    # Normalise surrounding whitespace BEFORE anything else, because the dedup
    # below compares byte-identical strings and the whole invariant rests on it.
    # Measured: `--seats live-a,'live-a '` produced live_seats=2 and planned lane 1
    # and lane 2 onto what is operationally ONE seat, with PLAN and every count
    # reading correct -- the exact double-map this script exists to prevent,
    # walking through because two spellings of one identifier are not
    # byte-identical. Found by blind cross-family refutation (Kimi K3).
    # Trimming rather than rejecting is deliberate: `--seats "a, b"` is an ordinary
    # way to write a list, and erroring on it would push callers toward a form
    # this tool handles worse. The trimmed value is what is used downstream, so
    # nothing is compared in one spelling and dispatched in another.
    seat="${seat#"${seat%%[![:space:]]*}"}"
    seat="${seat%"${seat##*[![:space:]]}"}"
    [[ -n "$seat" ]] || die "seat identifiers must not be empty"
    reject_control_chars "seat identifier" "$seat"
    seat_seen=0
    for unique_seat in "${unique_candidates[@]:-}"; do
        if [[ "$unique_seat" == "$seat" ]]; then
            seat_seen=1
            break
        fi
    done
    [[ "$seat_seen" -eq 0 ]] || continue
    unique_candidates+=("$seat")

    # BOTH halves of the library's answer have to agree before a seat is
    # dispatchable: exit 0 AND a printed state of LIVE.
    #
    # An earlier version trusted the printed string alone and discarded the exit
    # status behind a dead if/else that existed only to suppress errexit, under a
    # comment calling the status "useful metadata" -- which it then did not use.
    # Measured: a library answering `LIVE<TAB>stale-cache` while returning 1 (the
    # shape an exhausted-seat-with-a-cached-label produces) was counted LIVE and
    # the burst proceeded onto it. The contract defines the return code as
    # authoritative, so disagreement between the two halves is treated as
    # not-live, never as live. Found by blind cross-family refutation (Kimi K3).
    #
    # `|| lookup_rc=$?` is what keeps errexit from aborting here: a non-zero
    # return is the library ANSWERING (1=EXHAUSTED, 2=UNKNOWN), not failing.
    lookup_rc=0
    lookup="$(seat_state_lookup "$seat" 2>/dev/null)" || lookup_rc=$?
    state="${lookup%%$'\t'*}"
    if [[ "$lookup_rc" -eq 0 && "$state" == "LIVE" ]]; then
        live_seats+=("$seat")
    fi
done

printf 'PLAN\tconcurrency=%s\tmodel=%s\trequested_lanes=%s\tlive_seats=%s\n' \
    "$max_concurrency" "$model" "$lanes" "${#live_seats[@]}"

if [[ "${#live_seats[@]}" -lt "$lanes" ]]; then
    die "refusing burst: requested ${lanes} lanes but found only ${#live_seats[@]} verified-LIVE distinct seats"
fi

declare -a lane_seats=()
for ((lane = 1; lane <= lanes; lane++)); do
    lane_seats+=("${live_seats[lane - 1]}")
    config_dir="${run_dir}/lane-${lane}/config"
    output_path="${run_dir}/lane-${lane}/output.txt"
    printf 'LANE\tlane=%s\tseat=%s\tconfig_dir=%s\toutput=%s\n' \
        "$lane" "${lane_seats[lane - 1]}" "$config_dir" "$output_path"
done

if [[ "$dry_run" -eq 1 ]]; then
    exit 0
fi

[[ -n "$prompt" ]] || die "--prompt is required unless --dry-run is used"

# ORDER IS LOAD-BEARING: the seat-binding guard below runs BEFORE the check that
# `claude` is installed, and that is not cosmetic.
#
# Measured: with the availability check first, a machine WITHOUT claude on PATH
# refuses with "claude command is unavailable" and never evaluates the security
# guard at all -- so the reason a misconfigured burst is refused depends on which
# machine you are standing on. This shipped green through a local gate on a box
# where claude IS installed and went red only in CI, where it is not: the dev
# machine was structurally incapable of reaching the branch.
#
# A refusal that protects a credential boundary must not sit behind an unrelated
# availability check. Refuse for the security reason first, on every machine.
#
# Fail-closed on the seat-binding gap, and the reasoning is the point.
#
# This dispatcher PLANS one distinct verified-LIVE seat per lane, and it handles
# seat IDENTIFIERS only -- it never reads, logs or injects a credential value.
# That is a deliberate boundary, but it has a consequence worth stating plainly:
# by itself this script cannot make a child actually USE the seat it was planned
# for. A lane spawned with nothing but a sterile CLAUDE_CONFIG_DIR authenticates
# with whatever ambient credential it inherits, so three lanes would land on ONE
# seat, burn that seat's quota three times, and report success -- a plan that
# looks satisfied while the invariant it exists to hold is broken.
#
# So a real burst REFUSES unless a broker is named. The broker's contract is
# `<broker> <seat-key> <command...>`: it binds exactly that seat's credential
# and execs the command. --dry-run is unaffected -- planning is what it is for,
# and the plan is honest about being only a plan.
[[ -n "${FLEET_BURST_SEAT_BROKER:-}" ]] || die "refusing to dispatch: no FLEET_BURST_SEAT_BROKER set, so lanes cannot be bound to the seats planned for them and would silently share one credential (use --dry-run to plan only)"
[[ -x "${FLEET_BURST_SEAT_BROKER}" ]] || die "FLEET_BURST_SEAT_BROKER is not executable: ${FLEET_BURST_SEAT_BROKER}"

command -v claude >/dev/null 2>&1 || die "claude command is unavailable"

declare -a active_pids=()
failed=0
for ((lane = 1; lane <= lanes; lane++)); do
    config_dir="${run_dir}/lane-${lane}/config"
    output_path="${run_dir}/lane-${lane}/output.txt"
    mkdir -p "$config_dir"

    # Direct redirection preserves incremental child output; collecting it in a
    # shell variable would recreate the W98 all-or-nothing disk failure mode.
    #
    # `-p` is a boolean flag on this CLI (measured from `claude --help` this
    # turn: it carries no <value> placeholder, unlike `--input-format <format>`),
    # so the prompt is an ordinary positional. Do NOT copy the agy rule from
    # claude-cascade.sh here -- there `-p` DOES take a value, and that note is
    # about agy, not claude.
    CLAUDE_CONFIG_DIR="$config_dir" \
        "$FLEET_BURST_SEAT_BROKER" "${lane_seats[lane - 1]}" \
        claude -p --model "$model" "$prompt" >"$output_path" 2>"${output_path}.stderr" &
    active_pids+=("$!")

    if [[ "${#active_pids[@]}" -ge "$max_concurrency" ]]; then
        if ! wait_for_pid "${active_pids[0]}"; then
            failed=1
        fi
        active_pids=("${active_pids[@]:1}")
    fi
done

for pid in "${active_pids[@]:-}"; do
    [[ -n "$pid" ]] || continue
    if ! wait_for_pid "$pid"; then
        failed=1
    fi
done

exit "$failed"
