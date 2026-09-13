#!/usr/bin/env bash
# test_automations_reference_cron_wrapper.sh — proof for
# scripts/automations-reference-cron-wrapper.sh (nightly regen of
# docs/AUTOMATIONS_REFERENCE.md, promoted from an isolated worktree as a
# docs-only PR — decision 2026-09-11, ends the two-authors overwrite between
# Pro's live 23:15 regen and the hand-edited committed copy, PENDING-ARMS).
#
# Same recipe as test_lane_ship.sh: GIT IS REAL, GH IS FAKED. The wrapper's
# own worktree creation is delegated to `python3 scripts/agent_start.py`,
# which is a heavy real broker script this test does not want to exercise —
# so PYTHON3 IS FAKED TOO, and the fake performs the one thing the wrapper
# actually depends on (a real git clone/checkout that `git add/commit/push`
# can act on) without any of agent_start.py's TTL/lane/lock machinery. `gh`
# talks to GitHub's real API and must be faked for an offline, deterministic
# test; both fakes log every invocation to their own log for assertions,
# same pattern as test_lane_ship.sh's FAKE_GH_LOG.
#
# WHAT IT PINS
#   kill switch — AUTOMATIONS_REFERENCE_ENABLED=false exits 0 without
#                 touching git, gh, or python3's worktree path at all.
#   no change   — the generator produces no diff -> worktree released via
#                 `agent_start.py --release`, heartbeat ok "no change",
#                 gh never invoked.
#   changed     — the generator's diff is committed, pushed, a PR is opened,
#                 auto-merge is armed via `gh pr merge --auto`, heartbeat ok.
#   generator failure, no output -> heartbeat error, worktree released,
#                 exit 1, gh never invoked.
#   push failure -> heartbeat error naming the rc, exit 1, gh never invoked.
#   PR create failure -> heartbeat error, exit 1, branch pushed but no arm.
#   auto-merge does not arm -> heartbeat degraded, exit 0 (RUN_RC=0 still).
#
# No network, no real gh, no real agent_start.py, no real GitHub.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
WRAPPER="$REPO_ROOT/scripts/automations-reference-cron-wrapper.sh"
[ -f "$WRAPPER" ] || { echo "FAIL: wrapper not found at $WRAPPER"; exit 2; }

failures=0
check() {  # check <name> <0-or-1>
  if [ "$2" = "1" ]; then printf '  ok   %s\n' "$1"
  else printf '  FAIL %s\n' "$1"; failures=$((failures + 1)); fi
}
has() { case "$2" in *"$1"*) return 0 ;; *) return 1 ;; esac; }
yesno() { if "$@"; then echo 1; else echo 0; fi; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/automations_wrapper_test.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT

# One scenario = one fresh world: real bare "origin", a fake $HOME whose
# nuzantara/ is only a placeholder (the wrapper never reads its content —
# every python3 call, including the real agent_start.py invocation, is
# intercepted by the fake below), fake gh + fake python3 state dirs and logs.
new_world() {
  W="$(mktemp -d "$SANDBOX/w.XXXXXX")"
  # $HOME/logs pre-exists on Pro (every other wrapper already writes there);
  # the wrapper's own kill-switch branch (before REPO_ROOT/LOG are even
  # assigned) writes straight to "${HOME}/logs/..." with no mkdir -p of its
  # own, same as translate-articles-cron-wrapper.sh — so the fixture must
  # match that pre-existing production state, not paper over a real gap.
  mkdir -p "$W/bin" "$W/fgh" "$W/fpy" "$W/home/nuzantara/scripts" "$W/home/logs" "$W/wtbase"
  GHLOG="$W/ghlog"; PYLOG="$W/pylog"; NPXLOG="$W/npxlog"
  : > "$GHLOG"; : > "$PYLOG"; : > "$NPXLOG"
  : > "$W/home/nuzantara/scripts/agent_start.py"

  cat > "$W/bin/gh" <<'FAKEGH'
#!/usr/bin/env bash
set -uo pipefail
printf '%s\n' "$*" >> "$FAKE_GH_LOG"
case "${1:-}" in
  pr)
    case "${2:-}" in
      create)
        rc=0; [ -f "$FAKE_GH_STATE/create_rc" ] && rc="$(cat "$FAKE_GH_STATE/create_rc")"
        if [ -f "$FAKE_GH_STATE/create_out" ]; then cat "$FAKE_GH_STATE/create_out"; else echo 'https://github.com/test-owner/test-repo/pull/99'; fi
        exit "$rc" ;;
      list)
        rc=0; [ -f "$FAKE_GH_STATE/list_rc" ] && rc="$(cat "$FAKE_GH_STATE/list_rc")"
        [ -f "$FAKE_GH_STATE/list_out" ] && cat "$FAKE_GH_STATE/list_out"
        exit "$rc" ;;
      close)
        rc=0; [ -f "$FAKE_GH_STATE/close_rc" ] && rc="$(cat "$FAKE_GH_STATE/close_rc")"
        exit "$rc" ;;
      merge)
        rc=0; [ -f "$FAKE_GH_STATE/merge_rc" ] && rc="$(cat "$FAKE_GH_STATE/merge_rc")"
        [ -f "$FAKE_GH_STATE/merge_out" ] && cat "$FAKE_GH_STATE/merge_out"
        exit "$rc" ;;
    esac ;;
  api)
    case "${2:-}" in
      graphql)
        rc=0; [ -f "$FAKE_GH_STATE/graphql_rc" ] && rc="$(cat "$FAKE_GH_STATE/graphql_rc")"
        if [ -f "$FAKE_GH_STATE/graphql_out" ]; then cat "$FAKE_GH_STATE/graphql_out"; else echo 'null'; fi
        exit "$rc" ;;
    esac ;;
