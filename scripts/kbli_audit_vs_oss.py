#!/usr/bin/env python3
"""Audit CURRENT apps/mouth KBLI dataset vs OSS ground truth (2026-07-07).
Re-derivation of the 2026-06-19 comparison, on today's data. Deterministic, no LLM."""
import json, re, unicodedata
from difflib import SequenceMatcher

OURS = "/Users/balizero/nuzantara/apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
OSS = "/Users/balizero/nuzantara/data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json"
GOLD = "/Users/balizero/nuzantara/apps/mouth/data/kbli-gold-all.json"

def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", str(s)).lower().strip()
    return re.sub(r"\s+", " ", s)

ours_raw = json.load(open(OURS))
ours = {r["kode_kbli_2025"]: r for r in ours_raw["data"]} if isinstance(ours_raw, dict) else {r["kode_kbli_2025"]: r for r in ours_raw}
oss_raw = json.load(open(OSS))
# OSS shape unknown: try list of records with kbli/kode field
recs = oss_raw if isinstance(oss_raw, list) else oss_raw.get("data", oss_raw.get("records", []))
oss5 = {}
sample_fields = None
for r in recs:
    code = str(r.get("kbli") or r.get("kode") or r.get("code") or "")
    if len(code) == 5 and code.isdigit():
        oss5[code] = r
        if sample_fields is None: sample_fields = list(r.keys())

print(f"OURS: {len(ours)} codes | OSS 5-digit: {len(oss5)} | OSS total recs: {len(recs)}")
print(f"OSS fields: {sample_fields}")

def oss_title(r): return r.get("judul_id") or r.get("title") or r.get("nama") or ""
def oss_desc(r): return r.get("uraian_id") or r.get("description") or r.get("keterangan") or ""

missing = sorted(set(oss5) - set(ours))
phantom = sorted(set(ours) - set(oss5))
print(f"\nMISSING from ours: {len(missing)} {missing[:10]}")
print(f"PHANTOM in ours (not in OSS 2025): {len(phantom)} {phantom[:10]}")

title_mismatch, trunc, desc_low = [], [], []
for code, r in ours.items():
    if code not in oss5: continue
    o = oss5[code]
    tj, oj = norm(r.get("judul", "")), norm(oss_title(o))
    if tj != oj:
        # allow ours = "EN / ID" enrichment containing the OSS judul
        if oj and oj in tj:
            pass
        elif oj.startswith(tj) and len(tj) < len(oj) - 3:
            trunc.append(code)
        else:
            title_mismatch.append((code, r.get("judul", "")[:60], oss_title(o)[:60]))
    du, do = norm(r.get("uraian", "")), norm(oss_desc(o))
    if du and do:
        sim = SequenceMatcher(None, du[:1500], do[:1500]).ratio()
        if sim < 0.80:
            desc_low.append((code, round(sim, 3)))

print(f"\nJUDUL truncated: {len(trunc)} {trunc[:10]}")
print(f"JUDUL mismatch (real divergence): {len(title_mismatch)}")
for c, a, b in title_mismatch[:15]:
    print(f"  {c}: OURS='{a}' | OSS='{b}'")
print(f"\nURAIAN sim<0.80: {len(desc_low)}")
for c, s in sorted(desc_low, key=lambda x: x[1])[:15]:
    print(f"  {c}: sim={s}")

# Field coverage on ours
gold = json.load(open(GOLD))
n = len(ours)
def cov(pred): return sum(1 for r in ours.values() if pred(r))
print(f"\n--- COVERAGE (n={n}) ---")
print(f"gold-tier: {len(gold)}")
sample = next(iter(ours.values()))
print(f"ours fields: {list(sample.keys())}")
for f in sample.keys():
    c = cov(lambda r, f=f: r.get(f) not in (None, "", [], {}))
    print(f"  {f}: {c} ({100*c//n}%)")
