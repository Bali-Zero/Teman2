#!/usr/bin/env bash
# Proof for codex_auto_link_runtime_deps in scripts/codex_automation_lib.sh.
#
# TRAUMA (2026-08-10). `nightly_autofix_ci` had been dead for 11 of its last 14
# nights, and its 14 Telegram alerts said only "Exit: 1" — never the cause. The
# cause: `codex_auto_ensure_runtime_worktree` creates the runtime worktree with a
# bare `git worktree add`, which copies no UNTRACKED state, so
# `~/nuzantara/.worktrees/codex-autofix-ci-runtime` has no `apps/backend-rag/.venv`
# while the main checkout does. The path-aware pre-push gate is FAIL-CLOSED: it
# logs "SKIP Python tests — worktree has no apps/backend-rag/.venv", then
# "PUSH NOT VERIFIED LOCALLY — the backend suite was REQUIRED for this diff but
# never ran", and refuses. The organ built its fix every night and could never
# ship it.
#
# The half that matters is the EARLY RETURN. Linking only on creation would have
# healed nothing: the worktree that has been failing for 11 days already exists,
# so it takes the `is-inside-work-tree` branch every single run. A cure placed on
# a path the failing case never reaches is dead code (W116).
#
#   GUILT ×15   — an EXISTING venv-less worktree gains the link (the live case);
#                 a freshly created one gains it too (SYMMETRY — a fix that covers
#                 only the branch that bit you is half a fix, W101-recidiva); a
#                 DANGLING link left by an older primary path is repaired; a stale
#                 but still-resolving link is replaced too; link-creation failure is
#                 visible; ensure propagates that failure rather than claiming the
#                 runtime is ready; a failed `git worktree add` cannot be masked by
#                 successful dependency linking; and an occupied directory nested
#                 under the primary cannot impersonate a worktree merely because
#                 `git rev-parse` walks upward to the parent repository; and an
#                 unrelated standalone Git checkout cannot impersonate a linked
#                 worktree merely because it has its own exact top-level; neither
#                 the primary itself nor a symlink to it can be adopted as the
#                 runtime; stale links are removed even after the current primary
#                 loses its venv; and a symlinked parent cannot redirect writes
#                 outside the runtime worktree.
#   INNOCENCE ×4 — a primary WITHOUT the venv must not leave a dangling symlink
#                 behind (that would satisfy the gate's existence check and then
#                 fail inside pytest, which is worse than the disease); a real
#                 directory already sitting at the link path is never clobbered;
#                 and the pre-existing refusal on a non-git, non-empty runtime
#                 path still returns 1.
#   TRUST SPLIT — the unattended runtime gets exactly the backend venv. It must
#                 never inherit `.env`, node_modules, or Husky dispatchers from
#                 the interactive broker's broader, human-controlled trust zone.
#
# No network: a throwaway `git init` repo in tmp, `HEAD` as the base ref.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
LIB="$REPO/scripts/codex_automation_lib.sh"

[ -f "$LIB" ] || { echo "FATAL: lib not found at $LIB"; exit 1; }

TMP="$(mktemp -d)"
trap '/bin/rm -rf "$TMP"' EXIT

# shellcheck disable=SC1090
source "$LIB"

