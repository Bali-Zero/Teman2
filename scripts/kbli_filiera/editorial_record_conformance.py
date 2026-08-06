#!/usr/bin/env python3
"""Where the ARTICLE contradicts the RECORD it was written from.

Every KBLI code page leads with an authored article — `intel_2026.editorial`:
a headline, a standfirst, a pull quote, a "By the numbers" sidebar of
label/value cells, and a markdown body. It was written by narrating the JSON
record, and the renderer prints it VERBATIM. So it is not a consumer of the PMA
fields in the ordinary sense; it is a SECOND, INDEPENDENT ASSERTION of the same
facts, stored beside them.

And `editorial` is not where the prose ends. `intel_2026` carries eight further
authored keys — `whatItMeans`, `whatYouNeed`, `whatChanged`, `zantaraOpener`,
`baliContext`, `whoThisIsFor`, `youllAlsoNeed`, `tkaInfo` — thirteen prose
fields in all, every one of them stringified into the embedding text. Auditing
three of them and reporting the result as "the bodies" was this module's own
first defect: it named a population of 20 where the population is 27, and the
single largest offender was `whatYouNeed`, the field that tells a client what
to file. See `_prose_fields` for both halves of that mistake.

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

THE GUARDS THAT ALREADY EXIST — ONE IS UNRELATED, ONE IS A PARTIAL TWIN
------------------------------------------------------------------------
CORRECTION, and the way the mistake was made is the useful part. An earlier
version of this section said "there is already a guard for this, and it watches
the other direction", naming only rule L9. That was written after checking the
lint rule whose NAME matched (`validate_pma_consistency`) and never opening
rule **L10**, whose BEHAVIOUR matched — even though the first lint run printed
`L10: 28` in plain sight. Checking the guard whose name matches instead of the
one whose behaviour matches is the same form-over-entity habit this module's
Bali exclusion exists to avoid, committed while writing the paragraph about it.

**L9 — unrelated.** Two literal substring tests. Its two live findings
(`43110`, `86201`) are both TERBUKA/100 caught by the "record open, prose says
closed" branch — a page understating what a client may do. The branch guarding
the expensive direction requires `pma_status == "TERTUTUP"` AND the literal
string "100% foreign", which no live record satisfies. Disjoint from this
module, measured.

**L10 — a partial twin with complementary blind spots**, and NOT to be treated
as redundant in either direction. It walks the same prose via `iter_prose` and
compares a percentage claim against `pma_max_asing`, with a real SSOT
(`l10_ownership_contradiction`) carrying innocence idioms this module does not
have ("100% closed", "not 100% open"). Measured on the live catalogue:

    this module 31 · L10 17 · overlap 14 · this-module-only 17 · L10-only 3

So each finds real contradictions the other misses. This module reads sentences
for an openness ASSERTION, which catches "nationally open to full foreign
ownership" with no number in it; L10 reads for a PERCENTAGE, which catches
numeric claims phrased in ways no sentence-level openness predicate matches
(`41011`, `52292`, `53200` are live examples this module does not see, and they
are a DECLARED gap here, not a fixed one — closing them means widening a
predicate, which needs its own guilt and innocence).

The reason is structural rather than a matter of degree. L9 is two literal
substring tests:

    pma_status == "TERTUTUP" and "100% foreign" in text     # record closed, prose open
    pma_status == "TERBUKA"  and "closed to foreign" in text # record open, prose closed

Nothing is folded together here. Both lint rules stay exactly as they are: L10
is BLOCKING and already carries a long-standing backlog (28 findings before
2026-08-06, 31 after `#3673`, 23 after the stat-card cure), and rewiring a
blocking lint while its backlog is live is how an unrelated PR turns red (W95).
Reconciling them so two tools cannot answer one question two ways (W105) belongs
on the LINT's side, consuming this report the way `kbli_documents_cure.py`
consumes `kbli_surface_conformance.py --json`. The relationship is pinned by
`test_this_module_is_not_a_twin_of_the_existing_L9_lint_rule` so that it cannot
drift unnoticed again.

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
from collections import Counter
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


def _prose_fields(record: dict[str, Any]) -> list[tuple[str, str]]:
    """Every authored string under `intel_2026`, with the path that holds it.

    Two defects in the first version, both the same shape, both measured on the
    live catalogue rather than reasoned about:

    1. **It read three fields of thirteen.** `intel_2026` carries
       `whatItMeans`, `whatYouNeed`, `whatChanged`, `zantaraOpener`,
       `baliContext`, `whoThisIsFor`, `youllAlsoNeed`, a `tkaInfo` block and an
       `editorial` block whose own `pullQuote` was also unread — and
       `reindex_kbli_2025_final.py` stringifies the WHOLE dict into the
       embedding text, so all of them reach Qdrant and the RAG exactly as the
       body does. Auditing `headline`/`standfirst`/`body` and reporting the
       result as "the bodies that need an author" measured the fields that were
       convenient to read. Nineteen of the offending sentences live in
       `whatYouNeed` alone. Hence: walk every string, whatever its depth, so a
       prose key added next month is covered on the day it appears rather than
       whenever someone remembers to extend a list.

    2. **It JOINED the three before splitting into sentences.** A headline
       carries no terminal full stop, so `"Open to Foreign Investment" + " " +
       standfirst` becomes ONE sentence for the splitter — and if the standfirst
       opens with the Bali caveat ("...but this is not permitted at scale"), the
       negation guard acquits the headline on the strength of a denial that
       belongs to a different assertion. Each field is now judged alone, which
       is what it is: a separate claim, separately authored.

    `byTheNumbers` cells are walked too. Their values ("100%", "TERBATAS") can
    never satisfy the sentence predicate, which needs a national scope word and
    an openness claim together, so the overlap with the cell check costs
    nothing and the alternative — excluding a key by name — is the very habit
    that produced defect 1.
    """
    out: list[tuple[str, str]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, str):
            if node.strip():
                out.append((path, node))
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(record.get("intel_2026") or {}, "")
    return out


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
        "offending_fields": [],
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
        for path, text in _prose_fields(record):
            for sentence in _SENTENCE.findall(text):
                if not (_NATIONAL_SCOPE.search(sentence) and _OPENNESS_CLAIM.search(sentence)):
                    continue
                if _NEGATION.search(sentence):
                    continue
                out["body_asserts_national_openness"] = True
                out["offending_fields"].append(
                    {"field": path, "sentence": sentence.strip()[:300]}
                )
                break  # one sentence per field is enough to name the field

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
            # WHERE the prose lies, not just how much of it: the cure is a
            # different job in `whatYouNeed` (a filing instruction) than in a
            # `headline` (a promise), and a bare total hides that.
            "by_field": dict(
                sorted(
                    Counter(
                        f["field"] for r in editorial for f in r["offending_fields"]
                    ).items(),
                    key=lambda kv: (-kv[1], kv[0]),
                )
            ),
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
