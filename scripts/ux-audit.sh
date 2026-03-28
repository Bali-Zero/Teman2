#!/bin/bash
# UX/A11y Audit Script — Scans any directory for common UX gaps
# Usage: ./scripts/ux-audit.sh <target-dir> [--json]
#
# Outputs a prioritized list of issues found.
# Works on frontend (TSX) and backend (PY) files.

set -euo pipefail

TARGET="${1:-.}"
JSON_MODE="${2:-}"
ISSUES=()
SCORE=0

# Colors
RED='\033[0;31m'
YEL='\033[0;33m'
GRN='\033[0;32m'
DIM='\033[2m'
RST='\033[0m'

add_issue() {
  local severity="$1" category="$2" file="$3" detail="$4"
  local points=0
  case "$severity" in
    HIGH) points=10 ;;
    MEDIUM) points=5 ;;
    LOW) points=2 ;;
  esac
  SCORE=$((SCORE + points))
  ISSUES+=("${severity}|${category}|${file}|${detail}")
}

echo -e "${DIM}Scanning: ${TARGET}${RST}"
echo ""

# ============================================
# FRONTEND CHECKS (TSX/TS files)
# ============================================

TSX_COUNT=$(find "$TARGET" -name "*.tsx" -not -path "*/node_modules/*" -not -path "*/.next/*" -not -path "*/test*" 2>/dev/null | wc -l | tr -d ' ')

