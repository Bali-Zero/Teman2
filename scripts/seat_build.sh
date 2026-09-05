#!/usr/bin/env bash
# Give Codex, Kimi, Qwen, and agy (Gemini) one non-interactive build call shape
# so an orchestrator does not need to reimplement worktree setup, stdin
# closure, output parsing, or a watchdog. Fleet hosts have no working
# timeout(1) or gtimeout(1), so the sourced watchdog is pure Bash and kills
# process groups.
# Exit codes: 64 invalid arguments (includes a missing --tier when
# SEAT_BUILD_TIER_REQUIRED=1), 65 not a linked worktree OR an effort/gear policy
# violation (R2/R3: an effort above a tier's cap, or sol at xhigh/max without
# --gear 3), 66 dirty tree OR the task's estimated tokens exceed the requested
# seat/tier's context window (ctx-check), 73 report-write failure, 124 watchdog
# expiry, and 127 missing seat binary.
# JSON reports include "log": the durable seat/test sidecar path, or null when
# no seat was invoked (for example, validation failures and --dry-run).
#
# --tier selects the model within a seat: codex sol|terra|luna, kimi
# k3|coding|highspeed, agy flash|pro. Omitting it defaults (terra/coding/flash)
# with a stderr NOTICE; SEAT_BUILD_TIER_REQUIRED=1 turns that NOTICE into exit 64
# (mandatory from 2026-09-02). qwen has no tiers and ignores --tier entirely.
# --gear names the diff's CI-recomputed gear floor (1|2|3) — only consulted to
# gate codex/sol at effort xhigh|max (R2). --role, currently only "synthesis",
# lets agy/pro survive on a small task file without the usual ctx downgrade (R4).
#
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
    shift 2
    # Only meaningful when dry_run=true: the redacted argv preview (mandate E2
    # item 4, "prints the final argv as JSON"). Empty on every other call site.
    local -a argv_preview=("$@")
    local report_json
    report_json="$(python3 - "$SEAT" "$MODEL" "$EFFORT" "${TIER:-}" "$report_rc" "$DURATION" \
        "$DIFF_STAT" "$UNTRACKED" "$TESTS_CMD" "$TESTS_RC" "$QUOTA_EXHAUSTED" \
        "$LOG_PATH" "$dry_run" "${INPUT_TOKENS_EST:-0}" "${TIER_DOWNGRADED_FROM:-}" \
        "${EFFORT_SOURCE:-}" "${EFFORT_ADVISORY:-}" \
        ${argv_preview[@]+"${argv_preview[@]}"} <<'PY'
import json
import sys

(seat, model, effort, tier, rc, duration, diff_stat, untracked, tests_cmd,
 tests_rc, quota, log_path, dry, input_tokens_est, downgraded_from,
 effort_source, effort_advisory) = sys.argv[1:18]
argv_preview = sys.argv[18:]
report = {
    "seat": seat,
    "model": model,
    "effort": effort,
    "tier": tier or None,
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
    "input_tokens_est": int(input_tokens_est),
    # R4: non-null only when agy/pro was silently downgraded (e.g. to
    # "flash") — a caller checking rc==0 alone would otherwise believe it
    # got the tier it asked for (codex-sol adversarial review, PR #5044).
    "tier_downgraded_from": downgraded_from or None,
    # PR-3: which path set EFFORT ("unresolved" | "explicit" | "default" |
    # "derived-from-floor" | "advisory-floor-2"). "unresolved" means the run was
    # refused before the derivation ran, never that no path applies; floor 2 unenforced proposed value, None when not
    # applicable -- never the empty string. (No apostrophes in this heredoc body:
    # bash 3.2 mis-scans single quotes for command-substitution balance even
    # inside a quoted <<'PY' heredoc -- verified live, not theoretical.)
    "effort_source": effort_source,
    "effort_advisory": effort_advisory or None,
}
if dry == "true":
    report["dry_run"] = True
    report["argv"] = argv_preview
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

# seat_tier_default <seat> <default_tier>
# If --tier was not given, defaults it (NOTICE to stderr) unless
# SEAT_BUILD_TIER_REQUIRED=1, in which case a missing --tier is exit 64.
# No-op when --tier is already set (explicit value is validated by the caller).
seat_tier_default() {
    local seat="$1" default_tier="$2"
    [ -n "$TIER" ] && return 0
    if [ "${SEAT_BUILD_TIER_REQUIRED:-0}" = "1" ]; then
        refuse 64 "--tier is required for seat '$seat' (mandatory from 2026-09-02; SEAT_BUILD_TIER_REQUIRED=1)"
    fi
    printf 'seat_build: --tier missing, defaulting to %s (mandatory from 2026-09-02)\n' "$default_tier" >&2
    TIER="$default_tier"
}

