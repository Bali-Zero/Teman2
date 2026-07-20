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
  PRO_GIT_PULL_ALLOWLIST="${TEST_ALLOWLIST:-}" \
  PRO_GIT_PULL_NO_ALERT=1 bash "$PULLER"
  echo $?
}
head_of()     { git -C "$LOCAL" rev-parse HEAD 2>/dev/null; }
remote_head() { git -C "$LOCAL" rev-parse origin/main 2>/dev/null; }
stash_count() { git -C "$LOCAL" stash list 2>/dev/null | wc -l | tr -d ' '; }
# write a runtime-state allowlist fixture: $1=out path, $2.. = repo-relative pro paths
write_allowlist() {
  local out="$1"; shift; local sep="" p
  { printf '{"entries":['
    for p in "$@"; do printf '%s{"path":"%s","machines":["pro"]}' "$sep" "$p"; sep=","; done
    printf ']}\n'; } > "$out"
}

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

# ── D1: tracked file locally modified AND changed by incoming → backup+reset, ff succeeds ──
echo "[D1] tracked collision (local mod + incoming change) → backed up, origin wins"
setup_case D1
advance_origin "README.md" "ORIGIN README"             # origin changes the SAME tracked file
printf '%s' "LOCAL RUNTIME EDIT" > "$LOCAL/README.md"   # local in-place mod (pipeline-style)
git -C "$LOCAL" fetch -q origin main
RC=$(run_puller); eq_ne "$RC" "0" "D1 rc=0 (pulled despite tracked collision)"
eq_ne "$(head_of)" "$(remote_head)" "D1 HEAD advanced"
[ "$(cat "$LOCAL/README.md")" = "ORIGIN README" ] && ok "D1 tree has ORIGIN content" || bad "D1 wrong tree content"
BK=$(find "$SANDBOX/backup" -name 'README.md' 2>/dev/null | head -1)
[ -n "$BK" ] && [ "$(cat "$BK")" = "LOCAL RUNTIME EDIT" ] && ok "D1 local content recoverable in backup" || bad "D1 local content NOT backed up (LOSS!)"
[ "$(stash_count)" = "0" ] && ok "D1 no stash created (no shared-repo stash risk)" || bad "D1 created a stash (BAD)"
rm -rf "$SANDBOX"

# ── D2: tracked mod NOT touched by incoming → PRESERVED through ff (the core Pro guarantee) ──
echo "[D2] tracked local mod, no incoming collision → preserved (Pro syncs while dirty)"
setup_case D2
advance_origin "docs/other.md" "x"                     # origin changes a DIFFERENT file
printf '%s' "LOCAL RUNTIME STATE" > "$LOCAL/README.md"  # persistent runtime dirt, origin didn't touch
git -C "$LOCAL" fetch -q origin main
RC=$(run_puller); eq_ne "$RC" "0" "D2 rc=0 (synced despite dirty tree)"
eq_ne "$(head_of)" "$(remote_head)" "D2 HEAD advanced (did NOT skip on dirt)"
[ "$(cat "$LOCAL/README.md")" = "LOCAL RUNTIME STATE" ] && ok "D2 non-colliding runtime mod PRESERVED" || bad "D2 clobbered a non-colliding local mod"
[ ! -d "$SANDBOX/backup" ] && ok "D2 no backup (nothing collided)" || bad "D2 spurious backup"
rm -rf "$SANDBOX"