esac
echo "FAKE_GH: unhandled invocation: $*" >&2
exit 99
FAKEGH
  chmod +x "$W/bin/gh"

  # Fake python3 — the ONLY two shapes the wrapper ever hands it:
  #   scripts/agent_start.py --cleanup|--lane ...|--release TASK
  #   <worktree>/scripts/generate_automations_reference.py
  cat > "$W/bin/python3" <<'FAKEPY'
#!/usr/bin/env bash
set -uo pipefail
printf '%s\n' "$*" >> "$FAKE_PY_LOG"

case "${1:-}" in
  *agent_start.py)
    shift
    case "${1:-}" in
      --cleanup) exit 0 ;;
      --release) exit 0 ;;
      --lane)
        lane=""; task_id=""
        while [ $# -gt 0 ]; do
          case "$1" in
            --lane) lane="$2"; shift 2 ;;
            --task-id) task_id="$2"; shift 2 ;;
            --ttl-min) shift 2 ;;
            *) shift ;;
          esac
        done
        rc=0; [ -f "$FAKE_PY_STATE/create_rc" ] && rc="$(cat "$FAKE_PY_STATE/create_rc")"
        [ "$rc" -ne 0 ] && exit "$rc"
        WT="$FAKE_WT_BASE/$task_id"
        git clone --quiet "$FAKE_ORIGIN" "$WT" >/dev/null 2>&1
        git -C "$WT" checkout --quiet -b "agent/testhost/$lane/$task_id" >/dev/null 2>&1
        git -C "$WT" config user.email "test@example.test"
        git -C "$WT" config user.name "Test"
        mkdir -p "$WT/scripts" "$WT/docs"
        : > "$WT/scripts/generate_automations_reference.py"
        # Real pre-commit hook, real git — flips on $FAKE_PY_STATE/commit_fail
        # so the "commit fails" scenario below exercises the wrapper's actual
        # `git commit` rc handling, not a git shim standing in for it.
        mkdir -p "$WT/.git/hooks"
        cat > "$WT/.git/hooks/pre-commit" <<HOOK
#!/usr/bin/env bash
if [ -f "${FAKE_PY_STATE}/commit_fail" ]; then
  echo "pre-commit: simulated style errors (unformatted file)" >&2
  exit 1
