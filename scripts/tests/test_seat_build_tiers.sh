#!/usr/bin/env bash
# Offline contract tests for seat_build.sh's --tier / effort-cap / ctx-check surface
# (mandate E2/R2-R4). Complements test_seat_build.sh, which owns the pre-existing
# contract (seat=codex|kimi|qwen, no tiers). Uses --dry-run throughout: these are
# argument-shape and policy checks, never a real seat invocation.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEAT_BUILD="$REPO_ROOT/scripts/seat_build.sh"
FIXTURE="$(mktemp -d)"
MAIN_REPO="$FIXTURE/main"
LINKED_WT="$FIXTURE/linked"
TASK_FILE="$FIXTURE/task.txt"
BIG_TASK_FILE="$FIXTURE/big-task.txt"
FAKE_BIN="$FIXTURE/bin"
PASS_COUNT=0
FAIL_COUNT=0

cleanup() {
    rm -rf "$FIXTURE"
}
trap cleanup EXIT

mkdir -p "$FAKE_BIN"
git init -q "$MAIN_REPO"
git -C "$MAIN_REPO" config user.email test@example.invalid
git -C "$MAIN_REPO" config user.name "Seat Build Tier Test"
printf 'fixture\n' > "$MAIN_REPO/tracked.txt"
git -C "$MAIN_REPO" add tracked.txt
git -C "$MAIN_REPO" commit -qm "test fixture"
git -C "$MAIN_REPO" worktree add -qb linked-tier-fixture "$LINKED_WT"
printf 'Tier test task, small.\n' > "$TASK_FILE"
# 900 KB — bytes/4 ~= 230400 estimated tokens: over every kimi tier's 128000-token
# window in scripts/seat_ctx.json, under every codex/agy tier's ~1M window.
python3 -c "import sys; sys.stdout.write('x' * (900 * 1024))" > "$BIG_TASK_FILE"

for stub in codex kimi agy qwen; do
    printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$FAKE_BIN/$stub"
    chmod +x "$FAKE_BIN/$stub"
done

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
    env PATH="$FAKE_BIN:$PATH" "$@"
}

# ── argv per seat/tier (innocence: each tier resolves to its documented model) ──

case_codex_tier_sol_argv() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat codex --tier sol --effort xhigh --gear 3 \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["rc"] is None and d["tier"] == "sol"
argv=d["argv"]
assert "-m" in argv and argv[argv.index("-m")+1] == "gpt-5.6-sol", argv
assert "-c" in argv and argv[argv.index("-c")+1] == "model_reasoning_effort=xhigh", argv' \
        <<< "$out"
}

case_codex_tier_terra_argv() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat codex --tier terra --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
argv=d["argv"]
assert argv[argv.index("-m")+1] == "gpt-5.6-terra", argv' <<< "$out"
}

case_codex_tier_luna_argv() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat codex --tier luna --effort medium \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
argv=d["argv"]
assert argv[argv.index("-m")+1] == "gpt-5.6-luna", argv' <<< "$out"
}

case_kimi_tier_k3_argv() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat kimi --tier k3 --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
argv=d["argv"]
assert argv[argv.index("-m")+1] == "kimi-code/k3", argv' <<< "$out"
}

case_kimi_tier_highspeed_medium_ok() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat kimi --tier highspeed --effort medium \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
argv=d["argv"]
assert argv[argv.index("-m")+1] == "kimi-code/kimi-for-coding-highspeed", argv' <<< "$out"
}

case_agy_tier_flash_argv() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat agy --tier flash --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
argv=d["argv"]
assert "--model" in argv and argv[argv.index("--model")+1] == "gemini-3.5-flash", argv
assert "--print-timeout" in argv and argv[argv.index("--print-timeout")+1] == "8m", argv
assert "-p" in argv, argv' <<< "$out"
}

