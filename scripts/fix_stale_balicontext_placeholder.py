#!/usr/bin/env python3
"""fix_stale_balicontext_placeholder.py — replace the stale needs-review placeholder in
intel.baliContext with the now-definitive l4_bali.reason, for the 52 codes resolved by the
NB-3 moratorium-by-risk-tier pass (PR #1814).

WHY: while a code was `_l4_needs_review`, its intel.baliContext carried a placeholder:
  "no OSS-RBA scope (special/sectoral regime: OJK/BI/BPOM/etc.) — Bali registrability needs
   manual sectoral verification"
That placeholder is now (a) STALE — the review is done, the verdict is definite — and
(b) sometimes FACTUALLY WRONG: e.g. 49233 (non-motorized freight) is closed by the risk-tier
moratorium, NOT by an OJK/BI/BPOM sectoral regime; and for the 7 codes now OPEN (61909, 75001/2/9,
82911, 93114, 93124) the placeholder's "needs manual verification" directly contradicts the green
"open to a PT PMA" verdict shown above it on the card (the app's GOLD-TIER INTEL · BALI block
renders intel.baliContext verbatim).

FIX: for exactly the codes that (1) still carry the placeholder AND (2) now have a definite
l4_bali verdict from the #1814 pass (review_basis == "nb3_2026_06_28_moratoria_risk_tier"),
overwrite intel.baliContext with the l4_bali.reason. The reason is already accurate and
NB-3-grounded — NO new text is fabricated; we reuse the verified verdict string.

HARD CONSTRAINT: writes ONLY intel_2026.baliContext (or intel.baliContext) on the matched codes.
NEVER touches l4_bali / pma_status / pma_max_asing / per_skala / any other field. A PMA
fingerprint over (kode, pma_status, pma_max_asing, pma_kondisi) of every code is printed
before+after and must be identical.

Usage:
  python scripts/fix_stale_balicontext_placeholder.py --dry-run
  python scripts/fix_stale_balicontext_placeholder.py
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CANON = REPO / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

PLACEHOLDER = "no OSS-RBA scope (special/sectoral regime"
RESOLVED_BASIS = "nb3_2026_06_28_moratoria_risk_tier"


def code_of(r):
    return str(r.get("kode_kbli_2025") or r.get("kode") or "")


def intel_of(r):
    """Return the intel dict the app reads (prefer intel_2026, fall back to intel). None if absent."""
    return r.get("intel_2026") if isinstance(r.get("intel_2026"), dict) else r.get("intel")


def pma_fingerprint(rows):
    h = hashlib.sha256()
    for r in sorted(rows, key=code_of):
        h.update(f"{code_of(r)}|{r.get('pma_status')}|{r.get('pma_max_asing')}|{r.get('pma_kondisi')}\n".encode())
    return h.hexdigest()[:12]


def main():
    dry = "--dry-run" in sys.argv
    doc = json.load(open(CANON))
    rows = doc["data"] if isinstance(doc, dict) and "data" in doc else doc

    fp_before = pma_fingerprint(rows)

    fixed = []
    skipped_no_reason = []
    for r in rows:
        intel = intel_of(r)
        if not intel:
            continue
        bc = intel.get("baliContext") or ""
        if PLACEHOLDER not in bc:
            continue
        l4 = r.get("l4_bali") or {}
        if l4.get("review_basis") != RESOLVED_BASIS:
            continue  # placeholder present but not resolved by #1814 — leave it (shouldn't happen; set was exact)
        reason = (l4.get("reason") or "").strip()
        if not reason:
            skipped_no_reason.append(code_of(r))
            continue
        if not dry:
            intel["baliContext"] = reason
        fixed.append(code_of(r))

    fp_after = pma_fingerprint(rows)

    print(f"fix stale baliContext placeholder ({'DRY-RUN' if dry else 'APPLIED'}):")
    print(f"  codes fixed (placeholder -> l4 reason): {len(fixed)}")
    print(f"    {sorted(fixed)}")
    if skipped_no_reason:
        print(f"  skipped (no l4 reason to use): {sorted(skipped_no_reason)}")
    print(f"  PMA fingerprint: before={fp_before} after={fp_after} "
          f"{'OK (unchanged)' if fp_before == fp_after else '!!! CHANGED — ABORT'}")

    if fp_before != fp_after:
        print("::error:: PMA fingerprint changed — refusing to write.")
        return 2
    if not dry:
        json.dump(doc, open(CANON, "w"), ensure_ascii=False, indent=2)
        print(f"  wrote {CANON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
