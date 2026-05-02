#!/usr/bin/env bash
# codex-spalla.sh — dispatch Codex CLI as "spalla" (adversarial second opinion)
#
# Usage:
#   .claude/scripts/codex-spalla.sh <mode> <base_branch> [focus_brief]
#
# Args:
#   mode:        "review" (default) | "exec"
#   base_branch: base for diff comparison (default: main)
#   focus_brief: optional free-text focus area passed to Codex
#
# Behavior contract: see docs/superpowers/specs/2026-05-03-codex-spalla-design.md §4.3.
# Hard rules: see docs/decisions/2026-05-03-codex-spalla-architecture.md.
#
# Exit codes:
#   0  = dispatch completed (regardless of Codex verdict)
#   1  = invalid args or git error
#   2  = hard refused (empty diff)
#   3  = anti-pattern guard cancelled by user (Ctrl-C during countdown)
#   4  = codex CLI not installed
#   5  = codex CLI not logged in
#   >5 = codex non-zero exit propagated

set -euo pipefail

MODE="${1:-review}"
BASE="${2:-main}"
FOCUS="${3:-}"

if [[ "$MODE" != "review" && "$MODE" != "exec" ]]; then
    echo "ERROR: mode must be 'review' or 'exec' (got: '$MODE')" >&2
    exit 1
fi

# SECURITY (Codex spalla self-review BLOCKER #1, 2026-05-03):
# git accepts branch names containing shell metacharacters (`pwn;id`,
# `pwn$(id)`, `pwn|id`); the previous implementation interpolated $BASE
# into a string and ran it via `eval`, which could execute injected
# commands. Validate $BASE against a strict whitelist BEFORE any use.
if ! printf '%s' "$BASE" | grep -qE '^[A-Za-z0-9._/-]+$'; then
    echo "ERROR: base branch name '$BASE' contains characters outside [A-Za-z0-9._/-]" >&2
    echo "(refusing to proceed for shell-injection safety)" >&2
    exit 1
fi

if ! command -v codex >/dev/null 2>&1; then
    echo "ERROR: codex CLI not found. Install with: brew install codex" >&2
    exit 4
fi

if ! codex login status 2>&1 | grep -qi "Logged in using ChatGPT"; then
    echo "ERROR: codex CLI not logged in via ChatGPT OAuth. Run: codex login" >&2
    echo "(Hard rule: do NOT set OPENAI_API_KEY — use OAuth only.)" >&2
    exit 5
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
    echo "ERROR: not inside a git repo" >&2
    exit 1
fi
cd "$REPO_ROOT"

HEAD_REF="$(git rev-parse HEAD 2>/dev/null || echo HEAD)"

# Use array form (NOT eval) to safely pass refs to git.
declare -a DIFF_ARGS
if git rev-parse --verify --quiet "$BASE" >/dev/null; then
    DIFF_ARGS=(diff "${BASE}...${HEAD_REF}")
else
    DIFF_ARGS=(diff HEAD)
fi

DIFF_LINES="$(git "${DIFF_ARGS[@]}" 2>/dev/null | wc -l | tr -d ' ')"
FILES_CHANGED="$(git "${DIFF_ARGS[@]}" --stat 2>/dev/null | tail -1 | grep -oE '^[[:space:]]*[0-9]+ files? changed' | grep -oE '[0-9]+' | head -1 || echo 0)"

# Codex spalla BLOCKER #2 + #3: include uncommitted + untracked in the
# "what's about to ship" tally; otherwise fresh `Write` files look empty.
UNCOMMITTED_LINES="$(git diff HEAD 2>/dev/null | wc -l | tr -d ' ')"
UNTRACKED_FILES="$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')"
TOTAL_DIFF_LINES=$((DIFF_LINES + UNCOMMITTED_LINES))

WARNED="false"
CANCELLED="false"

if [[ "$TOTAL_DIFF_LINES" -eq 0 ]] && [[ "$UNTRACKED_FILES" -eq 0 ]]; then
    echo "REFUSED: diff is empty against base '$BASE', no uncommitted changes, no untracked files." >&2
    echo "Nothing to review. Make some changes first." >&2
    exit 2
fi

if [[ "$DIFF_LINES" -lt 10 ]] || [[ "$FILES_CHANGED" -lt 3 ]]; then
    WARNED="true"
    printf '⚠ scope is small — Claude self-review may be cheaper.\n' >&2
    printf '⚠ proceeding in 5s (Ctrl-C to cancel) ...\n' >&2
    printf '⚠ logged warned=true to telemetry.\n' >&2
    if ! sleep 5; then
        CANCELLED="true"
        echo "" >&2
        echo "CANCELLED by user." >&2
    fi
fi

TS="$(date -u +%Y%m%dT%H%M%SZ)"
# Codex spalla BLOCKER #7: race-safe random suffix so two same-second runs
# don't clobber the same transcript path.
RAND="$(printf '%04x' $(($$ ^ RANDOM)) 2>/dev/null || echo "$$")"
SLUG="$(echo "${FOCUS:-uncommitted}" | tr -c '[:alnum:]-' '-' | tr -s '-' | cut -c1-40 | sed 's/^-//;s/-$//')"
[[ -z "$SLUG" ]] && SLUG="diff"