PASS=0; FAIL=0
ok ()   { PASS=$((PASS + 1)); printf '  ok   %s\n' "$1"; }
bad ()  { FAIL=$((FAIL + 1)); printf '  FAIL %s\n' "$1"; }
check () { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (want=$3 got=$2)"; fi; }

# mkprimary <dir> [--with-venv]
# A real git repo with one commit, optionally carrying the untracked venv marker.
mkprimary () {
    local d="$1"; shift
    mkdir -p "$d"
    git -C "$d" init --quiet
    git -C "$d" config user.email t@t.local
    git -C "$d" config user.name t
    : > "$d/tracked.txt"
    git -C "$d" add tracked.txt
    git -C "$d" commit --quiet -m init
    if [ "${1:-}" = "--with-venv" ]; then
        mkdir -p "$d/apps/backend-rag/.venv/bin"
        # Executable on purpose: the resolves-through checks below test with -x,
        # and a `: >` file is mode 0644 — the first draft of this corpus reported
        # three reds that were its own doing (W108: a fake too poor to reach the
        # thing it claims to measure).
        printf '#!/bin/sh\nexit 0\n' > "$d/apps/backend-rag/.venv/bin/python3"
        chmod +x "$d/apps/backend-rag/.venv/bin/python3"
    fi
}

echo "== GUILT: the live case — an EXISTING venv-less worktree gains the venv =="
P="$TMP/g1/primary"; R="$TMP/g1/runtime"
mkprimary "$P" --with-venv
git -C "$P" worktree add --detach --quiet "$R" HEAD
check "precondition: the existing worktree has no venv" \
    "$([ -e "$R/apps/backend-rag/.venv" ] && echo present || echo absent)" "absent"
codex_auto_ensure_runtime_worktree "$P" "$R" HEAD
rc=$?
check "ensure returns 0 on an existing worktree" "$rc" "0"
check "the venv link now exists" \
    "$([ -L "$R/apps/backend-rag/.venv" ] && echo link || echo no)" "link"
check "and it RESOLVES (the gate's check must see a usable venv)" \
    "$([ -x "$R/apps/backend-rag/.venv/bin/python3" ] && echo usable || echo dangling)" "usable"

echo "== GUILT: symmetry — a freshly CREATED worktree gains it too =="
P="$TMP/g2/primary"; R="$TMP/g2/runtime"
mkprimary "$P" --with-venv
codex_auto_ensure_runtime_worktree "$P" "$R" HEAD
rc=$?
check "ensure returns 0 when it creates the worktree" "$rc" "0"
check "the created worktree is a real worktree" \
    "$(git -C "$R" rev-parse --is-inside-work-tree 2>/dev/null)" "true"
check "the venv link exists on the create path" \
    "$([ -x "$R/apps/backend-rag/.venv/bin/python3" ] && echo usable || echo no)" "usable"

echo "== GUILT: worktree creation failure is never masked by successful links =="
P="$TMP/g7/primary"; R="$TMP/g7/runtime"
mkprimary "$P" --with-venv
codex_auto_ensure_runtime_worktree "$P" "$R" refs/heads/does-not-exist >/dev/null 2>&1
check "ensure propagates git worktree add failure" "$?" "1"
check "a failed create does not leave a dependency-only worktree impostor" \
    "$([ -e "$R" ] || [ -L "$R" ] && echo impostor || echo absent)" "absent"

echo "== GUILT: a nested directory is not the runtime worktree =="
P="$TMP/g8/primary"; R="$P/.worktrees/codex-autofix-ci-runtime"
mkprimary "$P" --with-venv
mkdir -p "$R"
: > "$R/STRANGER"
check "precondition: Git resolves the nested directory to the primary root" \
    "$(git -C "$R" rev-parse --show-toplevel)" \
    "$(git -C "$P" rev-parse --show-toplevel)"
codex_auto_ensure_runtime_worktree "$P" "$R" HEAD >/dev/null 2>&1
check "ensure refuses an occupied nested directory that is not its own worktree" "$?" "1"
check "no dependency link was injected into the impostor" \
    "$([ -L "$R/apps/backend-rag/.venv" ] && echo injected || echo absent)" "absent"
check "the stranger file survives the refusal" \
    "$([ -f "$R/STRANGER" ] && echo kept || echo lost)" "kept"

echo "== GUILT: an unrelated Git checkout is not a linked runtime worktree =="
P="$TMP/g9/primary"; R="$TMP/g9/standalone-runtime"
mkprimary "$P" --with-venv
mkprimary "$R"
check "precondition: the standalone checkout has its own exact Git root" \
    "$(git -C "$R" rev-parse --show-toplevel)" \
    "$(cd "$R" && pwd -P)"
check "precondition: the primary has not registered the standalone checkout" \
    "$(git -C "$P" worktree list --porcelain | grep -Fqx "worktree $(cd "$R" && pwd -P)" && echo registered || echo foreign)" "foreign"
codex_auto_ensure_runtime_worktree "$P" "$R" HEAD >/dev/null 2>&1
check "ensure refuses a Git checkout outside the primary's worktree registry" "$?" "1"
check "no dependency link was injected into the foreign checkout" \
    "$([ -L "$R/apps/backend-rag/.venv" ] && echo injected || echo absent)" "absent"

echo "== GUILT: the primary checkout itself is never the runtime =="
P="$TMP/g10/primary"
mkprimary "$P" --with-venv
codex_auto_ensure_runtime_worktree "$P" "$P" HEAD >/dev/null 2>&1
check "ensure refuses runtime == primary" "$?" "1"
check "the primary venv remains a real directory" \
    "$([ -d "$P/apps/backend-rag/.venv" ] && [ ! -L "$P/apps/backend-rag/.venv" ] && echo intact || echo changed)" "intact"

echo "== GUILT: a symlink resolving to the primary is never the runtime =="
P="$TMP/g11/primary"; R="$TMP/g11/runtime-link"
mkprimary "$P" --with-venv
ln -s "$P" "$R"
codex_auto_ensure_runtime_worktree "$P" "$R" HEAD >/dev/null 2>&1
check "ensure refuses a runtime symlink that resolves to primary" "$?" "1"
check "the symlink still names the primary without injected nesting" \
    "$([ "$(readlink "$R")" = "$P" ] && [ ! -e "$P/apps/backend-rag/.venv/.venv" ] && echo intact || echo changed)" "intact"

echo "== GUILT: a DANGLING link from an older primary path is repaired =="
# The fleet's repo moved out of ~/Desktop on 2026-07-16 (W84/TCC). A link left
# pointing at the old home is worse than none: it satisfies an -e test on some
# shells' symlink semantics and then breaks inside the venv.
P="$TMP/g3/primary"; R="$TMP/g3/runtime"
mkprimary "$P" --with-venv
git -C "$P" worktree add --detach --quiet "$R" HEAD
mkdir -p "$R/apps/backend-rag"
ln -s "$TMP/g3/gone-away/apps/backend-rag/.venv" "$R/apps/backend-rag/.venv"
check "precondition: the link is dangling" \
    "$([ -L "$R/apps/backend-rag/.venv" ] && [ ! -e "$R/apps/backend-rag/.venv" ] && echo dangling || echo no)" "dangling"
codex_auto_link_runtime_deps "$P" "$R"
check "the dangling link was replaced by a resolving one" \
    "$([ -x "$R/apps/backend-rag/.venv/bin/python3" ] && echo usable || echo still-broken)" "usable"

echo "== GUILT: a resolving link to the WRONG primary is replaced =="
P="$TMP/g4/primary"; OLD="$TMP/g4/old-primary"; R="$TMP/g4/runtime"
mkprimary "$P" --with-venv
mkprimary "$OLD" --with-venv
printf 'current\n' > "$P/apps/backend-rag/.venv/ORIGIN"
printf 'old\n' > "$OLD/apps/backend-rag/.venv/ORIGIN"
git -C "$P" worktree add --detach --quiet "$R" HEAD
mkdir -p "$R/apps/backend-rag"
ln -s "$OLD/apps/backend-rag/.venv" "$R/apps/backend-rag/.venv"
check "precondition: the stale link still resolves" \
    "$(cat "$R/apps/backend-rag/.venv/ORIGIN")" "old"
codex_auto_link_runtime_deps "$P" "$R"
check "the link now names the current primary exactly" \
    "$(readlink "$R/apps/backend-rag/.venv")" "$(cd "$P" && pwd -P)/apps/backend-rag/.venv"
check "and consumers reach the current primary, not the old checkout" \
    "$(cat "$R/apps/backend-rag/.venv/ORIGIN")" "current"

echo "== GUILT: a resolving stale link is removed when current source is absent =="
P="$TMP/g12/primary"; OLD="$TMP/g12/old-primary"; R="$TMP/g12/runtime"
mkprimary "$P"
mkprimary "$OLD" --with-venv
git -C "$P" worktree add --detach --quiet "$R" HEAD
mkdir -p "$R/apps/backend-rag"
ln -s "$OLD/apps/backend-rag/.venv" "$R/apps/backend-rag/.venv"
codex_auto_link_runtime_deps "$P" "$R"
check "obsolete resolving link is removed rather than silently certified" \
    "$([ -L "$R/apps/backend-rag/.venv" ] || [ -e "$R/apps/backend-rag/.venv" ] && echo stale || echo absent)" "absent"

echo "== GUILT: a dangling stale link is removed when current source is absent =="
P="$TMP/g13/primary"; R="$TMP/g13/runtime"
mkprimary "$P"
git -C "$P" worktree add --detach --quiet "$R" HEAD
mkdir -p "$R/apps/backend-rag"
ln -s "$TMP/g13/gone/.venv" "$R/apps/backend-rag/.venv"
codex_auto_link_runtime_deps "$P" "$R"
check "obsolete dangling link is removed rather than left behind" \
    "$([ -L "$R/apps/backend-rag/.venv" ] || [ -e "$R/apps/backend-rag/.venv" ] && echo stale || echo absent)" "absent"

echo "== GUILT: a symlinked parent cannot redirect writes outside runtime =="
P="$TMP/g14/primary"; R="$TMP/g14/runtime"; OUT="$TMP/g14/outside"
mkprimary "$P" --with-venv
git -C "$P" worktree add --detach --quiet "$R" HEAD
mkdir -p "$OUT"
ln -s "$OUT" "$R/apps"
codex_auto_link_runtime_deps "$P" "$R" >/dev/null 2>&1
check "link setup rejects a symlinked parent component" "$?" "1"
check "nothing was written through the parent symlink" \
    "$([ -e "$OUT/backend-rag/.venv" ] || [ -L "$OUT/backend-rag/.venv" ] && echo escaped || echo clean)" "clean"

echo "== GUILT: an uncreatable runtime link fails closed =="
P="$TMP/g5/primary"; R="$TMP/g5/runtime"
mkprimary "$P" --with-venv
git -C "$P" worktree add --detach --quiet "$R" HEAD
: > "$R/apps"
codex_auto_link_runtime_deps "$P" "$R" >/dev/null 2>&1
check "link setup reports failure instead of claiming the runtime is ready" "$?" "1"

echo "== GUILT: ensure propagates dependency-link failure =="
P="$TMP/g6/primary"; R="$TMP/g6/runtime"
mkprimary "$P" --with-venv
git -C "$P" worktree add --detach --quiet "$R" HEAD
: > "$R/apps"
codex_auto_ensure_runtime_worktree "$P" "$R" HEAD >/dev/null 2>&1
check "ensure refuses an existing worktree whose dependencies cannot be linked" "$?" "1"

echo "== INNOCENCE: a primary WITHOUT the venv leaves NO dangling link =="
P="$TMP/i1/primary"; R="$TMP/i1/runtime"
mkprimary "$P"                      # deliberately no venv
git -C "$P" worktree add --detach --quiet "$R" HEAD
codex_auto_link_runtime_deps "$P" "$R"
check "no link was invented where there is nothing to lend" \
    "$([ -e "$R/apps/backend-rag/.venv" ] || [ -L "$R/apps/backend-rag/.venv" ] && echo created || echo absent)" "absent"

echo "== INNOCENCE: a REAL directory at the link path is never clobbered =="
P="$TMP/i2/primary"; R="$TMP/i2/runtime"
mkprimary "$P" --with-venv
git -C "$P" worktree add --detach --quiet "$R" HEAD
mkdir -p "$R/apps/backend-rag/.venv/bin"
: > "$R/apps/backend-rag/.venv/OWN_MARKER"
codex_auto_link_runtime_deps "$P" "$R"
check "the worktree's own venv is still a directory, not a link" \
    "$([ -L "$R/apps/backend-rag/.venv" ] && echo replaced || echo intact)" "intact"
check "and its contents survived" \
    "$([ -f "$R/apps/backend-rag/.venv/OWN_MARKER" ] && echo kept || echo lost)" "kept"
# Measured, not reasoned: with the already-present guard removed, `ln -s` against
# an existing DIRECTORY exits 0 and drops a self-referencing `.venv/.venv` inside
# it — so "still a directory" alone cannot see the damage. The first version of
# this corpus missed exactly that mutant.
check "no stray nested link was dropped inside it" \
    "$([ -e "$R/apps/backend-rag/.venv/.venv" ] && echo polluted || echo clean)" "clean"

echo "== INNOCENCE: idempotent — a second pass must not pollute the PRIMARY =="
# Worse than the nested link above: when the runtime path is ALREADY a correct
# symlink to a directory, an unguarded `ln -s` follows it and writes the stray
# INTO the primary checkout's real venv. This organ runs nightly, so "harmless
# on a repeat run" is the property that matters.
P="$TMP/i4/primary"; R="$TMP/i4/runtime"
mkprimary "$P" --with-venv
git -C "$P" worktree add --detach --quiet "$R" HEAD
codex_auto_link_runtime_deps "$P" "$R"
codex_auto_link_runtime_deps "$P" "$R"
check "the runtime link is still a single resolving link" \
    "$([ -x "$R/apps/backend-rag/.venv/bin/python3" ] && echo usable || echo broken)" "usable"
check "the primary's venv gained nothing" \
    "$([ -e "$P/apps/backend-rag/.venv/.venv" ] && echo polluted || echo clean)" "clean"

echo "== INNOCENCE: the pre-existing refusal on a non-git, non-empty path holds =="
P="$TMP/i3/primary"; R="$TMP/i3/runtime"
mkprimary "$P" --with-venv
mkdir -p "$R"; : > "$R/some-stranger-file"
codex_auto_ensure_runtime_worktree "$P" "$R" HEAD 2>/dev/null
check "ensure still refuses to adopt an occupied non-worktree path" "$?" "1"

echo "== TRUST SPLIT: unattended runtime receives only the backend venv =="
check "the dependency allowlist is exact and non-overridable" \
    "$CODEX_RUNTIME_LINKS" "apps/backend-rag/.venv"
P="$TMP/i5/primary"; R="$TMP/i5/runtime"
mkprimary "$P" --with-venv
mkdir -p "$P/node_modules" "$P/apps/mouth/node_modules" "$P/.husky/_"
: > "$P/apps/backend-rag/.env"
git -C "$P" worktree add --detach --quiet "$R" HEAD
codex_auto_link_runtime_deps "$P" "$R"
for forbidden in apps/backend-rag/.env node_modules apps/mouth/node_modules .husky/_; do
    check "unattended runtime does not inherit $forbidden" \
        "$([ -e "$R/$forbidden" ] || [ -L "$R/$forbidden" ] && echo inherited || echo absent)" "absent"
done

echo
echo "TOTAL: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
