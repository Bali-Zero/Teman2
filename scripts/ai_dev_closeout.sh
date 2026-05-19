#!/usr/bin/env bash
# Read-only close-out check for AI developers working in the Nuzantara repo.

set -u

STRICT=0
for arg in "$@"; do
  case "$arg" in
    --strict)
      STRICT=1
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/ai_dev_closeout.sh [--strict]

Read-only close-out check for AI developers.
--strict exits non-zero when the current state is not acceptable for handoff.
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "ERROR: not inside a git repository" >&2
  exit 2
fi

cd "$REPO_ROOT" || exit 2

BRANCH="$(git branch --show-current 2>/dev/null || true)"
HEAD="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"

ERRORS=0
WARNINGS=0
TRACKED=0
UNTRACKED=0
DIRTY_TOTAL=0

declare -a STATUS_LINES=()
declare -a SHELL_FILES=()
declare -a LOCALE_MDX_FILES=()
declare -a UNKNOWN_UNTRACKED=()

note_error() {
  echo "ERROR: $*"
  ERRORS=$((ERRORS + 1))
}

note_warn() {
  echo "WARN: $*"
  WARNINGS=$((WARNINGS + 1))
}

note_ok() {
  echo "OK: $*"
}

echo "AI dev closeout"
echo "repo: $REPO_ROOT"
echo "branch: ${BRANCH:-detached}"
echo "head: $HEAD"
echo "upstream: ${UPSTREAM:-none}"
echo

while IFS= read -r entry; do
  status="${entry:0:2}"
  path="${entry:3}"
  STATUS_LINES+=("$status $path")

  case "$status" in
    '??')
      UNTRACKED=$((UNTRACKED + 1))
      case "$path" in
        apps/mouth/src/content/articles/*.id.mdx|apps/mouth/src/content/articles/*.it.mdx|apps/mouth/src/content/articles/*.ru.mdx|apps/mouth/src/content/articles/*.fr.mdx)
          LOCALE_MDX_FILES+=("$path")
          ;;
        research/operations/*.md)
          note_ok "untracked operational research candidate: $path"
          ;;
        docs/operations/*.md|.github/pull_request_template.md)
          note_ok "untracked governance document candidate: $path"
          ;;
        scripts/*.sh)
          SHELL_FILES+=("$path")
          ;;
        *)
          UNKNOWN_UNTRACKED+=("$path")
          ;;
      esac
      ;;
    *)
      TRACKED=$((TRACKED + 1))
      ;;
  esac

  case "$path" in
    *.sh)
      SHELL_FILES+=("$path")
      ;;
    apps/mouth/src/content/articles/*.id.mdx|apps/mouth/src/content/articles/*.it.mdx|apps/mouth/src/content/articles/*.ru.mdx|apps/mouth/src/content/articles/*.fr.mdx)
      LOCALE_MDX_FILES+=("$path")
      ;;
  esac
done < <(git status --porcelain=v1)

echo "dirty summary: tracked=$TRACKED untracked=$UNTRACKED"
DIRTY_TOTAL=$((TRACKED + UNTRACKED))

if [ "$DIRTY_TOTAL" -eq 0 ]; then
  note_ok "working tree clean"
else
  if [ "${BRANCH:-}" = "main" ]; then
    note_error "main checkout is dirty; move valid work to a branch/PR or write an explicit status"
  elif [ "$STRICT" -eq 1 ]; then
    note_error "strict closeout requires a clean working tree before handoff"
  else
    note_warn "branch has dirty files; finish by committing, stashing, or documenting blockers"
  fi
fi

if [ "${#UNKNOWN_UNTRACKED[@]}" -gt 0 ]; then
  for path in "${UNKNOWN_UNTRACKED[@]}"; do
    if [ "$STRICT" -eq 1 ]; then
      note_error "unclassified untracked file: $path"
    else
      note_warn "unclassified untracked file: $path"
    fi
  done
fi

if [ "${#LOCALE_MDX_FILES[@]}" -gt 0 ]; then
  echo
  echo "localized MDX checks"
  seen=""
  for path in "${LOCALE_MDX_FILES[@]}"; do
    case " $seen " in
      *" $path "*) continue ;;
    esac
    seen="$seen $path"
    base="$(printf '%s' "$path" | sed -E 's/\.(id|it|ru|fr)\.mdx$/.mdx/')"
    if [ ! -f "$base" ]; then
      note_error "locale MDX has no base article: $path -> $base"
      continue
    fi
    suffix="$(printf '%s' "$path" | sed -E 's/^.*\.([a-z][a-z])\.mdx$/\1/')"
    if ! grep -Eq "^locale: \"?$suffix\"?" "$path"; then
      note_error "locale MDX frontmatter mismatch: $path expected locale=$suffix"
    else
      note_ok "locale MDX base/frontmatter OK: $path"
    fi
  done
fi

if [ "${#SHELL_FILES[@]}" -gt 0 ]; then
  echo
  echo "shell script checks"
  seen=""
  for path in "${SHELL_FILES[@]}"; do
    [ -f "$path" ] || continue
    case " $seen " in
      *" $path "*) continue ;;
    esac
    seen="$seen $path"
    if bash -n "$path"; then
      note_ok "bash -n: $path"
    else
      note_error "bash syntax failed: $path"
    fi
  done
fi

if [ -f "apps/bali-intel-scraper/data/published_articles.json" ]; then
  echo
  echo "published_articles registry check"
  if command -v node >/dev/null 2>&1; then
    if node - <<'NODE'
const fs = require("fs");
const path = "apps/bali-intel-scraper/data/published_articles.json";
const data = JSON.parse(fs.readFileSync(path, "utf8"));
if (!Array.isArray(data.articles)) {
  throw new Error("articles is not an array");
}
const urls = data.articles.map((item) => item.url).filter(Boolean);
const duplicates = urls.filter((url, index) => urls.indexOf(url) !== index);
if (duplicates.length > 0) {
  throw new Error(`duplicate URLs: ${[...new Set(duplicates)].join(", ")}`);
}
console.log(`OK: published_articles articles=${data.articles.length} duplicateUrls=0`);
NODE
    then
      :
    else
      note_error "published_articles registry validation failed"
    fi
  else
    note_warn "node not found; skipped published_articles validation"
  fi
fi

echo
echo "status lines"
if [ "${#STATUS_LINES[@]}" -eq 0 ]; then
  echo "(clean)"
else
  printf '%s\n' "${STATUS_LINES[@]}"
fi

echo
echo "summary: errors=$ERRORS warnings=$WARNINGS strict=$STRICT"

if [ "$STRICT" -eq 1 ] && [ "$ERRORS" -gt 0 ]; then
  exit 1
fi

exit 0