# ── D3: incoming collision on a pathspec-magic filename ('*') must NOT glob-reset others ──
echo "[D3] pathspec-magic filename → literal checkout, non-colliding file preserved (#2)"
setup_case D3
printf 'base star' > "$LOCAL/*"                                    # a tracked file literally named '*'
GIT_LITERAL_PATHSPECS=1 git -C "$LOCAL" add '*'
git -C "$LOCAL" commit -qm 'add star' && git -C "$LOCAL" push -q origin HEAD:main || fatal "D3 star base"
tmp="$(mktemp -d)"; git clone -q "$ORIGIN" "$tmp/w"; git -C "$tmp/w" config user.email t@t; git -C "$tmp/w" config user.name t
printf 'ORIGIN STAR' > "$tmp/w/*"; GIT_LITERAL_PATHSPECS=1 git -C "$tmp/w" add '*'
git -C "$tmp/w" commit -qm 'mod star' && git -C "$tmp/w" push -q origin HEAD:main || fatal "D3 star origin"; rm -rf "$tmp"
git -C "$LOCAL" fetch -q origin main
printf 'LOCAL STAR' > "$LOCAL/*"                                   # collides (local mod to incoming-changed '*')
printf 'LOCAL README MOD' > "$LOCAL/README.md"                     # non-colliding tracked mod
RC=$(run_puller); eq_ne "$RC" "0" "D3 rc=0"
eq_ne "$(head_of)" "$(remote_head)" "D3 HEAD advanced"
[ "$(cat "$LOCAL/README.md")" = "LOCAL README MOD" ] && ok "D3 non-colliding README preserved (checkout stayed literal)" || bad "D3 glob-reset clobbered README (#2 regressed!)"
[ "$(cat "$LOCAL/*")" = "ORIGIN STAR" ] && ok "D3 the '*' file got ORIGIN content" || bad "D3 '*' file wrong content"
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

# ── I1: allowlisted tracked collision → LOCAL kept (Pro-authoritative, not reset) ──
echo "[I1] allowlisted tracked collision → LOCAL kept, origin's older snapshot NOT restored"
setup_case I1
mkdir -p "$LOCAL/data"; printf '%s' '{"a":["base"]}' > "$LOCAL/data/published_articles.json"
git -C "$LOCAL" add data/published_articles.json && git -C "$LOCAL" commit -qm 'add pub' \
  && git -C "$LOCAL" push -q origin HEAD:main || fatal "I1 base pub"
advance_origin "data/published_articles.json" '{"a":["base","origin-promoted"]}'   # origin = Pro's OLDER snapshot
printf '%s' '{"a":["base","local-newer"]}' > "$LOCAL/data/published_articles.json"  # local superset (dirty)
write_allowlist "$SANDBOX/allowlist.json" "data/published_articles.json"
git -C "$LOCAL" fetch -q origin main
TEST_ALLOWLIST="$SANDBOX/allowlist.json"; RC=$(run_puller); unset TEST_ALLOWLIST
eq_ne "$RC" "0" "I1 rc=0 (synced)"
eq_ne "$(head_of)" "$(remote_head)" "I1 HEAD advanced"
[ "$(cat "$LOCAL/data/published_articles.json")" = '{"a":["base","local-newer"]}' ] \
  && ok "I1 LOCAL runtime-state kept (dedup index NOT regressed to origin)" \
  || bad "I1 allowlisted file was reset to origin (re-publish risk!)"
BK=$(find "$SANDBOX/backup" -path '*data/published_articles.json' ! -path '*.keep-local*' 2>/dev/null | head -1)
[ -n "$BK" ] && [ "$(cat "$BK")" = '{"a":["base","local-newer"]}' ] && ok "I1 local content recoverable in backup" || bad "I1 local content NOT backed up"
rm -rf "$SANDBOX"

# ── I2: allowlist present but colliding file NOT listed → origin wins (keep-local scoped) ──
echo "[I2] non-allowlisted tracked collision (allowlist present) → origin wins"
setup_case I2
advance_origin "README.md" "ORIGIN README"
printf '%s' "LOCAL EDIT" > "$LOCAL/README.md"
write_allowlist "$SANDBOX/allowlist.json" "data/published_articles.json"   # README NOT listed
git -C "$LOCAL" fetch -q origin main
TEST_ALLOWLIST="$SANDBOX/allowlist.json"; RC=$(run_puller); unset TEST_ALLOWLIST
eq_ne "$RC" "0" "I2 rc=0"
eq_ne "$(head_of)" "$(remote_head)" "I2 HEAD advanced"
[ "$(cat "$LOCAL/README.md")" = "ORIGIN README" ] && ok "I2 non-allowlisted file → ORIGIN wins (keep-local stays scoped)" || bad "I2 wrongly kept local for non-allowlisted file"
BK=$(find "$SANDBOX/backup" -name 'README.md' 2>/dev/null | head -1)
[ -n "$BK" ] && [ "$(cat "$BK")" = "LOCAL EDIT" ] && ok "I2 local recoverable in backup" || bad "I2 local not backed up"
rm -rf "$SANDBOX"

# ── I3: allowlisted file dirty but origin didn't touch it → preserved (no collision) ──
echo "[I3] allowlisted file dirty, non-colliding → preserved, no keep-local dir created"
setup_case I3
mkdir -p "$LOCAL/data"; printf '%s' 'base' > "$LOCAL/data/published_articles.json"
git -C "$LOCAL" add data/published_articles.json && git -C "$LOCAL" commit -qm 'add pub' \
  && git -C "$LOCAL" push -q origin HEAD:main || fatal "I3 base pub"
advance_origin "docs/unrelated.md" "x"                            # origin changes a DIFFERENT file
printf '%s' 'LOCAL DIRTY' > "$LOCAL/data/published_articles.json" # dirty, not in incoming diff
write_allowlist "$SANDBOX/allowlist.json" "data/published_articles.json"
git -C "$LOCAL" fetch -q origin main
TEST_ALLOWLIST="$SANDBOX/allowlist.json"; RC=$(run_puller); unset TEST_ALLOWLIST
eq_ne "$RC" "0" "I3 rc=0"
eq_ne "$(head_of)" "$(remote_head)" "I3 HEAD advanced (synced while dirty)"
[ "$(cat "$LOCAL/data/published_articles.json")" = 'LOCAL DIRTY' ] && ok "I3 non-colliding runtime-state preserved" || bad "I3 clobbered non-colliding runtime-state"
[ ! -d "$SANDBOX/backup/.keep-local" ] && ok "I3 no keep-local dir (nothing collided)" || bad "I3 spurious keep-local staging"
rm -rf "$SANDBOX"

# ── I4: allowlist EXISTS but is MALFORMED → fail-safe SKIP (never origin-win a Pro file) ──
echo "[I4] malformed allowlist + tracked collision → SKIP tick (fail-safe), file NOT reset"
setup_case I4
mkdir -p "$LOCAL/data"; printf '%s' '{"a":["base"]}' > "$LOCAL/data/published_articles.json"
git -C "$LOCAL" add data/published_articles.json && git -C "$LOCAL" commit -qm 'add pub' \
  && git -C "$LOCAL" push -q origin HEAD:main || fatal "I4 base pub"
advance_origin "data/published_articles.json" '{"a":["base","origin"]}'
printf '%s' '{"a":["base","local"]}' > "$LOCAL/data/published_articles.json"   # local dirty (collision)
printf '%s' 'NOT JSON {{{' > "$SANDBOX/allowlist.json"                          # corrupt allowlist
LOCAL_BEFORE=$(head_of)
git -C "$LOCAL" fetch -q origin main
TEST_ALLOWLIST="$SANDBOX/allowlist.json"; RC=$(run_puller); unset TEST_ALLOWLIST
eq_ne "$RC" "1" "I4 rc=1 (fail-safe skip on unreadable allowlist)"
eq_ne "$(head_of)" "$LOCAL_BEFORE" "I4 HEAD NOT advanced (skipped)"
[ "$(cat "$LOCAL/data/published_articles.json")" = '{"a":["base","local"]}' ] && ok "I4 local runtime-state NOT reset (config error stayed safe)" || bad "I4 reset the file on a config error (dangerous default!)"
rm -rf "$SANDBOX"

# ── I5: TWO allowlisted collisions in one pull → BOTH kept local (multi-file restore) ──
echo "[I5] two allowlisted collisions → both kept local (multi-file KEEP_LOCAL_FILES path)"
setup_case I5
mkdir -p "$LOCAL/data"
printf '%s' 'p-base' > "$LOCAL/data/published_articles.json"
printf '%s' 'e-base' > "$LOCAL/escalations.jsonl"
git -C "$LOCAL" add data/published_articles.json escalations.jsonl \
  && git -C "$LOCAL" commit -qm 'add two' && git -C "$LOCAL" push -q origin HEAD:main || fatal "I5 base"
tmp="$(mktemp -d)"; git clone -q "$ORIGIN" "$tmp/w"; git -C "$tmp/w" config user.email t@t; git -C "$tmp/w" config user.name t
printf '%s' 'p-origin' > "$tmp/w/data/published_articles.json"; printf '%s' 'e-origin' > "$tmp/w/escalations.jsonl"
git -C "$tmp/w" add -A && git -C "$tmp/w" commit -qm 'promote both' && git -C "$tmp/w" push -q origin HEAD:main || fatal "I5 promote"; rm -rf "$tmp"
printf '%s' 'p-local' > "$LOCAL/data/published_articles.json"   # both diverge locally (dirty)
printf '%s' 'e-local' > "$LOCAL/escalations.jsonl"
write_allowlist "$SANDBOX/allowlist.json" "data/published_articles.json" "escalations.jsonl"
git -C "$LOCAL" fetch -q origin main
TEST_ALLOWLIST="$SANDBOX/allowlist.json"; RC=$(run_puller); unset TEST_ALLOWLIST
eq_ne "$RC" "0" "I5 rc=0"
eq_ne "$(head_of)" "$(remote_head)" "I5 HEAD advanced"
[ "$(cat "$LOCAL/data/published_articles.json")" = 'p-local' ] && ok "I5 file#1 kept local" || bad "I5 file#1 reset to origin"
[ "$(cat "$LOCAL/escalations.jsonl")" = 'e-local' ] && ok "I5 file#2 kept local" || bad "I5 file#2 reset (multi-file restore missed one!)"
rm -rf "$SANDBOX"

echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