case_qwen_unchanged_ignores_tier() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat qwen --tier sol --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["rc"] is None
argv=d["argv"]
assert argv[1] == "-p", argv
assert "-m" not in argv and "--model" not in argv, argv' <<< "$out"
}

# ── R2: codex effort caps by tier ───────────────────────────────────────────

case_codex_luna_xhigh_capped() {
    local rc=0
    seat_env "$SEAT_BUILD" --seat codex --tier luna --effort xhigh \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    [ "$rc" -eq 65 ]
}

case_codex_terra_xhigh_capped() {
    local rc=0
    seat_env "$SEAT_BUILD" --seat codex --tier terra --effort xhigh \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    [ "$rc" -eq 65 ]
}

case_codex_sol_xhigh_without_gear_refused() {
    local err rc=0
    err="$(seat_env "$SEAT_BUILD" --seat codex --tier sol --effort xhigh \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run 2>&1 >/dev/null)" || rc=$?
    [ "$rc" -eq 65 ] || return 1
    grep -q 'R2' <<< "$err"
}

case_codex_sol_xhigh_with_gear3_allowed() {
    local rc=0
    seat_env "$SEAT_BUILD" --seat codex --tier sol --effort xhigh --gear 3 \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    [ "$rc" -eq 0 ]
}

case_codex_sol_max_without_gear_refused() {
    local rc=0
    seat_env "$SEAT_BUILD" --seat codex --tier sol --effort max \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    [ "$rc" -eq 65 ]
}

# ── R3: kimi effort cap on highspeed ─────────────────────────────────────────

case_kimi_highspeed_high_capped() {
    local rc=0
    seat_env "$SEAT_BUILD" --seat kimi --tier highspeed --effort high \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    [ "$rc" -eq 65 ]
}

# ── E2 ctx-check ─────────────────────────────────────────────────────────────

case_kimi_coding_ctx_overflow() {
    local err rc=0
    err="$(seat_env "$SEAT_BUILD" --seat kimi --tier coding --worktree "$LINKED_WT" \
        --task-file "$BIG_TASK_FILE" --dry-run 2>&1 >/dev/null)" || rc=$?
    [ "$rc" -eq 66 ] || return 1
    grep -q 'ctx-check' <<< "$err" && grep -q 'eligible' <<< "$err"
}

case_codex_sol_handles_same_big_file() {
    # Same 900 KB file must NOT overflow codex/sol's ~1M-token window.
    local rc=0
    seat_env "$SEAT_BUILD" --seat codex --tier sol --effort xhigh --gear 3 \
        --worktree "$LINKED_WT" --task-file "$BIG_TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    [ "$rc" -eq 0 ]
}

# ── R4: agy pro/flash ctx+role gate ──────────────────────────────────────────

case_agy_pro_small_input_downgrades_to_flash() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat agy --tier pro --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["tier"] == "flash", d
argv=d["argv"]
assert argv[argv.index("--model")+1] == "gemini-3.5-flash", argv' <<< "$out"
}

case_agy_pro_large_input_keeps_pro() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat agy --tier pro --worktree "$LINKED_WT" \
        --task-file "$BIG_TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["tier"] == "pro", d
argv=d["argv"]
assert argv[argv.index("--model")+1] == "gemini-3.1-pro", argv' <<< "$out"
}

case_agy_pro_role_synthesis_keeps_pro_on_small_input() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat agy --tier pro --role synthesis \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["tier"] == "pro", d' <<< "$out"
}

# ── tier defaulting / SEAT_BUILD_TIER_REQUIRED ───────────────────────────────

case_missing_tier_notice_defaults() {
    local out err
    err="$(seat_env "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run 2>&1 >/dev/null)" || return 1
    # Exact mandated wording (mandate item 1): "--tier missing, defaulting to
    # <t> (mandatory from 2026-09-02)". Not literally the word NOTICE.
    grep -q -- '--tier missing, defaulting to terra (mandatory from 2026-09-02)' <<< "$err" || return 1
    out="$(seat_env "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["tier"] == "terra", d' <<< "$out"
}

