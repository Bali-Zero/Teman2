#!/usr/bin/env bash
# test_lane_ship.sh — proof for scripts/lane_ship.sh (deterministic lane
# ship tail: push -> reuse-or-create PR -> arm -> GraphQL verify).
#
# GIT IS REAL, GH IS FAKED. lane_ship.sh's git calls (status/push/rev-parse)
# are exercised against a REAL local git repo with a REAL local bare "origin"
# (no network — a bare repo on the same filesystem is a legitimate git
# remote) rather than mocked, because reimplementing git's own semantics in
# a shell fake risks testing the fake's idea of git instead of git's actual
# behaviour (the exact failure mode this repo's "poverty check" convention
# — see test_mq_sh.sh — exists to catch). `gh` talks to GitHub's real API
# and MUST be faked for an offline, deterministic test; its fake answers
# from per-scenario fixture files and logs every invocation for assertions,
# same pattern as test_mq_sh.sh.
#
# WHAT IT PINS
#   guilt     — dirty worktree refused (files listed, exit 1, gh never
#               invoked); push failure surfaces the captured rc + last 40
#               lines of log, exit 2; GraphQL saying neither armed nor
#               queued -> LANE_SHIP_FAIL, exit 3.
#   innocence — an existing PR for the branch is REUSED (no `gh pr create`
#               call); a new PR is created, armed, and verified ->
#               LANE_SHIP_OK on stdout; `--no-arm` never calls `gh pr merge`.
#
# No network, no real gh, no real GitHub — fully offline.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
LANE_SHIP="$REPO_ROOT/lane_ship.sh"
[ -f "$LANE_SHIP" ] || { echo "FAIL: lane_ship.sh not found at $LANE_SHIP"; exit 2; }
[ -x "$LANE_SHIP" ] || { echo "FAIL: lane_ship.sh not executable at $LANE_SHIP"; exit 2; }

failures=0
check() {  # check <name> <0-or-1>
  if [ "$2" = "1" ]; then printf '  ok   %s\n' "$1"
  else printf '  FAIL %s\n' "$1"; failures=$((failures + 1)); fi
}
has() { case "$2" in *"$1"*) return 0 ;; *) return 1 ;; esac; }
yesno() { if "$@"; then echo 1; else echo 0; fi; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/lane_ship_test.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT

# One scenario = one fresh world: real bare "origin", a real clone/worktree
# checked out from it, its own fake-gh state dir + log. Nothing here touches
# the real $HOME, the real nuzantara repo, or the real GitHub.
new_world() {
  W="$(mktemp -d "$SANDBOX/w.XXXXXX")"
  mkdir -p "$W/bin" "$W/fgh"
  LOG="$W/log"
  : > "$LOG"

  cat > "$W/bin/gh" <<'FAKEGH'
#!/usr/bin/env bash
# Fake gh — logs every invocation to $FAKE_GH_LOG, answers from
# $FAKE_GH_STATE. An invocation shape this fake does not recognise is a
# HARNESS bug (exit 99), never a silent empty answer (W108).
set -uo pipefail
printf '%s\n' "$*" >> "$FAKE_GH_LOG"

case "${1:-}" in
  pr)
    case "${2:-}" in
      view)
        rc=0
        [ -f "$FAKE_GH_STATE/view_rc" ] && rc="$(cat "$FAKE_GH_STATE/view_rc")"
        if [ -f "$FAKE_GH_STATE/view_json" ]; then cat "$FAKE_GH_STATE/view_json"; else echo 'no pull requests found' >&2; fi
        exit "$rc"
        ;;
      create)
        rc=0
        [ -f "$FAKE_GH_STATE/create_rc" ] && rc="$(cat "$FAKE_GH_STATE/create_rc")"
        if [ -f "$FAKE_GH_STATE/create_out" ]; then cat "$FAKE_GH_STATE/create_out"; else echo 'https://github.com/test-owner/test-repo/pull/99'; fi
        # capture the body-file content for assertions
        prev=""
        for a in "$@"; do
          if [ "$prev" = "--body-file" ]; then cp "$a" "$FAKE_GH_STATE/create_body_seen" 2>/dev/null || true; fi
          prev="$a"
        done
        exit "$rc"
        ;;
      merge)
        rc=0
        [ -f "$FAKE_GH_STATE/arm_rc" ] && rc="$(cat "$FAKE_GH_STATE/arm_rc")"
        if [ -f "$FAKE_GH_STATE/arm_out" ]; then cat "$FAKE_GH_STATE/arm_out"; else echo 'Auto-merge enabled for pull request'; fi
        exit "$rc"
        ;;
    esac
    ;;
  api)
    case "${2:-}" in
      graphql)
        rc=0
        [ -f "$FAKE_GH_STATE/graphql_rc" ] && rc="$(cat "$FAKE_GH_STATE/graphql_rc")"
        if [ -f "$FAKE_GH_STATE/graphql_json" ]; then cat "$FAKE_GH_STATE/graphql_json"; else echo '{}'; fi
        exit "$rc"
        ;;
    esac
    ;;