fi
exit 0
HOOK
        chmod +x "$WT/.git/hooks/pre-commit"
        if [ -n "${FAKE_BROKEN_REMOTE:-}" ]; then
          git -C "$WT" remote set-url origin "$W_DOES_NOT_EXIST"
        fi
        echo "WORKTREE_READY $WT"
        exit 0 ;;
    esac
    echo "FAKE_PY: unhandled agent_start.py invocation: $*" >&2
    exit 98 ;;
  */generate_automations_reference.py)
    genpy="$1"
    wtroot="$(cd "$(dirname "$genpy")/.." && pwd)"
    rc=0; [ -f "$FAKE_PY_STATE/gen_rc" ] && rc="$(cat "$FAKE_PY_STATE/gen_rc")"
    if [ -f "$FAKE_PY_STATE/gen_change" ]; then
      echo "# Automations (updated)" >> "$wtroot/docs/AUTOMATIONS_REFERENCE.md"
    fi
    exit "$rc" ;;
esac
echo "FAKE_PY: unhandled invocation: $*" >&2
exit 97
FAKEPY
  chmod +x "$W/bin/python3"

  # Fake npx — records cwd + args for every invocation, so the wrapper-side
  # `(cd "$WT_PATH" && npx prettier --write docs/AUTOMATIONS_REFERENCE.md)`
  # belt-and-braces call can be asserted to run FROM the worktree, on the
  # RELATIVE path (the exact defect: it used to run from the main checkout's
  # cwd against an absolute path prettier's own .gitignore silently ignored).
  cat > "$W/bin/npx" <<'FAKENPX'
#!/usr/bin/env bash
printf 'PWD=%s ARGS=%s\n' "$(pwd)" "$*" >> "$FAKE_NPX_LOG"
exit 0
FAKENPX
  chmod +x "$W/bin/npx"

  # Real bare "origin" + a real seed clone with one commit on main.
  git init --quiet --bare "$W/origin.git"
  git init --quiet "$W/seed"
  git -C "$W/seed" config user.email "test@example.test"
  git -C "$W/seed" config user.name "Test"
  git -C "$W/seed" checkout --quiet -b main
  mkdir -p "$W/seed/docs"
  echo "# Automations" > "$W/seed/docs/AUTOMATIONS_REFERENCE.md"
  git -C "$W/seed" add docs/AUTOMATIONS_REFERENCE.md
  git -C "$W/seed" commit --quiet -m "seed"
  git -C "$W/seed" remote add origin "$W/origin.git"
  git -C "$W/seed" push --quiet origin main
}

# run [env-overrides...] — invokes the wrapper with fakes prepended to PATH
# and a fresh, isolated $HOME. Captures stdout/stderr/rc.
run() {
  OUT="$(env HOME="$W/home" \
             PATH="$W/bin:$PATH" \
             FAKE_GH_LOG="$GHLOG" FAKE_GH_STATE="$W/fgh" \
             FAKE_PY_LOG="$PYLOG" FAKE_PY_STATE="$W/fpy" \
             FAKE_NPX_LOG="$NPXLOG" \
             FAKE_ORIGIN="$W/origin.git" FAKE_WT_BASE="$W/wtbase" \
             W_DOES_NOT_EXIST="$W/does-not-exist.git" \
             "$@" \
             zsh "$WRAPPER" 2>"$W/stderr")"
  RC=$?
  ERR="$(cat "$W/stderr" 2>/dev/null || true)"
}

# poverty check — both fakes must actually be the ones the wrapper resolves.
new_world
resolved_gh="$(env PATH="$W/bin:$PATH" command -v gh)"
resolved_py="$(env PATH="$W/bin:$PATH" command -v python3)"
resolved_npx="$(env PATH="$W/bin:$PATH" command -v npx)"
if [ "$resolved_gh" != "$W/bin/gh" ] || [ "$resolved_py" != "$W/bin/python3" ] || [ "$resolved_npx" != "$W/bin/npx" ]; then
  echo "HARNESS TOO POOR TO JUDGE: PATH did not resolve to the fakes (gh=$resolved_gh python3=$resolved_py npx=$resolved_npx)" >&2
  exit 2
fi

