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
#   2  = hard refused (empty diff)
#   3  = anti-pattern guard cancelled by user (Ctrl-C during countdown)
#   4  = codex CLI not installed
#   5  = codex CLI not logged in
#   >0 = other failure (codex non-zero exit, etc.)

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────
# Args + defaults
# ─────────────────────────────────────────────────────────────────────────
MODE="${1:-review}"
BASE="${2:-main}"
FOCUS="${3:-}"

if [[ "$MODE" != "review" && "$MODE" != "exec" ]]; then
    echo "ERROR: mode must be 'review' or 'exec' (got: '$MODE')" >&2
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────
# Pre-flight checks
# ─────────────────────────────────────────────────────────────────────────
if ! command -v codex >/dev/null 2>&1; then
    echo "ERROR: codex CLI not found. Install with: brew install codex" >&2
    exit 4
fi

if ! codex login status 2>&1 | grep -qi "Logged in using ChatGPT"; then
    echo "ERROR: codex CLI not logged in via ChatGPT OAuth. Run: codex login" >&2
    echo "(Hard rule: do NOT set OPENAI_API_KEY — use OAuth only.)" >&2
    exit 5
fi

# Find git root (helper may be invoked from anywhere)
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
    echo "ERROR: not inside a git repo" >&2
    exit 1
fi
cd "$REPO_ROOT"

# ─────────────────────────────────────────────────────────────────────────
# Diff capture + anti-pattern guard
# ─────────────────────────────────────────────────────────────────────────
# Use base...HEAD (three-dot) so we compare against the merge base, not the
# current state of base. Falls back to working tree if no commits ahead.
HEAD_REF="$(git rev-parse HEAD 2>/dev/null || echo HEAD)"

if git rev-parse --verify --quiet "$BASE" >/dev/null; then
    DIFF_CMD="git diff $BASE...$HEAD_REF"
else
    # base branch doesn't exist locally; fall back to uncommitted changes
    DIFF_CMD="git diff HEAD"
fi

DIFF_LINES="$(eval "$DIFF_CMD" | wc -l | tr -d ' ')"
FILES_CHANGED="$(eval "$DIFF_CMD --stat" 2>/dev/null | tail -1 | grep -oE '^[[:space:]]*[0-9]+ files? changed' | grep -oE '[0-9]+' | head -1 || echo 0)"
# Also include uncommitted (staged + unstaged) changes — they're part of "what's about to ship"
UNCOMMITTED_LINES="$(git diff HEAD 2>/dev/null | wc -l | tr -d ' ')"
TOTAL_DIFF_LINES=$((DIFF_LINES + UNCOMMITTED_LINES))

WARNED="false"
CANCELLED="false"

# Hard refuse on empty diff (no countdown)
if [[ "$TOTAL_DIFF_LINES" -eq 0 ]]; then
    echo "REFUSED: diff is empty against base '$BASE' AND no uncommitted changes." >&2
    echo "Nothing to review. Make some changes first." >&2
    exit 2
fi

# Smart-loud warning on small diff (banner exactly 3 lines, 5s countdown)
if [[ "$DIFF_LINES" -lt 10 ]] || [[ "$FILES_CHANGED" -lt 3 ]]; then
    WARNED="true"
    printf '⚠ scope is small — Claude self-review may be cheaper.\n' >&2
    printf '⚠ proceeding in 5s (Ctrl-C to cancel) ...\n' >&2
    printf '⚠ logged warned=true to telemetry.\n' >&2
    if ! sleep 5; then
        # SIGINT arrived during sleep
        CANCELLED="true"
        echo "" >&2
        echo "CANCELLED by user." >&2
        # Still record telemetry below before exit
    fi
fi

# ─────────────────────────────────────────────────────────────────────────
# Output paths
# ─────────────────────────────────────────────────────────────────────────
TS="$(date -u +%Y%m%dT%H%M%SZ)"
SLUG="$(echo "${FOCUS:-uncommitted}" | tr -c '[:alnum:]-' '-' | tr -s '-' | cut -c1-40 | sed 's/^-//;s/-$//')"
[[ -z "$SLUG" ]] && SLUG="diff"

LOG_DIR="$HOME/logs/codex-spalla"
TELEMETRY_FILE="$HOME/logs/codex-spalla.jsonl"
TRANSCRIPT="$LOG_DIR/${TS}-${MODE}-${SLUG}.md"
mkdir -p "$LOG_DIR"

