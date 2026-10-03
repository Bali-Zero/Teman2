#!/usr/bin/env bash
# test_cron_agent_checkout_guard.sh — the hard half of the anti-git prompt
# sentence: run_agent() measures the H24 checkout before and after the agent
# turn and fails the run (exit 3, GIT-MUTATION log line, error state) when the
# agent committed or switched branch. A fake `claude` performs the mutation in a
# throwaway repo placed where the wrapper looks by default ($HOME/nuzantara), so
# this asserts on what the wrapper does with a real git state change.
#
# Guilt:     commit on HEAD; commit then fail; branch switch; commit then
#            push (origin/main moves with HEAD); commit then reset away;
#            the 2026-09-28 shape (worktree branch from origin/main, commit,
#            push, worktree and branch removed — HEAD never moves).
# Innocence: untracked report on disk; the sync cron's fetch + fast-forward
#            moving origin/main and HEAD together; no checkout at all; a
#            concurrent session committing on its own branch during the run.
set -uo pipefail
# Run from a git hook (pre-push) these point at the REAL repo and would win over
# `git -C <sandbox>`: fresh_checkout would commit and rewrite refs there.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR \
      GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_NAMESPACE GIT_PREFIX

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/cron-agent.sh"
[ -f "$WRAPPER" ] || { echo "FAIL: wrapper not found at $WRAPPER"; exit 2; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/croncheckoutguard.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
FAILED=0
ok()  { echo "  ok   — $1"; }
bad() { echo "  FAIL — $1"; FAILED=1; }

FAKE_HOME="$SANDBOX/home"
CHECKOUT="$FAKE_HOME/nuzantara"
PROMPT="$SANDBOX/prompt.txt"; echo "submit the daily indexing batch" > "$PROMPT"
G=(git -c user.name=t -c user.email=t@example.invalid -c init.defaultBranch=main)

# fake claude: mutate (or not) the checkout per FAKE_MODE, answer, exit FAKE_RC
cat > "$SANDBOX/claude" <<'FAKE'
#!/usr/bin/env bash
G=(git -c user.name=t -c user.email=t@example.invalid -C "$FAKE_CHECKOUT")
case "$FAKE_MODE" in
    commit)  "${G[@]}" commit -q --allow-empty -m "agent report" ;;
    branch)  "${G[@]}" checkout -q -b agent-side ;;
    pushed)  "${G[@]}" commit -q --allow-empty -m "agent report"
             "${G[@]}" update-ref refs/remotes/origin/main HEAD ;;
    undone)  "${G[@]}" commit -q --allow-empty -m "agent report"
             "${G[@]}" reset -q --hard origin/main ;;
    side|sibling)
             # sibling = another session on the host: its own identity, not the stamp
             [ "$FAKE_MODE" = sibling ] && unset GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL
             wt="$FAKE_CHECKOUT.wt"
             "${G[@]}" worktree add -q -b agent/x/deps-audit "$wt" origin/main
             git -c user.name=t -c user.email=t@example.invalid -C "$wt" commit -q --allow-empty -m deps
             "${G[@]}" update-ref refs/remotes/origin/agent/x/deps-audit agent/x/deps-audit
             if [ "$FAKE_MODE" = side ]; then
                 "${G[@]}" worktree remove --force "$wt"
                 "${G[@]}" branch -q -D agent/x/deps-audit
             fi ;;
    report)  echo '{"submitted":0}' > "$FAKE_CHECKOUT/daily_report.json" ;;
    sync)    # upstream commits come from GitHub, never from the agent's process tree
             unset GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL
             new="$("${G[@]}" commit-tree "origin/main^{tree}" -p origin/main -m upstream)"
             "${G[@]}" update-ref refs/remotes/origin/main "$new"
             "${G[@]}" merge -q --ff-only origin/main ;;
esac
echo "fake answer"
exit "${FAKE_RC:-0}"
FAKE
chmod +x "$SANDBOX/claude"
# fake timeout: drop the duration arg, exec the rest (macOS has no coreutils timeout)
cat > "$SANDBOX/timeout" <<'FAKE'
#!/usr/bin/env bash
shift
exec "$@"
FAKE
chmod +x "$SANDBOX/timeout"

