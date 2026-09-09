#!/usr/bin/env bash
# host_boundary_reminder_sessionstart.sh — SessionStart reminder while
# host_boundary is DISARMED.
#
# RULING (Zero, 2026-09-09): host_boundary (the guard that protects
# ~/.claude, ~/.ssh, ~/.aws, secrets and ~/.agent/decisions from writes)
# stays disarmed on Pro/M5/Mini via HOST_BOUNDARY_OFF=1 in each machine's
# ~/.claude/settings.json env block, until Zero decides otherwise. A
# disarmed guard that nobody is reminded of is cicatrix scar #2's own
# shape (Esiste!=Armato, in reverse: here the guard genuinely does not
# exist right now, and the risk is forgetting that fact) — this receptor
# closes that blindness the same way escalations_alert_sessionstart.sh
# closes the escalations-board one: a fact the harness already knows
# (the env var) becomes something every session is actually told.
#
# Logic: HOST_BOUNDARY_OFF == "1" in the process env -> emit ONE short
# Italian block (<=400 bytes) naming the ruling, what it protects, and
# the re-arm route: a `!`-prefixed line typed at the Claude Code prompt
# bar, which runs in the session's own shell — NOT through PreToolUse
# hooks — so it is not itself blocked by anything. It backs up
# ~/.claude/settings.json to .json.bak, then removes the
# HOST_BOUNDARY_OFF key from its env block. Any other value (unset, "0",
# "false", ...) -> print nothing, exit 0.
#
# FAIL-OPEN, same discipline as every sibling SessionStart receptor in
# this directory: missing python3, malformed env, any error -> silent,
# exit 0. A reminder hook that can crash session start is worse than no
# reminder at all.
#
# Kill switch: HOST_BOUNDARY_REMINDER_ENABLED=false

set -o pipefail

[[ "${HOST_BOUNDARY_REMINDER_ENABLED:-true}" == "false" ]] && exit 0

# Nothing to remind about unless the guard is actually disarmed.
[[ "${HOST_BOUNDARY_OFF:-}" == "1" ]] || exit 0

PY="$(command -v python3 2>/dev/null)"
[[ -n "$PY" ]] || exit 0

_TIMEOUT=()
if command -v timeout >/dev/null 2>&1; then _TIMEOUT=(timeout 4)
elif command -v gtimeout >/dev/null 2>&1; then _TIMEOUT=(gtimeout 4); fi

"${_TIMEOUT[@]}" "$PY" - <<'PYEOF' 2>/dev/null || exit 0
import json

# Re-arm one-liner (route printed verbatim below): typed with a `!` prefix
# at the prompt bar, runs in the session's own shell, not through
# PreToolUse hooks. Backs up ~/.claude/settings.json to .json.bak first,
# then drops HOST_BOUNDARY_OFF from the env block.
ONE_LINER = (
    "python3 -c \"import json,os;"
    "h=os.path.expanduser('~/.claude/settings.json');"
    "open(h+'.bak','w').write(open(h).read());"
    "d=json.load(open(h));"
    "d.get('env',{}).pop('HOST_BOUNDARY_OFF',0);"
    "json.dump(d,open(h,'w'),indent=2,ensure_ascii=False)\""
)

ctx = (
    "\U0001f6e1️ host_boundary DISARMATO (HOST_BOUNDARY_OFF=1, Zero 2026-09-09). "
    "Protegge ~/.claude ~/.ssh ~/.aws segreti ~/.agent/decisions da scrittura. "
    f"Riarma da prompt: ! {ONE_LINER}"
)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx,
    }
}))
PYEOF

exit 0
