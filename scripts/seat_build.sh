#!/usr/bin/env bash
# Give Codex, Kimi, and Qwen one non-interactive build call shape so an
# orchestrator does not need to reimplement worktree setup, stdin closure,
# output parsing, or a watchdog. Fleet hosts have no working timeout(1) or
# gtimeout(1), so the sourced watchdog is pure Bash and kills process groups.
# Exit codes: 64 invalid arguments, 65 not a linked worktree, 66 dirty tree,
# 73 report-write failure, 124 watchdog expiry, and 127 missing seat binary.
# JSON reports include "log": the durable seat/test sidecar path, or null when
# no seat was invoked (for example, validation failures and --dry-run).
# This wrapper never ships:
# no commit, push, merge, hosting, deployment, or service-control operations.
# The orchestrator remains the independent grader and publisher.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/seat_watchdog.sh
source "$SCRIPT_DIR/lib/seat_watchdog.sh"
source "$SCRIPT_DIR/seat_build_tp1.sh"

quota_output_exhausted() {
    local output_file="$1"
    # A bare 429 may be a diffstat, and bare "exhausted" is ordinary prose.
    # Require HTTP/status/code/Too Many context for 429 and a quota-shaped noun
    # for exhausted; "insufficient balance" is a provider error body.
    grep -qiE \
        -e 'out of extra usage' \
        -e 'usage limit' \
        -e 'quota([[:space:]_.-]+limit)?[[:space:]_.-]+(exceeded|exhausted)' \
        -e '(^|[^[:alnum:]_])rate[[:space:]_.-]*limit([^[:alnum:]_]|$)' \
        -e '(^|[^[:alnum:]_])HTTP([^[:space:]]*[[:space:]]+|[^[:alnum:]_]*)429([^[:digit:]]|$)' \
        -e '(^|[^[:alnum:]_])(status|code)[[:space:]:=_.-]*429([^[:digit:]]|$)' \
        -e '(^|[^[:digit:]])429[[:space:]]+Too[[:space:]]+Many([^[:alnum:]_]|$)' \
        -e '(usage|credits?|tokens?)[[:space:]_.-]+exhausted' \
        -e 'insufficient balance' \
        "$output_file"
}

collect_git_metrics() {
    DIFF_STAT=""
    UNTRACKED=0
    if [ -n "$WORKTREE" ] && git -C "$WORKTREE" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        DIFF_STAT="$(git -C "$WORKTREE" diff --shortstat 2>/dev/null || true)"
        UNTRACKED="$(git -C "$WORKTREE" ls-files --others --exclude-standard 2>/dev/null |
            wc -l | tr -d '[:space:]')" || UNTRACKED=0
    fi
}

emit_report() {
    local report_rc="$1"
    local dry_run="$2"
    local report_json
    report_json="$(python3 - "$SEAT" "$MODEL" "$EFFORT" "$report_rc" "$DURATION" \
        "$DIFF_STAT" "$UNTRACKED" "$TESTS_CMD" "$TESTS_RC" "$QUOTA_EXHAUSTED" \
        "$LOG_PATH" "$dry_run" <<'PY'
import json
import sys

seat, model, effort, rc, duration, diff_stat, untracked, tests_cmd, tests_rc, quota, log_path, dry = sys.argv[1:]
report = {
    "seat": seat,
    "model": model,
    "effort": effort,
    "rc": None if rc == "null" else int(rc),
    "duration_s": int(duration),
    "diff_stat": diff_stat,
    "untracked": int(untracked),
    "tests": None if not tests_cmd else {
        "cmd": tests_cmd,
        "rc": None if tests_rc == "null" else int(tests_rc),
    },
    "quota_exhausted": quota == "true",
    "log": log_path or None,
}
if dry == "true":
    report["dry_run"] = True
print(json.dumps(report, separators=(",", ":")))
PY
)"
    if [ -n "$OUT_PATH" ] && ! printf '%s\n' "$report_json" > "$OUT_PATH"; then
        printf 'seat_build: cannot write report: %s\n' "$OUT_PATH" >&2
        printf '%s\n' "$report_json"
        return 73
    fi
    printf '%s\n' "$report_json"
}

refuse() {
    local code="$1"
    shift
    printf 'seat_build: %s\n' "$*" >&2
    collect_git_metrics
    emit_report "$code" false || true
    exit "$code"
}

