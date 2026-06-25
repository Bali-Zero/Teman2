#!/usr/bin/env python3
"""
Propagate already-validated intel_2026 from the navigator file (apps/mouth/data, 0 mutes)
into the RAG/Qdrant source file (data/source_documents, 1055 mutes) — front C residue.

WHY: #1612 merged 995 fact-gated L3 records into apps/mouth/data/KBLI_2025_FINAL_CLEAN.json
(the navigator's file). The data/source_documents/ copy — read by the RAG/Qdrant ingest path
(reindex_kbli_2025_final.py, kbli_eye.py, build_kbli_oss_twin.py) — never received them and
still has 1055 mute records. The navigator shows rich intel; the RAG index shows nothing.

This is a DATA COPY, not generation: every intel_2026 block copied here was already
fact-gated when it was written into apps/mouth. We invent NOTHING. We match by
kode_kbli_2025 and only fill records that are currently mute in source_documents.

Idempotent: only fills a source record if (a) it is mute AND (b) the navigator has intel
for that exact code. Never overwrites an existing non-mute source record.

--align-all (front-C residue 2026-06-23): the fill-only-of-mutes default left ~288 records
whose source intel_2026 PRE-EXISTED (Indonesian whatItMeans) while the navigator had since
moved to the English L3 rewrite — those were skipped (not mute), so the RAG source drifted
behind the navigator. --align-all overwrites intel_2026 for EVERY code where the navigator's
block differs, making source == navigator on intel_2026. Still a pure data copy from the
already-fact-gated navigator; we invent nothing, only mirror the SSOT.

DRY-RUN by default. Pass --apply to write.
"""
import json
import os
import sys
import argparse

WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAV = f"{WT}/apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
SRC = f"{WT}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"
KEY = "kode_kbli_2025"


def load(path):
    with open(path) as fh:
        d = json.load(fh)
    if isinstance(d, list):
        return d, None
    recs = d.get("data") or d.get("records")
    if recs is not None:
        return recs, d
    # dict keyed by code
    return list(d.values()), d


def is_mute(rec):
    it = rec.get("intel_2026") or {}
    return not (it.get("whatItMeans") or it.get("whatYouNeed"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the file (default: dry-run)")
    ap.add_argument(
        "--align-all",
        action="store_true",
        help="overwrite intel_2026 for EVERY code where it differs from the navigator "
        "(not only mute source records) — closes the front-C residue drift",
    )
    args = ap.parse_args()

    nav_recs, _ = load(NAV)
    src_recs, src_wrapper = load(SRC)

    # index navigator intel by code (only non-mute)
    nav_intel = {}
    for r in nav_recs:
        code = str(r.get(KEY) or "")
        if code and not is_mute(r):
            nav_intel[code] = r.get("intel_2026")

    filled = 0
    skipped_no_nav = 0
    already_ok = 0
    realigned = 0
    for r in src_recs:
        code = str(r.get(KEY) or "")
        if not is_mute(r):
            already_ok += 1
            # --align-all: also re-sync non-mute records that drifted from the navigator
            if args.align_all and code in nav_intel and r.get("intel_2026") != nav_intel[code]:
                if args.apply:
                    r["intel_2026"] = nav_intel[code]
                realigned += 1
            continue
        if code in nav_intel:
            if args.apply:
                r["intel_2026"] = nav_intel[code]
            filled += 1
        else:
            skipped_no_nav += 1

    print(f"source records total:          {len(src_recs)}")
    print(f"  already non-mute:            {already_ok}")
    print(f"  WOULD FILL (nav has intel):  {filled}")
    print(f"  still mute (nav also mute):  {skipped_no_nav}")
    if args.align_all:
        print(f"  WOULD RE-ALIGN (drifted):    {realigned}")
    print(f"navigator non-mute codes:      {len(nav_intel)}")

    if args.apply:
        out = src_wrapper if src_wrapper is not None else src_recs
        if src_wrapper is not None and "data" in src_wrapper:
            src_wrapper["data"] = src_recs
        elif src_wrapper is not None and "records" in src_wrapper:
            src_wrapper["records"] = src_recs
        with open(SRC, "w") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"\n✅ APPLIED: filled {filled} + re-aligned {realigned} intel blocks into {SRC}")
    else:
        print("\n(dry-run — pass --apply to write)")


if __name__ == "__main__":
    main()