LOG_DIR="$HOME/logs/codex-spalla"
TELEMETRY_FILE="$HOME/logs/codex-spalla.jsonl"
TRANSCRIPT="$LOG_DIR/${TS}-${RAND}-${MODE}-${SLUG}.md"
mkdir -p "$LOG_DIR"

record_telemetry() {
    local exit_code="$1"
    local blocker="${2:-false}"
    local focus_json
    focus_json="$(printf '%s' "${FOCUS:-}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')"
    printf '{"ts":"%s","mode":"%s","base":"%s","focus":%s,"diff_lines":%s,"files_changed":%s,"untracked_files":%s,"warned":%s,"cancelled":%s,"exit_code":%s,"blocker":%s,"transcript":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$MODE" "$BASE" "$focus_json" \
        "$DIFF_LINES" "$FILES_CHANGED" "$UNTRACKED_FILES" \
        "$WARNED" "$CANCELLED" "$exit_code" "$blocker" \
        "$TRANSCRIPT" >> "$TELEMETRY_FILE"
}

trap 'if [[ "$CANCELLED" == "true" ]]; then record_telemetry 3 false; exit 3; fi' INT

if [[ "$CANCELLED" == "true" ]]; then
    record_telemetry 3 false
    exit 3
fi

# Capture diff bodies once for embedding in the prompt.
DIFF_BODY="$(git "${DIFF_ARGS[@]}" 2>/dev/null | head -2000 || echo '<diff capture failed>')"
UNCOMMITTED_BODY="$(git diff HEAD 2>/dev/null | head -1000 || true)"
UNTRACKED_LIST="$(git ls-files --others --exclude-standard 2>/dev/null | head -50 || true)"

PROMPT="[SPALLA]

You are Codex CLI in Spalla Mode (see ~/.codex/AGENTS.md). Claude Opus 4.7 has just produced the diff below and is about to commit/push. Adversarially review it.

Focus brief: ${FOCUS:-no specific focus — give a balanced adversarial review against CLAUDE.md and AGENTS.md rules.}

Base: $BASE
Committed diff stats: $DIFF_LINES lines across $FILES_CHANGED files.
Uncommitted lines: $UNCOMMITTED_LINES
Untracked files: $UNTRACKED_FILES

Output template (strict):
- Line 1: one of BLOCKER, MEDIUM, LOW, LGTM
- Para 2: one paragraph 'what Claude proposed'
- Bullets: edge cases / blind spots / CLAUDE.md or AGENTS.md drift, with file:line cites

Verify before asserting (grep the repo). No prose summary at end.

--- COMMITTED DIFF (truncated to 2000 lines) ---
${DIFF_BODY}
--- END COMMITTED DIFF ---

--- UNCOMMITTED DIFF (truncated to 1000 lines) ---
${UNCOMMITTED_BODY}
--- END UNCOMMITTED DIFF ---

--- UNTRACKED FILES (truncated to 50) ---
${UNTRACKED_LIST}
--- END UNTRACKED FILES ---"

echo "Dispatching codex (mode=$MODE base=$BASE committed=${DIFF_LINES}L/${FILES_CHANGED}f uncommitted=${UNCOMMITTED_LINES}L untracked=${UNTRACKED_FILES})" >&2
echo "Transcript will be saved to: $TRANSCRIPT" >&2

CODEX_EXIT=0
if [[ "$MODE" == "review" ]]; then
    # `codex review --base BRANCH "$PROMPT"` is rejected:
    # "argument '--base <BRANCH>' cannot be used with '[PROMPT]'".
    # Use `codex exec --sandbox read-only` instead — it accepts our
    # custom [SPALLA] prompt while staying read-only on the workspace.
    printf '%s' "$PROMPT" | codex exec --full-auto --sandbox read-only \
        -c model_reasoning_effort=xhigh - > "$TRANSCRIPT" 2>&1 || CODEX_EXIT=$?
else
    printf '%s' "$PROMPT" | codex exec --full-auto -c model_reasoning_effort=xhigh - \
        > "$TRANSCRIPT" 2>&1 || CODEX_EXIT=$?
fi

BLOCKER="false"
if grep -qiE '^[[:space:]]*BLOCKER\b' "$TRANSCRIPT" 2>/dev/null; then
    BLOCKER="true"
    REVIEWS_DIR="$REPO_ROOT/docs/codex-reviews"
    mkdir -p "$REVIEWS_DIR"
    cp "$TRANSCRIPT" "$REVIEWS_DIR/${TS}-${RAND}-blocker-${SLUG}.md"
    echo "BLOCKER detected — also copied to $REVIEWS_DIR/${TS}-${RAND}-blocker-${SLUG}.md" >&2
fi

record_telemetry "$CODEX_EXIT" "$BLOCKER"

echo "RESULT_PATH=$TRANSCRIPT"
exit "$CODEX_EXIT"