case_missing_tier_required_env_exit64() {
    local rc=0
    seat_env SEAT_BUILD_TIER_REQUIRED=1 "$SEAT_BUILD" --seat codex --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    [ "$rc" -eq 64 ]
}

case_invalid_tier_value_refused() {
    local rc=0
    seat_env "$SEAT_BUILD" --seat codex --tier bogus --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    [ "$rc" -eq 64 ]
}

case_invalid_gear_value_refused() {
    local rc=0
    seat_env "$SEAT_BUILD" --seat codex --tier sol --effort xhigh --gear 7 \
        --worktree "$LINKED_WT" --task-file "$TASK_FILE" --dry-run >/dev/null 2>/dev/null || rc=$?
    [ "$rc" -eq 64 ]
}

# ── report shape ─────────────────────────────────────────────────────────────

case_report_has_new_fields() {
    local out
    out="$(seat_env "$SEAT_BUILD" --seat codex --tier terra --worktree "$LINKED_WT" \
        --task-file "$TASK_FILE" --dry-run 2>/dev/null)" || return 1
    python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["tier"] == "terra"
assert isinstance(d["input_tokens_est"], int) and d["input_tokens_est"] >= 0
assert isinstance(d["argv"], list) and len(d["argv"]) > 0' <<< "$out"
}

run_case "codex/sol argv carries -m gpt-5.6-sol and effort=xhigh" case_codex_tier_sol_argv
run_case "codex/terra argv carries -m gpt-5.6-terra" case_codex_tier_terra_argv
run_case "codex/luna argv carries -m gpt-5.6-luna" case_codex_tier_luna_argv
run_case "kimi/k3 argv carries -m kimi-code/k3" case_kimi_tier_k3_argv
run_case "kimi/highspeed at medium effort is allowed" case_kimi_tier_highspeed_medium_ok
run_case "agy/flash argv carries --model gemini-3.5-flash" case_agy_tier_flash_argv
run_case "qwen ignores --tier entirely" case_qwen_unchanged_ignores_tier
run_case "R2: codex/luna capped at medium, xhigh refused (65)" case_codex_luna_xhigh_capped
run_case "R2: codex/terra capped at high, xhigh refused (65)" case_codex_terra_xhigh_capped
run_case "R2: codex/sol xhigh without --gear 3 refused (65)" case_codex_sol_xhigh_without_gear_refused
run_case "R2: codex/sol xhigh WITH --gear 3 allowed" case_codex_sol_xhigh_with_gear3_allowed
run_case "R2: codex/sol max without --gear 3 refused (65)" case_codex_sol_max_without_gear_refused
run_case "R3: kimi/highspeed capped at medium, high refused (65)" case_kimi_highspeed_high_capped
run_case "ctx-check: 900KB task on kimi/coding overflows (66)" case_kimi_coding_ctx_overflow
run_case "ctx-check: same 900KB task fits codex/sol window" case_codex_sol_handles_same_big_file
run_case "R4: agy/pro downgrades to flash on small input" case_agy_pro_small_input_downgrades_to_flash
run_case "R4: agy/pro keeps pro on >200k-token input" case_agy_pro_large_input_keeps_pro
run_case "R4: agy/pro keeps pro under --role synthesis" case_agy_pro_role_synthesis_keeps_pro_on_small_input
run_case "missing --tier defaults with a stderr NOTICE" case_missing_tier_notice_defaults
run_case "SEAT_BUILD_TIER_REQUIRED=1 turns missing --tier into exit 64" case_missing_tier_required_env_exit64
run_case "unknown --tier value is refused (64)" case_invalid_tier_value_refused
run_case "invalid --gear value is refused (64)" case_invalid_gear_value_refused
run_case "report JSON carries tier/input_tokens_est/argv" case_report_has_new_fields

printf 'SUMMARY %d passed, %d failed\n' "$PASS_COUNT" "$FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
