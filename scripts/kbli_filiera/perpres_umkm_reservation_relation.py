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
* `retired-2020-code` — the annex speaks KBLI 2020 and this code has NO live
  2025 heir, so no page renders it. Archaeology, not client-facing.
  **CORRECTED 2026-08-03, and the correction is the whole point of this
  paragraph.** The bucket asserted "no 2025 descendant" while the code tested
  `canonical.get(row["code"])` — i.e. whether the same NUMBER survives the
  vintage change. Every RENUMBERED code therefore landed here: `55193 Vila` ->
  `55203`, `96112 Salon kecantikan` -> `96220`, `96200 Penatu` -> `96100`.
  Measured before the fix: **30 of 30 rows in this bucket had a live heir; not
  one was retired**, and between them they reach **66 live pages**, all
  published `TERBUKA/100%`. Judging by form (the number) instead of entity (the
  activity, via the BPS crosswalk) is superscar #3 — and it failed in the one
  direction that hides a reservation, because this bucket is the one declared
  not-client-facing. It is now resolved through
  `bps-crosswalk/edges-lampiran5.json`, and the file is REQUIRED: without it
  this module exits CANNOT-VERIFY rather than silently re-deriving the bug.
* `split-heirs` — the 2020 activity was SPLIT across several 2025 codes, so the
  annex's single reserved bidang usaha cannot be carried to all of them. It is
  a separate bucket rather than N rows in `whole-row` because collapsing it
  would manufacture reservations: `55110` is reserved as **"Hotel Bintang I"**
  and the crosswalk sends it to all five star ratings; `10774` is reserved only
  for salt **"mendapatkan indikasi geografis: Garam Amed Bali"** and reaches two
  industrial codes; `96112 Salon kecantikan` also reaches the intermediation
  code `96400`. Each heir is a per-code reading for the owner, never a
  deduction. 12 rows -> 22, 8, 5, 5, 5, 5, 2, 2, 2, 2, 2, 2 heirs.
* `whole-row` — a live code (its own number or its single crosswalk heir), a
  readable single activity, no segment qualifier, and the catalogue publishes it
  open. This is the bucket that is genuinely a question for the owner, and it is
  the LARGEST of the divergent ones — which is why it must not be reported as a
  single number.

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
CROSSWALK = REPO_ROOT / "data" / "kbli-filiera" / "bps-crosswalk" / "edges-lampiran5.json"

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


def load_crosswalk(path: Path = CROSSWALK) -> dict[str, list[str]]:
    """The BPS 2020->2025 conversion edges, as `{kbli_2020: [kbli_2025, ...]}`.

    DECLARED LIMIT, because every 2025-numbered verdict downstream inherits it:
    the conversion table is a STATISTICAL artefact with no legal force. No
    investment instrument has ever been re-issued in KBLI-2025 numbering, so
    "this 2025 code is the reserved activity" is always an inference through
    BPS, never a citation. That is precisely why this module reports and never
    decides.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} missing — the annex speaks KBLI 2020 and the catalogue speaks 2025; "
            "without the crosswalk this module cannot tell a retired code from a renumbered one"
        )
    edges: dict[str, list[str]] = {}
    for edge in json.loads(path.read_text()):
        edges.setdefault(str(edge["kbli_2020"]), []).append(str(edge["kbli_2025"]))
    return edges


def live_heirs(code: str, canonical: dict[str, dict], crosswalk: dict[str, list[str]]) -> list[str]:
    """The live 2025 pages this 2020 code reaches — by ENTITY, not by number.

    The crosswalk wins over number-identity when both exist: a 2025 catalogue
    can reuse a number for a different activity, and the conversion table is the
    only thing that knows which activity carried over. Identity is the FALLBACK
    for codes the crosswalk is silent about, so a gap in the edges degrades to
    the old reading rather than erasing a live page.
    """
    heirs = [h for h in dict.fromkeys(crosswalk.get(code, [])) if h in canonical]
    if heirs:
        return heirs
    return [code] if code in canonical else []


def classify(
    row: dict, canonical: dict[str, dict], crosswalk: dict[str, list[str]]
) -> tuple[str, dict | None, list[str]]:
    """Bucket one relation row. Returns (bucket, record-or-None, heirs).

    Order matters and is not cosmetic: a row is judged unusable BEFORE it is
    judged divergent, so a missing activity or a dead code can never be counted
    as a live contradiction of a live page.

    `crosswalk` is REQUIRED, not defaulted. A default of `{}` would silently
    reproduce the number-identity bug this function was fixed for, and it would
    do so in the invisible direction (a live reservation filed as archaeology).
    A caller must say what crosswalk it holds; `{}` is a legitimate answer for a
    unit test asserting the no-heir branch, and an illegitimate one for a run.
    """
    if row["column"] != "dialokasikan":
        return "kemitraan-no-bar", None, []
    heirs = live_heirs(row["code"], canonical, crosswalk)
    if not heirs:
        return "retired-2020-code", None, []
    if len(heirs) > 1:
        # The 2020 activity was split. The annex names ONE bidang usaha; which
        # heirs inherit it is a reading, not a deduction — "Hotel Bintang I"
        # must not become a reservation on five-star hotels.
        return "split-heirs", None, heirs
    record = canonical[heirs[0]]
    if not foreign_can_take(record):
        return "agree", record, heirs
    if row.get("text") is None:
        return "activity-unknown", record, heirs
    if _SEGMENT_RE.search(row["text"]):
        return "segment-qualified", record, heirs
    return "whole-row", record, heirs


def report(relation: dict, canonical: dict[str, dict], crosswalk: dict[str, list[str]]) -> dict:
    buckets: dict[str, list[dict]] = {}
    for row in relation["rows"]:
        bucket, record, heirs = classify(row, canonical, crosswalk)
        entry = {
            "code": row["code"],
            "page": row["page"],
            "text": row.get("text"),
            "pma_status": (record or {}).get("pma_status"),
            "pma_max_asing": (record or {}).get("pma_max_asing"),
            "judul": (record or {}).get("judul"),
        }
        # Name the 2025 page a reader would actually open. Without this the
        # renumbered rows read as 2020 numbers nobody can look up.
        if heirs and heirs != [row["code"]]:
            entry["heirs_2025"] = [
                {"code": h, "judul": canonical[h].get("judul"),
                 "pma_status": canonical[h].get("pma_status"),
                 "pma_max_asing": canonical[h].get("pma_max_asing")}
                for h in heirs
            ]
        buckets.setdefault(bucket, []).append(entry)
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
        rep = report(load_relation(), load_canonical(), load_crosswalk())
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
        via = f" (2020 {row['code']})" if row.get("heirs_2025") else ""
        code = row["heirs_2025"][0]["code"] if row.get("heirs_2025") else row["code"]
        print(f"    {code}  {row['pma_status']}/{cap if cap is not None else '-'}%  "
              f"p{row['page']:<3} {(row['judul'] or '')[:44]:44} | annex: {(row['text'] or '')[:34]}{via}")
    for row in rep["detail"].get("split-heirs", []):
        print(f"    SPLIT 2020 {row['code']} p{row['page']:<3} -> {len(row['heirs_2025'])} live 2025 code(s) "
              f"| annex reserves only: {(row['text'] or '')[:46]}")
        for h in row["heirs_2025"]:
            cap = h["pma_max_asing"]
            print(f"          {h['code']}  {h['pma_status']}/{cap if cap is not None else '-'}%  "
                  f"{(h['judul'] or '')[:46]}")
    # Reporter, never a gate: divergence is a question for the owner (Legge 5).
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