main() {
    SEAT=""
    MODEL="unknown"
    WORKTREE=""
    TASK_FILE=""
    TESTS_CMD=""
    TESTS_RC="null"
    EFFORT="medium"
    TIMEOUT_SECS=1800
    OUT_PATH=""
    DRY_RUN=false
    DURATION=0
    DIFF_STAT=""
    UNTRACKED=0
    QUOTA_EXHAUSTED=false
    LOG_PATH=""

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --seat|--worktree|--task-file|--tests|--effort|--timeout|--out)
                [ "$#" -ge 2 ] || refuse 64 "missing value for $1"
                case "$1" in
                    --seat) SEAT="$2" ;;
                    --worktree) WORKTREE="$2" ;;
                    --task-file) TASK_FILE="$2" ;;
                    --tests) TESTS_CMD="$2" ;;
                    --effort) EFFORT="$2" ;;
                    --timeout) TIMEOUT_SECS="$2" ;;
                    --out) OUT_PATH="$2" ;;
                esac
                shift 2
                ;;
            --dry-run) DRY_RUN=true; shift ;;
            *) refuse 64 "unknown argument: $1" ;;
        esac
    done

    local binary_name
    case "$SEAT" in
        codex) binary_name="codex"; MODEL="codex-default" ;;
        kimi) binary_name="kimi"; MODEL="kimi-code/kimi-for-coding" ;;
        qwen) binary_name="qwen"; MODEL="qwen-default" ;;
        tp1) binary_name="$(tp1_binary_path)"; MODEL="${TP1_MODEL:-$TP1_DEFAULT_MODEL}" ;;
        "") refuse 64 "missing --seat" ;;
        *) refuse 64 "unknown seat: $SEAT" ;;
    esac
    [ -n "$WORKTREE" ] || refuse 64 "missing --worktree"
    [ -r "$TASK_FILE" ] || refuse 64 "missing or unreadable --task-file: $TASK_FILE"
    case "$EFFORT" in low|medium|high|xhigh) ;; *) refuse 64 "invalid --effort: $EFFORT" ;; esac
    [[ "$TIMEOUT_SECS" =~ ^[1-9][0-9]*$ ]] || refuse 64 "invalid --timeout: $TIMEOUT_SECS"

    local git_dir
    git_dir="$(git -C "$WORKTREE" rev-parse --git-dir 2>/dev/null)" ||
        refuse 65 "not a Git worktree: $WORKTREE"
    if [[ "$git_dir" != /* ]]; then
        git_dir="$(cd "$WORKTREE" && cd "$git_dir" && pwd -P)"
    else
        git_dir="$(cd "$git_dir" && pwd -P)"
    fi
    [[ "$git_dir" == */worktrees/* ]] || refuse 65 "main checkout refused: $WORKTREE"
    [ -z "$(git -C "$WORKTREE" status --porcelain)" ] || refuse 66 "dirty worktree refused: $WORKTREE"

    local seat_binary
    if ! seat_binary="$(command -v "$binary_name")"; then
        collect_git_metrics
        emit_report 127 false
        exit 127
    fi

    local task_text task_preview task_index stripped_count
    local -a seat_argv display_argv strip_env_args stripped_names
    task_text="$(< "$TASK_FILE")"
    case "$SEAT" in
        codex)
            seat_argv=("$seat_binary" exec --sandbox workspace-write --skip-git-repo-check \
                -c "model_reasoning_effort=$EFFORT" "$task_text")
            task_index=7
            ;;
        kimi) seat_argv=("$seat_binary" -p "$task_text" -m kimi-code/kimi-for-coding); task_index=2 ;;
        qwen) seat_argv=("$seat_binary" -p "$task_text"); task_index=2 ;;
        tp1) seat_argv=("$seat_binary" -p "$task_text" --model "$MODEL" --effort "$EFFORT"); task_index=2 ;;
    esac
    strip_env_args=()
    stripped_names=()
    stripped_count=0
    local env_name
    while IFS= read -r -d '' env_name; do
        if [[ "$env_name" =~ (_API_KEY|_TOKEN|_SECRET|_PASSWORD)$ ]] ||
            [[ "$env_name" =~ ^(ANTHROPIC_|CLAUDE_CODE_OAUTH|AWS_|GITHUB_TOKEN|GH_TOKEN) ]]; then
            strip_env_args+=(-u "$env_name")
            stripped_names+=("$env_name")
            stripped_count=$((stripped_count + 1))
        fi
    done < <(python3 -c 'import os,sys; sys.stdout.buffer.write(b"".join(os.fsencode(k)+b"\0" for k in sorted(os.environ)))')

    if [ "$DRY_RUN" = true ]; then
        task_preview="${task_text:0:60}"
        [ "${#task_text}" -le 60 ] || task_preview+="..."
        display_argv=(${seat_argv[@]+"${seat_argv[@]}"})
        display_argv[task_index]="$task_preview"
        printf 'Resolved argv:' >&2
        printf ' %q' ${display_argv[@]+"${display_argv[@]}"} >&2
        printf '\nStripped env names:' >&2
        if [ "$stripped_count" -eq 0 ]; then
            printf ' (none)' >&2
        else
            printf ' %s' ${stripped_names[@]+"${stripped_names[@]}"} >&2
        fi
        printf '\n' >&2
        collect_git_metrics
        emit_report null true
        exit 0
    fi

    local output_file seat_rc started_at log_dir
    log_dir="$(cd "$WORKTREE/.." && pwd -P)"
    LOG_PATH="$log_dir/seat-build-${SEAT}-$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
    output_file="$LOG_PATH"
    started_at="$(date +%s)"
    if (cd "$WORKTREE" && run_with_timeout "$TIMEOUT_SECS" \
        env ${strip_env_args[@]+"${strip_env_args[@]}"} \
            ${seat_argv[@]+"${seat_argv[@]}"} < /dev/null) > "$output_file" 2>&1; then
        seat_rc=0
    else
        seat_rc=$?
    fi
    if quota_output_exhausted "$output_file"; then
        QUOTA_EXHAUSTED=true
    fi
    if [ -n "$TESTS_CMD" ]; then
        if (cd "$WORKTREE" && run_with_timeout "$TIMEOUT_SECS" \
            bash -c "$TESTS_CMD" < /dev/null) >> "$output_file" 2>&1; then
            TESTS_RC=0
        else
            TESTS_RC=$?
        fi
    fi
    DURATION=$(( $(date +%s) - started_at ))
    collect_git_metrics
    emit_report "$seat_rc" false
    exit "$seat_rc"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
