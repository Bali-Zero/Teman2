#!/usr/bin/env python3
"""derive_fiktif_positif.py — derive the fiktif_positif (silenzio-assenso / deemed-approval) flag
for every per_skala scale from the jangka_waktu + risk, per NB-3 ground truth (PP 28/2025
Pasal 225 + Pasal 230, verbatim, 2026-06-28).

WHY: fiktif positif is NOT an optional per-code flag in the Lampiran — it is a GENERAL platform
rule of OSS-RBA (codified by UU Cipta Kerja 6/2023, which flipped fiktif negatif → positif).
When the authority misses the day-SLA, the OSS system auto-approves:
  - Pasal 225(1): Menengah Tinggi (NIB + Sertifikat Standar) → Sertifikat Standar deemed verified
  - Pasal 230   : Tinggi (NIB + Izin) WITH a day-SLA → Izin issued automatically
The source dataset only marked 119 codes True (a separate sparse ingestion), under-reporting a
legal protection on ~2363 eligible Menengah-Tinggi/Tinggi scales.

EXACT BOOLEAN RULE (NB-3 verbatim):
  fiktif_positif = True  IFF
    (kategori_risiko ∈ {"Menengah Tinggi", "Tinggi"})
    AND jangka_waktu is a real OSS day-SLA  ("N Hari"/"N Hari Kerja" or a bare number)
    AND jangka_waktu does NOT defer to an external/phased regime
        (not "Sesuai tahapan IUP", "Sesuai ketentuan OJK/BI", "Izin Kemendikbud", "Dinas Sosial")
  else fiktif_positif = False

Notes:
  - "Otomatis" (Rendah/Men-Rendah instant NIB) is NOT in the rule — those tiers issue without a
    verification step, so the silenzio-assenso-on-SLA concept does not apply. We therefore do NOT
    set True for Otomatis; but we ALSO do not clobber a pre-existing True on those scales (the
    original data marked 73 Rendah/Men-Rendah scales True with jw=Otomatis — leave-as-is, since
    "deemed approved" is trivially satisfied by instant issuance and removing it would understate).
  - This fixes the orphans I created earlier: 05102/05200 were fiktif=True but I changed their
    jangka to "Sesuai tahapan IUP" — now correctly set to False (external phased regime, no OSS
    timer).

HARD CONSTRAINT: writes ONLY per_skala.fiktif_positif. NEVER touches pma_* / l4_bali / jangka /
perizinan / any other key.

Usage:
  python scripts/derive_fiktif_positif.py            # apply
  python scripts/derive_fiktif_positif.py --dry-run  # report only
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CANON = REPO / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

ELIGIBLE_RISK = {"Menengah Tinggi", "Tinggi"}

# a real OSS day-SLA: "N", "N Hari", "N Hari Kerja"
_DAY_SLA = re.compile(r"^\s*\d{1,3}\s*([Hh]ari(\s*[Kk]erja)?)?\s*$")
# external / phased regimes that have NO OSS timer → no fiktif positif
_EXTERNAL = ("Sesuai", "Izin Kemendikbud", "Dinas Sosial", "OJK", "IUP")


def is_oss_day_sla(jw: str) -> bool:
    jw = (jw or "").strip()
    if not jw:
        return False
    if any(tok in jw for tok in _EXTERNAL):
        return False
    return bool(_DAY_SLA.match(jw))


def fiktif_for(risk: str, jw: str) -> bool:
    return (risk or "").strip() in ELIGIBLE_RISK and is_oss_day_sla(jw)


def code_of(r):
    return str(r.get("kode_kbli_2025") or r.get("kode") or "")


def main():
    dry = "--dry-run" in sys.argv
    doc = json.load(open(CANON))
    rows = doc["data"] if isinstance(doc, dict) and "data" in doc else doc

    set_true = 0
    set_false = 0
    preserved_otomatis_true = 0
    unchanged = 0
    fixed_orphans = []        # were True but jangka now external → corrected to False
    codes_touched = set()

    for r in rows:
        c = code_of(r)
        for p in r.get("per_skala", []):
            risk = (p.get("kategori_risiko") or "").strip()
            jw = (p.get("jangka_waktu") or "").strip()
            old = p.get("fiktif_positif")
            want = fiktif_for(risk, jw)

            # preserve a pre-existing True on an Otomatis (instant) scale — deemed-approval is
            # trivially satisfied there and the rule simply doesn't address that tier.
            if old is True and jw == "Otomatis" and not want:
                preserved_otomatis_true += 1
                continue

            # detect the orphans: was True, jangka now defers to an external regime
            if old is True and not want and any(tok in jw for tok in _EXTERNAL):
                fixed_orphans.append((c, jw))

            if want == bool(old) and old is not None:
                unchanged += 1
                continue

            if not dry:
                p["fiktif_positif"] = want
            if want:
                set_true += 1
            else:
                set_false += 1
            codes_touched.add(c)

    print(f"fiktif_positif derivation ({'DRY-RUN' if dry else 'APPLIED'}):")
    print(f"  set True  (Men-Tinggi/Tinggi + OSS day-SLA, Pasal 225/230): {set_true}")
    print(f"  set False (no OSS timer / external regime / wrong tier): {set_false}")
    print(f"  preserved pre-existing True on Otomatis scales: {preserved_otomatis_true}")
    print(f"  unchanged (already correct): {unchanged}")
    print(f"  corrected orphans (True→False, jangka now external): {fixed_orphans[:8]}"
          f"{' ...' if len(fixed_orphans) > 8 else ''}  total={len(fixed_orphans)}")
    print(f"  codes touched: {len(codes_touched)}")

    if not dry:
        json.dump(doc, open(CANON, "w"), ensure_ascii=False, indent=2)
        print(f"  wrote {CANON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
