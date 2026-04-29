#!/usr/bin/env bash
# lint_i18n_providers.sh
#
# Catches the white-screen regression from PR #273: a component imports
# `useTranslation()` from `@/i18n` (or relative path), but no ancestor
# layout (or the file itself) wraps children in `<I18nProvider>`. At
# runtime React throws and the page goes blank.
#
# For every .ts/.tsx file under the lint root that calls `useTranslation()`
# (excluding type-only imports and commented-out lines), walk the layout
# chain from the file's directory up to the lint root. If neither the
# file itself nor any ancestor layout.tsx contains `<I18nProvider`, that
# is a violation.
#
# Exit 1 on any violation, 0 otherwise. Designed to run in <5s on the
# full apps/mouth/ tree.
#
# Known limitation: aliased imports such as
#   `import { useTranslation as useT } from "@/i18n"` followed by `useT()`
# are NOT detected — this lint matches the literal `useTranslation(`
# token. There are zero such aliases in the codebase today. If the
# pattern becomes common, swap to a TypeScript AST-based check.
#
# Refs: docs/audits/2026-04-29-zero-crash-audit/09_intervention_plan.md (P1-10)

set -euo pipefail

# --- args ---------------------------------------------------------------
ROOT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: lint_i18n_providers.sh [--root <dir>]

Scans <dir> for .ts/.tsx files that call useTranslation() without an
ancestor I18nProvider. Defaults to apps/mouth/src/app relative to the
script's repository root.

Options:
  --root <dir>   Override the lint root (used by tests/CI).
  -h, --help     Show this help.
EOF
      exit 0
      ;;
    *)
      echo "lint_i18n_providers: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$ROOT_DIR" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  ROOT_DIR="$REPO_ROOT/apps/mouth/src/app"
fi

if [[ ! -d "$ROOT_DIR" ]]; then
  echo "lint_i18n_providers: root not found: $ROOT_DIR" >&2
  exit 2
fi

ROOT_DIR="$(cd "$ROOT_DIR" && pwd)"

# --- dependencies -------------------------------------------------------
if ! command -v rg >/dev/null 2>&1; then
  echo "lint_i18n_providers: ripgrep (rg) is required" >&2
  exit 2
fi

# --- helpers ------------------------------------------------------------

# Pattern matches a real call site `useTranslation(` that is NOT
# preceded only by whitespace + `//` (line comment). Also excludes
# `import type { ... } from "@/i18n"` lines because they never resolve
# to a runtime call. We do this in two stages: rg finds candidates,
# then we filter out comments and type-only imports.
USE_TRANSLATION_RE='useTranslation[[:space:]]*\('
PROVIDER_RE='<I18nProvider'
TYPE_IMPORT_RE='^[[:space:]]*import[[:space:]]+type[[:space:]]'
LINE_COMMENT_RE='^[[:space:]]*//'

# file_self_provides <file> -> 0 if file contains <I18nProvider, else 1
file_self_provides() {
  local file="$1"
  rg --quiet --no-config --fixed-strings "$PROVIDER_RE" "$file"
}

# layout_chain_provides <dir> -> 0 if any ancestor layout.tsx contains
# <I18nProvider, walking up from <dir> until ROOT_DIR's parent. We stop
# at ROOT_DIR (inclusive) because anything outside the lint root is
# irrelevant — Next.js doesn't read layouts above the app/ root.
layout_chain_provides() {
  local dir="$1"
  while :; do
    local layout="$dir/layout.tsx"
    if [[ -f "$layout" ]]; then
      if rg --quiet --no-config --fixed-strings "$PROVIDER_RE" "$layout"; then
        return 0
      fi
    fi
    if [[ "$dir" == "$ROOT_DIR" ]]; then
      return 1
    fi
    local parent
    parent="$(dirname "$dir")"
    if [[ "$parent" == "$dir" ]]; then
      return 1
    fi
    dir="$parent"
  done
}

# is_real_call_site <line_text> -> 0 if the line is a real
# `useTranslation(` call site (not a type-only import, not a comment).
is_real_call_site() {
  local text="$1"
  [[ "$text" =~ $TYPE_IMPORT_RE ]] && return 1
  [[ "$text" =~ $LINE_COMMENT_RE ]] && return 1
  local trimmed
  trimmed="${text#"${text%%[![:space:]]*}"}"
  [[ "$trimmed" == \** || "$trimmed" == /\** ]] && return 1
  return 0
}

# count_call_sites <file>: increments $total_checked for each real
# call site found in <file>.
count_call_sites() {
  local f="$1"
  while IFS= read -r match; do
    [[ -z "$match" ]] && continue
    if is_real_call_site "${match#*:}"; then
      total_checked=$((total_checked + 1))
    fi
  done < <(rg --no-config --line-number --no-heading \
    -e "$USE_TRANSLATION_RE" "$f" 2>/dev/null || true)
}

# --- scan ---------------------------------------------------------------

# rg finds every line in a .ts/.tsx file (excluding typical build dirs
# and node_modules) that contains `useTranslation(`. We then post-filter
# to drop comment lines and type-only imports.
violations=0
total_checked=0

# rg --files-with-matches gives one path per line. We disable globbing
# in the for-loop and read line-by-line so paths with spaces survive.
# (NUL-delimited mode would be cleaner but mapfile -d '' is bash 4+,
# and macOS still ships bash 3.2 — keep the script portable so it runs
# both in CI and on dev machines.)
hit_files_tmp="$(mktemp)"
trap 'rm -f "$hit_files_tmp"' EXIT
rg \
  --no-config \
  --files-with-matches \
  --glob '*.ts' \
  --glob '*.tsx' \
  --glob '!**/node_modules/**' \
  --glob '!**/.next/**' \
  --glob '!**/dist/**' \
  --glob '!**/build/**' \
  --glob '!api/**' \
  -e "$USE_TRANSLATION_RE" \
  "$ROOT_DIR" > "$hit_files_tmp" 2>/dev/null || true

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  # Skip the I18nProvider definition site — it exports the hook + provider,
  # but is never itself rendered as a route component.
  base="$(basename "$file")"
  parent_dir="$(dirname "$file")"
  if [[ "$base" == "index.tsx" || "$base" == "index.ts" ]]; then
    if [[ "$parent_dir" == */i18n ]]; then
      continue
    fi
  fi

  # Provider in scope (self or ancestor)? Just tally call sites for the
  # final stats and move on.
  if file_self_provides "$file" || layout_chain_provides "$parent_dir"; then
    count_call_sites "$file"
    continue
  fi

  # No provider. Emit a violation per real call site.
  while IFS= read -r match; do
    [[ -z "$match" ]] && continue
    line_no="${match%%:*}"
    line_text="${match#*:}"
    if ! is_real_call_site "$line_text"; then
      continue
    fi
    total_checked=$((total_checked + 1))
    printf '%s:%s: useTranslation() without <I18nProvider> ancestor\n' \
      "$file" "$line_no"
    violations=$((violations + 1))
  done < <(rg --no-config --line-number --no-heading \
    -e "$USE_TRANSLATION_RE" "$file" 2>/dev/null || true)
done < "$hit_files_tmp"

if [[ "$violations" -gt 0 ]]; then
  printf '\nlint_i18n_providers: %d violation(s) found (checked %d call site(s) under %s)\n' \
    "$violations" "$total_checked" "$ROOT_DIR" >&2
  exit 1
fi

printf 'lint_i18n_providers: OK (%d call site(s) checked under %s)\n' \
  "$total_checked" "$ROOT_DIR"
exit 0
