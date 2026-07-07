#!/usr/bin/env python3
"""enrich_kbli_jangka_richfile_v2.py — second-pass jangka_waktu fill for the codes the first
enrichment left empty, recovering the value from the already-parsed rich-file
(apps/kbli-navigator/data/kbli-2025.json) by NORMALISING its descriptive day-count strings.

Why a v2: the first pass (enrich_kbli_jangka_waktu.py) used a STRICT validator (_VALID_JW) that
only accepted clean "N" / "N Hari" / "Otomatis". But the Lampiran rich-file often stores the SLA
as a descriptive sentence — e.g. "29 Hari (7 Hari untuk verifikasi persyaratan administrasi...)",
"30 Hari setelah memenuhi persyaratan dan melakukan...". Those carry a perfectly good leading
day-count that the strict validator threw away, leaving the card blank.

This pass extracts the LEADING "N Hari" from such strings and fills it — but ONLY when it is safe:

  SAFE   (fill): the code has a SINGLE distinct clean value across all its rich-file scopes
                 (uniform regime — e.g. 60101 broadcasting = "29 Hari" everywhere, 85591
                 edu = "5 Hari" everywhere). No ambiguity about which scope gets which value.
  UNSAFE (skip): the code has MULTIPLE distinct clean values across scopes (e.g. 26601 =
                 30/45 Hari, 46743 = 10/14 Hari). Without the Lampiran's scope↔value mapping
                 we cannot know which empty canonical scale takes which number — filling
                 blindly would FABRICATE a per-scope SLA. Leave empty (honest), like the
                 mining 14/30 case NB-3 warned about.

A bare leading number with no "Hari" unit (e.g. "14", "30") is NOT accepted here — those are the
mining IUP-phase truncations that must read "Sesuai tahapan IUP (ESDM)", handled by
mark_kbli_special_regime.py, not a day-count.

HARD CONSTRAINT (same as the other two scripts): writes ONLY per_skala.jangka_waktu +
jangka_waktu_source, ONLY where currently empty. NEVER touches pma_*, l4_bali, status_mapping,
intel, or any other key.

Usage:
  python scripts/enrich_kbli_jangka_richfile_v2.py            # apply
  python scripts/enrich_kbli_jangka_richfile_v2.py --dry-run  # report only
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CANON = REPO / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
RICH_CANDIDATES = [
    REPO / "apps" / "kbli-navigator" / "data" / "kbli-2025.json",
    Path.home() / "Desktop" / "nuzantara" / "apps" / "kbli-navigator" / "data" / "kbli-2025.json",
]

# leading "N Hari" (the SLA), tolerating an optional " Kerja". Must have the Hari unit — a bare
# number is rejected (those are mining IUP-phase truncations, not a day-count).
_LEAD_HARI = re.compile(r"^\s*(\d{1,3})\s*[Hh]ari(\s*[Kk]erja)?", re.UNICODE)


def normalise(raw: str):
    """Return a clean 'N Hari[ Kerja]' or 'Otomatis', else None (not a usable day-count)."""
    if not raw:
        return None
    s = raw.strip()
    if s == "Otomatis":
        return "Otomatis"
    m = _LEAD_HARI.match(s)
    if m:
        kerja = " Kerja" if m.group(2) else ""
        return f"{m.group(1)} Hari{kerja}"
    return None


def code_of(r):
    return str(r.get("kode_kbli_2025") or r.get("kode") or "")


def load(p):
    d = json.load(open(p))
    return d, (d.get("data") if isinstance(d, dict) and "data" in d else d)


def main():
    dry = "--dry-run" in sys.argv

    rich_path = next((p for p in RICH_CANDIDATES if p.exists()), None)
    if not rich_path:
        print("::error:: rich-file not found")
        return 2
    _, rdata = load(rich_path)

    # rich index: code -> set of normalised distinct values, AND a per-risk normalised map
    rich_uniform = {}     # code -> the single value (only if uniform)
    rich_by_risk = {}     # code -> {risk -> value}  (for the ambiguous-but-risk-distinct case)
    for r in rdata:
        c = code_of(r)
        if not c:
            continue
        vals = set()
        risk_map = rich_by_risk.setdefault(c, {})
        for p in r.get("per_skala", []):
            n = normalise(p.get("jangka_waktu") or "")
            if n and n != "Otomatis":     # Otomatis is the rule-path's job, not this recovery
                vals.add(n)
                rk = (p.get("kategori_risiko") or "").strip()
                if rk:
                    risk_map.setdefault(rk, n)
        if len(vals) == 1:
            rich_uniform[c] = next(iter(vals))

    canon_doc, cdata = load(CANON)

    filled_uniform = 0
    filled_byrisk = 0
    skipped_ambiguous = set()
    codes_touched = set()

    for r in cdata:
        c = code_of(r)
        uniform = rich_uniform.get(c)
        risk_map = rich_by_risk.get(c, {})
        # a code is ambiguous if rich has >1 distinct value and no clean per-risk disambiguation
        distinct_vals = set(risk_map.values())
        for p in r.get("per_skala", []):
            jw = (p.get("jangka_waktu") or "").strip()
            if jw and jw not in ("-", "—"):
                continue  # already has a value
            rk = (p.get("kategori_risiko") or "").strip()
            if uniform:
                if not dry:
                    p["jangka_waktu"] = uniform
                    p["jangka_waktu_source"] = "lampiran_richfile_normalized"
                filled_uniform += 1
                codes_touched.add(c)
            elif len(distinct_vals) > 1 and rk in risk_map:
                # multiple values but THIS scale's risk maps to exactly one — safe by risk
                if not dry:
                    p["jangka_waktu"] = risk_map[rk]
                    p["jangka_waktu_source"] = "lampiran_richfile_normalized_byrisk"
                filled_byrisk += 1
                codes_touched.add(c)
            elif distinct_vals:
                skipped_ambiguous.add(c)  # divergent scopes, no safe mapping → leave empty
            # else: rich has nothing usable → leave empty

    print(f"richfile-v2 jangka recovery ({'DRY-RUN' if dry else 'APPLIED'}):")
    print(f"  filled (uniform rich value): {filled_uniform}")
    print(f"  filled (disambiguated by risk): {filled_byrisk}")
    print(f"  codes left empty (ambiguous divergent scopes, honest): {sorted(skipped_ambiguous)}")
    print(f"  codes touched: {len(codes_touched)}")

    if not dry:
        json.dump(canon_doc, open(CANON, "w"), ensure_ascii=False, indent=2)
        print(f"  wrote {CANON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