echo "kill switch — AUTOMATIONS_REFERENCE_ENABLED=false skips the run entirely:"
new_world
run AUTOMATIONS_REFERENCE_ENABLED=false
check "exit 0" "$(yesno test "$RC" -eq 0)"
check "python3 (agent_start.py) never invoked" "$(yesno eval '[ ! -s "$PYLOG" ]')"
check "gh never invoked" "$(yesno eval '[ ! -s "$GHLOG" ]')"
check "log line names the kill switch" "$(yesno eval 'grep -q "AUTOMATIONS_REFERENCE_ENABLED=false" "$W/home/logs/automations-reference-wrapper.log"')"

echo "no change — generator produces no diff, worktree released, heartbeat ok:"
new_world
run
check "exit 0" "$(yesno test "$RC" -eq 0)"
check "agent_start.py --release was called" "$(yesno eval 'grep -q -- "--release" "$PYLOG"')"
check "gh never invoked" "$(yesno eval '[ ! -s "$GHLOG" ]')"
check "heartbeat sidecar status=ok" "$(yesno eval 'grep -q "\"status\": *\"ok\"" "$W/home/.organism/last_seen/pro.automations_reference.json"')"
check "heartbeat note says no change" "$(yesno eval 'grep -q "no change" "$W/home/.organism/last_seen/pro.automations_reference.json"')"

