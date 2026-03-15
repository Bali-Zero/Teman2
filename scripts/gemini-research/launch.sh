#!/bin/bash
# Launch 8 Gemini CLI deep research sessions
# 4 on Pro (coding), 4 on Air (business)
# Usage: ./launch.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Gemini Deep Research Launcher ==="
echo "Project: $PROJECT_DIR"
echo ""

# Ensure research output dir exists
mkdir -p "$PROJECT_DIR/docs/research"
ssh air "mkdir -p ~/Desktop/projects/nuzantara/docs/research" 2>/dev/null

echo "--- Launching 4 CODING research on Pro ---"

for i in 01 02 03 04; do
    FILE="$SCRIPT_DIR/${i}-coding-*.md"
    FILE=$(ls $FILE 2>/dev/null | head -1)
    NAME=$(basename "$FILE" .md | sed 's/^[0-9]*-coding-//')
    PROMPT=$(cat "$FILE")

    echo "  [$i] $NAME"
    osascript -e "
        tell application \"iTerm2\"
            create window with default profile
            tell current session of current window
                set name to \"Gemini: $NAME\"
                write text \"cd $PROJECT_DIR && gemini -m gemini-2.5-pro -p \\\"$(echo "$PROMPT" | sed 's/"/\\"/g' | head -c 200)... [full prompt in $FILE]\\\"\"
            end tell
        end tell
    " 2>/dev/null || echo "    (iTerm launch failed, run manually)"
done

echo ""
echo "--- Launching 4 BUSINESS research on Air ---"

for i in 05 06 07 08; do
    FILE="$SCRIPT_DIR/${i}-business-*.md"
    FILE=$(ls $FILE 2>/dev/null | head -1)
    NAME=$(basename "$FILE" .md | sed 's/^[0-9]*-business-//')

    echo "  [$i] $NAME"
    # Copy prompt file to Air
    scp -q "$FILE" "air:~/Desktop/projects/nuzantara/scripts/gemini-research/" 2>/dev/null
done

echo ""
echo "=== Ready ==="
echo ""
echo "ON PRO — run each in a separate iTerm tab:"
echo "  cd $PROJECT_DIR"
for i in 01 02 03 04; do
    FILE=$(ls $SCRIPT_DIR/${i}-coding-*.md 2>/dev/null | head -1)
    NAME=$(basename "$FILE" .md)
    echo "  gemini -m gemini-2.5-pro < scripts/gemini-research/$NAME.md"
done
echo ""
echo "ON AIR (ssh air) — run each in a separate iTerm tab:"
echo "  cd ~/Desktop/projects/nuzantara"
for i in 05 06 07 08; do
    FILE=$(ls $SCRIPT_DIR/${i}-business-*.md 2>/dev/null | head -1)
    NAME=$(basename "$FILE" .md)
    echo "  gemini -m gemini-2.5-pro < scripts/gemini-research/$NAME.md"
done
echo ""