# Ordinal rank of an effort level, low..max. -1 for an unrecognized value
# (unreachable here: EFFORT is already validated before this is called).
effort_rank() {
    case "$1" in
        low) echo 0 ;;
        medium) echo 1 ;;
        high) echo 2 ;;
        xhigh) echo 3 ;;
        max) echo 4 ;;
        *) echo -1 ;;
    esac
}

# R2/R3: static per-tier effort ceilings, plus R2's dynamic sol/xhigh+ gear gate.
# Requires SEAT/TIER/EFFORT/GEAR already resolved. Exits 65 on violation.
enforce_effort_cap() {
    local rank cap_rank
    rank="$(effort_rank "$EFFORT")"
    case "$SEAT/$TIER" in
        codex/luna)
            cap_rank="$(effort_rank medium)"
            [ "$rank" -le "$cap_rank" ] ||
                refuse 65 "R2: codex/luna is capped at effort medium (got $EFFORT)"
            ;;
        codex/terra)
            cap_rank="$(effort_rank high)"
            [ "$rank" -le "$cap_rank" ] ||
                refuse 65 "R2: codex/terra is capped at effort high (got $EFFORT)"
            ;;
        codex/sol)
            cap_rank="$(effort_rank xhigh)"
            if [ "$rank" -ge "$cap_rank" ] && [ "$GEAR" != "3" ]; then
                refuse 65 "R2: codex/sol at effort $EFFORT requires --gear 3 (got --gear=${GEAR:-<unset>})"
            fi
            ;;
        kimi/highspeed)
            cap_rank="$(effort_rank medium)"
            [ "$rank" -le "$cap_rank" ] ||
                refuse 65 "R3: kimi/highspeed is capped at effort medium (got $EFFORT)"
            ;;
        *) ;;  # kimi/k3, kimi/coding, agy/flash, agy/pro: no cap in this mandate
    esac
}

# derive_effort_from_floor — PR-3 (R2/R5): when --effort is omitted, derive the
# default from --gear's compute-floor instead of leaving the hardcoded literal
# "medium" (main()'s init value) to apply regardless of floor. floor-1 -> medium
# and floor-3 -> xhigh come straight from the source report's R2 and existing
# modus doctrine (xhigh is the coding/agentic default; max is
# Gear-3-adjudication-only, so this derivation path can never produce max).
# floor-2 has NO default specified by the source report or by existing
# doctrine, so this function does not invent one: it logs `high` as a proposal
# (this spec's suggestion, <ruled value - Zero>) and enforces nothing until
# Zero rules it — whoever rules floor-2 flips the advisory branch below into
# an enforcing one, it does not need a new mechanism.
derive_effort_from_floor() {
    if [ "$EFFORT_EXPLICIT" = true ]; then
        EFFORT_SOURCE="explicit"
        return 0
    fi
    if [ -z "$GEAR" ]; then
        EFFORT_SOURCE="default"
        return 0
    fi
    case "$GEAR" in
        1)
            EFFORT="medium"
            EFFORT_SOURCE="derived-from-floor"
            ;;
        3)
            EFFORT="xhigh"
            EFFORT_SOURCE="derived-from-floor"
            ;;
        2)
            # Advisory only (needs-ruling, PR-3): do NOT overwrite EFFORT.
            EFFORT_ADVISORY="high"
            EFFORT_SOURCE="advisory-floor-2"
            printf 'seat_build: --gear 2 has no ruled default effort yet (advisory only, not enforced): proposed high, pending Zero ruling\n' >&2
            ;;
    esac
}

# ctx_window_for <seat> <tier> — prints the configured context window (tokens)
# from scripts/seat_ctx.json. Exit 1 means the seat/tier pair is legitimately
# absent from an otherwise-valid table (this is how qwen, which carries no
# tiers, is exempted). Exit 2 means the table itself could not be trusted
# (missing file, unreadable, invalid JSON) — the caller must NOT treat that
# the same as an intentional exemption, or ctx-check fails open exactly when
# its own configuration is broken (codex-sol adversarial review, PR #5044).
ctx_window_for() {
    python3 - "$SCRIPT_DIR/seat_ctx.json" "$1" "$2" <<'PY'
import json
import sys

path, seat, tier = sys.argv[1:4]
try:
    with open(path) as f:
        data = json.load(f)
except (OSError, ValueError) as exc:
    print(f"seat_build: seat_ctx.json unreadable/invalid: {exc}", file=sys.stderr)
    sys.exit(2)
window = data.get(seat, {}).get(tier)
if not isinstance(window, int):
    sys.exit(1)
print(window)
PY
}

