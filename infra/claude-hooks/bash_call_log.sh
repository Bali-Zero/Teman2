#!/usr/bin/env bash
# bash_call_log.sh — one PostToolUse process replacing three separate inline
# Bash loggers that used to fire on every Bash tool call (per-call-hook-diet,
# 2026-09-09). Writes, in this single bash process:
#
#   1. ~/.claude/command-history.log — human-readable command trail, one
#      line per call. Command text is REDACTED before it is written (see
#      below) — this is the ONE artifact this script writes the command
#      text into directly.
#   2. the {cmd,cwd} JSON that used to be piped inline to
#      ~/.claude/scripts/hotfix-notify.sh — SAME script, SAME unredacted
#      payload, SAME byte format as before. Deliberately NOT redacted: that
#      script's own DROP/ALTER/fly-secrets classifier needs the raw command
#      (e.g. `PGPASSWORD=... psql -c 'DROP TABLE ...'` — redacting from the
#      earliest anchor would cut the PGPASSWORD assignment AND everything
#      after it, including the DROP, on exactly the command this exists to
#      catch). hotfix-notify.sh decides for itself whether to append
#      shared/hotfix_audit.jsonl + notify Telegram; this script only builds
#      its input, exactly like the inline command it replaces did.
#   3. ~/.claude/live-status.json — last-tool-call marker read by
#      tmux-briefing.sh. Never carried command text before or now.
#
# Command-text redaction uses infra/claude-hooks/redact_secrets.py (the same
# earliest-anchor-cut pattern as .claude/hooks/codex-spalla-trigger.sh,
# added after a live leak — cicatrix superscar #4). The installer
# (install_hook_diet.py) copies both files into ~/.claude/hooks/ together,
# so this script's own directory always has redact_secrets.py beside it.
#
# Input: Claude Code's PostToolUse hook convention for a Bash matcher — the
# legacy $TOOL_CALL env var (what the inline hooks this replaces relied on)
# with a stdin-JSON fallback for forward compatibility, same dual-input
# convention documented in infra/claude-hooks/mos_capture_post_tool.py.
#
# Fail-open for the tool call: exit 0, empty stdout, best-effort writes.
# Command text fails closed: redaction failure logs only a placeholder.

set -u
umask 077

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDACT_PY="$HOOK_DIR/redact_secrets.py"

PAYLOAD="${TOOL_CALL:-}"
if [ -z "$PAYLOAD" ] && [ ! -t 0 ]; then
    PAYLOAD="$(cat 2>/dev/null || true)"
fi

CMD="$(printf '%s' "$PAYLOAD" | /usr/bin/jq -r '.tool_input.command // "unknown"' 2>/dev/null)"
[ -z "$CMD" ] && CMD="unknown"

# --- 1. command-history.log (redacted) --------------------------------
HIST_FILE="$HOME/.claude/command-history.log"
mkdir -p "$(dirname "$HIST_FILE")" 2>/dev/null || true
LOGGED_CMD=""
REDACT_REASON="missing"
T="${BASH_CALL_LOG_REDACT_TIMEOUT_S:-2}"
if [[ ! "$T" =~ ^[1-9][0-9]*$ ]]; then
    T=2
elif [ "${#T}" -gt 1 ]; then
    T=10 # Cap without overflowing shell arithmetic on a huge integer.
fi
if command -v python3 >/dev/null 2>&1 && [ -f "$REDACT_PY" ]; then
    LOGGED_CMD="$(printf '%s' "$CMD" | python3 -c 'import signal,sys,runpy; signal.alarm(int(sys.argv[1])); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0], run_name="__main__")' "$T" "$REDACT_PY" 2>/dev/null)"
    REDACT_RC=$?
    if [ "$REDACT_RC" -ne 0 ]; then
        REDACT_REASON="rc=$REDACT_RC"
    elif [ -z "$LOGGED_CMD" ]; then
        REDACT_REASON="empty"
    else
        REDACT_REASON=""
    fi
fi
if [ -n "$REDACT_REASON" ]; then
    LOGGED_CMD="$(LC_ALL=C; printf '<REDACTION-FAILED reason=%s len=%s>' "$REDACT_REASON" "${#CMD}")"
fi
printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$LOGGED_CMD" >> "$HIST_FILE" 2>/dev/null || true
chmod 0600 "$HIST_FILE" 2>/dev/null || true

# --- 2. hotfix jsonl / Telegram, delegated UNCHANGED -------------------
if [ -x "$HOME/.claude/scripts/hotfix-notify.sh" ] || [ -f "$HOME/.claude/scripts/hotfix-notify.sh" ]; then
    /usr/bin/jq -nc --arg cmd "$CMD" --arg cwd "$PWD" '{cmd:$cmd, cwd:$cwd}' 2>/dev/null \
        | bash "$HOME/.claude/scripts/hotfix-notify.sh" 2>/dev/null || true
fi

# --- 3. live-status.json ------------------------------------------------
STATUS_FILE="$HOME/.claude/live-status.json"
STATUS_TMP="${STATUS_FILE}.tmp.$$"
BRANCH="$(git branch --show-current 2>/dev/null || echo n/a)"
if printf '{"ts":"%s","tool":"%s","cwd":"%s","git_branch":"%s"}' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "Bash" "$PWD" "$BRANCH" > "$STATUS_TMP" 2>/dev/null; then
    mv -f "$STATUS_TMP" "$STATUS_FILE" 2>/dev/null || rm -f "$STATUS_TMP" 2>/dev/null
fi
chmod 0600 "$STATUS_FILE" 2>/dev/null || true

exit 0
