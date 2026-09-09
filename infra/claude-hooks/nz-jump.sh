#!/bin/bash
# nz-jump <from_session> — what window_jump.sh types into the new Ghostty window.
# Installed as ~/.claude/scripts/nz-jump (on PATH). Reads the per-session
# pending-jump-<from>.json, moves to the old session's cwd and starts a FRESH
# `claude` (new session id, empty history — never --resume/--continue/
# --fork-session, which inherit the old context) with the old session's model
# and permission mode and a short continuation prompt. The real content —
# original mandate, commands that succeeded, files touched, next action — is
# injected by the SessionStart hook context_jump_resume.py from the jump file
# and the handoff, so nothing long ever travels through keystrokes.
set -u
FROM="${1:-}"
PENDING="$HOME/.organism/context-guard/pending-jump-$FROM.json"
[ -n "$FROM" ] && [ -f "$PENDING" ] || { echo "nz-jump: no pending jump for '${FROM:-?}'"; exit 1; }
eval "$(python3 - "$PENDING" <<'EOF'
import json, shlex, sys
d = json.load(open(sys.argv[1]))
for k in ("model", "cwd", "hops", "permission_mode"):
    print(f"{k.upper()}=" + shlex.quote(str(d.get(k) or "")))
EOF
)"
[ -n "$CWD" ] && [ -d "$CWD" ] && cd "$CWD"
ARGS=()
[ -n "$MODEL" ] && ARGS+=(--model "$MODEL")
[ -n "$PERMISSION_MODE" ] && ARGS+=(--permission-mode "$PERMISSION_MODE")
echo "nz-jump: continuing session $FROM (hop ${HOPS:-?}) in $(pwd)"
exec claude "${ARGS[@]}" \
    "Sei la finestra successiva della sessione $FROM (salto ${HOPS:-?}). Il mandato originale e lo stato raggiunto sono nel contesto iniettato da context_jump_resume: continua da lì, senza chiedere, e non ripetere il lavoro già verificato."