esac
echo "FAKE_GH: unhandled invocation: $*" >&2
exit 99
FAKEGH
  chmod +x "$W/bin/gh"

  # Real bare "origin" — a local filesystem remote, no network involved.
  git init --quiet --bare "$W/origin.git"

  # Real seed clone: one commit on main, so `origin/main` exists for the
  # worktree's branch to diverge from.
  git init --quiet "$W/seed"
  git -C "$W/seed" config user.email "test@example.test"
  git -C "$W/seed" config user.name "Test"
  git -C "$W/seed" checkout --quiet -b main
  echo "seed" > "$W/seed/README.md"
  git -C "$W/seed" add README.md
  git -C "$W/seed" commit --quiet -m "seed"
  git -C "$W/seed" remote add origin "$W/origin.git"
  git -C "$W/seed" push --quiet origin main

  # Real worktree, real feature branch, one real commit — this is what
  # lane_ship.sh is handed as $1.
  WT="$W/wt"
  git -C "$W/seed" worktree add --quiet -b "feat/lane-ship-test" "$WT" main
  git -C "$WT" config user.email "test@example.test"
  git -C "$WT" config user.name "Test"
}

# run <worktree> <title> [extra args...] — invokes lane_ship.sh via `env`
# with the fake gh prepended to PATH. Captures stdout in $OUT, stderr in
# $ERR, exit code in $RC.
run() {
  local wt="$1" title="$2"
  shift 2
  OUT="$(env LANE_SHIP_REPO="test-owner/test-repo" \
             FAKE_GH_LOG="$LOG" FAKE_GH_STATE="$W/fgh" \
             PATH="$W/bin:$PATH" \
             bash "$LANE_SHIP" "$wt" "$title" "$@" 2>"$W/stderr")"
  RC=$?
  ERR="$(cat "$W/stderr" 2>/dev/null || true)"
}

# poverty check — the fake must actually be the one gh resolves to.
new_world
resolved="$(PATH="$W/bin:$PATH" command -v gh)"
if [ "$resolved" != "$W/bin/gh" ]; then
  echo "HARNESS TOO POOR TO JUDGE: PATH did not resolve gh to the fake ($resolved)" >&2
  exit 2
fi

echo "guilt — refuses the main checkout (the seed repo itself, not a worktree):"
new_world
run "$W/seed" "should not ship"
check "exit non-zero" "$(yesno test "$RC" -ne 0)"
check "reason names it the main checkout" "$(yesno has "main checkout" "$ERR")"
check "gh was never invoked" "$(yesno eval '[ ! -s "$LOG" ]')"

echo "guilt — refuses a dirty worktree and lists the dirty files:"
new_world
echo "uncommitted" > "$WT/dirty.txt"
run "$WT" "should not ship"
check "exit non-zero" "$(yesno test "$RC" -ne 0)"
check "LANE_SHIP_FAIL printed" "$(yesno has "LANE_SHIP_FAIL" "$ERR")"
check "dirty file is named" "$(yesno has "dirty.txt" "$ERR")"
check "gh was never invoked" "$(yesno eval '[ ! -s "$LOG" ]')"

echo "guilt — push failure surfaces the captured rc + log tail, exit 2:"
new_world
git -C "$WT" remote set-url origin "$W/does-not-exist.git"
run "$WT" "should not ship"
check "exit 2" "$(yesno test "$RC" -eq 2)"
check "LANE_SHIP_FAIL printed" "$(yesno has "LANE_SHIP_FAIL" "$ERR")"
check "reason names git push" "$(yesno has "git push failed" "$ERR")"
check "gh was never invoked (push failed before step 3)" "$(yesno eval '[ ! -s "$LOG" ]')"

