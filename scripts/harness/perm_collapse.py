#!/usr/bin/env python3
"""perm_collapse2.py — SOLO mosse a colpo sicuro: (1) rimuovi path-morti, (2) dedup literali già
coperti da un pattern * esistente. NESSUN nuovo pattern (parsing troppo sporco per autogenerarli)."""
import json, os, re, sys
P=os.path.expanduser("~/nuzantara/.claude/settings.local.json")
APPLY=os.environ.get("APPLY")=="1"
d=json.load(open(P)); allow=d["permissions"]["allow"]; before=len(allow)

def has_secret(a): return "PGPASSWORD" in a or "PASSWORD=" in a
DEAD=re.compile(r'/Users/nuzantara/|monitor-air|/Users/antonellosiano/')  # path morti (M5=balizero)

# comandi che hanno GIÀ un Bash(cmd:*) pattern
existing=set()
for a in allow:
    if a.startswith("Bash(") and "*" in a:
        m=re.match(r'Bash\(([^\s:]+):', a)
        if m: existing.add(m.group(1))

def first_cmd(a):
    inner=(a[5:-1] if a.endswith(")") else a[5:]).strip().strip('"').strip("'").strip()
    inner=re.sub(r'^(\w+=\S+\s+)+','',inner)
    t=inner.split(); return t[0] if t else ""

removed_dead=[]; deduped=[]; kept=[]
for a in allow:
    if has_secret(a): kept.append(a); continue          # secret intatti (rotazione operatore)
    if a.startswith("Bash(") and "*" not in a and DEAD.search(a):
        removed_dead.append(a); continue                # path morto → via
    if a.startswith("Bash(") and "*" not in a and first_cmd(a) in existing:
        deduped.append(a); continue                     # già coperto da pattern → via
    kept.append(a)

print(f"PRIMA: {before}")
print(f"  path MORTI rimossi: {len(removed_dead)}")
print(f"  literali dedup (già coperti da pattern *): {len(deduped)}")
print(f"  TENUTI: {len(kept)}")
print(f"DOPO: {len(kept)}  (guadagno {before-len(kept)})")
print(f"\nDedup examples (già coperti, sicuri da togliere):")
for a in deduped[:5]: print(f"  → {a[:72]}  [Bash({first_cmd(a)}:*)]")
print(f"\nDead-path examples:")
for a in removed_dead[:3]: print(f"  ✗ {a[:72]}")

if APPLY:
    json.dump(d, open(P+".bak-collapse2","w"), indent=2, ensure_ascii=False)
    d["permissions"]["allow"]=kept
    json.dump(d, open(P,"w"), indent=2, ensure_ascii=False)
    print(f"\n✅ APPLICATO {before}→{len(kept)}. Backup: .bak-collapse2")
else:
    print(f"\n(DRY-RUN)")
