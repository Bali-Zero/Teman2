#!/usr/bin/env python3
"""
m5_block_heavy_brew.py — PreToolUse(Bash) hook.
Blocca l'installazione di TOOL PESANTI su Air-M5 (thin-client).
Regola R1 mappa thin-client: i tool pesanti vivono sul Pro/Mini, su M5 si usano via ssh pro.
Enforcement vero (il system prompt non basta — test 50-casi 2026-06-01: 3 FAIL + 16 PARTIAL
offrivano 'brew install <pesante>' come scappatoia).

Si attiva SOLO su M5 (user balizero). Sul Pro (user nuzantara) è no-op: là i tool DEVONO stare.
Protocollo hook: legge JSON da stdin, exit 2 + messaggio su stderr = BLOCCA il tool call.
Kill switch: env M5_HEAVY_BREW_GUARD=off.
"""
import json
import os
import re
import sys

# Tool pesanti che NON devono essere installati su M5 (lista R1 + modelli)
HEAVY = {
    "ffmpeg", "ffmpeg-full", "cmake", "ollama", "cloudflared", "ghostscript",
    "gcc", "qdrant", "redis",
}
# NOTE 2026-06-12 (M5 local PostgreSQL spec): postgresql* REMOVED from HEAVY (§2.4) —
# M5 runs a local PG17 for the CI-parity pre-push test gate + dev snapshot.
# flyctl/fly REMOVED too: M5 had no native flyctl (`fly` was a shell-function proxying
# ssh→Pro), so `fly proxy` for nuz_db_refresh.sh (AC4 prod snapshot) opened the tunnel
# on the Pro, unreachable by the local M5 pg_dump. Native flyctl makes the snapshot
# self-contained (proxy+dump+restore all local), per the "dev uguale al Pro" doctrine.
# Redis/Qdrant stay blocked (same snapshot pattern available later; for now Pro/Mini only).


def main() -> int:
    # Kill switch
    if os.environ.get("M5_HEAVY_BREW_GUARD", "").lower() == "off":
        return 0

    # Solo su M5 (user balizero). Sul Pro (nuzantara) i tool DEVONO esserci → no-op.
    if os.environ.get("USER") != "balizero":
        return 0

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # input illeggibile → non bloccare (fail-open, è un guard non un veto cieco)

    cmd = (data.get("tool_input", {}) or {}).get("command", "") or ""
    if "brew install" not in cmd and "brew reinstall" not in cmd:
        return 0

    # 'brew install' deve essere un COMANDO vero, non testo dentro una stringa quotata
    # (es. mem save "...brew install ffmpeg..." o echo). Heuristica: ignora se il match
    # è dentro una coppia di virgolette. Matcha solo a inizio comando o dopo ; && | & ( newline.
    m = re.search(r"(?:^|[;&|(\n]|\bsudo\s+)\s*brew\s+(?:install|reinstall)\s+([^\n;&|()'\"]+)", cmd)
    if not m:
        return 0
    # Se il pezzo di comando è racchiuso tra virgolette nel contesto, è un argomento testuale.
    # Conta le virgolette prima del match: se dispari, siamo dentro una stringa → non un comando.
    prefix = cmd[: m.start()]
    if prefix.count('"') % 2 == 1 or prefix.count("'") % 2 == 1:
        return 0
    tokens = [t for t in m.group(1).split() if not t.startswith("-")]
    hit = sorted(set(t.lower() for t in tokens) & HEAVY)
    if not hit:
        return 0

    pkgs = ", ".join(hit)
    sys.stderr.write(
        f"\n🛑 BLOCCATO: 'brew install {pkgs}' su Air-M5 (thin-client).\n"
        f"Regola R1: i tool pesanti vivono sul Pro, NON su M5 (blast-radius minimo, telecomando leggero).\n"
        f"Usa il Pro via SSH invece di installare localmente:\n"
        f"  ssh pro '{hit[0]} ...'        # il tool gira sul Pro, l'output torna qui\n"
        f"Se serve VERAMENTE in locale (caso eccezionale, chiedi ad Antonello): M5_HEAVY_BREW_GUARD=off.\n"
    )
    return 2  # exit 2 = blocca il tool call


if __name__ == "__main__":
    sys.exit(main())
