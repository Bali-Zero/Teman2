#!/usr/bin/env python3
"""The Koperasi/UMKM reservation relation, and what the catalogue says instead.

WHAT THIS IS
------------
The reader side of `parse_perpres_lampiran2.py`. That compiler turns the vaulted
`Perpres 49/2021 Lampiran II` into rows; this module joins those rows against
the 1,559-code catalogue and reports where the two disagree. Sibling of
`perpres_foreign_cap_relation.py`, which does the same job for Lampiran III
(percentage caps). Together they are the only checkable source under the
`pma_source: "Perpres 10/2021, 49/2021"` that all 1,559 records carry.

IT REPORTS, IT DOES NOT DECIDE — AND THAT IS DELIBERATE
--------------------------------------------------------
`--check` exits 0 while divergences exist, exactly like its sibling. A
reservation is not mechanically a `pma_status` value: most rows reserve a
SEGMENT of an activity (a construction grade, one bidang usaha among several),
and turning "reserved" into a client-facing verdict is a legal reading reserved
to the owner (Legge 5). Wiring this into a gate would mean a script silently
re-labelling client-facing pages on a reading nobody made.

DIALOKASIKAN != KEMITRAAN — THE WHOLE POINT
--------------------------------------------
Only the DIALOKASIKAN column bars foreign ownership: the bidang usaha is
allocated to Koperasi/UMKM, and a PT PMA (Usaha Besar by law) cannot take it.
KEMITRAAN is a duty to partner with them, which an open PMA discharges by
partnering. Collapsing the two — e.g. a substring match on "UMKM" over the
annex title, which names both — asserts a bar on 57 rows that carry none.
`kbli_eye.is_umkm_reserved` was `not is_open_pma` until 2026-07-27, i.e. that
error at full strength across 71 codes; it now names 2. This relation is the
evidence for widening that 2 honestly rather than by inference.

THE BUCKETS ARE THE PRODUCT
----------------------------
A flat "N codes are wrong" would be the third defect this axis has produced.
Each divergent row is instead sorted by WHY it cannot simply be applied:

* `segment-qualified` — the bidang usaha names a construction grade
  ("sederhana dan madya") or another sub-slice. The code stays partly open;
  only the named segment is reserved. Never a whole-code verdict.
* `activity-unknown` — the code is certain but WHICH bidang usaha is reserved
  is unreadable. **Currently EMPTY, and the reason is worth keeping**: it held
  30 rows while the compiler read only the line each tick sits on. Reading the
  whole multi-line cell emptied it. The branch stays because an empty bucket
  that is still computed will speak again if the layout shifts, whereas a
  deleted one turns the same failure into a silent misclassification.
* `retired-2020-code` — the annex speaks KBLI 2020 and this code has no 2025
  descendant, so no live page renders it. Archaeology, not client-facing.
* `whole-row` — a live code, a readable single activity, no segment qualifier,
  and the catalogue publishes it open. This is the bucket that is genuinely a
  question for the owner, and it is the LARGEST of the divergent ones — which
  is why it must not be reported as a single number.

Known floor on `segment-qualified`, declared rather than silently absorbed: a
grade qualifier can live in the numbered PARENT heading instead of the row
("35. Konstruksi bangunan yang menggunakan teknologi sederhana dan madya:"
governs `42911`/`42912`/`42913` below it). Those rows are left in `whole-row`
on purpose. Inheriting a parent's qualifier would move rows OUT of the owner's
list on an inference, and a question wrongly withdrawn is worse than a question
wrongly asked.

Usage:
    python scripts/kbli_filiera/perpres_umkm_reservation_relation.py --check [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RELATION = REPO_ROOT / "data" / "kbli-filiera" / "perpres-umkm-reservation.json"
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

EXIT_OK, EXIT_CANNOT_VERIFY = 0, 4

# A construction grade or an explicit sub-slice: the row reserves part of the
# activity. Matched with word boundaries — "madya" must not fire inside a longer
# word, and this list is deliberately short: an unrecognised qualifier falls to
# `whole-row`, where a human reads it, rather than being silently absorbed.
_SEGMENT_RE = re.compile(r"\b(sederhana|madya|kecil|mikro|kualifikasi)\b", re.IGNORECASE)

# Statuses that leave a foreign investor able to take the activity. TERTUTUP is
# already closed to everyone, so a reservation adds nothing a client would see.
_OPEN_STATUSES = frozenset({"TERBUKA", "TERBATAS"})


def foreign_can_take(record: dict) -> bool:
    """Whether the catalogue, as published, leaves a foreign investor able to
    take this activity — the only thing a reservation could contradict.

    Judged on the effective CAP, not the status label: `47111` is
    `TERBATAS` with `pma_max_asing: 0`, i.e. already barred, and counting it as
    a divergence would have reported the one code the backend already names
    reserved as evidence that it is not.

    An ABSENT `pma_max_asing` is NOT zero. Exactly one record lacks the key
    (`01122`, TERBUKA) and reading that absence as 0% is the coercion that
    rendered "0% Open" on a live page until 2026-07-27. Absent means unstated,
    which under a TERBUKA status leaves the investor able to take it.
    """
    if record.get("pma_status") not in _OPEN_STATUSES:
        return False
    cap = record.get("pma_max_asing")
    return not (cap is not None and float(cap) == 0)


def load_relation(path: Path = RELATION) -> dict:
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} missing — run: python scripts/kbli_filiera/parse_perpres_lampiran2.py --write"
        )
    return json.loads(path.read_text())


def load_canonical(path: Path = CANONICAL) -> dict[str, dict]:
    return {str(rec["kode_kbli_2025"]): rec for rec in json.loads(path.read_text())["data"]}


def classify(row: dict, canonical: dict[str, dict]) -> tuple[str, dict | None]:
    """Bucket one relation row. Returns (bucket, record-or-None).

    Order matters and is not cosmetic: a row is judged unusable BEFORE it is
    judged divergent, so a missing activity or a dead code can never be counted
    as a live contradiction of a live page.
    """
    if row["column"] != "dialokasikan":
        return "kemitraan-no-bar", None
    record = canonical.get(row["code"])
    if record is None:
        return "retired-2020-code", None
    if not foreign_can_take(record):
        return "agree", record
    if row.get("text") is None:
        return "activity-unknown", record
    if _SEGMENT_RE.search(row["text"]):
        return "segment-qualified", record
    return "whole-row", record


def report(relation: dict, canonical: dict[str, dict]) -> dict:
    buckets: dict[str, list[dict]] = {}
    for row in relation["rows"]:
        bucket, record = classify(row, canonical)
        buckets.setdefault(bucket, []).append({
            "code": row["code"],
            "page": row["page"],
            "text": row.get("text"),
            "pma_status": (record or {}).get("pma_status"),
            "pma_max_asing": (record or {}).get("pma_max_asing"),
            "judul": (record or {}).get("judul"),
        })
    return {
        "instrument": relation["instrument"],
        "source": relation["source"],
        "ticks": relation["counts"]["ticks"],
        "rows_emitted": relation["counts"]["rows_emitted"],
        "rows_unresolved": relation["counts"]["unresolved"],
        "buckets": {name: len(items) for name, items in sorted(buckets.items())},
        "detail": buckets,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="print the join report")
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    args = ap.parse_args(argv)

    try:
        rep = report(load_relation(), load_canonical())
    except FileNotFoundError as exc:
        print(f"CANNOT-VERIFY: {exc}", file=sys.stderr)
        return EXIT_CANNOT_VERIFY

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return EXIT_OK

    print(f"{rep['instrument']} — {rep['rows_emitted']} rows from {rep['ticks']} ticks "
          f"({rep['rows_unresolved']} unresolved)")
    for name, count in rep["buckets"].items():
        print(f"  {name:20} {count}")
    for row in rep["detail"].get("whole-row", []):
        cap = row["pma_max_asing"]
        print(f"    {row['code']}  {row['pma_status']}/{cap if cap is not None else '-'}%  "
              f"p{row['page']:<3} {(row['judul'] or '')[:44]:44} | annex: {(row['text'] or '')[:34]}")
    # Reporter, never a gate: divergence is a question for the owner (Legge 5).
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