echo "changed — commit + push + PR create + auto-merge armed, heartbeat ok:"
new_world
: > "$W/fpy/gen_change"
run
check "exit 0" "$(yesno test "$RC" -eq 0)"
check "origin gained a new ref (pushed)" "$(yesno eval 'git -C "$W/origin.git" for-each-ref --format="%(refname)" | grep -q "agent/testhost/docs/automations-"')"
check "gh pr create WAS called" "$(yesno eval 'grep -q "pr create" "$GHLOG"')"
check "gh pr merge --auto WAS called" "$(yesno eval 'grep -q -- "--auto" "$GHLOG"')"
check "heartbeat sidecar status=ok" "$(yesno eval 'grep -q "\"status\": *\"ok\"" "$W/home/.organism/last_seen/pro.automations_reference.json"')"
check "agent_start.py --release NOT called (worktree left pending merge)" "$(yesno eval '! grep -q -- "--release" "$PYLOG"')"
# GitHub's `--search` matches WORDS, not a `type(scope):` prefix — measured on
# Pro: `gh pr list --state merged --search "chore(mouth): promote
# hourly-translated in:title"` returned [] while the same query without the
# `chore(mouth): ` prefix returned 5 PRs. The supersede clause was a silent
# no-op with the prefix in it. This asserts the shipped wrapper's --search
# value carries no `(` or `:` before the trailing `in:title` qualifier.
SEARCH_ARG="$(grep 'pr list' "$GHLOG" | sed -n 's/.*--search \(.*\) --json.*/\1/p')"
check "gh pr list --search value was captured" "$(yesno test -n "$SEARCH_ARG")"
check "supersede --search is words-only (no type(scope): prefix)" \
  "$(yesno eval 'case "${SEARCH_ARG% in:title}" in *"("*|*":"*) false ;; *) true ;; esac')"

echo "generator failure, no output -> heartbeat error, worktree released, exit 1:"
new_world
echo 1 > "$W/fpy/gen_rc"
run
check "exit 1" "$(yesno test "$RC" -eq 1)"
check "gh never invoked" "$(yesno eval '[ ! -s "$GHLOG" ]')"
check "agent_start.py --release was called" "$(yesno eval 'grep -q -- "--release" "$PYLOG"')"
check "heartbeat sidecar status=error" "$(yesno eval 'grep -q "\"status\": *\"error\"" "$W/home/.organism/last_seen/pro.automations_reference.json"')"

echo "push failure -> heartbeat error naming the rc, exit 1, gh never invoked:"
new_world
: > "$W/fpy/gen_change"
run FAKE_BROKEN_REMOTE=1
check "exit 1" "$(yesno test "$RC" -eq 1)"
check "log names push failure" "$(yesno eval 'grep -q "push failed" "$W/home/logs/automations-reference-wrapper.log"')"
check "gh never invoked" "$(yesno eval '[ ! -s "$GHLOG" ]')"
check "heartbeat sidecar status=error" "$(yesno eval 'grep -q "\"status\": *\"error\"" "$W/home/.organism/last_seen/pro.automations_reference.json"')"

echo "gh pr create failure -> heartbeat error, exit 1, branch pushed but no arm:"
new_world
: > "$W/fpy/gen_change"
echo 1 > "$W/fgh/create_rc"
run
check "exit 1" "$(yesno test "$RC" -eq 1)"
check "origin still gained the pushed ref" "$(yesno eval 'git -C "$W/origin.git" for-each-ref --format="%(refname)" | grep -q "agent/testhost/docs/automations-"')"
check "gh pr merge was NEVER called (create failed first)" "$(yesno eval '! grep -q "pr merge" "$GHLOG"')"
check "heartbeat sidecar status=error" "$(yesno eval 'grep -q "\"status\": *\"error\"" "$W/home/.organism/last_seen/pro.automations_reference.json"')"

echo "auto-merge does not arm -> heartbeat degraded, exit 0 (RUN_RC still 0):"
new_world
: > "$W/fpy/gen_change"
echo 1 > "$W/fgh/merge_rc"
run
check "exit 0" "$(yesno test "$RC" -eq 0)"
check "gh pr merge WAS attempted" "$(yesno eval 'grep -q "pr merge" "$GHLOG"')"
check "heartbeat sidecar status=degraded" "$(yesno eval 'grep -q "\"status\": *\"degraded\"" "$W/home/.organism/last_seen/pro.automations_reference.json"')"

echo "commit fails (pre-commit hook) -> no push, no gh pr create, heartbeat error:"
new_world
: > "$W/fpy/gen_change"
: > "$W/fpy/commit_fail"
run
check "exit 1" "$(yesno test "$RC" -eq 1)"
check "log names commit failure" "$(yesno eval 'grep -q "commit failed" "$W/home/logs/automations-reference-wrapper.log"')"
check "origin gained NO new ref (never pushed)" "$(yesno eval '! git -C "$W/origin.git" for-each-ref --format="%(refname)" | grep -q "agent/testhost/docs/automations-"')"
check "gh never invoked" "$(yesno eval '[ ! -s "$GHLOG" ]')"
check "heartbeat sidecar status=error" "$(yesno eval 'grep -q "\"status\": *\"error\"" "$W/home/.organism/last_seen/pro.automations_reference.json"')"
check "heartbeat note mentions commit failed" "$(yesno eval 'grep -q "commit failed" "$W/home/.organism/last_seen/pro.automations_reference.json"')"

echo "prettier (wrapper-side belt-and-braces) runs FROM the worktree, on the relative path:"
new_world
: > "$W/fpy/gen_change"
run
check "exit 0" "$(yesno test "$RC" -eq 0)"
check "npx WAS invoked" "$(yesno eval '[ -s "$NPXLOG" ]')"
# Canonicalize $W before comparing — mktemp under TMPDIRs with a trailing slash
# (macOS: /var/folders/.../T/) can leave a double slash baked into the shell
# variable's string form, which a real `pwd` inside the subprocess normalises
# away; comparing the raw strings would be a harness false negative, not a
# defect in the wrapper.
WNORM="$(cd "$W" && pwd)"
check "npx ran with PWD inside the worktree (not the fake \$HOME/nuzantara placeholder)" \
  "$(yesno eval 'grep -q "PWD=$WNORM/wtbase/" "$NPXLOG"')"
check "npx was given the RELATIVE path, not an absolute one" \
  "$(yesno eval 'grep -q "ARGS=prettier --write docs/AUTOMATIONS_REFERENCE.md" "$NPXLOG"')"
check "npx was NOT given an absolute worktree path" "$(yesno eval '! grep -q "ARGS=prettier --write $WNORM/wtbase" "$NPXLOG"')"

echo
if [ "$failures" -eq 0 ]; then echo "PASS (all checks)"; exit 0; fi
echo "FAIL ($failures check(s))"; exit 1
