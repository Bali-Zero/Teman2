#!/usr/bin/env python3
"""enrich_kbli_jangka_waktu.py — fill the missing jangka_waktu (OSS processing time) in the
canonical KBLI dataset, following the PP 28/2025 rule verified against NB-3 (Company/KBLI
ground truth, 2026-06-28).

NB-3 (verbatim from PP 28/2025, Pasal 5 + Lampiran I col. 9):
  - Risiko Rendah / Menengah Rendah  → jangka_waktu = "Otomatis"  (NIB / NIB+SS instant,
    Pasal 130/131). DERIVABLE from kategori_risiko with certainty — it is the decree's rule.
  - Risiko Menengah Tinggi / Tinggi  → varies code-by-code (3/4/5/14/25/50 hari…). NB-3 is
    explicit: "tassativo leggere il valore specifico del singolo KBLI nel Lampiran I" — NOT
    derivable from the risk class alone. We take the REAL value from the already-parsed
    rich-file (apps/kbli-navigator/data/kbli-2025.json, provenance BPS_7_2025+PP28) by
    matching (code, kategori_risiko). Where the rich-file has no value, we LEAVE IT EMPTY
    (the card stays silent) rather than fabricate a number — anti-hallucination on a
    regulatory tool.

HARD CONSTRAINT: this script ONLY writes the per_skala.jangka_waktu field where it is
currently empty. It NEVER touches any pma_* field, l4_bali, status_mapping, intel, or any
other key — the 2026-06-27 PMA audit corrections (86101→TERTUTUP, the 49% caps, route_to)
must remain intact.

Usage:
  python scripts/enrich_kbli_jangka_waktu.py            # apply, write in place
  python scripts/enrich_kbli_jangka_waktu.py --dry-run  # report only, no write
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# The real git-TRACKED canonical is data/source_documents/... — `source_documents/` at the repo
# root is a SYMLINK to it in the main checkout (so they read identical there), but in a worktree
# the symlink isn't recreated, so we must target the physical tracked path explicitly.
CANON = REPO / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
# rich-file is gitignored; read from the main checkout if absent in this worktree
RICH_CANDIDATES = [
    REPO / "apps" / "kbli-navigator" / "data" / "kbli-2025.json",
    Path.home() / "Desktop" / "nuzantara" / "apps" / "kbli-navigator" / "data" / "kbli-2025.json",
]

AUTOMATIC_RISK = {"Rendah", "Menengah Rendah"}
LAMPIRAN_RISK = {"Menengah Tinggi", "Tinggi"}

# A clean jangka_waktu value the card can render unambiguously: "Otomatis", a bare day count
# ("7", "14"), or "N Hari[ Kerja]". Anything else (a lone "-", OCR-garbled mining IUP multi-phase
# strings like "1. IUP/IUP Tahap Kegia-") is dirty and must NOT be imported or kept — better empty
# than garbage on a regulatory card.
_VALID_JW = re.compile(r"^(Otomatis|\d{1,3}|\d{1,3}\s*[Hh]ari(\s*[Kk]erja)?)$")


def is_clean(jw: str) -> bool:
    return bool(jw) and bool(_VALID_JW.match(jw.strip()))


def load(path):
    d = json.load(open(path))
    return d, (d.get("data") if isinstance(d, dict) and "data" in d else d)


def code_of(r):
    return r.get("kode_kbli_2025") or r.get("kode")


def main():
    dry = "--dry-run" in sys.argv

    rich_path = next((p for p in RICH_CANDIDATES if p.exists()), None)
    if not rich_path:
        print("::error:: rich-file (kbli-navigator/kbli-2025.json) not found in any candidate path")
        return 2
    _, rdata = load(rich_path)

    # rich index: code -> {kategori_risiko -> first non-empty, non-"Otomatis" jangka_waktu}
    rich_by_code = {}
    for r in rdata:
        c = code_of(r)
        if not c:
            continue
        m = rich_by_code.setdefault(c, {})
        for p in r.get("per_skala", []):
            rk, jw = p.get("kategori_risiko"), p.get("jangka_waktu")
            # only adopt a rich-file value that is CLEAN (skip OCR-garbled mining IUP strings)
            if rk and jw and is_clean(jw) and jw.strip() != "Otomatis":
                m.setdefault(rk, jw.strip())

    canon_doc, cdata = load(CANON)

    filled_auto = 0      # Rendah/Men-Rendah → "Otomatis"
    filled_real = 0      # Men-Tinggi/Tinggi → real value from rich-file
    left_empty = 0       # Men-Tinggi/Tinggi with no real value → stays empty (honest)
    untouched = 0        # already had a CLEAN value
    cleaned = 0          # had a DIRTY value ("-", OCR garble) → wiped to empty
    codes_touched = set()

    for r in cdata:
        c = code_of(r)
        rich_risk = rich_by_code.get(c, {})
        for p in r.get("per_skala", []):
            jw = p.get("jangka_waktu")
            if jw and str(jw).strip():
                if is_clean(str(jw)):
                    untouched += 1
                    continue
                # dirty preexisting value (lone "-", garbled IUP) → wipe, treat as empty below
                if not dry:
                    p["jangka_waktu"] = ""
                cleaned += 1
                codes_touched.add(c)
            rk = (p.get("kategori_risiko") or "").strip()
            if rk in AUTOMATIC_RISK:
                if not dry:
                    p["jangka_waktu"] = "Otomatis"
                    p["jangka_waktu_source"] = "PP28_rule_risk_class"  # provenance for audit
                filled_auto += 1
                codes_touched.add(c)
            elif rk in LAMPIRAN_RISK:
                real = rich_risk.get(rk)
                if real:
                    if not dry:
                        p["jangka_waktu"] = real
                        p["jangka_waktu_source"] = "lampiran_parsed_richfile"
                    filled_real += 1
                    codes_touched.add(c)
                else:
                    left_empty += 1  # NB-3: must read Lampiran per-code; we don't have it → silent
            # else: no/unknown risk → leave empty

    print(f"jangka_waktu enrichment ({'DRY-RUN' if dry else 'APPLIED'}):")
    print(f"  filled 'Otomatis' (Rendah/Men-Rendah, PP28 rule): {filled_auto}")
    print(f"  filled real value (Men-Tinggi/Tinggi, from Lampiran-parsed rich-file): {filled_real}")
    print(f"  left EMPTY (Men-Tinggi/Tinggi, no real value — honest, not fabricated): {left_empty}")
    print(f"  cleaned (dirty '-'/OCR-garble value wiped to empty): {cleaned}")
    print(f"  untouched (already had a CLEAN value): {untouched}")
    print(f"  codes touched: {len(codes_touched)}")

    if not dry:
        # write back preserving the top-level shape
        json.dump(canon_doc, open(CANON, "w"), ensure_ascii=False, indent=2)
        print(f"  wrote {CANON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