# ─────────────────────────────────────────────────────────────────────────
# Telemetry helper (always called even on early exit)
# ─────────────────────────────────────────────────────────────────────────
record_telemetry() {
    local exit_code="$1"
    local blocker="${2:-false}"
    # Sanitize focus for JSON
    local focus_json
    focus_json="$(printf '%s' "${FOCUS:-}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')"
    cat >> "$TELEMETRY_FILE" <<JSON
{"ts":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","mode":"$MODE","base":"$BASE","focus":$focus_json,"diff_lines":$DIFF_LINES,"files_changed":$FILES_CHANGED,"warned":$WARNED,"cancelled":$CANCELLED,"exit_code":$exit_code,"blocker":$blocker,"transcript":"$TRANSCRIPT"}
JSON
}

# Trap to ensure telemetry is recorded on any exit
trap 'rc=$?; if [[ "$CANCELLED" == "true" ]]; then record_telemetry 3 false; exit 3; fi' INT

if [[ "$CANCELLED" == "true" ]]; then
    record_telemetry 3 false
    exit 3
fi

# ─────────────────────────────────────────────────────────────────────────
# Build the [SPALLA] prompt
# ─────────────────────────────────────────────────────────────────────────
PROMPT="[SPALLA]

You are Codex CLI in Spalla Mode (see ~/.codex/AGENTS.md). Claude Opus 4.7 has just produced the diff below and is about to commit/push. Adversarially review it.

Focus brief: ${FOCUS:-no specific focus — give a balanced adversarial review against CLAUDE.md and AGENTS.md rules.}

Base: $BASE
Diff stats: $DIFF_LINES lines across $FILES_CHANGED files.

Output template (strict):
- Line 1: one of BLOCKER, MEDIUM, LOW, LGTM
- Para 2: one paragraph 'what Claude proposed'
- Bullets: edge cases / blind spots / CLAUDE.md or AGENTS.md drift, with file:line cites

Verify before asserting (grep the repo). No prose summary at end."

# ─────────────────────────────────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────────────────────────────────
echo "Dispatching codex (mode=$MODE base=$BASE diff=${DIFF_LINES}L/${FILES_CHANGED}f) ..." >&2
echo "Transcript will be saved to: $TRANSCRIPT" >&2

CODEX_EXIT=0
if [[ "$MODE" == "review" ]]; then
    # `codex review --base ...` takes the prompt as a positional arg, NOT stdin
    # (verified 2026-05-03: --base conflicts with [PROMPT] when passed via `-`).
    # We pass the [SPALLA] prompt as the positional PROMPT argument.
    codex review --base "$BASE" --title "[SPALLA] ${FOCUS:-uncommitted-diff}" "$PROMPT" \
        > "$TRANSCRIPT" 2>&1 || CODEX_EXIT=$?
else
    # Pattern A: autonomous exec, workspace-write sandbox.
    # `codex exec` accepts the prompt via stdin with the `-` sentinel.
    printf '%s' "$PROMPT" | codex exec --full-auto -c model_reasoning_effort=xhigh - \
        > "$TRANSCRIPT" 2>&1 || CODEX_EXIT=$?
fi

# ─────────────────────────────────────────────────────────────────────────
# Verdict parsing + BLOCKER routing
# ─────────────────────────────────────────────────────────────────────────
BLOCKER="false"
if grep -qiE '^[[:space:]]*BLOCKER\b' "$TRANSCRIPT" 2>/dev/null; then
    BLOCKER="true"
    REVIEWS_DIR="$REPO_ROOT/docs/codex-reviews"
    mkdir -p "$REVIEWS_DIR"
    cp "$TRANSCRIPT" "$REVIEWS_DIR/${TS}-blocker-${SLUG}.md"
    echo "BLOCKER detected — also copied to $REVIEWS_DIR/${TS}-blocker-${SLUG}.md" >&2
fi

# ─────────────────────────────────────────────────────────────────────────
# Telemetry + result for Claude
# ─────────────────────────────────────────────────────────────────────────
record_telemetry "$CODEX_EXIT" "$BLOCKER"

# Last non-empty line of stdout for Claude to parse
echo "RESULT_PATH=$TRANSCRIPT"
exit "$CODEX_EXIT"
