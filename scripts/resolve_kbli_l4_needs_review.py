#!/usr/bin/env python3
"""resolve_kbli_l4_needs_review.py — resolve the 85 KBLI codes flagged `_l4_needs_review`
into a definite l4_bali verdict, grounded in NB-3 (Company/KBLI, UUID 933509f9…, queried
2026-06-28) + the structured per_skala risk already in the dataset.

THE RULE (Zero's, refined by NB-3 ground truth):
  The Bali PMA moratorium (Governor letter B.27.000/642/PM/DPMPTSP, 13 May 2026, island-wide,
  VERIFIED 2026-06-09 via Exa 8+ sources) operates at the RISK-CLASSIFICATION level, NOT
  per-code: OSS blocks EVERY KBLI at risk *Rendah* or *Menengah Rendah* for a PT PMA with a
  Bali address. Only *Menengah Tinggi* and *Tinggi* remain registrable. So for a nationally
  TERBUKA code, what decides Bali-openness is the risk on the **Besar** scale (a PT PMA is
  Usaha Besar by law — that is the tier it actually faces).

  Therefore, for each flagged code:
    A. NO Besar scale row              -> PMA closed (reserved UMKM). blocked stays True.
    B. Besar risk ∈ {Men-Tinggi, Tinggi} -> SURVIVES the moratorium -> OPEN at Bali (blocked=False)
                                          UNLESS a national SECTOR REGULATOR closes it anyway
                                          (NB-3 exceptions, see SECTOR_CLOSED below).
    C. Besar risk ∈ {Rendah, Men-Rendah} -> BLOCKED by the moratorium -> closed (confirmed).
    D. nationally TERTUTUP / 0%         -> already closed nationally; confirm.

  In every case we REMOVE the `_l4_needs_review` flag (the review is now done) and lift
  confidence MEDIUM -> HIGH, because the verdict is now NB-3-grounded, not heuristic.

SECTOR_CLOSED — NB-3 named these as closed by a NATIONAL sector regulator regardless of risk
(the mechanical risk test would wrongly OPEN 86201/86202). Verbatim NB-3:
  - 86201 / 86202 (praktik dokter): TERTUTUP to WNA under Kemenkes health law — a foreign
    doctor cannot open a solo practice; PMA must use 86103 (klinik, TERBATAS 67%).
  - 64110 (Bank Sentral): exclusive State monopoly via Bank Indonesia, structurally closed.
  - 38122 (radioactive waste): strategic sector reserved to BUMN/BAPETEN, closed to private.
These STAY blocked (do not open them even though some carry a high Besar risk).

HARD CONSTRAINT: writes ONLY l4_bali.{status,blocked,confidence,reason,review_basis} and removes
the top-level `_l4_needs_review` key. NEVER touches pma_status / pma_max_asing / per_skala /
judul / any other field. A sha256 fingerprint over (kode, pma_status, pma_max_asing, pma_kondisi)
of EVERY code is printed before+after and must be identical.

Usage:
  python scripts/resolve_kbli_l4_needs_review.py --dry-run
  python scripts/resolve_kbli_l4_needs_review.py
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CANON = REPO / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

HIGH_RISK = {"Menengah Tinggi", "Tinggi"}  # survive the Bali moratorium

# NB-3 exceptions: closed by a national sector regulator regardless of the risk tier.
SECTOR_CLOSED = {
    "86201": ("TERTUTUP", "TERTUTUP to WNA under Kemenkes health law — a foreign doctor cannot "
              "open a solo practice; for PMA use 86103 (klinik, TERBATAS 67%). [NB-3 2026-06-28]"),
    "86202": ("TERTUTUP", "TERTUTUP to WNA under Kemenkes health law — a foreign specialist cannot "
              "open a solo practice; for PMA use 86103 (klinik, TERBATAS 67%). [NB-3 2026-06-28]"),
    "64110": ("CHIUSO_REGOLATORE_SETTORIALE", "Bank Sentral — exclusive State monopoly operated by "
              "Bank Indonesia; structurally closed to any private/PMA capital. [NB-3 2026-06-28]"),
    "38122": ("CHIUSO_REGOLATORE_SETTORIALE", "Radioactive-waste collection — strategic sector "
              "reserved to the State (BUMN) and BAPETEN; closed to private/PMA capital. [NB-3 2026-06-28]"),
}


def code_of(r):
    return str(r.get("kode_kbli_2025") or r.get("kode") or "")


def besar_risk(r):
    """Risk on the scale-row that contains 'Besar' (the tier a PT PMA actually faces). None if no Besar."""
    for p in r.get("per_skala", []) or []:
        sk = p.get("skala_usaha") or []
        if isinstance(sk, str):
            sk = [sk]
        if any("besar" in (s or "").lower() for s in sk):
            return (p.get("kategori_risiko") or "").strip()
    return None


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

    opened = []      # blocked True -> False (open at Bali)
    confirmed = []   # stayed blocked, flag cleared
    flag_cleared = 0

    for r in rows:
        if not r.get("_l4_needs_review"):
            continue
        c = code_of(r)
        l4 = r.setdefault("l4_bali", {})
        br = besar_risk(r)
        nationally_closed = (r.get("pma_status") == "TERTUTUP" or r.get("pma_max_asing") == 0)

        if c in SECTOR_CLOSED:
            new_status, reason = SECTOR_CLOSED[c]
            decision = ("CLOSE", new_status, reason)
        elif nationally_closed:
            decision = ("CLOSE", "TERTUTUP", "Closed to foreign ownership at the national level (TERTUTUP/0%).")
        elif br is None:
            decision = ("CLOSE", "CHIUSO_PMA_NO_BESAR",
                        "OSS has no Usaha Besar scale row -> reserved for UMKM; a PT PMA (Usaha Besar by law) "
                        "cannot register. [structural]")
        elif br in HIGH_RISK:
            decision = ("OPEN", "APERTO_BALI_RISCHIO_ALTO",
                        f"Nationally TERBUKA and the Besar scale is '{br}' -> survives the Bali moratorium "
                        f"(which blocks only Rendah/Menengah Rendah). Registrable by a PT PMA in Bali. [NB-3 2026-06-28]")
        else:
            decision = ("CLOSE", "CHIUSO_MORATORIA_BALI",
                        f"Nationally TERBUKA but the Besar scale is '{br}' -> blocked by the Bali PMA moratorium "
                        f"(Gov. letter B.27.000/642, 13 May 2026: all Rendah/Menengah Rendah blocked for a Bali "
                        f"address). [NB-3 2026-06-28]")

        action, status, reason = decision
        if not dry:
            l4["status"] = status
            l4["blocked"] = (action == "CLOSE")
            l4["confidence"] = "HIGH"
            l4["reason"] = reason
            l4["review_basis"] = "nb3_2026_06_28_moratoria_risk_tier"
            r.pop("_l4_needs_review", None)
        flag_cleared += 1
        (opened if action == "OPEN" else confirmed).append((c, status, br))

    fp_after = pma_fingerprint(rows)

    print(f"resolve _l4_needs_review ({'DRY-RUN' if dry else 'APPLIED'}):")
    print(f"  flags cleared:        {flag_cleared}")
    print(f"  OPENED at Bali:       {len(opened)}")
    for c, st, br in sorted(opened):
        print(f"      {c}  risk={br!s:16} -> {st}")
    print(f"  CONFIRMED closed:     {len(confirmed)}")
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
