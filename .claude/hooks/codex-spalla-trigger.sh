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
# live file, mode 0644 and still being appended to: 14 lines match the literal
# `sk-ant-oat`, but a length histogram of the runs (8x10, 5x13, 1x46, 1x87,
# 1x108) shows 13 are the bare literal with no secret material -- only 3 runs
# carry any. Of those 3, magnitude is 1 whole token + 2 truncation-clipped
# partials, not "2 whole tokens": measured by END POSITION inside the
# 200-char logged field, the 108-char run ends at char 151 -- well short of
# the boundary, i.e. a complete token -- while the 87-char and 46-char runs
# both end EXACTLY at char 200, the truncation boundary itself, which is what
# a partial cut off mid-token looks like, not proof of two more full-length
# secrets. CORRECTED 2026-08-21 by the Gear-3 gate, twice: the first draft of
# this comment said "11 real values, 108 chars each" (a LINE count restated
# as a VALUE count, and the maximum restated as "each"); a later draft said
# "2 whole tokens" (a truncation artifact restated as two more complete
# secrets). The leak is real; the magnitude was inflated both times, in the
# very comment that preaches counting by run length. Two independent
# defenses, because either alone fails:
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
# ORDERING CAVEAT, measured, because the obvious reading is wrong: redacting
# BEFORE truncating is not strictly protective. Redaction SHORTENS the string,
# which pulls bytes that the 200-char window used to cut off INTO the window.
# Proven on a 277-char command with a secret at char 253: truncate-only left it
# out; redact-then-truncate brought a following fragment in. The ordering is
# still right — it is the only order that can redact a secret sitting inside
# the window at all — but it trades one exposure for a smaller one rather than
# eliminating exposure.
#
# KNOWN BLIND SPOTS of the value branch (a redactor that claims a closed class
# is worse than one that names its holes): it only fires on `NAME=value` or
# `NAME: value` shapes. A secret passed positionally with no name at all
# (`mytool deploy s3cr3t`) is NOT redacted by that branch — only the prefix
# rules above can catch it, and only if it carries a known prefix.
#
# OVER-MATCH residual risk (cicatrix superscar #3, the guard-over-match twin
# of the under-match spot above): the keyword must be a delimited SEGMENT
# (see below) to fire, but it is still a bare keyword match with no notion of
# "is this actually a secret" -- a config line that legitimately names a
# non-secret value with a `_KEY=`/`_TOKEN=`-suffixed identifier (e.g. an
# internal cache-partition or feature-flag name) redacts just as hard as a
# real credential. The guilt/innocence corpus in
# scripts/tests/test_codex_spalla_trigger_redaction.sh proves the specific
# forms it enumerates stay innocent; it is not a proof that no legitimately-
# named non-secret value anywhere can still trip the keyword-segment match.
# Given the choice between over-redacting a non-secret and under-redacting a
# real one, this hook accepts the former.
#
# The wildcards on BOTH SIDES of the keyword are the load-bearing detail.
# A redactor written as `TOKEN=` matches CLAUDE_CODE_OAUTH_TOKEN= and misses
# CLAUDE_CODE_OAUTH_TOKEN_1= -- that exact off-by-one is how four tokens were
# printed by a probe that believed it was redacting. But the first version of
# THIS fix then required at least one char BEFORE the keyword, so it caught
# CLAUDE_CODE_OAUTH_TOKEN_1= and missed a bare TOKEN= — the same off-by-one,
# mirrored, found by the Gear-3 gate on this diff. Wildcards on both sides,
# case-insensitive, are what close the class -- each side is delimited by
# `_`/`-`/string-start-or-end, plus a negative lookbehind on the left that
# also excludes a preceding `.` (so `foo.key = x` attribute access is
# innocent). MEASURED, not assumed: the optional leading `(?:--?)?` does NOT
# widen coverage and does NOT even change the redacted output -- a leading
# `-`/`--` is neither alnum nor `.`, so the lookbehind already lets the match
# start right after it either way. Driven side-by-side (with and without
# `(?:--?)?`) through the real hook across the full guilt+innocence+flag
# corpus: byte-identical output in every case, including `--token=`/`-key=`
# flag forms. It is dead weight in this regex, not a coverage or even a
# readability lever.
TARGET_JSON="$(printf '%s' "$TARGET" | python3 -c '
import sys, re, json
s = sys.stdin.read()
# 1. Known credential shapes, by their own prefixes.
s = re.sub(r"sk-ant-[A-Za-z0-9_-]{8,}", "sk-ant-<REDACTED>", s)
s = re.sub(r"gh[pousr]_[A-Za-z0-9]{8,}", "gh_<REDACTED>", s)
s = re.sub(r"github_pat_[A-Za-z0-9_]{8,}", "github_pat_<REDACTED>", s)
# 2. Anything ASSIGNED to a secret-ish variable name, suffixes included.
s = re.sub(
    r"(?i)((?<![A-Za-z0-9.])(?:--?)?(?:[A-Za-z0-9]+[_-])*"
    r"(?:TOKEN|KEY|SECRET|PASSWORD|PASSWD|CREDENTIAL)(?:[_-][A-Za-z0-9]+)*)"
    r"\s*[=:]\s*(?:\"[^\"]*\"|\x27[^\x27]*\x27|[^\s\"\x27]+)",
    lambda m: m.group(1) + "=<REDACTED>",
    s,
)
# 3. Bearer/Authorization, which carry no keyword in a NAME at all.
s = re.sub(
    r"(?i)\b(Authorization\s*:\s*Bearer|Bearer)\s+[A-Za-z0-9._-]{8,}",
    r"\1 <REDACTED>",
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