if [ "$TSX_COUNT" -gt 0 ]; then

  # 1. Dead onClick handlers
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | cut -d: -f1)
    add_issue "HIGH" "dead-button" "$file" "Empty onClick={() => {}}"
  done < <(grep -rn "onClick={() => {}}\|onClick={()=>{}}" "$TARGET" --include="*.tsx" 2>/dev/null | grep -v "node_modules\|\.test\.\|__tests__")

  # 2. Buttons without onClick (truly dead)
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | cut -d: -f1)
    lineno=$(echo "$line" | cut -d: -f2)
    # Check next 8 lines for onClick, onSubmit, type="submit", href, or asChild
    has_action=$(sed -n "$((lineno)),$(($lineno+8))p" "$file" 2>/dev/null | grep -c "onClick\|onSubmit\|type=\"submit\"\|href=\|asChild" || true)
    if [ "$has_action" -eq 0 ]; then
      add_issue "HIGH" "dead-button" "$file:$lineno" "Button without onClick handler"
    fi
  done < <(grep -rn "^[[:space:]]*<button$\|^[[:space:]]*<Button$" "$TARGET" --include="*.tsx" 2>/dev/null | grep -v "node_modules\|\.test\.\|__tests__\|type=\"submit\"\|onClick\|href")

  # 3. Overlays/modals missing Escape key handler
  while IFS= read -r file; do
    [ -z "$file" ] && continue
    if ! grep -q "Escape" "$file" 2>/dev/null; then
      add_issue "HIGH" "no-escape" "$file" "Fixed overlay/modal without Escape key handler"
    fi
  done < <(grep -rln "fixed.*z-50\|z-50.*fixed\|fixed.*inset-0" "$TARGET" --include="*.tsx" 2>/dev/null | grep -v "node_modules\|\.test\.\|__tests__")

  # 4. Missing error.tsx boundaries
  while IFS= read -r dir; do
    [ -z "$dir" ] && continue
    has_page=$(find "$dir" -maxdepth 1 -name "page.tsx" 2>/dev/null | head -1)
    if [ -n "$has_page" ] && [ ! -f "$dir/error.tsx" ]; then
      add_issue "MEDIUM" "no-error-boundary" "$dir" "Route missing error.tsx"
    fi
  done < <(find "$TARGET" -type d -not -path "*/node_modules/*" -not -path "*/.next/*" -not -path "*/__tests__/*" 2>/dev/null)

  # 5. Missing loading.tsx skeletons
  while IFS= read -r dir; do
    [ -z "$dir" ] && continue
    has_page=$(find "$dir" -maxdepth 1 -name "page.tsx" 2>/dev/null | head -1)
    if [ -n "$has_page" ] && [ ! -f "$dir/loading.tsx" ]; then
      add_issue "LOW" "no-loading-skeleton" "$dir" "Route missing loading.tsx"
    fi
  done < <(find "$TARGET" -type d -not -path "*/node_modules/*" -not -path "*/.next/*" -not -path "*/__tests__/*" 2>/dev/null)

  # 6. Icon-only buttons without aria-label
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | cut -d: -f1)
    lineno=$(echo "$line" | cut -d: -f2)
    # Check surrounding lines for aria-label
    has_aria=$(sed -n "$((lineno > 3 ? lineno-3 : 1)),$((lineno+3))p" "$file" 2>/dev/null | grep -c "aria-label" || true)
    if [ "$has_aria" -eq 0 ]; then
      title_val=$(echo "$line" | grep -oE 'title="[^"]*"' | head -1)
      add_issue "MEDIUM" "no-aria-label" "$file:$lineno" "Icon button with $title_val but no aria-label"
    fi
  done < <(grep -rn 'title="' "$TARGET" --include="*.tsx" 2>/dev/null | grep -v "aria-label\|{title}\|articleTitle\|pageTitle\|const \|node_modules\|\.test\.\|__tests__")

  # 7. Inputs without aria-label or associated label
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | cut -d: -f1)
    lineno=$(echo "$line" | cut -d: -f2)
    has_label=$(sed -n "$((lineno > 8 ? lineno-8 : 1)),$((lineno+8))p" "$file" 2>/dev/null | grep -c "aria-label\|htmlFor\|id=\|<label" || true)
    if [ "$has_label" -eq 0 ]; then
      add_issue "MEDIUM" "input-no-label" "$file:$lineno" "Input without aria-label or associated label"
    fi
  done < <(grep -rn "<input" "$TARGET" --include="*.tsx" 2>/dev/null | grep -v "aria-label\|htmlFor\|hidden\|checkbox\|radio\|node_modules\|\.test\.\|__tests__")

  # 8. Images without onError fallback (cover images)
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | cut -d: -f1)
    lineno=$(echo "$line" | cut -d: -f2)
    has_onerror=$(sed -n "$((lineno)),$((lineno+5))p" "$file" 2>/dev/null | grep -c "onError" || true)
    if [ "$has_onerror" -eq 0 ]; then
      add_issue "MEDIUM" "image-no-fallback" "$file:$lineno" "Image without onError fallback"
    fi
  done < <(grep -rn "coverImage\|src={.*image" "$TARGET" --include="*.tsx" 2>/dev/null | grep "<Image\|<img" | grep -v "node_modules\|\.test\.\|__tests__")

fi

# ============================================
# BACKEND CHECKS (PY files)
# ============================================

PY_COUNT=$(find "$TARGET" -name "*.py" -not -path "*/node_modules/*" -not -path "*/.venv/*" -not -path "*/venv/*" 2>/dev/null | wc -l | tr -d ' ')

