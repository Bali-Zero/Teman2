#!/usr/bin/env bash
# codex-spalla-trigger.sh — PostToolUse hook (telemetry-only, NO auto-spawn)
#
# Suggests `/codex-second-opinion` to the user when they touch high-risk paths,
# without actually dispatching Codex. Pure observability for week-1 learning.
#
# Configured via .claude/settings.json `hooks.PostToolUse`. The harness invokes
# this with a JSON event payload on stdin describing the tool call that just
# completed. We parse it, decide if the action is a strong spalla candidate,
# log to ~/logs/codex-spalla-trigger.jsonl, and emit a one-line stderr nudge.
#
# Hard rules (per docs/decisions/2026-05-03-codex-spalla-architecture.md):
#   - NEVER auto-spawn Codex. Suggestion only.
#   - Burn no quota. Stay cheap.
#   - Fail-open: any error or unexpected payload exits 0 silently.

set -u  # NOT -e: we want to fail open, not propagate errors.

# SECRET HYGIENE (added 2026-08-21 after a live leak; cicatrix superscar #4).
# This hook logs `tool_input.command` verbatim. A Bash tool call can carry a
# credential in argv, so this log is secret-bearing BY CONSTRUCTION -- and it
# was being created world-readable (0644) and never redacted. Measured on the
# live file: 11 real `sk-ant-oat...` values, 108 chars each, mode 0644, still
# being appended to. Two independent defenses, because either alone fails:
#   (1) umask 077 so the file can never be born readable by anyone else, plus
#       an explicit chmod for a file that already exists at the old mode --
#       `>>` does NOT change the mode of an existing file, so the umask alone
#       would leave every pre-existing log exposed forever;
#   (2) redaction of the value itself, so the log is safe even if the mode is
#       later widened by a rotation, a copy, or a backup that resets it.
umask 077

LOG_FILE="$HOME/logs/codex-spalla-trigger.jsonl"
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
chmod 0600 "$LOG_FILE" 2>/dev/null || true

# Read event payload from stdin (JSON). If unparseable, exit 0 quietly.
PAYLOAD="$(cat 2>/dev/null || true)"
[[ -z "$PAYLOAD" ]] && exit 0

# Extract fields with python (jq may not be available; python3 is).
TOOL_NAME="$(printf '%s' "$PAYLOAD" | python3 -c 'import sys,json
try:
    d = json.load(sys.stdin)
    print(d.get("tool_name") or d.get("toolName") or "")
except Exception:
    pass' 2>/dev/null || echo "")"

[[ -z "$TOOL_NAME" ]] && exit 0

TARGET="$(printf '%s' "$PAYLOAD" | python3 -c 'import sys,json
try:
    d = json.load(sys.stdin)
    inp = d.get("tool_input") or d.get("toolInput") or {}
    # Edit/Write: file_path. Bash: command. Read: file_path.
    print(inp.get("file_path") or inp.get("command") or "")
except Exception:
    pass' 2>/dev/null || echo "")"

# ─────────────────────────────────────────────────────────────────────────
# Trigger rules
# ─────────────────────────────────────────────────────────────────────────
SUGGEST="false"
REASON=""

# Rule 1: gh pr create (always)
if [[ "$TOOL_NAME" == "Bash" ]] && printf '%s' "$TARGET" | grep -qE 'gh pr create\b'; then
    SUGGEST="true"
    REASON="pr-create"
fi

# Rule 2: large git diff touching sensitive keywords
if [[ "$TOOL_NAME" == "Bash" ]] && printf '%s' "$TARGET" | grep -qE 'git diff\b'; then
    # We don't have the diff output here, only the command. As a heuristic,
    # flag if the command itself names a sensitive area.
    if printf '%s' "$TARGET" | grep -qiE 'auth|payment|migration|pricing|webhook|partner|commission|alembic'; then
        SUGGEST="true"
        REASON="sensitive-diff"
    fi
fi

# Rule 3: Edit/Write on sensitive paths
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" ]]; then
    if printf '%s' "$TARGET" | grep -qE 'apps/backend-rag/backend/services/(auth|pricing|partner|commission|payment)'; then
        SUGGEST="true"
        REASON="sensitive-service-edit"
    fi
    if printf '%s' "$TARGET" | grep -qE 'alembic/versions/[^/]+\.py$'; then
        SUGGEST="true"
        REASON="migration-file"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────
# Log + emit
# ─────────────────────────────────────────────────────────────────────────
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Always log even non-suggesting events (gives us denominator for tuning)
# Redact BEFORE truncating: a 200-char window can slice a token in half and
# leave a usable prefix, and it can also carry a whole short one.
#
# The suffix wildcard on the variable-name branch is the load-bearing detail.
# A redactor written as `TOKEN=` matches CLAUDE_CODE_OAUTH_TOKEN= and misses
# CLAUDE_CODE_OAUTH_TOKEN_1= -- that exact off-by-one is how four tokens were
# printed by a probe that believed it was redacting. `[A-Z0-9_]*` after the
# keyword is what closes it.
TARGET_JSON="$(printf '%s' "$TARGET" | python3 -c '
import sys, re, json
s = sys.stdin.read()
# 1. Known credential shapes, by their own prefixes.
s = re.sub(r"sk-ant-[A-Za-z0-9_-]{8,}", "sk-ant-<REDACTED>", s)
s = re.sub(r"gh[pousr]_[A-Za-z0-9]{8,}", "gh_<REDACTED>", s)
s = re.sub(r"github_pat_[A-Za-z0-9_]{8,}", "github_pat_<REDACTED>", s)
# 2. Anything ASSIGNED to a secret-ish variable name, suffixes included.
s = re.sub(
    r"\b([A-Z][A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Z0-9_]*)"
    r"\s*[=:]\s*[\"\x27]?[^\s\"\x27]+",
    r"\1=<REDACTED>",
    s,
)
print(json.dumps(s[:200]))
' 2>/dev/null || echo '""')"
{
    printf '{"ts":"%s","tool":"%s","target":%s,"suggested":%s,"reason":"%s"}\n' \
        "$TS" "$TOOL_NAME" "$TARGET_JSON" "$SUGGEST" "$REASON"
} >> "$LOG_FILE" 2>/dev/null || true

if [[ "$SUGGEST" == "true" ]]; then
    echo "[spalla-suggest] consider /codex-second-opinion before commit (reason: $REASON)" >&2
fi

exit 0
