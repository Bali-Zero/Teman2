#!/usr/bin/env bash
# Hermetic checks for fleet_burst.sh.  The optional --dry-run is accepted so
# the documented acceptance command can use the same test suite invocation.

set -u

if [[ "${1:-}" == "--dry-run" ]]; then
    shift
fi
[[ "$#" -eq 0 ]] || {
    printf 'usage: %s [--dry-run]\n' "$0" >&2
    exit 2
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
burst_script="${script_dir}/../fleet_burst.sh"
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/fleet-burst-test.XXXXXX")"
fake_lib="${tmp_dir}/seat_state.sh"
failed=0
total=0

cleanup() {
    rm -rf "$tmp_dir"
}
trap cleanup EXIT

printf '%s\n' \
    'seat_state_lookup() {' \
    '    case "$1" in' \
    "        live-*) printf 'LIVE\\tfake-live\\n'; return 0 ;;" \
    "        exhausted-*) printf 'EXHAUSTED\\tfake-exhausted\\n'; return 1 ;;" \
    "        unknown-*) printf 'UNKNOWN\\tfake-unknown\\n'; return 2 ;;" \
    "        *) printf 'UNKNOWN\\tfake-unlisted\\n'; return 2 ;;" \
    '    esac' \
    '}' \
    '' \
    'seat_is_live() {' \
    '    seat_state_lookup "$1" >/dev/null' \
    '}' >"$fake_lib"

check() {
    local name="$1"
    local result="$2"

    total=$((total + 1))
    if [[ "$result" == "pass" ]]; then
        printf 'PASS %s\n' "$name"
    else
        printf 'FAIL %s\n' "$name"
        failed=$((failed + 1))
    fi
}

count_nonempty() {
    awk 'NF { count += 1 } END { print count + 0 }'
}

field_values() {
    local field="$1"
    awk -F '\t' -v key="${field}=" '$1 == "LANE" { for (i = 2; i <= NF; i++) if (index($i, key) == 1) { sub(key, "", $i); print $i } }'
}

run_burst() {
    local label="$1"
    shift

    run_stdout="${tmp_dir}/${label}.stdout"
    run_stderr="${tmp_dir}/${label}.stderr"
    FLEET_BURST_SEAT_STATE_LIB="$fake_lib" \
        "$burst_script" "$@" >"$run_stdout" 2>"$run_stderr"
    run_status=$?
}

# Guilt: refusal must happen BEFORE any lane is mapped, so five lanes can never
# be spread over three seats.
#
# The assertion here is deliberately "zero LANE rows", not "the emitted seats are
# unique". An earlier form of this check compared the seat column's count against
# its sorted-unique count -- but a refusal emits no LANE rows at all, so that
# comparison was 0 == 0: true by construction, and it would have stayed green if
# the refusal moved to AFTER the mapping loop, which is the exact defect it named.
# Measured this turn: the guilt run emits 0 LANE rows. Counting them is a check
# that can fail; comparing an empty column against itself is not.
run_burst guilt --lanes 5 --seats live-a,live-b,live-c --dry-run
guilt_lane_rows="$(awk -F '\t' '$1 == "LANE" { count += 1 } END { print count + 0 }' "$run_stdout")"
if [[ "$run_status" -ne 0 && "$guilt_lane_rows" -eq 0 ]] \
    && grep -q 'refusing burst' "$run_stderr"; then
    check GUILT_REFUSES_BEFORE_MAPPING_ANY_LANE pass
else
    check GUILT_REFUSES_BEFORE_MAPPING_ANY_LANE fail
fi

# The guard that actually stops a double-map. If the same seat is offered twice
# and the dispatcher does not collapse duplicates, two lanes resolve to ONE seat
# while every count still looks right -- the failure mode the refusal check above
# cannot see, because in that world there are enough "live seats" to proceed.
# Mutation-verified: deleting the dedup block in fleet_burst.sh turns this red
# (2 lanes both mapped to live-a) and leaves every other check green.
run_burst dedup --lanes 2 --seats live-a,live-a --dry-run
dedup_lane_rows="$(awk -F '\t' '$1 == "LANE" { count += 1 } END { print count + 0 }' "$run_stdout")"
if [[ "$run_status" -ne 0 && "$dedup_lane_rows" -eq 0 ]] \
    && grep -q 'refusing burst' "$run_stderr"; then
    check DUPLICATE_SEAT_CANNOT_FILL_TWO_LANES pass
else
    check DUPLICATE_SEAT_CANNOT_FILL_TWO_LANES fail
fi

run_burst innocence --lanes 3 --seats live-a,live-b,live-c --run-dir "${tmp_dir}/innocence" --dry-run
innocence_lanes="$(awk -F '\t' '$1 == "LANE" { count += 1 } END { print count + 0 }' "$run_stdout")"
innocence_seats="$(field_values seat <"$run_stdout")"
innocence_configs="$(field_values config_dir <"$run_stdout")"
innocence_outputs="$(field_values output <"$run_stdout")"
if [[ "$run_status" -eq 0 && "$innocence_lanes" -eq 3 ]] \
    && [[ "$(printf '%s\n' "$innocence_seats" | sort -u | count_nonempty)" -eq 3 ]] \
    && [[ "$(printf '%s\n' "$innocence_configs" | sort -u | count_nonempty)" -eq 3 ]] \
    && [[ "$(printf '%s\n' "$innocence_outputs" | sort -u | count_nonempty)" -eq 3 ]]; then
    check INNOCENCE_DISTINCT_LANES_AND_PATHS pass
else
    check INNOCENCE_DISTINCT_LANES_AND_PATHS fail
fi

run_burst excluded --lanes 2 --seats live-a,exhausted-a,unknown-a,live-b --dry-run
excluded_seats="$(field_values seat <"$run_stdout" | sort)"
if [[ "$run_status" -eq 0 && "$excluded_seats" == $'live-a\nlive-b' ]]; then
    check EXHAUSTED_AND_UNKNOWN_EXCLUDED pass
else
    check EXHAUSTED_AND_UNKNOWN_EXCLUDED fail
fi

run_burst fable --lanes 1 --seat live-a --model claude-fable-5 --dry-run
if [[ "$run_status" -ne 0 ]] && grep -qi 'fable' "$run_stderr"; then
    check FABLE_REFUSED pass
else
    check FABLE_REFUSED fail
fi

run_burst concurrency --lanes 1 --seat live-a --dry-run
if [[ "$run_status" -eq 0 ]] && grep -q $'^PLAN\tconcurrency=3\t' "$run_stdout"; then
    check DEFAULT_CONCURRENCY_REPORTED_AS_3 pass
else
    check DEFAULT_CONCURRENCY_REPORTED_AS_3 fail
fi

missing_stdout="${tmp_dir}/missing.stdout"
missing_stderr="${tmp_dir}/missing.stderr"
FLEET_BURST_SEAT_STATE_LIB="${tmp_dir}/does-not-exist.sh" \
    "$burst_script" --lanes 1 --seat live-a --dry-run >"$missing_stdout" 2>"$missing_stderr"
missing_status=$?
if [[ "$missing_status" -ne 0 ]] && grep -q 'seat state library' "$missing_stderr"; then
    check MISSING_SEAT_LIBRARY_FAILS_LOUDLY pass
else
    check MISSING_SEAT_LIBRARY_FAILS_LOUDLY fail
fi

# A real burst with no seat broker must REFUSE, not proceed. Without this the
# script's central promise (one distinct seat per lane) degrades silently at the
# only moment it matters: every lane inherits the same ambient credential, the
# plan still reads correct, and one seat's quota is spent N times.
#
# The assertion is that the run directory does not exist AT ALL, not merely that
# no output file appeared. An earlier form checked only for lane-1/output.txt,
# which is created by the spawn redirection -- so it proved "did not spawn" while
# its own comment claimed "no side effects", and moving the guard to after
# `mkdir -p` would have left it green while the script mutated the filesystem
# before refusing. Found by blind cross-family refutation (Kimi K3).
# Mutation-verified: dropping the FLEET_BURST_SEAT_BROKER guard turns this red.
real_run_dir="${tmp_dir}/no-broker"
real_stdout="${tmp_dir}/no-broker.stdout"
real_stderr="${tmp_dir}/no-broker.stderr"
env -u FLEET_BURST_SEAT_BROKER FLEET_BURST_SEAT_STATE_LIB="$fake_lib" \
    "$burst_script" --lanes 1 --seat live-a --prompt 'noop' --run-dir "$real_run_dir" \
    >"$real_stdout" 2>"$real_stderr"
real_status=$?
if [[ "$real_status" -ne 0 ]] && grep -q 'FLEET_BURST_SEAT_BROKER' "$real_stderr" \
    && [[ ! -e "$real_run_dir" ]]; then
    check REAL_BURST_REFUSES_BEFORE_TOUCHING_THE_FILESYSTEM pass
else
    check REAL_BURST_REFUSES_BEFORE_TOUCHING_THE_FILESYSTEM fail
fi

# The SAME refusal, on a machine where `claude` is not installed.
#
# This is the check the local gate could not have written from imagination: the
# first version of the guard sat AFTER `command -v claude`, so on a dev box with
# claude on PATH it refused for the seat-binding reason and on a CI runner without
# it refused for "claude command is unavailable" -- the same misconfiguration
# producing two different verdicts depending on where you stand. It passed
# locally 14/14 and went red only in CI.
# Restricting PATH here reproduces the runner's shape on any machine, so the
# ordering cannot silently regress back.
noclaude_stderr="${tmp_dir}/noclaude.stderr"
noclaude_run_dir="${tmp_dir}/noclaude-rd"
env -u FLEET_BURST_SEAT_BROKER PATH="/usr/bin:/bin" \
    FLEET_BURST_SEAT_STATE_LIB="$fake_lib" \
    "$burst_script" --lanes 1 --seat live-a --prompt 'noop' --run-dir "$noclaude_run_dir" \
    >/dev/null 2>"$noclaude_stderr"
noclaude_status=$?
if [[ "$noclaude_status" -ne 0 ]] && grep -q 'FLEET_BURST_SEAT_BROKER' "$noclaude_stderr" \
    && [[ ! -e "$noclaude_run_dir" ]]; then
    check SEAT_BINDING_REFUSAL_DOES_NOT_DEPEND_ON_CLAUDE_BEING_INSTALLED pass
else
    check SEAT_BINDING_REFUSAL_DOES_NOT_DEPEND_ON_CLAUDE_BEING_INSTALLED fail
fi

# Two spellings of one seat must not fill two lanes. This is the double-map the
# refusal check cannot see: with `live-a` and `live-a ` both counted, there ARE
# enough "live seats" to proceed, so nothing refuses and both lanes plan onto one
# real seat while PLAN and every count read correct.
# Mutation-verified: removing the whitespace normalisation turns this red.
run_burst nearduplicate --lanes 2 --seats "live-a,live-a " --dry-run
if [[ "$run_status" -ne 0 ]] && grep -q 'refusing burst' "$run_stderr"; then
    check NEAR_DUPLICATE_SEAT_CANNOT_FILL_TWO_LANES pass
else
    check NEAR_DUPLICATE_SEAT_CANNOT_FILL_TWO_LANES fail
fi

# The library answers with a status AND a string; a seat is dispatchable only if
# both say live. A stub that prints LIVE while returning 1 is the shape an
# exhausted seat carrying a cached label produces, and trusting the string alone
# sends the burst onto it.
# Mutation-verified: dropping the exit-status half of the condition turns this red.
liar_lib="${tmp_dir}/seat_state_liar.sh"
printf '%s\n' 'seat_state_lookup() { printf "LIVE\tstale-cache\n"; return 1; }' >"$liar_lib"
liar_stdout="${tmp_dir}/liar.stdout"
FLEET_BURST_SEAT_STATE_LIB="$liar_lib" \
    "$burst_script" --lanes 1 --seat seat-x --dry-run >"$liar_stdout" 2>"${tmp_dir}/liar.stderr"
liar_status=$?
liar_lane_rows="$(awk -F '\t' '$1 == "LANE" { count += 1 } END { print count + 0 }' "$liar_stdout")"
if [[ "$liar_status" -ne 0 && "$liar_lane_rows" -eq 0 ]]; then
    check PRINTED_LIVE_WITH_NONZERO_STATUS_IS_NOT_DISPATCHABLE pass
else
    check PRINTED_LIVE_WITH_NONZERO_STATUS_IS_NOT_DISPATCHABLE fail
fi

# Every value interpolated into a plan row must be rejected if it carries a tab,
# because the rows are the machine-readable contract and a tab silently
# TRUNCATES the field a reader gets. Measured before the fix: --run-dir with an
# embedded tab made the config_dir field parse as "/tmp/x" instead of the real
# path, so a plan could read correct while describing something else.
# Both are checked because the original guard covered only the seat identifier
# and left these two -- the same defect on two of three call sites.
for injection_case in "--run-dir" "--model"; do
    inject_stderr="${tmp_dir}/inject$(printf '%s' "$injection_case" | tr -d -- '-').stderr"
    FLEET_BURST_SEAT_STATE_LIB="$fake_lib" \
        "$burst_script" --lanes 1 --seat live-a "$injection_case" "$(printf 'x\ty')" --dry-run \
        >/dev/null 2>"$inject_stderr"
    inject_status=$?
    if [[ "$inject_status" -ne 0 ]] && grep -q 'corrupt the plan rows' "$inject_stderr"; then
        check "TSV_INJECTION_REJECTED${injection_case}" pass
    else
        check "TSV_INJECTION_REJECTED${injection_case}" fail
    fi
done

# The throttle itself, not the number the plan prints about it.
#
# Blind refutation (Kimi K3) pointed out that DEFAULT_CONCURRENCY_REPORTED_AS_3
# greps the PLAN row and nothing more: break the throttle so every lane spawns at
# once and that check stays green, because the plan would still SAY 3. The
# ceiling is one of the two scars this dispatcher exists for (W96), so the
# property worth pinning is "never more than N children alive at once", which
# only a real dispatch can show.
#
# Hermetic: a shim `claude` earlier on PATH logs its own start and end, a stub
# broker execs its command, and the seat library is the fake. Nothing here
# reaches the network, a real CLI, or a real seat. Max concurrency is recovered
# by walking the log (+1 START, -1 END); appends of a short line are atomic, so
# the ordering in the file is the real ordering.
shim_bin="${tmp_dir}/bin"
mkdir -p "$shim_bin"
conc_log="${tmp_dir}/concurrency.log"
: >"$conc_log"
printf '%s\n' '#!/usr/bin/env bash' 'printf "START\n" >>"$CONC_LOG"' 'sleep 0.4' 'printf "END\n" >>"$CONC_LOG"' \
    >"${shim_bin}/claude"
chmod +x "${shim_bin}/claude"
stub_broker="${tmp_dir}/stub_broker.sh"
printf '%s\n' '#!/usr/bin/env bash' 'shift' 'exec "$@"' >"$stub_broker"
chmod +x "$stub_broker"

CONC_LOG="$conc_log" PATH="${shim_bin}:${PATH}" \
    FLEET_BURST_SEAT_STATE_LIB="$fake_lib" FLEET_BURST_SEAT_BROKER="$stub_broker" \
    "$burst_script" --lanes 5 --seats live-a,live-b,live-c,live-d,live-e \
    --max-concurrency 2 --prompt 'noop' --run-dir "${tmp_dir}/throttle" \
    >/dev/null 2>"${tmp_dir}/throttle.stderr"
throttle_status=$?
observed_peak="$(awk '/^START$/ { n += 1; if (n > peak) peak = n } /^END$/ { n -= 1 } END { print peak + 0 }' "$conc_log")"
observed_starts="$(grep -c '^START$' "$conc_log" || true)"
if [[ "$throttle_status" -eq 0 && "$observed_starts" -eq 5 && "$observed_peak" -le 2 ]]; then
    check THROTTLE_HOLDS_UNDER_REAL_DISPATCH pass
else
    check "THROTTLE_HOLDS_UNDER_REAL_DISPATCH (starts=${observed_starts} peak=${observed_peak} rc=${throttle_status})" fail
fi

if bash -n "$burst_script"; then
    check BASH_SYNTAX pass
else
    check BASH_SYNTAX fail
fi

printf 'TOTAL %s FAILED %s\n' "$total" "$failed"
[[ "$failed" -eq 0 ]]
