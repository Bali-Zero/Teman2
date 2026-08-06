#!/usr/bin/env python3
"""Where the ARTICLE contradicts the RECORD it was written from.

Every KBLI code page leads with an authored article — `intel_2026.editorial`:
a headline, a standfirst, a "By the numbers" sidebar of label/value cells, and
a markdown body. It was written by narrating the JSON record, and the renderer
prints it VERBATIM. So it is not a consumer of the PMA fields in the ordinary
sense; it is a SECOND, INDEPENDENT ASSERTION of the same facts, stored beside
them.

That is the whole problem. A consumer that READS a field moves when the field
moves. A parallel assertion never moves at all. Nine codes were restricted on
2026-08-06 and their pages kept a sidebar cell reading "Foreign-ownership
ceiling: 100%" under a headline reading "Closed to Foreign Investment" — one
page, two answers, and the wrong one is the one shaped like a number.

WHY THIS IS NOT A WEB PROBLEM
-----------------------------
`reindex_kbli_2025_final.py` stringifies the WHOLE `intel_2026` dict into the
embedding text (`for k, v in intel.items(): parts.append(f"- {k}: {v}")`), so
the same contradicted sentences are in Qdrant and reachable by the RAG. A
client asking on WhatsApp about `79122` — Umrah/Hajj travel, adjudicated cap
0% — can be handed retrieved context asserting 100%. Curing this in the
renderer would leave that untouched. It is a DATA defect and it is fixed at the
source or not at all.

TWO KINDS OF CONTRADICTION, AND ONLY ONE IS MECHANICAL
------------------------------------------------------
* A `byTheNumbers` CELL is a restatement of a field we own. "Foreign-ownership
  ceiling: 100%" against `pma_max_asing == 0` is not a difference of opinion;
  it is a stale copy. Correcting it asserts nothing new.
* The BODY is authored narrative. "This activity is nationally open to full
  foreign ownership" is wrong in the same way, but replacing a sentence means
  writing one, and what to say instead is an editorial call (Legge 5). This
  module REPORTS those and never rewrites them.

Reporting them separately is the point. A single number — "31 codes are wrong"
— would hide that some of it is a find-and-replace and some of it needs a human
to write a sentence.

SCOPE IS AN ENTITY, NOT A SUBSTRING (superscar #3)
--------------------------------------------------
A cell labelled `Bali PMA status: TERTUTUP` on a record whose `pma_status` is
TERBUKA is NOT a contradiction: the Bali layer is closed while the national one
is open, and both are true at once — the catalogue says so explicitly. Judging
these cells by matching "PMA status" anywhere in the label convicts 132 lawful
Bali-scoped cells. So the label's SCOPE is resolved first and Bali-scoped cells
are excluded by name, with the exclusion counted and reported rather than left
silent.

IT REPORTS, IT DOES NOT DECIDE
------------------------------
`--check` exits 0 while divergences exist, like its siblings in this directory.
The tripwire that makes a NEW contradiction fail CI is a test, not this script.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

# A label naming the BALI layer. Resolved before anything else: these cells
# describe a different fact and comparing them to the national fields is the
# category error this module's docstring is mostly about.
_BALI_SCOPED = re.compile(r"\bbali\b", re.IGNORECASE)
_CEILING_LABEL = re.compile(r"ceiling", re.IGNORECASE)
_STATUS_LABEL = re.compile(r"PMA status", re.IGNORECASE)
_PERCENT = re.compile(r"(\d+)\s*%")
_STATUSES = frozenset({"TERBUKA", "TERTUTUP", "TERBATAS"})

# Body sentences asserting the activity is nationally open.
#
# The first version of this was a proximity match — "national" within 80
# characters of "open" — and it convicted pages that were RIGHT. `59121` says
# "this is NOT an activity open to foreign ownership at the national level",
# which is correct and which the proximity rule read as an openness claim: it
# matched the words and not the assertion, which is the same form-over-entity
# error the Bali exclusion above exists to avoid. Found by reading the twenty
# bodies the first version flagged where the sidebar cells were clean.
#
# So: work a SENTENCE at a time, require an affirmative openness claim, and
# drop any sentence carrying a negation. The negation list is deliberately
# blunt — a sentence containing "not"/"no"/"cannot"/"never" near an openness
# word is not evidence of a false claim, and letting one through costs nothing
# because the sidebar cells are checked independently.
_SENTENCE = re.compile(r"[^.!?\n]+")
_NATIONAL_SCOPE = re.compile(r"national(?:ly)?", re.IGNORECASE)
_OPENNESS_CLAIM = re.compile(
    r"open\s+(?:to|nationally|for)|nationally\s+open|open\s+national|"
    r"100\s*%\s*(?:national|foreign)|full\s+foreign\s+ownership",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:not|no|never|cannot|can't|isn't|does\s+not|nor)\b", re.IGNORECASE)


def load_records(path: Path = CANONICAL) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["data"]


def _cells(record: dict[str, Any]) -> list[dict[str, Any]]:
    editorial = (record.get("intel_2026") or {}).get("editorial") or {}
    return [c for c in (editorial.get("byTheNumbers") or []) if isinstance(c, dict)]


def _body(record: dict[str, Any]) -> str:
    editorial = (record.get("intel_2026") or {}).get("editorial") or {}
    return " ".join(
        str(editorial.get(k) or "") for k in ("headline", "standfirst", "body")
    )


def classify(record: dict[str, Any]) -> dict[str, Any]:
    """Buckets for ONE record. Empty lists everywhere means it agrees with itself."""
    cap = record.get("pma_max_asing")
    status = (record.get("pma_status") or "").upper()
    out: dict[str, Any] = {
        "code": record.get("kode_kbli_2025"),
        "pma_status": status,
        "pma_max_asing": cap,
        "ceiling_cells": [],
        "status_cells": [],
        "bali_scoped_skipped": 0,
        "body_asserts_national_openness": False,
    }

    for cell in _cells(record):
        label = str(cell.get("label") or "")
        value = str(cell.get("value") or "")
        if _BALI_SCOPED.search(label):
            # Counted, not silently dropped: a skip nobody can see is a scope
            # decision nobody can audit.
            if _CEILING_LABEL.search(label) or _STATUS_LABEL.search(label):
                out["bali_scoped_skipped"] += 1
            continue
        if _CEILING_LABEL.search(label):
            m = _PERCENT.search(value)
            if m is not None and isinstance(cap, int) and int(m.group(1)) != cap:
                out["ceiling_cells"].append(
                    {"label": label, "says": value, "record_says": cap}
                )
        elif _STATUS_LABEL.search(label):
            said = value.strip().upper()
            if said in _STATUSES and status and said != status:
                out["status_cells"].append(
                    {"label": label, "says": said, "record_says": status}
                )

    # Asked only where a national openness claim would actually be FALSE, and
    # that test is the CEILING, not the status word. `79110` is TERBATAS with a
    # cap of 100: "a 100% national foreign-ownership ceiling" is true of it, and
    # the first version of this predicate — `status in {TERBATAS, TERTUTUP} or
    # cap < 100` — convicted it. TERBATAS at 100 means restricted by conditions
    # that are not a percentage, which is a different sentence to write and not
    # this module's business.
    capped = isinstance(cap, int) and cap < 100
    if capped:
        for sentence in _SENTENCE.findall(_body(record)):
            if not (_NATIONAL_SCOPE.search(sentence) and _OPENNESS_CLAIM.search(sentence)):
                continue
            if _NEGATION.search(sentence):
                continue
            out["body_asserts_national_openness"] = True
            out["body_sentence"] = sentence.strip()[:300]
            break

    return out


def report(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [classify(r) for r in records]
    mechanical = [
        r for r in rows if r["ceiling_cells"] or r["status_cells"]
    ]  # a stale copy of a field we own
    editorial = [
        r for r in rows if r["body_asserts_national_openness"]
    ]  # needs a sentence written, not a value replaced
    return {
        "codes": len(records),
        "mechanically_correctable": {
            "codes": sorted(r["code"] for r in mechanical),
            "ceiling_cells": sum(len(r["ceiling_cells"]) for r in mechanical),
            "status_cells": sum(len(r["status_cells"]) for r in mechanical),
        },
        "needs_an_author": {
            "codes": sorted(r["code"] for r in editorial),
        },
        "bali_scoped_cells_excluded": sum(r["bali_scoped_skipped"] for r in rows),
        "rows": mechanical,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--dataset", type=Path, default=CANONICAL)
    args = ap.parse_args(argv)

    rep = report(load_records(args.dataset))
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    mech, auth = rep["mechanically_correctable"], rep["needs_an_author"]
    lines = [
        f"editorial_record_conformance — {rep['codes']} codes",
        "",
        f"  stale copies of a field we own : {len(mech['codes'])} codes "
        f"({mech['ceiling_cells']} ceiling cells, {mech['status_cells']} status cells)",
        f"  bodies that need an author     : {len(auth['codes'])} codes",
        f"  Bali-scoped cells excluded     : {rep['bali_scoped_cells_excluded']} "
        f"(a closed Bali layer over an open national one is lawful, not a contradiction)",
        "",
    ]
    for row in rep["rows"]:
        for c in row["ceiling_cells"]:
            lines.append(
                f"  {row['code']}  {c['label']!r} says {c['says']} — record says {c['record_says']}%"
            )
        for c in row["status_cells"]:
            lines.append(
                f"  {row['code']}  {c['label']!r} says {c['says']} — record says {c['record_says']}"
            )
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
