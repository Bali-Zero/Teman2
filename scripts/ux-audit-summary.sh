#!/bin/bash
# Quick UX audit summary — runs on key directories only, outputs one line
# Used by Claude Code SessionStart hook

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
AUDIT="$ROOT/scripts/ux-audit.sh"

[ ! -x "$AUDIT" ] && exit 0

H=0; M=0; L=0

for d in \
  "$ROOT/apps/mouth/src/app" \
  "$ROOT/apps/mouth/src/components" \
  "$ROOT/apps/backend-rag/backend/app" \
  "$ROOT/apps/backend-rag/backend/services"; do

  [ ! -d "$d" ] && continue

  # Run audit, capture only the summary line
  summary=$("$AUDIT" "$d" 2>/dev/null | grep "^Summary:")

  h=$(echo "$summary" | grep -oE '[0-9]+ HIGH' | grep -oE '[0-9]+' || echo 0)
  m=$(echo "$summary" | grep -oE '[0-9]+ MEDIUM' | grep -oE '[0-9]+' || echo 0)
  l=$(echo "$summary" | grep -oE '[0-9]+ LOW' | grep -oE '[0-9]+' || echo 0)

  H=$((H + ${h:-0}))
  M=$((M + ${m:-0}))
  L=$((L + ${l:-0}))
done

if [ $H -eq 0 ] && [ $M -eq 0 ] && [ $L -eq 0 ]; then
  echo "UX Audit: all clean"
else
  echo "UX Audit: ${H} HIGH, ${M} MEDIUM, ${L} LOW — run ./scripts/ux-audit.sh <dir> for details"
fi
