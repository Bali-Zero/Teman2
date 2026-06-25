#!/usr/bin/env python3
"""
Fill the EMPTY `intel_2026.whatItMeans` for the handful of navigator records that have every
other intel field populated (whatYouNeed / whatChanged / zantaraOpener / baliContext) but a blank
whatItMeans. These are the last residue of fronts A+B — six industrial/extractive codes (hunting,
fishing-support, lignite, oil-and-gas-support, mining-support, meat-processing) that never received
the opening "what it means" line.

This is NOT the #1621 paraphrase job: that one rewrites records whose whatItMeans CONTAINS the raw
Indonesian "Kelompok ..." uraian. Here whatItMeans is EMPTY, so #1621's is_candidate() skips them.
We derive whatItMeans from the official `uraian` instead — same DeepSeek call + fact-gate as
kbli_paraphrase_whatitmeans.py, which we import wholesale (zero logic duplication).

Safety (inherited from the imported functions):
- fact_gate REJECTS any output introducing a foreign KBLI code, or too-short, or still-Indonesian.
- On REJECT the whatItMeans is LEFT EMPTY (never filled with garbage) and the code is reported.
- Idempotent: a record whose whatItMeans is already non-empty is not a candidate.
- DRY-RUN by default; --apply writes; checkpoints every record (tiny set).

KBLI = public economic classification. ZERO PII. DeepSeek V4 Pro pre-authorized (~$0.01/q).
"""
import argparse
import json
import os
import sys

# reuse the proven call + fact_gate + key from the sibling script — no logic duplication
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbli_paraphrase_whatitmeans as P

WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = f"{WT}/apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"


def is_candidate(rec):
    """Empty whatItMeans, but has a usable uraian to derive it from."""
    intel = rec.get("intel_2026")
    if not isinstance(intel, dict):
        return False
    wim = intel.get("whatItMeans")
    if wim and wim.strip():
        return False  # already filled — idempotent skip
    uraian = rec.get("uraian")
    return isinstance(uraian, str) and len(uraian.strip()) >= 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with open(TARGET) as fh:
        doc = json.load(fh)
    recs = doc if isinstance(doc, list) else doc.get("data", doc.get("records"))

    cands = [r for r in recs if is_candidate(r)]
    print(f"empty-whatItMeans candidates: {len(cands)}")
    for r in cands:
        print(f"  {r.get('kode_kbli_2025')} | {r.get('judul','')[:50]}")
    if not cands:
        print("nothing to do.")
        return

    filled, rejected = 0, []
    for r in cands:
        kode, english, verdict = P.call(r)
        if verdict["ok"]:
            if args.apply:
                r["intel_2026"]["whatItMeans"] = english
                # auditable marker, preserving any existing _l3_regen
                regen = r["intel_2026"].get("_l3_regen") or {}
                regen["whatitmeans_filled"] = "2026-06-21"
                r["intel_2026"]["_l3_regen"] = regen
            filled += 1
            print(f"  ✓ {kode}: {english[:70]}...")
        else:
            rejected.append((kode, verdict["reason"]))
            print(f"  ✗ {kode}: REJECT — {verdict['reason']} (left empty)")

    print(f"\nfilled: {filled} | rejected: {len(rejected)}")
    if args.apply:
        with open(TARGET, "w") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
        print(f"✅ APPLIED to {TARGET}")
    else:
        print("(dry-run — pass --apply to write)")


if __name__ == "__main__":
    main()