fresh_checkout() {
    rm -rf "$CHECKOUT"; mkdir -p "$CHECKOUT"
    "${G[@]}" -C "$CHECKOUT" init -q
    "${G[@]}" -C "$CHECKOUT" commit -q --allow-empty -m base
    "${G[@]}" -C "$CHECKOUT" update-ref refs/remotes/origin/main HEAD
}

# run_case <job> <mode> [fake_rc] [checkout_dir_override] -> sets RC, LOG, STATE
run_case() {
    local job="$1" mode="$2" fake_rc="${3:-0}" override="${4:-}"
    env HOME="$FAKE_HOME" CRON_AGENT_HOME="$FAKE_HOME" \
        ${override:+"CRON_AGENT_CHECKOUT_DIR=$override"} \
        FAKE_MODE="$mode" FAKE_RC="$fake_rc" FAKE_CHECKOUT="${override:-$CHECKOUT}" \
        CRON_AGENT_CLAUDE_BIN="$SANDBOX/claude" CRON_AGENT_TIMEOUT_BIN="$SANDBOX/timeout" \
        CLAUDE_CODE_OAUTH_TOKEN_1=faketoken \
        TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= \
        bash "$WRAPPER" agent "$job" "$PROMPT" > "$SANDBOX/$job.out" 2>&1
    RC=$?
    LOG="$(cat "$FAKE_HOME/logs/cron-agent/$job.log" 2>/dev/null)"
    STATE="$(cat "$FAKE_HOME/.cron-agent/$job.state.json" 2>/dev/null)"
}

expect_mutation() {
    local what="$1"
    if [[ "$RC" == "3" && "$LOG" == *"GIT-MUTATION"* && "$STATE" == *'"exit_code":3'* ]]; then
        ok "$what -> exit 3, GIT-MUTATION logged, error state"
    else
        bad "$what -> rc=$RC (want 3); log tail: $(printf '%s' "$LOG" | tail -2 | tr '\n' ' ')"
    fi
}

expect_clean() {
    local what="$1"
    if [[ "$RC" == "0" && "$LOG" != *"GIT-MUTATION"* && "$STATE" == *'"status":"ok"'* ]]; then
        ok "$what -> exit 0, no GIT-MUTATION"
    else
        bad "$what -> rc=$RC (want 0); log tail: $(printf '%s' "$LOG" | tail -2 | tr '\n' ' ')"
    fi
}

echo "guilt"
fresh_checkout; run_case guard-commit commit
expect_mutation "agent commits on the H24 checkout"
fresh_checkout; run_case guard-commit-fail commit 1
expect_mutation "agent commits and then the run fails"
fresh_checkout; run_case guard-branch branch
expect_mutation "agent switches the H24 checkout to another branch"
fresh_checkout; run_case guard-pushed pushed
expect_mutation "agent commits and pushes (ahead stays 0)"
fresh_checkout; run_case guard-undone undone
expect_mutation "agent commits then resets it away (branch and ahead unchanged)"
fresh_checkout; run_case guard-side side
expect_mutation "agent ships from a side worktree, then removes it (2026-09-28 shape)"
[[ "$LOG" == *"commits stamped by this run"* ]] \
    && ok "the side-worktree commit was caught by the committer stamp" \
    || bad "the side-worktree case was not caught by the committer stamp"

echo "innocence"
fresh_checkout; run_case guard-report report
expect_clean "agent writes its report to disk, uncommitted"
fresh_checkout; run_case guard-sibling sibling
expect_clean "another session commits on its own worktree branch mid-run"
rm -rf "$CHECKOUT.wt"
fresh_checkout; run_case guard-sync sync
expect_clean "sync cron fast-forwards HEAD with origin/main mid-run"
# the innocence above only counts if the fast-forward really happened
[ "$(git -C "$CHECKOUT" rev-list --count HEAD)" = "2" ] \
    || bad "sync fake did not fast-forward HEAD — the innocence case proved nothing"
mkdir -p "$SANDBOX/not-a-repo"
run_case guard-norepo none 0 "$SANDBOX/not-a-repo"
expect_clean "no checkout to measure (guard stays out)"
[[ "$LOG" == *"checkout guard OFF"* ]] \
    && ok "an unmeasurable checkout says so in the log" \
    || bad "the guard went silent instead of logging that it is off"

echo
[ "$FAILED" -eq 0 ] && { echo "PASS — cron-agent H24 checkout guard"; exit 0; } || { echo "FAIL"; exit 1; }
