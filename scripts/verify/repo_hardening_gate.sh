#!/usr/bin/env bash
set -euo pipefail

if ! command -v git >/dev/null 2>&1; then
  echo "repo-hardening-gate: git not found; skipping (CI should install git)" >&2
  exit 0
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "repo-hardening-gate: not a git repository; skipping" >&2
  exit 0
fi

deny_reason=()
deny_file=()
content_reason=()
content_file=()

is_allowed_env_file() {
  case "$1" in
    .env.example | .env.sample | .env.template) return 0 ;;
    *) return 1 ;;
  esac
}

is_denied_file() {
  local rel="$1"
  local base
  base="$(basename "$rel")"

  # Environment files
  if [[ "$base" == ".env"* ]]; then
    if is_allowed_env_file "$base"; then
      return 1
    fi
    return 0
  fi

  # Private keys / cert material
  case "$rel" in
    *.pem | *.key | *.p12 | *.pfx | *.der) return 0 ;;
  esac

  # Credential JSONs (service accounts, etc.)
  if [[ "$base" == *credentials*.json || "$base" == "google_credentials.json" ]]; then
    if [[ "$base" == *.example.json ]]; then
      return 1
    fi
    return 0
  fi

  return 1
}

is_denied_path_fragment() {
  local rel="$1"
  if [[ "$rel" == ".secrets/README.md" ]]; then
    return 1
  fi
  case "$rel" in
    .cursor/* | */.cursor/*) return 0 ;;
    .libs/* | */.libs/*) return 0 ;;
    .scannerwork/* | */.scannerwork/*) return 0 ;;
    .secrets/* | */.secrets/*) return 0 ;;
    node_modules/* | */node_modules/*) return 0 ;;
    .next/* | */.next/*) return 0 ;;
    htmlcov/* | */htmlcov/*) return 0 ;;
    htmlcov_backend/* | */htmlcov_backend/*) return 0 ;;
    htmlcov_plugins/* | */htmlcov_plugins/*) return 0 ;;
    .coverage_data/* | */.coverage_data/*) return 0 ;;
    deep-analysis-results/* | */deep-analysis-results/*) return 0 ;;
    logs/* | */logs/*) return 0 ;;
    test-results/* | */test-results/*) return 0 ;;
    test_results/* | */test_results/*) return 0 ;;
    .venv/* | */.venv/*) return 0 ;;
  esac
  return 1
}

while IFS= read -r -d '' rel; do
  if is_denied_path_fragment "$rel"; then
    deny_reason+=("artifact-directory")
    deny_file+=("$rel")
    continue
  fi
  if is_denied_file "$rel"; then
    deny_reason+=("secret-file")
    deny_file+=("$rel")
    continue
  fi
done < <(git ls-files -z)

if ((${#deny_file[@]} > 0)); then
  echo "repo-hardening-gate: FAILED" >&2
  echo "The following tracked files must not be committed:" >&2
  for i in "${!deny_file[@]}"; do
    printf -- "- [%s] %s\n" "${deny_reason[$i]}" "${deny_file[$i]}" >&2
  done
  echo "" >&2
  echo "Fix:" >&2
  echo "  - Remove these files from git history/index, keep only templates (e.g. *.example)" >&2
  echo "  - Ensure local secrets stay untracked via .gitignore" >&2
  exit 1
fi

add_content_hits() {
  local reason="$1"
  local pattern="$2"

  # List matching tracked files only (no secret content).
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    content_reason+=("$reason")
    content_file+=("$file")
  done < <(git grep -l -I -E -e "$pattern" || true)
}

# Content-based secret detection (best-effort, tuned to reduce false positives).
add_content_hits "private-key-content" "-----BEGIN [A-Z ]*PRIVATE KEY-----"
add_content_hits "google-api-key" "AIza[0-9A-Za-z_-]{20,}"
add_content_hits "openai-api-key" "sk-[A-Za-z0-9_-]{20,}"
add_content_hits "github-token" "ghp_[A-Za-z0-9]{20,}"
add_content_hits "slack-token" "xox[baprs]-[A-Za-z0-9-]{10,}"
add_content_hits "aws-access-key" "AKIA[0-9A-Z]{16}"

if ((${#content_file[@]} > 0)); then
  echo "repo-hardening-gate: FAILED" >&2
  echo "Secret-like patterns detected in tracked file contents:" >&2
  for i in "${!content_file[@]}"; do
    printf -- "- [%s] %s\n" "${content_reason[$i]}" "${content_file[$i]}" >&2
  done
  echo "" >&2
  echo "Fix:" >&2
  echo "  - Remove/redact secrets from these files (use env vars/secrets manager)" >&2
  echo "  - Rotate any exposed keys/tokens immediately" >&2
  exit 1
fi

echo "repo-hardening-gate: OK"
