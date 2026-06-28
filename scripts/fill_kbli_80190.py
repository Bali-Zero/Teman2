#!/usr/bin/env python3
"""fill_kbli_80190.py — fill the per_skala data-gap for KBLI 80190 (Aktivitas Keamanan YTDL).

This is the ONE genuine data-gap from the card-field audit that is recoverable. 80190 is a real
KBLI 2025 code (verified in both the dataset and the rich-file BPS 7/2025 source) but its
per_skala was empty at source. NB-3 (PP 28/2025 Lampiran I, sub sektor Keamanan, verbatim)
confirmed it has a real OSS regime row and gave the values, cross-confirmed by the sibling code
80110 on disk (which carries the identical ruang lingkup "Jasa Penerapan Peralatan Keamanan").

DECISION (operator, minimal/honest variant): create the 4 business-scale rows with ONLY the
fields NB-3 gives with numeric certainty. Leave persyaratan/kewajiban/kewenangan EMPTY — NB-3
describes them in prose but does not provide the structured Lampiran list, and fabricating
requirement text on a regulatory card is worse than a blank. perizinan kept as the empty array
[] (the dataset's normal form — the web derives "NIB + Izin" from risk via resolveLicenseType).

NB-3 values (Lampiran I, Tinggi tier, PT PMA = Usaha Besar):
  kategori_risiko  = "Tinggi"
  jangka_waktu     = "7"          (7 Hari Kerja; bare-number form, matching sibling 80110)
  perizinan        = []           (→ web derives "NIB + Izin" from Tinggi)
  fiktif_positif   = True         (Pasal 230: Tinggi WITH a day-SLA → Izin auto-issued)
  scope_uraian     = "Jasa Penerapan Peralatan Keamanan (security devices)"  (verbatim NB-3,
                     identical to 80110 scope_index 0)

80190 is NOT remapped to 80110 — NB-3 was explicit they are distinct (80190 = security
technology / ARC / remote monitoring; 80110 = physical guards). Remapping would cause Izin
rejection at the Polda.

HARD CONSTRAINT: writes ONLY the 80190 record's per_skala. NEVER touches any other code, nor
80190's pma_* / l4_bali / judul / status_mapping.

Usage:
  python scripts/fill_kbli_80190.py --dry-run
  python scripts/fill_kbli_80190.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CANON = REPO / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

CODE = "80190"
SCALES = ["Mikro", "Kecil", "Menengah", "Besar"]
SCOPE_URAIAN = "Jasa Penerapan Peralatan Keamanan (security devices)"


def make_scale(skala: str) -> dict:
    """A single per_skala row, schema-matching the sibling 80110 rows."""
    return {
        "skala_usaha": [skala],
        "kategori_risiko": "Tinggi",
        "jangka_waktu": "7",
        "scope_index": 0,
        "scope_uraian": SCOPE_URAIAN,
        "perizinan": [],          # web derives "NIB + Izin" from Tinggi
        "persyaratan": [],        # NB-3 prose-only — not fabricated
        "kewajiban": [],          # NB-3 prose-only — not fabricated
        "kewenangan": [],         # not provided structured — left empty
        "fiktif_positif": True,   # Pasal 230: Tinggi + day-SLA → auto-issue
        "jangka_waktu_source": "nb3_lampiran_keamanan_verified",
    }


def main():
    dry = "--dry-run" in sys.argv
    doc = json.load(open(CANON))
    rows = doc["data"] if isinstance(doc, dict) and "data" in doc else doc

    target = None
    for r in rows:
        if str(r.get("kode_kbli_2025") or r.get("kode")) == CODE:
            target = r
            break
    if target is None:
        print(f"::error:: {CODE} not found")
        return 2

    existing = target.get("per_skala") or []
    if existing:
        print(f"::warn:: {CODE} already has {len(existing)} per_skala rows — refusing to overwrite.")
        return 1

    new_scales = [make_scale(s) for s in SCALES]
    print(f"fill 80190 per_skala ({'DRY-RUN' if dry else 'APPLIED'}):")
    print(f"  creating {len(new_scales)} scales: {SCALES}")
    print(f"  risk=Tinggi jangka=7 perizinan=[] fiktif=True scope={SCOPE_URAIAN!r}")
    print(f"  persyaratan/kewajiban/kewenangan left EMPTY (NB-3 prose-only, not fabricated)")

    if not dry:
        target["per_skala"] = new_scales
        json.dump(doc, open(CANON, "w"), ensure_ascii=False, indent=2)
        print(f"  wrote {CANON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
