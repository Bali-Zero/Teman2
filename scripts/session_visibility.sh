#!/bin/bash
# session_visibility.sh — X1/F7 visibility lines (2026-08-27 hook-visibility lane).
#
# Prints two lines: live worktree count for the current repo, and the
# largest transcript MB under the current Claude Code project dir. Standalone
# by design — infra/home-fork/declared-pairs.json has NO entry for
# ~/.claude/scripts/tmux-briefing.sh (checked 2026-08-27, grep came back
# empty), so there is no repo twin to extend. Splice it into tmux-briefing.sh
# yourself (operator[control-plane], ~/.claude/ is off-limits for an agent to
# write): add this line near the end of the box, before the closing
# `echo "╚...╝"`:
#
#   bash "$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || echo ~/nuzantara)/scripts/session_visibility.sh" 2>/dev/null
#
# Usage: bash scripts/session_visibility.sh   (resolves its own repo root and
# Claude Code project dir; safe to run standalone, from any cwd, any time).
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"

WT_COUNT="$(git -C "$ROOT" worktree list 2>/dev/null | wc -l | tr -d ' ')"
echo "worktrees live: ${WT_COUNT:-?}"

# Claude Code project dir naming: "-" + repo path with "/" -> "-" (verified
# against this exact fleet's live paths, e.g.
# ~/.claude/projects/-Users-nuzantara-nuzantara/memory/MEMORY.md).
SLUG="$(echo "$ROOT" | sed 's#^/##; s#/#-#g')"
PROJECT_DIR="$HOME/.claude/projects/-${SLUG}"

if [[ -d "$PROJECT_DIR" ]]; then
  LARGEST_BYTES="$(find "$PROJECT_DIR" -name '*.jsonl' -exec stat -f '%z' {} \; 2>/dev/null | sort -rn | head -1)"
  if [[ -n "${LARGEST_BYTES:-}" ]]; then
    LARGEST_MB="$(python3 -c "print(round(${LARGEST_BYTES}/1048576, 1))" 2>/dev/null || echo "?")"
    echo "largest transcript: ${LARGEST_MB} MB"
  else
    echo "largest transcript: (none found under $PROJECT_DIR)"
  fi
else
  echo "largest transcript: (project dir not found: $PROJECT_DIR)"
fi
