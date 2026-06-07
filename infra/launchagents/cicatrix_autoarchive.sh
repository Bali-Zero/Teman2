#!/usr/bin/env bash
# cicatrix_autoarchive.sh — daily safety net for the cicatrix-scars.md 40k limit.
#
# WHY: /scar APPENDS to .claude/rules/cicatrix-scars.md but nothing PRUNES.
# The pre-commit hook auto-archives only when someone commits THAT file; this
# cron catches the case where /scar appends and no commit touches it for days,
# so the harness keeps warning "... over the 40.0k-char limit" every session.
#
# SAFETY (sibling-race aware, per cicatrix W59/W62/untracked-lost family):
#   - Operates on the authoritative checkout ($REPO_ROOT, default ~/Desktop/nuzantara).
#   - Runs the archiver in-place (it only rewrites the two scar md files).
#   - Commits ONLY if: branch == $EXPECT_BRANCH AND the ONLY dirty paths are the
#     two scar files. Any other dirty/staged content → archive stays on disk,
#     NO commit, log a WARN (operator picks it up). Never `git add -A`.
#   - Never pushes. A human/automation pushes on the next normal commit.
#
# Kill switch: CICATRIX_ARCHIVE_ENFORCEMENT=false
# Env knobs: REPO_ROOT, EXPECT_BRANCH (default the repo's current branch).
set -uo pipefail

if [ "${CICATRIX_ARCHIVE_ENFORCEMENT:-true}" = "false" ]; then
    echo "[cicatrix-cron] disabled via CICATRIX_ARCHIVE_ENFORCEMENT=false"
    exit 0
fi

REPO_ROOT="${REPO_ROOT:-$HOME/Desktop/nuzantara}"
ACTIVE=".claude/rules/cicatrix-scars.md"
ARCHIVE=".claude/rules/cicatrix-scars-archive.md"
LIMIT="${CICATRIX_SIZE_LIMIT_CHARS:-40000}"

cd "$REPO_ROOT" || { echo "[cicatrix-cron] FATAL: cannot cd $REPO_ROOT"; exit 1; }

if [ ! -f "$ACTIVE" ]; then
    echo "[cicatrix-cron] $ACTIVE not found in $REPO_ROOT — skipping."
    exit 0
fi

SIZE=$(LC_ALL=C wc -c < "$ACTIVE" | tr -d '[:space:]')
if [ "$SIZE" -le "$LIMIT" ]; then
    echo "[cicatrix-cron] OK: $SIZE chars (<= $LIMIT). No archiving needed."
    exit 0
fi

echo "[cicatrix-cron] $SIZE chars (> $LIMIT) — archiving..."
if ! python3 scripts/archive_cicatrix_scars.py; then
    echo "[cicatrix-cron] WARN: archiver could not bring file under limit (see output)."
    # Fall through: still try to commit what it managed to move, if safe.
fi

# Decide whether it's safe to auto-commit.
EXPECT_BRANCH="${EXPECT_BRANCH:-$(git symbolic-ref --short HEAD 2>/dev/null || echo DETACHED)}"
CUR_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo DETACHED)

# Porcelain of everything dirty/staged, path-only (handles renames defensively).
DIRTY=$(git status --porcelain | sed 's/^...//' | sed 's/.* -> //' | sort -u)
# Strip the two scar files; whatever remains is "other" work we must not touch.
OTHER=$(printf '%s\n' "$DIRTY" | grep -vxF "$ACTIVE" | grep -vxF "$ARCHIVE" | grep -v '^$' || true)

if [ "$CUR_BRANCH" != "$EXPECT_BRANCH" ]; then
    echo "[cicatrix-cron] WARN: on branch '$CUR_BRANCH' != expected '$EXPECT_BRANCH'."
    echo "                Archived files left on disk, NOT committed (sibling-race safety)."
    exit 0
fi
if [ -n "$OTHER" ]; then
    echo "[cicatrix-cron] WARN: other uncommitted changes present — NOT committing:"
    printf '%s\n' "$OTHER" | sed 's/^/                  /'
    echo "                Archived scar files left staged-able on disk for operator."
    exit 0
fi

# Safe: only the scar files changed, on the expected branch. Commit them.
if git diff --quiet -- "$ACTIVE" "$ARCHIVE" && git diff --cached --quiet -- "$ACTIVE" "$ARCHIVE"; then
    echo "[cicatrix-cron] nothing changed after archive run (already under limit?). Done."
    exit 0
fi

git add "$ACTIVE" "$ARCHIVE"
NEW_SIZE=$(LC_ALL=C wc -c < "$ACTIVE" | tr -d '[:space:]')
BRANCH_EXPECTED="$EXPECT_BRANCH" git commit -q -m "chore(cicatrix): daily auto-archive old scars (${SIZE}->${NEW_SIZE} chars, under ${LIMIT})

Automated by infra/launchagents/cicatrix_autoarchive.sh (daily LaunchAgent).
Moved old RESOLVED/INFO + STRUCTURAL>=15d scars to cicatrix-scars-archive.md.
P0/P1 SECURITY + recent scars untouched." \
    && echo "[cicatrix-cron] committed $(git rev-parse --short HEAD) on $EXPECT_BRANCH (${NEW_SIZE} chars)." \
    || echo "[cicatrix-cron] WARN: commit failed (hook block?). Files archived on disk."
