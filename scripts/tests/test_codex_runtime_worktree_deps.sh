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
#   GUILT ×3    — an EXISTING venv-less worktree gains the link (the live case);
#                 a freshly created one gains it too (SYMMETRY — a fix that covers
#                 only the branch that bit you is half a fix, W101-recidiva); and a
#                 DANGLING link left by an older primary path is repaired, because
#                 this fleet's repo moved out of ~/Desktop on 2026-07-16.
#   INNOCENCE ×3 — a primary WITHOUT the venv must not leave a dangling symlink
#                 behind (that would satisfy the gate's existence check and then
#                 fail inside pytest, which is worse than the disease); a real
#                 directory already sitting at the link path is never clobbered;
#                 and the pre-existing refusal on a non-git, non-empty runtime
#                 path still returns 1.
#   PARITY      — CODEX_RUNTIME_LINKS must equal agent_start.py's SYMLINK_TARGETS.
#                 The source comment says "keep them in step", and a comment that
#                 states an invariant does not enforce it (W115): two tools that
#                 must agree on which untracked deps a worktree needs do not get
#                 to invent two answers.
#
# No network: a throwaway `git init` repo in tmp, `HEAD` as the base ref.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
LIB="$REPO/scripts/codex_automation_lib.sh"
BROKER="$REPO/scripts/agent_start.py"

[ -f "$LIB" ] || { echo "FATAL: lib not found at $LIB"; exit 1; }
[ -f "$BROKER" ] || { echo "FATAL: broker not found at $BROKER"; exit 1; }

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

echo "== PARITY: CODEX_RUNTIME_LINKS == agent_start.py SYMLINK_TARGETS =="
broker_list="$(python3 - "$BROKER" <<'PY'
import ast, re, sys
src = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"^SYMLINK_TARGETS[^=]*=\s*(\(.*?\n\))", src, re.S | re.M)
if not m:
    print("PARSE-FAILED")
    raise SystemExit(0)
pairs = ast.literal_eval(m.group(1))
# Both halves of each pair are the same relative path in this broker; the codex
# side takes one path per entry, so assert that shape rather than assume it.
out = []
for src_rel, dst_rel in pairs:
    if src_rel != dst_rel:
        print("SHAPE-CHANGED")
        raise SystemExit(0)
    out.append(src_rel)
print(" ".join(sorted(out)))
PY
)"
codex_list="$(printf '%s\n' $CODEX_RUNTIME_LINKS | sort | tr '\n' ' ' | sed 's/ $//')"
check "the broker's list parsed" \
    "$([ "$broker_list" = "PARSE-FAILED" ] || [ "$broker_list" = "SHAPE-CHANGED" ] && echo no || echo yes)" "yes"
check "the two dependency lists agree" "$codex_list" "$broker_list"

echo
echo "TOTAL: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
