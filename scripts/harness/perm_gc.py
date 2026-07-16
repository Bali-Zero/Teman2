#!/usr/bin/env python3
"""perm_gc.py — garbage-collector dei permessi auto-accumulati (settings.local.json).
CONSERVATIVO: rimuove SOLO spazzatura inequivocabile, MAI pattern/mcp/read (quelli sono regole sane).
Default dry-run. APPLY=1 per scrivere (con backup). Genesi: opus-mythos TAC harness — "il guardiano svuota"."""
import json, os, re, sys

P=os.path.expanduser("~/nuzantara/.claude/settings.local.json")
APPLY=os.environ.get("APPLY")=="1"
d=json.load(open(P))
allow=d["permissions"]["allow"]
before=len(allow)

def is_garbage(a):
    if not isinstance(a,str): return False
    if not a.startswith("Bash("): return False          # tocca SOLO Bash
    if "*" in a: return False                            # MAI rimuovere un pattern (è una regola)
    inner=a[len("Bash("):-1] if a.endswith(")") else a[len("Bash("):]
    inner=inner.strip().strip('"').strip("'").strip()
    # spazzatura inequivocabile:
    if len(a)>500: return True                            # script embeddato (incidente, non permesso)
    if inner.startswith("#"): return True                # commento salvato come permesso
    first=re.sub(r'^(\w+=\S+\s+)+','',inner).split()
    if not first: return True
    cmd=first[0]
    # one-off banali che non servono mai come permesso permanente:
    JUNK={"echo","cd","source","cat","ls","pwd","true","sleep",":"}
    if cmd in JUNK: return True
    return False

# NON tocco i secret qui (argomento password chiuso — aspettano rotazione)
def has_secret(a): return isinstance(a,str) and ("PGPASSWORD" in a or "PASSWORD=" in a)

garbage=[a for a in allow if is_garbage(a) and not has_secret(a)]
kept=[a for a in allow if a not in garbage]

print(f"TOT allow: {before}")
print(f"  spazzatura rimovibile (literali one-off + 36 script-mostro): {len(garbage)}")
print(f"  TENUTI (pattern sani + mcp + read + literali utili + 15 secret): {len(kept)}")
print(f"  → dopo GC: {len(kept)} allow (da {before})")
print("\nEsempi di cosa RIMUOVO (primi 8):")
for a in garbage[:8]:
    print(f"  - {a[:80]}{'…' if len(a)>80 else ''}")
print("\nEsempi di cosa TENGO (verifica che siano sani):")
for a in kept[:6]:
    print(f"  ✓ {a[:80]}{'…' if len(a)>80 else ''}")

if APPLY:
    import datetime
    bak=P+".bak-permgc"
    json.dump(d,open(bak,"w"),indent=2,ensure_ascii=False)  # backup pre-mod (copia attuale)
    d["permissions"]["allow"]=kept
    json.dump(d,open(P,"w"),indent=2,ensure_ascii=False)
    print(f"\n✅ APPLICATO. Backup: {bak}. allow {before}→{len(kept)}.")
else:
    print(f"\n(DRY-RUN. APPLY=1 per scrivere. Toglierebbe {len(garbage)}, terrebbe {len(kept)}.)")