# ctx_eligible_seats <need_tokens> — comma-joined "seat/tier" list of every
# entry in scripts/seat_ctx.json whose window can hold need_tokens.
ctx_eligible_seats() {
    python3 - "$SCRIPT_DIR/seat_ctx.json" "$1" <<'PY'
import json
import sys

path, need = sys.argv[1], int(sys.argv[2])
with open(path) as f:
    data = json.load(f)
out = []
for seat in sorted(data):
    for tier in sorted(data[seat]):
        window = data[seat][tier]
        if isinstance(window, int) and window >= need:
            out.append(f"{seat}/{tier}")
print(",".join(out))
PY
}

# E2 ctx-check: refuses (exit 66) when the task file's estimated token count
# (bytes/4, already computed into INPUT_TOKENS_EST) exceeds the requested
# seat/tier's declared context window.
enforce_ctx_window() {
    local window rc=0
    window="$(ctx_window_for "$SEAT" "$TIER")" || rc=$?
    if [ "$rc" -eq 2 ]; then
        refuse 64 "ctx-check: scripts/seat_ctx.json is missing or invalid — cannot verify $SEAT/$TIER's context window (refusing rather than failing open)"
    elif [ "$rc" -eq 1 ]; then
        return 0  # seat/tier has no declared window in a VALID table: exempt, not a config error
    fi
    [ "$INPUT_TOKENS_EST" -le "$window" ] && return 0
    local eligible
    eligible="$(ctx_eligible_seats "$INPUT_TOKENS_EST")"
    refuse 66 "ctx-check: $SEAT/$TIER context window is $window tokens, task is ~$INPUT_TOKENS_EST estimated tokens; eligible seats: ${eligible:-none}"
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
    EFFORT_EXPLICIT=false
    # "unresolved", not "": several refusals (invalid --effort/--gear/--seat/
    # --tier) emit the report BEFORE derive_effort_from_floor runs, and an empty
    # string there is a fifth, undocumented state that a consumer cannot tell
    # apart from "resolved to nothing". Found by a blind codex-sol refutation
    # and reproduced: those paths reported effort_source='' with rc=64.
    EFFORT_SOURCE="unresolved"
    EFFORT_ADVISORY=""
    TIMEOUT_SECS=1800
    OUT_PATH=""
    DRY_RUN=false
    DURATION=0
    DIFF_STAT=""
    UNTRACKED=0
    QUOTA_EXHAUSTED=false
    LOG_PATH=""
    TIER=""
    GEAR=""
    ROLE=""
    INPUT_TOKENS_EST=0
    TIER_DOWNGRADED_FROM=""

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --seat|--worktree|--task-file|--tests|--effort|--timeout|--out|--tier|--gear|--role)
                [ "$#" -ge 2 ] || refuse 64 "missing value for $1"
                case "$1" in
                    --seat) SEAT="$2" ;;
                    --worktree) WORKTREE="$2" ;;
                    --task-file) TASK_FILE="$2" ;;
                    --tests) TESTS_CMD="$2" ;;
                    --effort) EFFORT="$2"; EFFORT_EXPLICIT=true ;;
                    --timeout) TIMEOUT_SECS="$2" ;;
                    --out) OUT_PATH="$2" ;;
                    --tier) TIER="$2" ;;
                    --gear) GEAR="$2" ;;
                    --role) ROLE="$2" ;;
                esac
                shift 2
                ;;
            --dry-run) DRY_RUN=true; shift ;;
            *) refuse 64 "unknown argument: $1" ;;
        esac
    done

    local binary_name
    case "$SEAT" in
        codex)
            binary_name="codex"
            seat_tier_default codex terra
            case "$TIER" in
                sol|terra|luna) ;;
                *) refuse 64 "invalid --tier for seat codex: $TIER (expected sol|terra|luna)" ;;
            esac
            MODEL="gpt-5.6-$TIER"
            ;;
        kimi)
            binary_name="kimi"
            seat_tier_default kimi coding
            case "$TIER" in
                k3) MODEL="kimi-code/k3" ;;
                coding) MODEL="kimi-code/kimi-for-coding" ;;
                highspeed) MODEL="kimi-code/kimi-for-coding-highspeed" ;;
                *) refuse 64 "invalid --tier for seat kimi: $TIER (expected k3|coding|highspeed)" ;;
            esac
            ;;
        agy)
            binary_name="agy"
            seat_tier_default agy flash
            case "$TIER" in
                flash|pro) ;;
                *) refuse 64 "invalid --tier for seat agy: $TIER (expected flash|pro)" ;;
            esac
            MODEL="pending"  # finalized below, after the pro/flash ctx+role gate (R4)
            ;;
        qwen)
            binary_name="qwen"; MODEL="${QWEN_MODEL:-qwen-default}"
            # QWEN_MODEL (generals exam, 2026-09-06): the `qwen` CLI drives every
            # coding-plan model that PONGed 26/26 on all three machines
            # (qwen3.8-max, deepseek-v4-pro, glm-5.2, ...); without a passthrough
            # the seat could only ever sit the account default. Report shows the
            # slug actually requested.
            # unchanged: no tiers. Clear (not just ignore) a --tier the caller
            # passed anyway, so the report never claims a tier qwen never used
            # (codex-sol adversarial review, PR #5044: a stray --tier value
            # would otherwise leak into telemetry/routing downstream).
            TIER=""
            ;;
        tp1)
            binary_name="$(tp1_binary_path)"; MODEL="${TP1_MODEL:-$TP1_DEFAULT_MODEL}"
            # Forward-compatible with PR #5044's tier system (codex/kimi/agy
            # sol/terra/luna-style tiers): tp1 has no tiers of its own — one
            # OpenAI-compatible door per model slug — so clear (not just
            # ignore) a stray --tier the same way qwen's arm does, so the
            # report never claims a tier tp1 never used.
            TIER=""
            ;;
        "") refuse 64 "missing --seat" ;;
        *) refuse 64 "unknown seat: $SEAT" ;;
    esac
    [ -n "$WORKTREE" ] || refuse 64 "missing --worktree"
    [ -r "$TASK_FILE" ] || refuse 64 "missing or unreadable --task-file: $TASK_FILE"
    case "$EFFORT" in low|medium|high|xhigh|max) ;; *) refuse 64 "invalid --effort: $EFFORT" ;; esac
    [[ "$TIMEOUT_SECS" =~ ^[1-9][0-9]*$ ]] || refuse 64 "invalid --timeout: $TIMEOUT_SECS"
    case "$GEAR" in ""|1|2|3) ;; *) refuse 64 "invalid --gear: $GEAR (expected 1|2|3)" ;; esac

    derive_effort_from_floor

    INPUT_TOKENS_EST=$(( $(wc -c < "$TASK_FILE" | tr -d '[:space:]') / 4 ))

    if [ "$SEAT" = "agy" ]; then
        if [ "$TIER" = "pro" ] && [ "$INPUT_TOKENS_EST" -le 200000 ] && [ "$ROLE" != "synthesis" ]; then
            printf 'seat_build: R4 — agy/pro needs >200000 estimated input tokens or --role synthesis (got ~%s tokens, role=%s); downgrading to flash\n' \
                "$INPUT_TOKENS_EST" "${ROLE:-none}" >&2
            TIER_DOWNGRADED_FROM="pro"
            TIER=flash
        fi
        case "$TIER" in
            flash) MODEL="gemini-3.5-flash" ;;
            pro) MODEL="gemini-3.1-pro" ;;
        esac
    fi

    if [ -n "$TIER" ]; then
        enforce_effort_cap
        enforce_ctx_window
    fi

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
                -m "$MODEL" -c "model_reasoning_effort=$EFFORT" "$task_text")
            task_index=9
            ;;
        kimi)
            seat_argv=("$seat_binary" -p "$task_text" -m "$MODEL"); task_index=2
            [ "${SEAT_AUTONOMOUS:-0}" = 1 ] && seat_argv+=(--auto)  # "Never Ask": nobody is there to answer
            ;;
        agy)
            seat_argv=("$seat_binary" -p "$task_text" --model "$MODEL" --print-timeout "$((TIMEOUT_SECS / 60))m"); task_index=2  # was a hardcoded 8m: shorter than any real build
            [ "${SEAT_AUTONOMOUS:-0}" = 1 ] && seat_argv+=(--dangerously-skip-permissions)  # same flag agy_code_dispatch.py uses by default
            ;;
        qwen)
            seat_argv=("$seat_binary" -p "$task_text"); task_index=2
            [ -n "${QWEN_MODEL:-}" ] && seat_argv+=(--model "$QWEN_MODEL")
            # Headless qwen cannot run a shell without -y (measured 2026-09-06: "requires
            # user approval but cannot execute in non-interactive mode"). Opt-in only, for
            # lanes whose worktree is disposable (the generals exam) — never the default.
            [ "${SEAT_AUTONOMOUS:-0}" = 1 ] && seat_argv+=(-y)
            ;;
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
        emit_report null true ${display_argv[@]+"${display_argv[@]}"}
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