echo "innocence — existing PR for the branch is REUSED, never re-created:"
new_world
printf '{"number":42,"url":"https://github.com/test-owner/test-repo/pull/42"}\n' > "$W/fgh/view_json"
printf '{"data":{"repository":{"pullRequest":{"autoMergeRequest":{"enabledAt":"2026-08-21T00:00:00Z"},"isInMergeQueue":false,"headRefOid":"deadbeef","url":"https://github.com/test-owner/test-repo/pull/42"}}}}\n' > "$W/fgh/graphql_json"
run "$WT" "reuse me"
check "exit 0" "$(yesno test "$RC" -eq 0)"
check "LANE_SHIP_OK printed with pr=42" "$(yesno has "LANE_SHIP_OK pr=42" "$OUT")"
check "armed=yes" "$(yesno has "armed=yes" "$OUT")"
check "gh pr create was NEVER called" "$(yesno eval '! grep -q "pr create" "$LOG"')"
check "gh pr view WAS called" "$(yesno eval 'grep -q "pr view" "$LOG"')"
check "gh pr merge --auto WAS called (arm still runs on a reused PR)" "$(yesno eval 'grep -q -- "--auto" "$LOG"')"

echo "innocence — new PR created + armed -> LANE_SHIP_OK, body carries the Adversarial review section:"
new_world
printf '{"data":{"repository":{"pullRequest":{"autoMergeRequest":{},"isInMergeQueue":true,"headRefOid":"cafef00d","url":"https://github.com/test-owner/test-repo/pull/99"}}}}\n' > "$W/fgh/graphql_json"
run "$WT" "brand new PR"
check "exit 0" "$(yesno test "$RC" -eq 0)"
check "LANE_SHIP_OK printed with pr=99" "$(yesno has "LANE_SHIP_OK pr=99" "$OUT")"
check "armed=queued (isInMergeQueue path, W118)" "$(yesno has "armed=queued" "$OUT")"
check "gh pr create WAS called" "$(yesno eval 'grep -q "pr create" "$LOG"')"
check "created PR's body carries the Adversarial review section (auto-appended)" \
  "$(yesno eval 'grep -q "## Adversarial review" "$W/fgh/create_body_seen"')"

echo "innocence — a body-file that already carries the section is NOT rewritten twice:"
new_world
printf '{"data":{"repository":{"pullRequest":{"autoMergeRequest":{"enabledAt":"x"},"isInMergeQueue":false,"headRefOid":"abc123","url":"u"}}}}\n' > "$W/fgh/graphql_json"
BODY_F="$W/body.md"
printf 'Why/What here.\n\n## Adversarial review\nseat X reviewed it.\n' > "$BODY_F"
run "$WT" "with body file" --body-file "$BODY_F"
check "exit 0" "$(yesno test "$RC" -eq 0)"
check "seat's own review text preserved verbatim" "$(yesno eval 'grep -q "seat X reviewed it" "$W/fgh/create_body_seen"')"
check "no duplicated Adversarial review heading" \
  "$(yesno test "$(grep -c '## Adversarial review' "$W/fgh/create_body_seen")" -eq 1)"

echo "--no-arm skips step 4 (gh pr merge is never invoked) and step 5 (no GraphQL call):"
new_world
run "$WT" "no arm please" --no-arm
check "exit 0" "$(yesno test "$RC" -eq 0)"
check "LANE_SHIP_OK armed=skipped" "$(yesno has "armed=skipped" "$OUT")"
check "gh pr merge was NEVER called" "$(yesno eval '! grep -q "pr merge" "$LOG"')"
check "gh api graphql was NEVER called" "$(yesno eval '! grep -q "graphql" "$LOG"')"

echo "guilt — GraphQL says neither armed nor queued -> LANE_SHIP_FAIL, exit 3:"
new_world
printf '{"data":{"repository":{"pullRequest":{"autoMergeRequest":{},"isInMergeQueue":false,"headRefOid":"abc","url":"u"}}}}\n' > "$W/fgh/graphql_json"
run "$WT" "will not verify armed"
check "exit 3" "$(yesno test "$RC" -eq 3)"
check "LANE_SHIP_FAIL printed" "$(yesno has "LANE_SHIP_FAIL" "$ERR")"
check "reason names both checked fields" "$(yesno has "enabledAt" "$ERR")"

echo
if [ "$failures" -eq 0 ]; then echo "PASS (all checks)"; exit 0; fi
echo "FAIL ($failures check(s))"; exit 1
