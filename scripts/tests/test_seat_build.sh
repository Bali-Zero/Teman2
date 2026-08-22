#!/usr/bin/env bash
# Offline contract tests for seat_build.sh and its pure-Bash watchdog.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEAT_BUILD="$REPO_ROOT/scripts/seat_build.sh"
WATCHDOG="$REPO_ROOT/scripts/lib/seat_watchdog.sh"
FIXTURE="$(mktemp -d)"
MAIN_REPO="$FIXTURE/main"
LINKED_WT="$FIXTURE/linked"
TASK_FILE="$FIXTURE/task.txt"
FAKE_BIN="$FIXTURE/bin"
MARKER="$FIXTURE/seat-invoked"
PASS_COUNT=0
FAIL_COUNT=0

cleanup() {
    rm -rf "$FIXTURE"
}
trap cleanup EXIT

mkdir -p "$FAKE_BIN"
git init -q "$MAIN_REPO"
git -C "$MAIN_REPO" config user.email test@example.invalid
git -C "$MAIN_REPO" config user.name "Seat Build Test"
printf 'fixture\n' > "$MAIN_REPO/tracked.txt"
git -C "$MAIN_REPO" add tracked.txt
git -C "$MAIN_REPO" commit -qm "test fixture"
git -C "$MAIN_REPO" worktree add -qb linked-fixture "$LINKED_WT"
printf 'Change nothing.\n' > "$TASK_FILE"
# The fake expands this only if invoked.
# shellcheck disable=SC2016
printf '%s\n' '#!/usr/bin/env bash' ': > "${SEAT_TEST_MARKER:?}"' \
    'if [ "${FOO_API_KEY+x}" = x ]; then exit 9; fi' \
    'printf "%s\n" "fake seat output sentinel"' \
    'if [ "${SEAT_TEST_OUTPUT_MODE:-}" = quota ]; then printf "%s\n" "You have hit your usage limit"; fi' \
    > "$FAKE_BIN/codex"
chmod +x "$FAKE_BIN/codex"

run_case() {
    local name="$1"
    local fn="$2"
    if "$fn"; then
        printf 'PASS %s\n' "$name"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        printf 'FAIL %s\n' "$name"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

seat_env() {
    env PATH="$FAKE_BIN:$PATH" SEAT_TEST_MARKER="$MARKER" "$@"
}

case_clean_linked_dry_run() {
    local output
    [ -f "$SEAT_BUILD" ] || return 1
    rm -f "$MARKER"
    output="$(seat_env "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    [ ! -e "$MARKER" ] || return 1
    python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["dry_run"] is True and d["rc"] is None' \
        <<< "$output"
}

case_dirty_worktree_refused() {
    local rc=0
    [ -f "$SEAT_BUILD" ] || return 1
    printf 'dirty\n' > "$LINKED_WT/untracked.txt"
    seat_env "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    rm -f "$LINKED_WT/untracked.txt"
    [ "$rc" -ne 0 ]
}

case_main_checkout_refused() {
    local output
    local rc=0
    [ -f "$SEAT_BUILD" ] || return 1
    output="$(seat_env "$SEAT_BUILD" --seat codex --worktree "$MAIN_REPO" \
        --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || rc=$?
    [ "$rc" -eq 65 ] || return 1
    python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["rc"] == 65' <<< "$output"
}

case_unknown_seat_refused() {
    [ -f "$SEAT_BUILD" ] || return 1
    ! seat_env "$SEAT_BUILD" --seat unknown --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null
}

case_missing_task_refused() {
    [ -f "$SEAT_BUILD" ] || return 1
    ! seat_env "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" \
        --task-file "$FIXTURE/missing-task.txt" --dry-run >/dev/null 2>/dev/null
}

case_invalid_effort_refused() {
    [ -f "$SEAT_BUILD" ] || return 1
    ! seat_env "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --effort extreme --dry-run >/dev/null 2>/dev/null
}

case_quota_output_detected() {
    local output_file="$FIXTURE/quota-output.txt"
    [ -f "$SEAT_BUILD" ] || return 1
    # shellcheck source=/dev/null
    source "$SEAT_BUILD"
    printf "You've hit your usage limit\n" > "$output_file"
    quota_output_exhausted "$output_file"
}

case_quota_report_keeps_seat_rc() {
    local output
    output="$(seat_env FOO_API_KEY=private SEAT_TEST_OUTPUT_MODE=quota \
        "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" --task-file "$TASK_FILE" \
        --tests 'exit 7' --timeout 5 2>/dev/null)" || return 1
    python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["quota_exhausted"] is True; assert d["rc"] == 0; assert d["tests"] == {"cmd":"exit 7","rc":7}' \
        <<< "$output"
}

case_no_ship_commands() {
    [ -f "$SEAT_BUILD" ] || return 1
    ! sed '/^[[:space:]]*#/d' "$SEAT_BUILD" |
        grep -nE 'git (commit|push|merge)|(^|[^a-z])gh |launchctl|fly |vercel ' >/dev/null
}

case_no_external_timeout() {
    [ -f "$SEAT_BUILD" ] && [ -f "$WATCHDOG" ] || return 1
    ! grep -nE '(^|[;&|[:space:]])g?timeout[[:space:]]' "$SEAT_BUILD" "$WATCHDOG" >/dev/null
}

case_sensitive_env_stripped() {
    local json_file="$FIXTURE/dry-run.json"
    local log_file="$FIXTURE/dry-run.log"
    [ -f "$SEAT_BUILD" ] || return 1
    env PATH="$FAKE_BIN:$PATH" HOME="$FIXTURE/home" FOO_API_KEY=private \
        FOO_PUBLIC=visible SEAT_TEST_MARKER="$MARKER" \
        "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run > "$json_file" 2> "$log_file" || return 1
    python3 -c 'import json,sys; json.load(sys.stdin)' < "$json_file" || return 1
    grep -qw 'FOO_API_KEY' "$log_file" || return 1
    ! grep -Eq '(^|[ ,])PATH([ ,]|$)|(^|[ ,])HOME([ ,]|$)|(^|[ ,])FOO_PUBLIC([ ,]|$)' "$log_file"
}

case_clean_environment_reaches_seat() {
    local output
    rm -f "$MARKER"
    output="$(env -i PATH="$FAKE_BIN:$PATH" HOME="$FIXTURE/home" \
        SEAT_TEST_MARKER="$MARKER" bash "$SEAT_BUILD" --seat codex \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --timeout 5 \
        2>/dev/null)" || return 1
    [ -e "$MARKER" ] || return 1
    python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["rc"] == 0' <<< "$output"
}

case_quota_matching_requires_quota_context() {
    local output_file="$FIXTURE/quota-signature.txt"
    local line
    # shellcheck source=/dev/null
    source "$SEAT_BUILD"
    while IFS= read -r line; do
        printf '%s\n' "$line" > "$output_file"
        quota_output_exhausted "$output_file" || return 1
    done <<'EOF'
out of extra usage
usage limit reached
quota exceeded
rate limit reached
rate-limit reached
HTTP 429
HTTP: 429
status 429
status: 429
429 Too Many Requests
code 429
code: 429
quota exhausted
usage exhausted
credits exhausted
tokens exhausted
insufficient balance
EOF
    while IFS= read -r line; do
        printf '%s\n' "$line" > "$output_file"
        if quota_output_exhausted "$output_file"; then
            return 1
        fi
    done <<'EOF'
seat wrote code
 3 files changed, 429 insertions(+), 4 deletions(-)
the search space was exhausted
tokens used 45.736
EOF
}

case_seat_log_is_reported_and_persisted() {
    local output log_path
    output="$(seat_env "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --timeout 5 2>/dev/null)" || return 1
    log_path="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["log"])' \
        <<< "$output")" || return 1
    [ -f "$log_path" ] || return 1
    grep -Fq 'fake seat output sentinel' "$log_path"
}

