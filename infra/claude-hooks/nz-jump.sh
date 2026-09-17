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
#
# The model in the jump file is the BARE id the hook payload carries
# (claude-opus-5); the window the old session actually had comes from the
# settings alias (opus[1m]). Passing the bare id restarts the successor at
# 200K (measured 2026-09-18 on M5: 11 opus jump files, every one bare), so the
# `[1m]` suffix is kept when this seat's default model carries it for the same
# family (`opus[1m]`) or the same id (`claude-opus-5[1m]`). Nothing is invented
# for another family or for a default without the suffix.
# NZ_JUMP_DRY=1 prints the argv one per line and exits 0 instead of launching
# (test seam: scripts/tests/test_nz_jump_model_alias.py).
set -u
FROM="${1:-}"
PENDING="$HOME/.organism/context-guard/pending-jump-$FROM.json"
[ -n "$FROM" ] && [ -f "$PENDING" ] || { echo "nz-jump: no pending jump for '${FROM:-?}'"; exit 1; }
eval "$(python3 - "$PENDING" <<'EOF'
import json, os, shlex, sys
d = json.load(open(sys.argv[1]))
model = str(d.get("model") or "")
config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
try:
    default = str(json.load(open(os.path.join(config_dir, "settings.json"))).get("model") or "")
except Exception:
    default = ""
if model and "[1m]" not in model and default.endswith("[1m]"):
    base = default[:-len("[1m]")]
    if base == model or ("-" not in base and model.startswith(f"claude-{base}-")):
        model += "[1m]"
d["model"] = model
for k in ("model", "cwd", "hops", "permission_mode"):
    print(f"{k.upper()}=" + shlex.quote(str(d.get(k) or "")))
EOF
)"
[ -n "$CWD" ] && [ -d "$CWD" ] && cd "$CWD"
ARGS=()
[ -n "$MODEL" ] && ARGS+=(--model "$MODEL")
[ -n "$PERMISSION_MODE" ] && ARGS+=(--permission-mode "$PERMISSION_MODE")
if [ -n "${NZ_JUMP_DRY:-}" ]; then
    printf 'nz-jump: dry-run argv\n'
    printf '%s\n' claude "${ARGS[@]}"
    exit 0
fi
echo "nz-jump: continuing session $FROM (hop ${HOPS:-?}) in $(pwd)"
export NZ_JUMP_FROM="$FROM"
exec claude "${ARGS[@]}" \
    "Sei la finestra successiva della sessione $FROM (salto ${HOPS:-?}). Il mandato originale e lo stato raggiunto sono nel contesto iniettato da context_jump_resume: continua da lì, senza chiedere, e non ripetere il lavoro già verificato."
