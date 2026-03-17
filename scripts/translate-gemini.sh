#!/usr/bin/env bash
# translate-gemini.sh — Translate MDX articles using Gemini CLI
# Usage: ./scripts/translate-gemini.sh <lang> <category>
# Example: ./scripts/translate-gemini.sh ru immigration

set -euo pipefail

LANG="${1:?Usage: $0 <lang> <category>}"
CATEGORY="${2:?Usage: $0 <lang> <category>}"
ARTICLES_DIR="apps/mouth/src/content/articles"
LOG="/tmp/translate_gemini_${CATEGORY}_${LANG}.log"

case "$LANG" in
  ru) LANG_NAME="Russian" ;;
  fr) LANG_NAME="French" ;;
  id) LANG_NAME="Bahasa Indonesia" ;;
  it) LANG_NAME="Italian" ;;
  *) echo "Unknown lang: $LANG"; exit 1 ;;
esac

echo "=== Gemini translate: $CATEGORY → $LANG ($LANG_NAME) ===" | tee "$LOG"
echo "Started: $(date)" | tee -a "$LOG"

CAT_DIR="$ARTICLES_DIR/$CATEGORY"
if [ ! -d "$CAT_DIR" ]; then
  echo "ERROR: Directory not found: $CAT_DIR" | tee -a "$LOG"
  exit 1
fi

DONE=0
SKIP=0
FAIL=0

for src in "$CAT_DIR"/*.mdx; do
  name="$(basename "$src")"

  # Skip translation files
  case "$name" in
    *.id.mdx|*.it.mdx|*.ru.mdx|*.fr.mdx) continue ;;
    *.sync-conflict-*) continue ;;
  esac

  slug="${name%.mdx}"
  [ -z "$slug" ] && continue

  out="$CAT_DIR/${slug}.${LANG}.mdx"

  # Skip if already translated
  if [ -f "$out" ]; then
    SKIP=$((SKIP+1))
    continue
  fi

  echo "[$(date +%H:%M:%S)] Translating: $slug" | tee -a "$LOG"

  # Extract frontmatter and body
  FRONTMATTER=$(awk '/^---/{c++; if(c==2){exit}} {print}' "$src")
  BODY=$(awk '/^---/{c++; if(c==2){found=1; next}} found{print}' "$src")

  if [ -z "$BODY" ]; then
    echo "  SKIP (empty body)" | tee -a "$LOG"
    SKIP=$((SKIP+1))
    continue
  fi

  # Truncate very long articles (>8000 words)
  WORD_COUNT=$(echo "$BODY" | wc -w | tr -d ' ')
  if [ "$WORD_COUNT" -gt 8000 ]; then
    echo "  Truncating from $WORD_COUNT to 8000 words" | tee -a "$LOG"
    BODY=$(echo "$BODY" | tr ' ' '\n' | head -8000 | tr '\n' ' ')
  fi

  PROMPT="You are an expert translator specializing in legal, immigration, and business content about Indonesia.

Translate the following MDX article content from English to ${LANG_NAME}.

CRITICAL RULES:
1. Translate ONLY the human-readable text (headings, paragraphs, list items, alt text).
2. DO NOT translate or modify:
   - MDX/JSX component tags: <InfoCard>, <Checklist>, <CallToAction>, etc.
   - Markdown links: keep URL unchanged, translate only link text
   - Image paths and src attributes
   - Code blocks and inline code
   - Frontmatter (not included)
3. DO NOT translate proper nouns: KITAS, KITAP, KBLI, PT PMA, NPWP, NIB, OSS, BKPM, Bali, Jakarta, Indonesia
4. Keep the same Markdown formatting (##, **, *, -, numbered lists).
5. Output ONLY the translated content. No preamble, no explanation, no code fences.
6. Maintain the exact same structure and paragraph breaks as the original.

CONTENT TO TRANSLATE:
${BODY}"

  # Call Gemini CLI with timeout
  TRANSLATED=$(echo "$PROMPT" | timeout 120 gemini --model gemini-2.5-flash 2>>"$LOG" | grep -v "^Loaded cached\|^Server '\|^Error when" || true)

  if [ -z "$TRANSLATED" ] || [ "${#TRANSLATED}" -lt 50 ]; then
    echo "  FAIL: empty or too short response (${#TRANSLATED} chars)" | tee -a "$LOG"
    FAIL=$((FAIL+1))
    continue
  fi

  # Patch frontmatter locale and write output
  PATCHED_FM=$(echo "$FRONTMATTER" | sed "s/^locale:.*$/locale: \"${LANG}\"/")
  if ! echo "$PATCHED_FM" | grep -q "^locale:"; then
    PATCHED_FM="${PATCHED_FM%---}
locale: \"${LANG}\"
---"
  fi

  printf '%s\n%s\n' "$PATCHED_FM" "$TRANSLATED" > "$out"
  echo "  OK: ${slug}.${LANG}.mdx (${#TRANSLATED} chars)" | tee -a "$LOG"
  DONE=$((DONE+1))
done

echo "" | tee -a "$LOG"
echo "=== DONE: $DONE translated, $SKIP skipped, $FAIL failed ===" | tee -a "$LOG"
echo "Finished: $(date)" | tee -a "$LOG"
