#!/bin/bash
# scripts/mini-migration/preflight-job.sh <label>
#
# Pre-flight check for a candidate cron job before migration Pro->Mini.
# Reads the plist on Pro, extracts the script path, greps for hidden
# dependencies on Pro-local services (Postgres@17, Qdrant, Redis Pro,
# Ollama Pro endpoint, NFS path Pro, ssh-pro patterns).
#
# Exit 0: clean — job is safe to migrate (no Pro-bound deps detected).
# Exit 1: BLOCKER — found Pro-bound dependency, classify as Cluster C-exception.
# Exit 2: usage error.
#
# Read-only: never modifies anything. Safe to run anytime.

set -u

LABEL="${1:-}"
if [ -z "$LABEL" ]; then
  echo "usage: $0 <launchd-label>" >&2
  exit 2
fi

# Patterns that indicate Pro-bound dependency (from spec §4.6, panel feedback).
# Any match in script body or .env files referenced => block migration.
DEP_PATTERNS=(
  'localhost:5432'
  '127\.0\.0\.1:5432'
  'postgresql.*:5432'
  ':5432/'
  'localhost:6333'
  '127\.0\.0\.1:6333'
  'qdrant.*:6333'
  ':6333/'
  'pg_ctl|psql -h'
  'asyncpg|psycopg|sqlalchemy'
  'qdrant_client|QdrantClient'
  'localhost:11434'
  '127\.0\.0\.1:11434'
  '/Users/nuzantara/agents/'
  '/Users/antonellosiano/'
  'fly ssh|fly proxy'
  'ssh\s+pro\b|ssh\s+air\b'
  'Nuzantara-9'  # legacy Air hostname
)

# Pull plist from Pro
PLIST_TMP=$(mktemp -t "preflight-${LABEL}-plist.XXXX")
trap 'rm -f "$PLIST_TMP" "$SCRIPT_TMP" 2>/dev/null' EXIT

if ! ssh -o ConnectTimeout=5 -o BatchMode=yes pro \
     "cat ~/Library/LaunchAgents/${LABEL}.plist" > "$PLIST_TMP" 2>/dev/null; then
  echo "FATAL: cannot fetch ~/Library/LaunchAgents/${LABEL}.plist from Pro" >&2
  exit 2
fi

if [ ! -s "$PLIST_TMP" ]; then
  echo "FATAL: plist empty or missing on Pro for ${LABEL}" >&2
  exit 2
fi

echo "[preflight] ${LABEL}"
echo "[preflight] plist size: $(wc -c < "$PLIST_TMP") bytes"

# Extract script path (ProgramArguments[1] or [2])
SCRIPT=$(/usr/bin/plutil -p "$PLIST_TMP" 2>/dev/null \
  | awk '/ProgramArguments/,/^[[:space:]]*}$/' \
  | grep -E '^\s+[12]\s+=>\s+"/' \
  | head -1 \
  | sed 's/.*=> //;s/^"//;s/"$//')

if [ -z "$SCRIPT" ]; then
  # Probably inline -lc command; extract the -lc arg
  SCRIPT=$(/usr/bin/plutil -p "$PLIST_TMP" 2>/dev/null \
    | awk '/ProgramArguments/,/^[[:space:]]*}$/' \
    | grep -E '^\s+2\s+=>\s+"' \
    | head -1 \
    | sed 's/.*=> //;s/^"//;s/"$//')
fi

if [ -z "$SCRIPT" ]; then
  echo "[preflight] WARN: cannot extract script path from plist" >&2
  echo "[preflight] verdict: SKIP (plist structure unusual, manual review)"
  exit 1
fi

echo "[preflight] script/cmd: ${SCRIPT}"

# Fetch script body from Pro if it's a real path
SCRIPT_TMP=$(mktemp -t "preflight-${LABEL}-script.XXXX")
SCRIPT_BODY=""
if [[ "$SCRIPT" == /* ]] && [[ "$SCRIPT" != *"\$"* ]]; then
  if ssh -o ConnectTimeout=5 -o BatchMode=yes pro \
       "[ -f '$SCRIPT' ] && cat '$SCRIPT'" > "$SCRIPT_TMP" 2>/dev/null; then
    SCRIPT_BODY=$(cat "$SCRIPT_TMP")
  else
    echo "[preflight] WARN: script file ${SCRIPT} not readable on Pro"
  fi
else
  # Inline shell command — body IS the command
  SCRIPT_BODY="$SCRIPT"
fi

# Combine plist + script body for grep
SEARCH_TARGET="${PLIST_TMP} ${SCRIPT_TMP}"

HITS=0
HIT_LINES=()
for pat in "${DEP_PATTERNS[@]}"; do
  matches=$(grep -nE "$pat" $SEARCH_TARGET 2>/dev/null | head -3)
  if [ -n "$matches" ]; then
    HITS=$((HITS + 1))
    HIT_LINES+=("=== pattern: ${pat} ===")
    HIT_LINES+=("$matches")
  fi
done

echo ""
if [ "$HITS" -gt 0 ]; then
  echo "[preflight] BLOCKED: found ${HITS} Pro-bound dependency pattern(s):"
  for line in "${HIT_LINES[@]}"; do
    echo "  $line"
  done
  echo ""
  echo "[preflight] verdict: REJECT migration of ${LABEL} (classify as Cluster C-exception)"
  exit 1
fi

echo "[preflight] no Pro-bound dependency patterns found"
echo "[preflight] verdict: PASS — ${LABEL} can be migrated to Mini"
exit 0
