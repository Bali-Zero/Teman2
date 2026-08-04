#!/usr/bin/env python3
"""Replace the Bali verdict on the 39 codes whose closure rested on one bad inference.

WHAT THIS UNDOES
----------------
`scripts/resolve_kbli_l4_needs_review.py` (#1814) derives the Bali verdict from
the risk/scale layer, and one of its branches reads:

    elif besar_risk(r) is None:
        CLOSE, "CHIUSO_PMA_NO_BESAR",
        "OSS has no Usaha Besar scale row -> reserved for UMKM; a PT PMA
         (Usaha Besar by law) cannot register. [structural]"

i.e. **the absence of a licensing row is read as an ownership bar**.
**Permeninves/BKPM 5/2025 Pasal 26(1) inverts it**: being *Usaha Besar* is a
CONSEQUENCE of PMA status, not a gate a licensing table can withhold. That single
inference produced all 39 closures, and the page renders it as *"Reserved for
MSME — closed to PT PMA"* — an assertion about Indonesian investment law that no
instrument makes.

THE REPLACEMENT IS NOT A GUESS
------------------------------
`data/kbli-filiera/kbli39-perpres-adjudication.json` carries a per-code verdict
adjudicated against primary instruments (8 research lanes + 8 refute lanes on
fresh context, then graded by Codex on the finished report). Ownership comes from
THAT; the Bali position comes from the risk tier, as it does for every other code
in the catalogue. The two questions are answered by the two things that answer
them, which is the whole point:

  RESERVED    -> `CHIUSO_PMA_NO_BESAR` KEPT. The label happens to be right for
                 these seven: they ARE allocated to Koperasi/UMKM. Only the
                 `reason` changes, from the inference to the annex row.
  PARTIAL     -> `BLOCCATO_DIPENDE_SCOPE`. Pasal 5(5) scopes a reservation to the
                 wording in the Bidang Usaha column, so `55209` is reserved only
                 as *Guest House* and `43110` only for *simple and intermediate
                 technology* demolition. "Depends on declared scope" is exactly
                 what that is.
  otherwise   -> the ownership bar is withdrawn and the Bali question is answered
                 on its own terms (below).

DECLARED EXTENSION — read this before trusting the tier
-------------------------------------------------------
The existing pass reads the risk tier off the row that CONTAINS `Besar`. For
these 39 that row does not exist — its absence is why they were closed. So the
tier here is taken from **whatever scale rows the code does have**, and that is a
NEW rule, stated rather than smuggled: the Governor's letter blocks by the
ACTIVITY's risk tier (`Rendah` / `Menengah Rendah`), not by the scale a PMA would
occupy, so the rows that exist are evidence about the activity.

  no rows at all -> `NON_CLASSIFICABILE` ("Bali status not classifiable —
                    verify"). We hold nothing; saying so is the honest verdict and
                    is a strict improvement on a false closure.
  any HIGH tier  -> `APERTO_BALI_RISCHIO_ALTO`. Measured 0 of 39 today. The branch
                    stays because an empty bucket that is still computed will
                    speak if the licensing rows arrive, whereas a deleted one
                    turns the same case into a silent misclassification.
  otherwise      -> `CHIUSO_MORATORIA_BALI`. Still blocked, still a red badge —
                    but for the TRUE reason, and it joins the 35 codes that
                    already carry it.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It never touches `pma_status` / `pma_max_asing` / `pma_kondisi`. Those are the
national ownership fields; this cure is about the Bali verdict layer. The
fingerprint over them is asserted before and after, and a change ABORTS the
write — the same guard `resolve_kbli_l4_needs_review.py` uses, for the same
reason.

It also does not touch the 1,520 codes outside the adjudication. Scope is the
file, and the file is 39 rows.

Usage:
    python scripts/kbli_filiera/cure_l4bali_perpres_adjudication.py            # dry-run
    python scripts/kbli_filiera/cure_l4bali_perpres_adjudication.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
ADJUDICATION = REPO_ROOT / "data" / "kbli-filiera" / "kbli39-perpres-adjudication.json"

EXIT_OK, EXIT_REFUSED, EXIT_CANNOT_VERIFY = 0, 3, 4

CODE_FIELD = "kode_kbli_2025"

# The tiers that survive the Bali moratorium. Same set as
# `resolve_kbli_l4_needs_review.HIGH_RISK`; a tripwire test asserts the two agree,
# because a set copied into two files is how this dataset earned its scars.
HIGH_RISK = frozenset({"Menengah Tinggi", "Tinggi"})

# The verdict this cure exists to withdraw. A row not carrying it is out of scope
# — the cure must never move a code some other pass has since re-decided.
EXPECTED_CURRENT_STATUS = "CHIUSO_PMA_NO_BESAR"

_PASAL_5_5 = (
    "Perpres 10/2021 Pasal 5(5) scopes a Lampiran II reservation to the activity named in the "
    "Bidang Usaha column, not to the whole KBLI code"
)


def risk_tiers(record: dict) -> set[str]:
    """Every risk tier this code's licensing rows carry, from ANY scale.

    Not `besar_risk()`: these codes have no Besar row, which is precisely the
    fact that was misread as an ownership bar.
    """
    return {
        (row.get("kategori_risiko") or "").strip()
        for row in (record.get("per_skala") or [])
        if (row.get("kategori_risiko") or "").strip()
    }


def pma_fingerprint(records: list[dict]) -> str:
    """Hash of the NATIONAL ownership fields — the ones this cure must not move."""
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda r: str(r.get(CODE_FIELD))):
        digest.update(
            f"{record.get(CODE_FIELD)}|{record.get('pma_status')}|"
            f"{record.get('pma_max_asing')}|{record.get('pma_kondisi')}\n".encode()
        )
    return digest.hexdigest()[:16]


def decide(verdict: str, record: dict, instrument: str) -> tuple[str, str]:
    """Pure. (new_status, reason) for one adjudicated code."""
    if verdict == "RESERVED":
        return (
            "CHIUSO_PMA_NO_BESAR",
            "Allocated to Koperasi/UMKM by Perpres 49/2021 Lampiran II (dialokasikan column): a "
            f"PT PMA cannot take this bidang usaha. {instrument} "
            "[Perpres annex, not an OSS scale inference]",
        )
    if verdict == "PARTIAL":
        return (
            "BLOCCATO_DIPENDE_SCOPE",
            f"Reserved to Koperasi/UMKM only as to a NAMED sub-activity — {_PASAL_5_5}. "
            f"{instrument} The rest of the code is not reserved; the answer depends on the "
            "scope actually declared. [Perpres annex]",
        )

    # The ownership bar is withdrawn. What remains is the ordinary Bali question.
    withdrawn = (
        "No foreign-ownership restriction located in Perpres 49/2021 Lampiran I/II/III, the closed "
        "list, or any sectoral instrument read"
        if verdict == "NONE"
        else (
            "The located requirement is not an ownership rule and a PT PMA can satisfy it: "
            f"{instrument}"
            if verdict == "REQUIREMENT"
            else f"A partnership duty, which does not bar foreign ownership: {instrument}"
        )
    )
    tiers = risk_tiers(record)
    if not tiers:
        return (
            "NON_CLASSIFICABILE",
            f"{withdrawn}. The catalogue holds no licensing rows for this code, so its Bali risk "
            "tier is unknown and the Bali position cannot be stated — verify case by case. The "
            "previous 'reserved for MSME' verdict rested on that same absence and was withdrawn "
            "(Permeninves/BKPM 5/2025 Pasal 26(1): Usaha Besar is a consequence of PMA status, not "
            "a gate).",
        )
    if tiers & HIGH_RISK:
        return (
            "APERTO_BALI_RISCHIO_ALTO",
            f"{withdrawn}. Risk tier {sorted(tiers)} survives the Bali PMA moratorium, which is "
            "requested for Rendah and Menengah Rendah only.",
        )
    return (
        "CHIUSO_MORATORIA_BALI",
        f"{withdrawn} — so this is NOT closed to foreign ownership. It is blocked in Bali by the "
        f"PMA moratorium: risk tier {sorted(tiers)} falls inside the Rendah / Menengah Rendah "
        "categories the Governor of Bali asked BKPM to close on OSS (letter B.27.000/642/PM/DPMPTSP, "
        "28 Jan 2026, read at source: the request is by RISK TIER, and carries no annex or code list).",
    )


def plan(records: list[dict], adjudication: dict) -> tuple[list[dict], list[dict]]:
    """Pure. (changes, refusals). A refusal is named, never dropped silently."""
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    changes, refusals = [], []
    for row in adjudication["rows"]:
        code = row["code"]
        record = by_code.get(code)
        if record is None:
            refusals.append({"code": code, "why": "not in canonical"})
            continue
        current = (record.get("l4_bali") or {}).get("status")
        if current != EXPECTED_CURRENT_STATUS:
            refusals.append(
                {"code": code, "why": f"already re-decided elsewhere: {current!r}, not {EXPECTED_CURRENT_STATUS!r}"}
            )
            continue
        status, reason = decide(row["verdict"], record, row.get("instrument", ""))
        changes.append(
            {
                "code": code,
                "verdict": row["verdict"],
                "from": current,
                "to": status,
                "reason": reason,
                "blocked": status not in {"APERTO_BALI_RISCHIO_ALTO"},
                "confidence": "MEDIUM" if status == "NON_CLASSIFICABILE" else "HIGH",
            }
        )
    return changes, refusals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--apply", action="store_true", help="write canonical (default: dry-run)")
    ap.add_argument("--json", action="store_true", help="machine-readable plan on stdout")
    args = ap.parse_args(argv)

    try:
        payload = json.loads(CANONICAL.read_text())
        adjudication = json.loads(ADJUDICATION.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"CANNOT-VERIFY: {exc}", file=sys.stderr)
        return EXIT_CANNOT_VERIFY

    records = payload["data"]
    changes, refusals = plan(records, adjudication)

    if args.json:
        print(json.dumps({"changes": changes, "refusals": refusals}, ensure_ascii=False, indent=1))
        return EXIT_OK

    counts: dict[str, int] = {}
    for change in changes:
        counts[change["to"]] = counts.get(change["to"], 0) + 1
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"{mode}: {len(changes)} of {len(adjudication['rows'])} adjudicated code(s) to re-decide")
    for status, count in sorted(counts.items()):
        print(f"  {status:26} {count}")
    for change in sorted(changes, key=lambda c: (c["to"], c["code"])):
        print(f"    {change['code']}  {change['verdict']:11} {change['from']} -> {change['to']}")
    for refusal in refusals:
        print(f"  REFUSED {refusal['code']}: {refusal['why']}")

    if not changes:
        print("nothing to do")
        return EXIT_OK
    if not args.apply:
        print("dry-run complete — rerun with --apply to write")
        return EXIT_OK

    before = pma_fingerprint(records)
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    for change in changes:
        l4 = by_code[change["code"]].setdefault("l4_bali", {})
        l4["status"] = change["to"]
        l4["blocked"] = change["blocked"]
        l4["confidence"] = change["confidence"]
        l4["reason"] = change["reason"]
        l4["review_basis"] = "perpres_adjudication_2026_08_03"
    after = pma_fingerprint(records)
    if before != after:
        print("::error:: national PMA fields moved — refusing to write", file=sys.stderr)
        return EXIT_REFUSED

    CANONICAL.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"WROTE {CANONICAL} — PMA fingerprint {before} unchanged")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