if [ "$PY_COUNT" -gt 0 ]; then

  # 9. datetime.now() without timezone
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | cut -d: -f1)
    add_issue "MEDIUM" "naive-datetime" "$file" "datetime.now() without tz= (use datetime.now(tz=timezone.utc))"
  done < <(grep -rn "datetime\.now()" "$TARGET" --include="*.py" 2>/dev/null | grep -v "tz=\|timezone\|\.venv\|venv\|node_modules\|__pycache__")

  # 10. date.today() (should be timezone-aware)
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | cut -d: -f1)
    add_issue "LOW" "naive-date" "$file" "date.today() (prefer datetime.now(tz=timezone.utc).date())"
  done < <(grep -rn "date\.today()" "$TARGET" --include="*.py" 2>/dev/null | grep -v "\.venv\|venv\|node_modules\|__pycache__")

  # 11. print() instead of logger
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | cut -d: -f1)
    add_issue "LOW" "print-not-logger" "$file" "print() used instead of logger"
  done < <(grep -rn "^\s*print(" "$TARGET" --include="*.py" 2>/dev/null | grep -v "\.venv\|venv\|node_modules\|__pycache__\|test_\|_test\.py")

  # 12. Missing timezone import where datetime.now(tz=timezone.utc) is used
  while IFS= read -r file; do
    [ -z "$file" ] && continue
    uses_tz=$(grep -c "timezone\.utc\|tz=timezone" "$file" 2>/dev/null || true)
    has_import=$(grep -c "from datetime.*import.*timezone\|import.*timezone" "$file" 2>/dev/null || true)
    if [ "$uses_tz" -gt 0 ] && [ "$has_import" -eq 0 ]; then
      add_issue "HIGH" "missing-import" "$file" "Uses timezone.utc but doesn't import timezone"
    fi
  done < <(find "$TARGET" -name "*.py" -not -path "*/.venv/*" -not -path "*/venv/*" -not -path "*/__pycache__/*" 2>/dev/null)

  # 13. Bare except (catch-all)
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | cut -d: -f1)
    add_issue "LOW" "bare-except" "$file" "Bare 'except:' without exception type"
  done < <(grep -rn "^\s*except:$" "$TARGET" --include="*.py" 2>/dev/null | grep -v "\.venv\|venv\|__pycache__")

fi

# ============================================
# OUTPUT
# ============================================

echo ""
if [ ${#ISSUES[@]} -eq 0 ]; then
  echo -e "${GRN}No issues found. Clean!${RST}"
  exit 0
fi

# Sort by severity (HIGH first)
echo -e "Found ${RED}${#ISSUES[@]}${RST} issues (score: ${SCORE}):"
echo ""

# HIGH
for issue in "${ISSUES[@]}"; do
  sev=$(echo "$issue" | cut -d'|' -f1)
  [ "$sev" != "HIGH" ] && continue
  cat=$(echo "$issue" | cut -d'|' -f2)
  file=$(echo "$issue" | cut -d'|' -f3)
  detail=$(echo "$issue" | cut -d'|' -f4)
  echo -e "  ${RED}HIGH${RST}  [${cat}] ${file}"
  echo -e "        ${DIM}${detail}${RST}"
done

# MEDIUM
for issue in "${ISSUES[@]}"; do
  sev=$(echo "$issue" | cut -d'|' -f1)
  [ "$sev" != "MEDIUM" ] && continue
  cat=$(echo "$issue" | cut -d'|' -f2)
  file=$(echo "$issue" | cut -d'|' -f3)
  detail=$(echo "$issue" | cut -d'|' -f4)
  echo -e "  ${YEL}MED${RST}   [${cat}] ${file}"
  echo -e "        ${DIM}${detail}${RST}"
done

# LOW
for issue in "${ISSUES[@]}"; do
  sev=$(echo "$issue" | cut -d'|' -f1)
  [ "$sev" != "LOW" ] && continue
  cat=$(echo "$issue" | cut -d'|' -f2)
  file=$(echo "$issue" | cut -d'|' -f3)
  detail=$(echo "$issue" | cut -d'|' -f4)
  echo -e "  ${DIM}LOW${RST}   [${cat}] ${file}"
  echo -e "        ${DIM}${detail}${RST}"
done

echo ""
echo -e "Summary: ${RED}$(printf '%s\n' "${ISSUES[@]}" | grep "^HIGH" | wc -l | tr -d ' ') HIGH${RST}, ${YEL}$(printf '%s\n' "${ISSUES[@]}" | grep "^MEDIUM" | wc -l | tr -d ' ') MEDIUM${RST}, ${DIM}$(printf '%s\n' "${ISSUES[@]}" | grep "^LOW" | wc -l | tr -d ' ') LOW${RST} (score: ${SCORE})"
