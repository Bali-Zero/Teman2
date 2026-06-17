#!/usr/bin/env python3
"""harness_lifecycle_guard.py — SessionStart hook. Cura "Delega Invisibile del Lifecycle".
NON solo avvisa: AGISCE. Auto-svuota il vaso dei permessi (GC conservativo) + avvisa su cio' che
richiede l'operatore (memoria troncata, secret). Fail-OPEN TOTALE: qualunque errore -> sessione parte
comunque (un guardiano che blocca l'avvio e' peggio della malattia). Genesi: opus-mythos TAC 2026-06-16."""
import json, os, re, sys

HOME = os.path.expanduser("~")
MEM = f"{HOME}/.claude/projects/-Users-balizero-Desktop-nuzantara/memory/MEMORY.md"
PROJ = f"{HOME}/Desktop/nuzantara/.claude/settings.local.json"
MEM_HARD, MEM_SOFT, ALLOW_SOFT = 25600, 20000, 600


def _is_garbage(a):
    """SOLO spazzatura Bash inequivocabile. MAI pattern(*), mcp, read, o secret."""
    if not isinstance(a, str) or not a.startswith("Bash(") or "*" in a:
        return False
    if "PGPASSWORD" in a or "PASSWORD=" in a:
        return False
    if len(a) > 500:
        return True
    inner = (a[5:-1] if a.endswith(")") else a[5:]).strip().strip('"').strip("'").strip()
    if inner.startswith("#"):
        return True
    toks = re.sub(r'^(\w+=\S+\s+)+', '', inner).split()
    if not toks:
        return True
    return toks[0] in {"echo", "cd", "source", "cat", "ls", "pwd", "true", "sleep", ":"}


def _gc_permissions():
    try:
        d = json.load(open(PROJ))
        allow = d["permissions"]["allow"]
        before = len(allow)
        kept = [a for a in allow if not _is_garbage(a)]
        if len(kept) == before:
            return (before, before)
        json.dump(d, open(PROJ + ".bak-guard", "w"), indent=2, ensure_ascii=False)
        d["permissions"]["allow"] = kept
        json.dump(d, open(PROJ, "w"), indent=2, ensure_ascii=False)
        return (before, len(kept))
    except Exception:
        return None


def main():
    out = []
    gc = _gc_permissions()
    if gc and gc[0] != gc[1]:
        out.append(f"AUTO-GC permessi: {gc[0]}->{gc[1]} (rimossa spazzatura one-off, backup .bak-guard).")
    try:
        sz = os.path.getsize(MEM) if os.path.exists(MEM) else 0
        if sz >= MEM_HARD:
            out.append(f"MEMORY.md {sz}B >= {MEM_HARD} (#40614): TAIL TRONCATO. Comprimi l'indice.")
        elif sz >= MEM_SOFT:
            out.append(f"MEMORY.md {sz}B (tetto {MEM_HARD}): avvicini il troncamento.")
    except Exception:
        pass
    try:
        d = json.load(open(PROJ))
        allow = d["permissions"]["allow"]
        if len(allow) >= ALLOW_SOFT:
            out.append(f"{len(allow)} allow residui: il GC toglie one-off, i pattern restano (revisione manuale per collassarli).")
        sec = sum(1 for a in allow if isinstance(a, str) and ("PGPASSWORD" in a or "PASSWORD=" in a))
        if sec:
            out.append(f"{sec} permessi con SECRET (cicatrix #4): ruota poi pulisci (ordine, operatore).")
    except Exception:
        pass
    if out:
        print("## Harness lifecycle guard\n" + "\n".join(f"- {w}" for w in out))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