case_tests_avoid_login_shell() {
    [ -f "$SEAT_BUILD" ] || return 1
    ! grep -nE 'bash[[:space:]]+-lc([[:space:]]|$)' "$SEAT_BUILD" >/dev/null
}

case_watchdog_kills_process_group() {
    local descendant_pid_file="$FIXTURE/descendant.pid"
    local rc=0
    local descendant_pid
    [ -f "$WATCHDOG" ] || return 1
    # shellcheck source=/dev/null
    source "$WATCHDOG"
    # Positional parameters belong to the child shells.
    # shellcheck disable=SC2016
    AI_DISPATCH_TIMEOUT_GRACE_SECS=0 run_with_timeout 1 bash -c \
        'trap "" TERM; bash -c '\''trap "" TERM; echo $$ > "$1"; while :; do sleep 1; done'\'' _ "$1" & wait' \
        _ "$descendant_pid_file" || rc=$?
    [ "$rc" -eq 124 ] || return 1
    descendant_pid="$(cat "$descendant_pid_file")"
    ! kill -0 "$descendant_pid" 2>/dev/null
}

run_case "clean linked worktree dry-run is JSON and invokes no seat" case_clean_linked_dry_run
run_case "dirty linked worktree is refused" case_dirty_worktree_refused
run_case "main checkout is refused" case_main_checkout_refused
run_case "unknown seat is refused" case_unknown_seat_refused
run_case "missing task file is refused" case_missing_task_refused
run_case "invalid effort is refused" case_invalid_effort_refused
run_case "quota text is detected directly" case_quota_output_detected
run_case "quota report preserves seat and test exit codes" case_quota_report_keeps_seat_rc
run_case "shipping commands are absent" case_no_ship_commands
run_case "external timeout commands are absent" case_no_external_timeout
run_case "secret env names are stripped selectively" case_sensitive_env_stripped
run_case "clean environment reaches the seat with no strip matches" case_clean_environment_reaches_seat
run_case "quota matching requires quota-shaped context" case_quota_matching_requires_quota_context
run_case "seat output log is reported and persists" case_seat_log_is_reported_and_persisted
run_case "test commands avoid login shells" case_tests_avoid_login_shell
run_case "watchdog kills the entire process group" case_watchdog_kills_process_group

printf 'SUMMARY %d passed, %d failed\n' "$PASS_COUNT" "$FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
