#!/usr/bin/env python3
"""memory_budget_gate.py — PreToolUse gate: keep MEMORY.md under its read limit.

WHY THIS EXISTS
---------------
`MEMORY.md` is the memory index, and it is INJECTED into every session's context.
The harness reads at most ~24.4 KiB of it. Past that byte the tail is dropped
**silently**: no error, no warning to the reader, and the entries that disappear
are the ones at the BOTTOM — which in this file are the "Workflow rules
(load-bearing per Claude)".

Measured 2026-08-24: the index sat at 25.4 KB, i.e. already over the cliff, and
had been dropping its tail for an unknown period. Nothing caught it, because the
only existing signal is a POST-write warning that no one is obliged to act on.
Every session that appends a hard-won scar does the right thing individually and
the file sinks anyway — a commons with no enforcement.

This gate turns that warning into a constraint: a write that would push the index
past the cliff is REFUSED, so whoever adds an entry must first retire one (or move
a body into a `MEMORY_*.md` topic file). Same family as cicatrice #2 (Esiste ≠
Armato): a number nobody is obliged to look at protects nothing.

DESIGN PROPERTIES (each one is load-bearing — do not "simplify" them away)
-------------------------------------------------------------------------
1. **A shrinking write is ALWAYS allowed, even while over the limit.**
   Without this the gate deadlocks the very compaction needed to get back under,
   and the file could never be repaired. This is the most important rule here.
2. **Fail-open on uncertainty.** Unparseable payload, unreadable file, unknown
   tool shape -> exit 0. A false block costs a session its memory save; a false
   allow costs a few hundred bytes. The asymmetry is deliberate.
3. **Byte-accurate, UTF-8.** This file is full of emoji and accented Italian;
   len(str) would under-count badly and the gate would fire late.
4. **Path-aware.** M5 is `-Users-balizero`, Pro/Mini are `-Users-nuzantara`.
   Match structurally (`.claude/projects/*/memory/MEMORY.md`), never by hardcoded
   username — cicatrice #1.
5. **Topic files are exempt.** MEMORY_LATEST_WORK.md and friends are NOT injected;
   they are where bodies are supposed to go, so capping them would defeat the cure.

Exit 2 + stderr = block. Exit 0 = allow.
Kill switch: MEMORY_BUDGET_GATE=off
"""

import json
import os
import pathlib
import sys

# The harness read limit. 24.4 KiB — verified empirically 2026-08-24: at 25067 B
# it reported "over its 24.4KB read limit", at 24414 B "approaching".
HARD_LIMIT_BYTES = int(os.environ.get("MEMORY_BUDGET_LIMIT_BYTES", 24 * 1024 + 409))


def _is_memory_index(path_str: str) -> bool:
    """True only for a MEMORY.md that is an injected index.

    Structural match, not a username match:
    `.../.claude/projects/<anything>/memory/MEMORY.md`.
    """
    try:
        p = pathlib.Path(path_str).expanduser()
    except (ValueError, OSError):
        return False
    if p.name != "MEMORY.md":
        return False
    # .../.claude/projects/<project>/memory/MEMORY.md
    #      [-5]     [-4]      [-3]     [-2]    [-1]
    parts = p.parts
    if len(parts) < 5:
        return False
    return (
        parts[-2] == "memory"
        and parts[-4] == "projects"
        and parts[-5] == ".claude"
    )


def _b(s: str) -> int:
    return len(s.encode("utf-8"))


def _predicted_size(tool: str, ti: dict, path: pathlib.Path, current: int):
    """Return predicted byte size after the write, or None if not computable."""
    if tool == "Write":
        content = ti.get("content")
        if not isinstance(content, str):
            return None
        return _b(content)

    if tool in ("Edit", "MultiEdit"):
        edits = ti.get("edits") if tool == "MultiEdit" else [ti]
        if not isinstance(edits, list):
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        delta = 0
        for e in edits:
            if not isinstance(e, dict):
                return None
            old = e.get("old_string")
            new = e.get("new_string")
            if not isinstance(old, str) or not isinstance(new, str):
                return None
            # An old_string that is not present means the Edit will fail anyway,
            # so it must contribute ZERO — otherwise the gate blocks a write that
            # would never have landed.
            occurrences = text.count(old)
            count = occurrences if e.get("replace_all") else (1 if occurrences else 0)
            if count == 0:
                continue
            delta += (_b(new) - _b(old)) * count
        return current + delta

    return None


def main():
    if os.environ.get("MEMORY_BUDGET_GATE", "").lower() == "off":
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # fail-open (property 2)
    if not isinstance(payload, dict):
        sys.exit(0)

    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    if not isinstance(ti, dict):
        sys.exit(0)

    file_path = ti.get("file_path", "")
    if not isinstance(file_path, str) or not _is_memory_index(file_path):
        sys.exit(0)

    p = pathlib.Path(file_path).expanduser()
    try:
        current = p.stat().st_size
    except OSError:
        sys.exit(0)  # new file / unreadable -> fail-open

    predicted = _predicted_size(tool, ti, p, current)
    if predicted is None:
        sys.exit(0)  # fail-open (property 2)

    if predicted <= HARD_LIMIT_BYTES:
        sys.exit(0)

    # Over the limit. Property 1: never stand in the way of a shrinking write.
    if predicted < current:
        sys.exit(0)

    over = predicted - HARD_LIMIT_BYTES
    sys.stderr.write(
        f"[MEMORY-BUDGET] BLOCCATO: questa scrittura porterebbe l'indice a "
        f"{predicted} byte, oltre il limite di lettura di {HARD_LIMIT_BYTES}.\n"
        f"  attuale:  {current} byte\n"
        f"  previsto: {predicted} byte  (+{predicted - current}, {over} oltre il limite)\n"
        f"\n"
        f"Oltre quel byte il harness TRONCA in silenzio: le voci in fondo — le\n"
        f"Workflow rules — spariscono dal contesto senza alcun errore. Aggiungere\n"
        f"qui una voce senza toglierne un'altra non la salva: la paga la coda.\n"
        f"\n"
        f"Per procedere, libera spazio PRIMA (una sola di queste basta):\n"
        f"  1. Sposta il corpo di una voce grassa in un file-tema MEMORY_<TEMA>.md\n"
        f"     e lascia qui una riga-puntatore (e' il pattern che il file usa gia':\n"
        f"     MEMORY_SHELL_CLI_TRAPS.md, MEMORY_VERIFICATION_RULES.md, ...).\n"
        f"  2. Ritira una voce SUPERATA secondo il criterio del preambolo — (a) gia'\n"
        f"     auto-caricata da CLAUDE.md/cicatrix-superscar.md, o (b) chiusa con la\n"
        f"     cura viva — spostandola in MEMORY_ARCHIVE.md verbatim, col motivo.\n"
        f"\n"
        f"Una scrittura che RIMPICCIOLISCE l'indice non e' mai bloccata, anche se il\n"
        f"file e' gia' oltre il limite: comprimi pure liberamente.\n"
        f"Kill switch (motivalo): MEMORY_BUDGET_GATE=off\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
