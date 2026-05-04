#!/usr/bin/env bash
# subhi-bash-guard.sh — PreToolUse hook on Bash for Subhi tutor sessions.
# Reads JSON from stdin, returns:
#   exit 0 → allow
#   exit 2 → block with stderr message shown to model
# Reference: https://docs.claude.com/en/docs/claude-code/hooks

set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))")
TOOL_INPUT=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))")
CWD=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd',''))")

# === 1. CWD check ===
case "$CWD" in
  "$HOME/zantara-onboarding"*|"$HOME/Projects/nuzantara"*) ;;
  *)
    echo "Subhi, working directory di luar scope kamu: $CWD" >&2
    echo "Pindah ke ~/Projects/nuzantara/ atau ~/zantara-onboarding/ dulu." >&2
    exit 2
    ;;
esac

# === 2. Pattern reject ===
PATTERNS=(
  'fly[[:space:]]'
  'fly$'
  'gcloud[[:space:]]'
  'aws[[:space:]]'
  'sudo[[:space:]]'
  'rm[[:space:]]+-rf[[:space:]]+/'
  'chmod[[:space:]]+777'
  'curl[[:space:]].*\|[[:space:]]*(bash|sh)'
  'wget[[:space:]].*\|[[:space:]]*(bash|sh)'
  ':\(\)\s*\{[^}]*\}'  # fork bomb
)

for pat in "${PATTERNS[@]}"; do
  if echo "$TOOL_INPUT" | grep -qE "$pat"; then
    echo "Subhi, command ini di luar perimeter kamu (pattern: ${pat:0:30}...)." >&2
    echo "Production resource (fly, gcloud, aws), sudo, atau pipe-to-shell tidak diizinkan." >&2
    echo "Kalau perlu deploy/ssh prod, ping Antonello." >&2
    exit 2
  fi
done

# === 3. Branch check (only on git push) ===
if echo "$TOOL_INPUT" | grep -qE '^[[:space:]]*git[[:space:]]+push'; then
  if [[ -d "$CWD/.git" || -f "$CWD/.git" ]]; then
    cd "$CWD"
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    case "$BRANCH" in
      sancho/*|subhi/memory-mirror|HEAD) ;;
      main|master)
        echo "Subhi, push langsung ke $BRANCH ditolak." >&2
        echo "Buat branch sancho/<task-slug> dulu:" >&2
        echo "  git checkout -b sancho/$(echo "$TOOL_INPUT" | head -c 30)" >&2
        exit 2
        ;;
      "")
        ;;  # detached HEAD or non-git, allow
      *)
        echo "Subhi, branch '$BRANCH' bukan pattern sancho/* atau subhi/*." >&2
        echo "Konvensi: gunakan 'sancho/<task-slug>'." >&2
        exit 2
        ;;
    esac
  fi
fi

# All checks passed
exit 0
