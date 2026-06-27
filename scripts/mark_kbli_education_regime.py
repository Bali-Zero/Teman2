#!/usr/bin/env python3
"""mark_kbli_education_regime.py — fill the jangka_waktu for the education / childcare / spa codes
whose value the OCR re-parse + rich-file could not recover, using NB-3 ground truth
(PP 28/2025 + UU 20/2003, verbatim Pasal citations, 2026-06-28).

The OCR scan of all 18 Lampiran PDFs found ZERO of these codes (and the rich-file has scale=0
for them). NB-3 explained why, per code family:

  FORMAL GENERAL EDUCATION (85102 TK, 85202 SD, 85312 SMP, 85316 SMA — swasta)
    Pasal 90(3): OSS-RBA applies to formal schools ONLY inside KEK (special economic zones).
    Outside KEK (ordinary Bali territory) the izin pendirian satuan pendidikan is issued by
    Kemendikbudristek under UU 20/2003, OUTSIDE OSS — no risk row, no day-SLA in Lampiran I.
    → "Izin Kemendikbud (di luar OSS)"

  CHILDCARE / PLAYGROUP (88906 Kelompok Bermain, 88907 Taman Penitipan Anak)
    Reclassified in KBLI 2025 from Education (Q) to Social Activities (R). Licensed locally by
    Dinas Sosial / PAUD with mandatory premises inspection, NOT in Lampiran I, no OSS day-SLA.
    → "Izin Dinas Sosial/PAUD (di luar OSS)"

  SPA (96230) — the ONE recoverable code here: NB-3 says it HAS a row in Lampiran I.L (tourism),
    Sertifikat Standar verified, SLA = 14 Hari Kerja.
    → "14 Hari"

The 8 ambiguous 855xx codes (85510/85520/85530/85541/85542/85549/85579/85699) are NOT touched —
NB-3 did not cover them explicitly and they are a mix of non-formal courses (likely have a
Lampiran SLA) and religious/formal (likely Kemenag-excluded). Leaving them empty is honest;
fabricating a value would be worse than a blank on a regulatory card.

HARD CONSTRAINT (same as the sibling scripts): writes ONLY per_skala.jangka_waktu +
jangka_waktu_source, ONLY where currently empty. NEVER touches pma_* / l4_bali / any other key.

Usage:
  python scripts/mark_kbli_education_regime.py            # apply
  python scripts/mark_kbli_education_regime.py --dry-run  # report only
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CANON = REPO / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

# code -> (jangka value, provenance tag). Grounded code-by-code in NB-3.
MARKS = {
    # formal general education: outside OSS, Kemendikbud izin pendirian (UU 20/2003, Pasal 90(3))
    "85102": ("Izin Kemendikbud (di luar OSS)", "PP28_special_regime_kemendikbud"),
    "85202": ("Izin Kemendikbud (di luar OSS)", "PP28_special_regime_kemendikbud"),
    "85312": ("Izin Kemendikbud (di luar OSS)", "PP28_special_regime_kemendikbud"),
    "85316": ("Izin Kemendikbud (di luar OSS)", "PP28_special_regime_kemendikbud"),
    # childcare / playgroup: reclassified Category R, Dinas Sosial/PAUD, outside Lampiran
    "88906": ("Izin Dinas Sosial/PAUD (di luar OSS)", "PP28_special_regime_dinsos"),
    "88907": ("Izin Dinas Sosial/PAUD (di luar OSS)", "PP28_special_regime_dinsos"),
    # SPA: HAS a Lampiran I.L (tourism) row, Sertifikat Standar SLA 14 Hari Kerja
    "96230": ("14 Hari", "lampiran_nb3_verified"),
}


def code_of(r):
    return str(r.get("kode_kbli_2025") or r.get("kode") or "")


def main():
    dry = "--dry-run" in sys.argv
    doc = json.load(open(CANON))
    rows = doc["data"] if isinstance(doc, dict) and "data" in doc else doc

    filled = 0
    codes_touched = set()
    skipped_has_value = 0

    for r in rows:
        c = code_of(r)
        mark = MARKS.get(c)
        if not mark:
            continue
        label, tag = mark
        for p in r.get("per_skala", []):
            jw = (p.get("jangka_waktu") or "").strip()
            if jw and jw not in ("-", "—"):
                skipped_has_value += 1
                continue
            if not dry:
                p["jangka_waktu"] = label
                p["jangka_waktu_source"] = tag
            filled += 1
            codes_touched.add(c)

    print(f"education-regime marking ({'DRY-RUN' if dry else 'APPLIED'}):")
    print(f"  scales filled: {filled}")
    print(f"  scales skipped (already had a value): {skipped_has_value}")
    print(f"  codes touched: {sorted(codes_touched)}")

    if not dry:
        json.dump(doc, open(CANON, "w"), ensure_ascii=False, indent=2)
        print(f"  wrote {CANON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
