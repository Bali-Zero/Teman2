#!/usr/bin/env python3
"""mark_kbli_special_regime.py — fill the jangka_waktu that is STRUCTURALLY ABSENT from the
PP 28/2025 Lampiran I (not OCR-recoverable, because the decree itself defers the SLA to a
sector regulator) with the correct special-regime label instead of leaving a blank/misleading
empty cell on the card.

NB-3 (Company/KBLI ground truth, PP 28/2025 verbatim, 2026-06-28) established that two sector
families do NOT carry a day-count jangka_waktu penerbitan in Lampiran I:

  MINING (KBLI 05/07/08/09, Pertambangan/ESDM)
    Pasal 90(3): natural-resource permits are issued in sequential phases (Konstruksi, Operasi,
    Dekomisioning) — the IUP (Izin Usaha Pertambangan) timeline is gated on RKAB/AMDAL approval
    at the Ministry of ESDM, so NO standardised OSS SLA in days exists. The Lampiran defers to
    "tahapan kegiatan" (IUP Eksplorasi → Operasi Produksi).
    → label: "Sesuai tahapan IUP (ESDM)"

  FINANCE / INSURANCE (KBLI 64/65/66, Keuangan/Asuransi)
    Jurisdiction is OJK (Otoritas Jasa Keuangan) and Bank Indonesia by their own laws; the
    Lampiran column reads "sesuai dengan ketentuan OJK/BI", leaving the real SLA outside the
    OSS platform (governed by POJK / PBI).
    → label: "Sesuai ketentuan OJK/BI"

This is the HONEST representation: the empty cell was the symptom of a regulatory deferral, not
a missing parse. Education (85xxx) DOES carry a day-count in the Lampiran (e.g. 85321 = "13
Hari", confirmed on disk) and is handled by the OCR re-parse path, NOT here.

HARD CONSTRAINT (identical to enrich_kbli_jangka_waktu.py): writes ONLY per_skala.jangka_waktu
and jangka_waktu_source, ONLY where currently empty AND the scale's risk is Men-Tinggi/Tinggi
(the special regimes attach to the high-risk Izin tier; low-risk scales already read
"Otomatis"). NEVER touches pma_*, l4_bali, status_mapping, intel, or any other key — the
2026-06-27 PMA audit corrections must remain intact.

Usage:
  python scripts/mark_kbli_special_regime.py            # apply, write in place
  python scripts/mark_kbli_special_regime.py --dry-run  # report only, no write
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# the real git-TRACKED canonical (source_documents/ at root is a symlink, absent in worktrees)
CANON = REPO / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

# sector prefix (first 2 digits of KBLI) → (regime label, provenance tag). Per NB-3 verdict.
MINING_PREFIXES = {"05", "07", "08", "09"}
FINANCE_PREFIXES = {"64", "65", "66"}

MINING_LABEL = "Sesuai tahapan IUP (ESDM)"
FINANCE_LABEL = "Sesuai ketentuan OJK/BI"

# The special regime is a high-risk-tier deferral. Low-risk scales of these codes (rare, e.g.
# a Mikro tier) already carry "Otomatis" from the PP28 rule and must not be relabelled.
SPECIAL_REGIME_RISK = {"Menengah Tinggi", "Tinggi"}


def regime_for(code: str):
    """Return (label, tag) for a code whose jangka is structurally absent, else (None, None)."""
    pref = code[:2] if len(code) >= 2 else code
    if pref in MINING_PREFIXES:
        return MINING_LABEL, "PP28_special_regime_esdm"
    if pref in FINANCE_PREFIXES:
        return FINANCE_LABEL, "PP28_special_regime_ojk_bi"
    return None, None


def code_of(r):
    return str(r.get("kode_kbli_2025") or r.get("kode") or "")


def main():
    dry = "--dry-run" in sys.argv
    doc = json.load(open(CANON))
    rows = doc["data"] if isinstance(doc, dict) and "data" in doc else doc

    marked_mining = 0
    marked_finance = 0
    codes_touched = set()
    skipped_has_value = 0

    for r in rows:
        c = code_of(r)
        label, tag = regime_for(c)
        if not label:
            continue
        for p in r.get("per_skala", []):
            jw = (p.get("jangka_waktu") or "").strip()
            if jw and jw not in ("-", "—"):
                skipped_has_value += 1
                continue  # already has a clean value (e.g. "Otomatis") — leave it
            risk = (p.get("kategori_risiko") or "").strip()
            if risk not in SPECIAL_REGIME_RISK:
                continue  # low-risk scale: the PP28 rule path owns it ("Otomatis"), not here
            if not dry:
                p["jangka_waktu"] = label
                p["jangka_waktu_source"] = tag
            codes_touched.add(c)
            if tag.endswith("esdm"):
                marked_mining += 1
            else:
                marked_finance += 1

    print(f"special-regime marking ({'DRY-RUN' if dry else 'APPLIED'}):")
    print(f"  mining scales marked '{MINING_LABEL}': {marked_mining}")
    print(f"  finance/insurance scales marked '{FINANCE_LABEL}': {marked_finance}")
    print(f"  scales skipped (already had a value): {skipped_has_value}")
    print(f"  codes touched: {len(codes_touched)}")

    if not dry:
        json.dump(doc, open(CANON, "w"), ensure_ascii=False, indent=2)
        print(f"  wrote {CANON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
