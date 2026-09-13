#!/usr/bin/env python3
"""context_jump_resume.py — SessionStart injector for the window jump.

The receiving half of the jump (Ruling Zero 2026-09-09). When
context_window_guard.py trips it writes ~/.organism/context-guard/pending-jump-<from>.json
(one file PER SESSION — two windows jumping at once never overwrite each other)
and the new window is opened by window_jump.sh / nz-jump (interactive) or by
the cascade wrapper re-invoking `claude -p` (headless). This hook runs at the
start of EVERY session (SessionStart, matcher `startup`) and:

  - picks ONLY the jump this window was opened FOR: `NZ_JUMP_FROM=<from>` in
    the env, set by nz-jump.sh (interactive, typed by window_jump.sh or by a
    human) and by the cascade wrapper's hop (headless). That file must still be
    unclaimed (`to_session` null), fresh (< MAX_AGE_S) and not our own;
  - a window opened BY HAND (plain `claude`, no NZ_JUMP_FROM) gets NOTHING.
    Until 2026-09-09 it fell back to "the freshest unclaimed same-cwd jump",
    so for 15 minutes after every guard trip any window Zero opened in
    ~/nuzantara was handed a stale mandate plus "continua senza chiedere" and
    started working on its own instead of waiting for the owner's prompt
    (Zero, Pro 2026-09-09 23:50: "quando apro comincia a fare quello che vuole
    e non aspetta il mio prompt"). The launcher knows the id, so it says it;
    nobody else is a continuation;
  - injects it as `additionalContext` (the documented SessionStart field): the
    original mandate in full (carried in the jump file across hops — the hop-2
    transcript's first prompt is nz-jump's stub, not the mandate), successful
    commands, files touched, risks, next action, hop count;
  - stamps `to_session` = this session id, so window_jump.sh knows the new
    window is alive and may close the old one, and so a second SessionStart
    (another window, a subagent) never claims the same jump;
  - otherwise stays MUTE (no output, exit 0). Never blocks anything.

PII note (CLAUDE.md §4): the mandate is the owner's own prompt, copied
verbatim between two of the owner's windows on the same machine; it is not an
output artifact. It still lives on disk under ~/.organism: keep client PII out
of mandates, as the ledger rule already asks.
Kill switch: CONTEXT_JUMP_OFF=1.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

MAX_AGE_S = 15 * 60
STATE_DIR = Path("~/.organism/context-guard").expanduser()


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def pick_jump(state_dir: Path, cwd: str, session_id: str, now: float | None = None,
              want: str | None = None):
    """The jump this session was opened FOR — and only that one.

    `want` (NZ_JUMP_FROM in the env, set by nz-jump.sh and by the cascade
    wrapper's hop) names the originating session outright: that file is
    considered, still only if unclaimed, fresh and not our own. Without it
    the answer is None: a window opened by hand is Zero's window, not a
    continuation. Cross-family review (codex, 2026-09-09) had already shown
    the old same-cwd fallback let a stranger session claim a jump meant for
    another window; the same evening it handed a hand-opened interactive
    session a stale mandate. `cwd` is kept in the signature for the payload
    but is no longer a filter — the launcher has already cd'd into the jump's
    cwd, and a hand-opened window is refused whatever its cwd."""
    if not want:
        return None
    now = time.time() if now is None else now
    p = state_dir / f"pending-jump-{want}.json"
    j = _load(p)
    if not isinstance(j, dict) or j.get("to_session"):
        return None
    try:
        ts = float(j.get("ts") or 0)
    except (TypeError, ValueError):
        return None
    if now - ts > MAX_AGE_S or j.get("from_session") == session_id:
        return None
    return (p, j)


def build_context(jump: dict, handoff: dict | None) -> str:
    lines = [
        f"🪟 SALTO DI FINESTRA — sei la continuazione della sessione {jump.get('from_session')} "
        f"(salto {jump.get('hops', 0)}). Il contesto precedente era pieno: NON è stato compattato, "
        f"riparti da questo stato e non ripetere il lavoro già verificato.",
    ]
    mandate = (jump.get("mandate") or (handoff or {}).get("mandate") or "").strip()
    if mandate:
        lines += ["", "## Mandato originale (integrale)", mandate]
    if handoff:
        obj = handoff.get("objective") or []
        if obj and not mandate:
            lines += ["", "## Ultimi prompt utente"] + [f"- {o}" for o in obj]
        ok = handoff.get("successful_commands") or []
        if ok:
            lines += ["", "## Comandi riusciti (ultimi)"] + [f"- {c}" for c in ok[-15:]]
        files = handoff.get("successful_file_changes") or []
        if files:
            lines += ["", "## File modificati"] + [f"- {f}" for f in files[-20:]]
        risks = handoff.get("risks") or []
        if risks:
            lines += ["", "## Rischi rilevati"] + [f"- {r}" for r in risks]
        lines += ["", "## Prossima azione dichiarata", str(handoff.get("next_action") or "(deduci dal mandato)")]
        lines += ["", f"Handoff completo: {jump.get('handoff_path')}"]
    else:
        lines += ["", f"(handoff non leggibile: {jump.get('handoff_path')} — ricostruisci da `mem recent`)"]
    lines += ["", "Prima di lavorare: `~/.claude/scripts/mem recent` per le decisioni salvate dalla finestra precedente."]
    return "\n".join(lines)


def main() -> int:
    if os.environ.get("CONTEXT_JUMP_OFF") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    session_id = str(payload.get("session_id") or "")
    if not session_id or not STATE_DIR.is_dir():
        return 0
    cwd = str(payload.get("cwd") or os.getcwd())
    picked = pick_jump(STATE_DIR, cwd, session_id, want=os.environ.get("NZ_JUMP_FROM") or None)
    if not picked:
        return 0
    path, jump = picked

    handoff = _load(Path(str(jump.get("handoff_path") or "")).expanduser()) if jump.get("handoff_path") else None
    ctx = build_context(jump, handoff if isinstance(handoff, dict) else None)

    jump["to_session"] = session_id
    jump["claimed_ts"] = time.time()
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(jump, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass  # inject anyway: a lost stamp costs one manual close, not the mandate

    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": ctx}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
