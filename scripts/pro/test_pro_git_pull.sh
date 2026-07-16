#!/bin/bash
# Adversarial test for scripts/pro/pro-git-pull.sh — the collision-robust main puller.
#
# Builds a throwaway origin+local git pair under a tmp dir and drives the script
# through every branch that matters, asserting on real repo state (HEAD OID, file
# content, backup dir, stash list) — never on the script's own log claims (scar #2:
# probe the work, not the proxy). Hermetic: PRO_GIT_PULL_NO_ALERT=1, per-case tmp
# dirs, own lock/log/backup paths, zero network (origin is a local bare repo).
#
# Anti-vacuity (Codex red-team 2026-07-16): every fixture step is guarded (a failed
# clone/commit aborts the run, so empty==empty can't masquerade as PASS), and every
# HEAD comparison requires the value to be NON-EMPTY.
#
# Run:  bash scripts/pro/test_pro_git_pull.sh   (exit 0 = all pass)

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PULLER="$SCRIPT_DIR/pro-git-pull.sh"
[ -f "$PULLER" ] || { echo "FATAL: $PULLER not found"; exit 1; }

PASS=0; FAIL=0
ok()  { echo "  PASS: $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
fatal() { echo "  FATAL fixture: $1"; exit 3; }
# actual==expected AND actual non-empty (kills the empty==empty vacuous pass)
eq_ne() { if [ -n "$1" ] && [ "$1" = "$2" ]; then ok "$3"; else bad "$3 (got '$1' want '$2')"; fi; }
ne_ne() { if [ -n "$1" ] && [ "$1" != "$2" ]; then ok "$3"; else bad "$3 (both '$1')"; fi; }

setup_case() {
  SANDBOX="$(mktemp -d "/tmp/pgp-test-$1-XXXXXX")" || fatal "mktemp $1"
  ORIGIN="$SANDBOX/origin.git"; LOCAL="$SANDBOX/local"
  git init -q --bare "$ORIGIN" || fatal "init bare $1"
  git -C "$ORIGIN" symbolic-ref HEAD refs/heads/main || fatal "symref $1"
  git clone -q "$ORIGIN" "$LOCAL" 2>/dev/null
  [ -f "$LOCAL/.git/HEAD" ] || fatal "clone $1"
  git -C "$LOCAL" config user.email t@t; git -C "$LOCAL" config user.name t
  echo "base" > "$LOCAL/README.md"
  git -C "$LOCAL" add README.md && git -C "$LOCAL" commit -qm base || fatal "base commit $1"
  git -C "$LOCAL" push -q origin HEAD:main || fatal "base push $1"
  git -C "$LOCAL" rev-parse HEAD >/dev/null 2>&1 || fatal "no base HEAD $1"
  git -C "$LOCAL" branch --set-upstream-to=origin/main main >/dev/null 2>&1 || true
}

# advance origin by committing tracked file $1=path $2=content; $3="force" to add an ignored path
advance_origin() {
  local tmp; tmp="$(mktemp -d)" || fatal "mktemp adv"
  git clone -q "$ORIGIN" "$tmp/w" 2>/dev/null
  [ -f "$tmp/w/.git/HEAD" ] || fatal "adv clone"
  git -C "$tmp/w" config user.email t@t; git -C "$tmp/w" config user.name t
  mkdir -p "$tmp/w/$(dirname "$1")"; printf '%s' "$2" > "$tmp/w/$1"
  if [ "${3:-}" = "force" ]; then git -C "$tmp/w" add -f "$1"; else git -C "$tmp/w" add "$1"; fi
  git -C "$tmp/w" commit -qm "add $1" || fatal "adv commit $1"
  git -C "$tmp/w" push -q origin HEAD:main || fatal "adv push $1 (origin didn't advance!)"
  rm -rf "$tmp"
}

run_puller() {
  PRO_GIT_PULL_REPO="$LOCAL" PRO_GIT_PULL_LOG="$SANDBOX/pull.log" \
  PRO_GIT_PULL_LOCK="$SANDBOX/pull.lock.d" PRO_GIT_PULL_BACKUP_ROOT="$SANDBOX/backup" \
  PRO_GIT_PULL_NO_ALERT=1 bash "$PULLER"
  echo $?
}
head_of()     { git -C "$LOCAL" rev-parse HEAD 2>/dev/null; }
remote_head() { git -C "$LOCAL" rev-parse origin/main 2>/dev/null; }
stash_count() { git -C "$LOCAL" stash list 2>/dev/null | wc -l | tr -d ' '; }

echo "=== pro-git-pull adversarial suite ==="

# ── A: clean behind → ff, no backup ──
echo "[A] clean behind → ff, no backup"
setup_case A; advance_origin "docs/new.md" "hello"; git -C "$LOCAL" fetch -q origin main
RC=$(run_puller); eq_ne "$RC" "0" "A rc=0"
eq_ne "$(head_of)" "$(remote_head)" "A HEAD advanced to origin/main"
[ -f "$LOCAL/docs/new.md" ] && ok "A incoming file present" || bad "A incoming file missing"
[ ! -d "$SANDBOX/backup" ] && ok "A no backup dir" || bad "A spurious backup"
rm -rf "$SANDBOX"

# ── B: untracked (non-ignored) collision → moved to backup, ff succeeds ──
echo "[B] untracked collision → moved to backup"
setup_case B; advance_origin "research/regulatory/d.json" '{"from":"origin"}'
mkdir -p "$LOCAL/research/regulatory"; printf '%s' '{"from":"local"}' > "$LOCAL/research/regulatory/d.json"
git -C "$LOCAL" fetch -q origin main
RC=$(run_puller); eq_ne "$RC" "0" "B rc=0 (pulled despite collision)"
eq_ne "$(head_of)" "$(remote_head)" "B HEAD advanced"
[ "$(cat "$LOCAL/research/regulatory/d.json")" = '{"from":"origin"}' ] && ok "B tree has ORIGIN content" || bad "B wrong tree content"
BK=$(find "$SANDBOX/backup" -name 'd.json' 2>/dev/null | head -1)
[ -n "$BK" ] && [ "$(cat "$BK")" = '{"from":"local"}' ] && ok "B local content recoverable in backup" || bad "B local content NOT backed up (LOSS!)"
rm -rf "$SANDBOX"

# ── H: IGNORED untracked collision → moved to backup (CRIT#1 regression guard) ──
echo "[H] IGNORED-file collision → moved to backup (not silently clobbered)"
setup_case H
printf 'runtime/\n' > "$LOCAL/.gitignore"
git -C "$LOCAL" add .gitignore && git -C "$LOCAL" commit -qm gitignore || fatal "H gitignore commit"
git -C "$LOCAL" push -q origin HEAD:main || fatal "H gitignore push"
advance_origin "runtime/x.json" "ORIGIN" force
git -C "$LOCAL" fetch -q origin main
mkdir -p "$LOCAL/runtime"; printf '%s' "LOCAL-ONLY" > "$LOCAL/runtime/x.json"   # ignored + untracked
RC=$(run_puller); eq_ne "$RC" "0" "H rc=0"
eq_ne "$(head_of)" "$(remote_head)" "H HEAD advanced"
[ "$(cat "$LOCAL/runtime/x.json")" = "ORIGIN" ] && ok "H tree has ORIGIN content" || bad "H wrong tree content"
BK=$(find "$SANDBOX/backup" -name 'x.json' 2>/dev/null | head -1)
[ -n "$BK" ] && [ "$(cat "$BK")" = "LOCAL-ONLY" ] && ok "H ignored local content recoverable (no silent clobber)" || bad "H IGNORED content LOST (CRIT#1 regressed!)"
rm -rf "$SANDBOX"

# ── C: untracked NON-colliding → untouched ──
echo "[C] untracked non-colliding → untouched"
setup_case C; advance_origin "docs/other.md" "x"
mkdir -p "$LOCAL/scratch"; printf '%s' "my wip" > "$LOCAL/scratch/notes.txt"
git -C "$LOCAL" fetch -q origin main
RC=$(run_puller); eq_ne "$RC" "0" "C rc=0"
eq_ne "$(head_of)" "$(remote_head)" "C HEAD advanced"
[ "$(cat "$LOCAL/scratch/notes.txt" 2>/dev/null)" = "my wip" ] && ok "C sibling untracked WIP untouched" || bad "C sibling WIP disturbed"
[ ! -d "$SANDBOX/backup" ] && ok "C no backup" || bad "C spurious backup"
rm -rf "$SANDBOX"

# ── D: tracked-modified → SKIP (Option B: never stash sibling WIP) ──
echo "[D] tracked-modified → SKIP, no stash, no advance"
setup_case D; advance_origin "docs/d.md" "x"
printf '%s' "LOCAL EDIT" > "$LOCAL/README.md"    # dirty a TRACKED file
git -C "$LOCAL" fetch -q origin main
LOCAL_BEFORE=$(head_of); RC=$(run_puller)
eq_ne "$RC" "0" "D rc=0 (deliberate skip)"
eq_ne "$(head_of)" "$LOCAL_BEFORE" "D HEAD NOT advanced (skipped)"
ne_ne "$(head_of)" "$(remote_head)" "D still behind origin (correctly not pulled)"
[ "$(cat "$LOCAL/README.md")" = "LOCAL EDIT" ] && ok "D tracked edit untouched" || bad "D tracked edit disturbed"
[ "$(stash_count)" = "0" ] && ok "D no stash created (Law 5)" || bad "D created a stash (BAD)"
rm -rf "$SANDBOX"

# ── E: up to date → no-op ──
echo "[E] up-to-date → no-op"
setup_case E; git -C "$LOCAL" fetch -q origin main
H_BEFORE=$(head_of); RC=$(run_puller)
eq_ne "$RC" "0" "E rc=0"
eq_ne "$(head_of)" "$H_BEFORE" "E HEAD unchanged"
rm -rf "$SANDBOX"

# ── F: diverged → skip rc=1, no touch ──
echo "[F] diverged → skip rc=1, no data touched"
setup_case F; advance_origin "docs/f.md" "o"
printf '%s' "local only" > "$LOCAL/localfile.md"
git -C "$LOCAL" add localfile.md && git -C "$LOCAL" commit -qm "local divergent" || fatal "F local commit"
LOCAL_BEFORE=$(head_of); git -C "$LOCAL" fetch -q origin main
RC=$(run_puller); eq_ne "$RC" "1" "F rc=1 (skipped diverged)"
eq_ne "$(head_of)" "$LOCAL_BEFORE" "F HEAD untouched"
[ -f "$LOCAL/localfile.md" ] && ok "F local commit intact" || bad "F local data lost"
rm -rf "$SANDBOX"

# ── G: local ahead → skip rc=0, no touch ──
echo "[G] local ahead → skip rc=0"
setup_case G; printf '%s' "ahead" > "$LOCAL/ahead.md"
git -C "$LOCAL" add ahead.md && git -C "$LOCAL" commit -qm unpushed || fatal "G commit"
AHEAD=$(head_of); git -C "$LOCAL" fetch -q origin main
RC=$(run_puller); eq_ne "$RC" "0" "G rc=0"
eq_ne "$(head_of)" "$AHEAD" "G HEAD untouched (ahead preserved)"
rm -rf "$SANDBOX"

echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
