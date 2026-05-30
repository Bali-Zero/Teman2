#!/usr/bin/env bash
set -euo pipefail

if [ "${CICATRIX_SIZE_ENFORCEMENT:-true}" = "false" ]; then
  exit 0
fi

TARGET_FILE=".claude/rules/cicatrix-scars.md"
LIMIT_CHARS="${CICATRIX_SIZE_LIMIT_CHARS:-40000}"

if ! git diff --cached --name-only --diff-filter=ACMR | grep -Fxq "$TARGET_FILE"; then
  exit 0
fi

if ! git cat-file -e ":$TARGET_FILE" 2>/dev/null; then
  exit 0
fi

SIZE_CHARS=$(git show ":$TARGET_FILE" | LC_ALL=C wc -c | tr -d '[:space:]')

if [ "$SIZE_CHARS" -le "$LIMIT_CHARS" ]; then
  exit 0
fi

cat >&2 <<EOF
ERROR: $TARGET_FILE is too large for auto-loaded agent context.
Current staged size: ${SIZE_CHARS} chars
Limit: ${LIMIT_CHARS} chars

Move old/resolved scars into .claude/rules/cicatrix-scars-archive.md before
committing, or use CICATRIX_SIZE_ENFORCEMENT=false only for an emergency commit.
EOF
exit 1
