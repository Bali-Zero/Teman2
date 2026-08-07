#!/usr/bin/env python3
"""Replace the stale PT PMA paid-up figure in `apps/mouth/data/kbli-gold-all.json`.

THE CLAIM, AND THE GUARD THAT COULD NOT SEE IT
----------------------------------------------
`apps/mouth/src/content/_regulatory-claim-ledger.json` carries
`CAPITAL-PAIDUP-10B` at severity **P0**, with the current fact stated correctly:
minimum paid-up capital for a PT PMA is IDR **2.5** billion (Permen
Investasi/BKPM 5/2025 Pasal 26(10), 12-month lock-in); the separate
investment-plan threshold is **above IDR 10 billion per 5-digit KBLI per
location** (Pasal 26(2)). Under the revoked BKPM 4/2021 the paid-up figure was
10 billion, which is why so much of our own copy still says it.

The ledger's only executor is `content-freshness-sentinel.test.ts`, whose own
header declares "Scope: English canonical .mdx only". `kbli-gold-all.json` is
not an .mdx and has never been in its reach — and gold OVERRIDES canonical on
every rendered `/kbli/[code]` page. Measured 2026-08-07: **37 of the 428 gold
codes state the 10-billion figure next to "paid-up"**. Two independent holes:
the SCOPE above, and the ledger's two LITERAL patterns ("Paid-up Capital: IDR
10 billion", "Minimum paid-up capital IDR 10 billion") against the **nine**
different phrasings gold actually uses — so even in scope it would read green.

Direction of harm: a client is told to deposit four times the cash the law
requires, before anyone quotes them anything.

NEVER SWEEP THE NUMBER
----------------------
Three distinct live rules share the string "10 billion": paid-up (now 2.5bn),
total investment (>10bn, STANDS), and the E28A Investor-KITAS shareholding
threshold (10bn, an immigration rule that STANDS). The only safe anchor is
adjacency to `paid-up` / `modal disetor`, and even that is not enough — see the
refusals. Positive control: 32 other gold codes already say 2.5bn, which is what
makes the 37 an error rather than a house convention.

REFUSALS — all three found by READING the whole sentence, not the match
----------------------------------------------------------------------
  * `65121` / `66151` — "IDR 100 billion paid-up (OJK requirement) + IDR 10B PT
    PMA **stated** capital". These already separate the two figures correctly;
    the 10B is attached to STATED capital, and my proximity anchor matched
    across the `+`. A probe that measures a disease can carry it.
  * `85102` — the 10B is listed as a requirement of registering as a **Satuan
    Pendidikan Kerjasama**, a sector regime with its own rules. Whether an SPK
    capital floor exists at that figure is a question for the education
    regulation, not a deduction from BKPM 5/2025.

Dry-run is the default; nothing is written without --apply.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"
LEDGER_PATH = REPO_ROOT / "apps/mouth/src/content/_regulatory-claim-ledger.json"

log = logging.getLogger("cure_gold_paidup_capital")

# Adjacency to `paid-up`/`modal disetor`, both orders. Bounded so it cannot run
# across a sentence boundary and pair a figure with a phrase from the next one.
PAIDUP10_RE = re.compile(
    r"(?:paid[- ]?up|modal disetor|disetor)[^.\n;]{0,60}?IDR\s*10\s*(?:billion|miliar|B\b)"
    r"|IDR\s*10\s*(?:billion|miliar)[^.\n;]{0,40}?(?:paid[- ]?up|modal disetor)",
    re.I,
)

# A second capital figure, or "stated capital", in the same clause means the
# 10B is not the paid-up minimum being asserted — it is the other half of a
# distinction the text is already drawing. Refuse rather than "fix" it.
BOUNDARY_RE = re.compile(r"stated capital|OJK|Satuan Pendidikan Kerjasama|\bSPK\b", re.I)

# 65121 was here until 2026-08-08: `cure_gold_65121_sector_law_sweep.py`
# (sector-law brief item 2) swept every "IDR 10B"/"IDR 100 billion" figure
# out of its zantaraOpener/whatYouNeed/baliContext entirely (POJK 23/2023's
# actual minimum was never primary-fetched, so the hard rule is no figure at
# all, not a corrected one) — the FIGURE_RE trigger this scan looks for no
# longer appears anywhere in the record, so it stops surfacing here as a
# refusal on its own; nothing left for this cure to decline.
REFUSAL_NOTE = {
    "66151": "OJK paid-up + PT PMA STATED capital — the two are already separated",
    "85102": "the figure is attached to SPK registration, a sector regime with its own rules",
}

# The figure is swapped IN PLACE and the distinction added after the clause,
# rather than the clause being replaced wholesale. Replacing it would have been
# simpler and would have deleted the sentence's own content — `32112` opens with
# where silver work is done in Bali (Celuk) and only then reaches the figure.
# A cure is not a licence to rewrite the paragraph it landed in.
FIGURE_RE = re.compile(r"IDR\s*10\s*(?:billion|miliar|B\b)", re.I)
FIGURE_NEW = "IDR 2.5 billion"
ADDENDUM = (
    " Total investment must still exceed IDR 10 billion per 5-digit KBLI per "
    "location — a separate threshold from the paid-up minimum (Permen BKPM "
    "5/2025 art. 26(2) and art. 26(10))."
)


class CureError(RuntimeError):
    """A refusal. Never downgraded to a warning."""


def clause_span(text: str, i: int, j: int) -> tuple[int, int]:
    """The clause containing [i, j) — bounded by `.`, `;` and newline.

    `;` is a boundary and not a decoration: `53200`'s sentence carries the 49%
    foreign-ownership cap before the semicolon and the capital figure after it.
    Taking the whole sentence would delete a cure applied an hour earlier.
    """
    start = max(text.rfind(c, 0, i) for c in ".;\n")
    start = 0 if start < 0 else start + 1
    ends = [e for e in (text.find(".", j), text.find(";", j), text.find("\n", j)) if e >= 0]
    end = min(ends) + 1 if ends else len(text)
    return start, end


def scan(gold: dict) -> tuple[dict, dict]:
    """{code: (field, clause)} to cure, and {code: (field, clause)} refused."""
    cure: dict[str, tuple[str, str]] = {}
    refused: dict[str, tuple[str, str]] = {}
    for code, rec in gold.items():
        for k, v in rec.items():
            if not isinstance(v, str):
                continue
            m = PAIDUP10_RE.search(v)
            if not m:
                continue
            s, e = clause_span(v, m.start(), m.end())
            clause = v[s:e]
            (refused if BOUNDARY_RE.search(clause) else cure)[code] = (k, clause)
            break
    return cure, refused


def plan(gold: dict) -> tuple[dict, dict]:
    cure, refused = scan(gold)
    patch: dict[str, dict] = {}
    for code, (field, clause) in sorted(cure.items()):
        text = gold[code][field]
        m = PAIDUP10_RE.search(clause)
        if m is None:
            raise CureError(f"{code}.{field}: the clause no longer holds the match")
        figures = FIGURE_RE.findall(clause)
        if len(FIGURE_RE.findall(clause)) != 1:
            raise CureError(
                f"{code}.{field}: {len(figures)} ten-billion figures in one clause — "
                "which one is the paid-up minimum is not a deduction"
            )
        new_clause = FIGURE_RE.sub(FIGURE_NEW, clause, count=1)
        new_clause = new_clause.rstrip()
        if not new_clause.endswith((".", ";")):
            new_clause += "."
        new_clause = new_clause + ADDENDUM
        new_text = text.replace(clause.rstrip(), new_clause, 1)
        if new_text == text:
            raise CureError(f"{code}.{field}: replacement was a no-op")
        if PAIDUP10_RE.search(new_text):
            raise CureError(f"{code}.{field}: the stale figure survives the replacement")
        patch[code] = {
            "field": field,
            "old_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "new": new_text,
            "was": clause.strip(),
        }
    return patch, refused


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Refuse to run against a ledger that no longer states this fact — the
    # figure below is not this file's to assert on its own (W106: a constant
    # that nobody re-measures is a countdown).
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    claims = ledger.get("claims", ledger)
    entries = list(claims.values()) if isinstance(claims, dict) else list(claims)
    fact = next((c.get("current_fact", "") for c in entries
                 if isinstance(c, dict) and c.get("id") == "CAPITAL-PAIDUP-10B"), "")
    if "IDR 2.5 billion" not in fact:
        raise CureError(
            "the claim ledger no longer states 2.5 billion as the paid-up minimum; "
            "re-read Permen BKPM 5/2025 before running this"
        )

    gold_raw = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    gold = gold_raw.get("data", gold_raw)
    patch, refused = plan(gold)

    log.info("gold codes: %d | stale paid-up figure: %d | refused: %d",
             len(gold), len(patch), len(refused))
    for code, (field, clause) in sorted(refused.items()):
        log.info("    REFUSE %s [%s] — %s", code, field,
                 REFUSAL_NOTE.get(code, "second capital figure in the same clause"))
        log.info("           «%s»", clause.strip()[:120])
    if not args.apply:
        for code, p in sorted(patch.items()):
            log.info("    %s [%s] «%s»", code, p["field"], p["was"][:105])

    if not patch:
        log.info("nothing to patch")
        return 0

    staged = copy.deepcopy(gold)
    for code, p in patch.items():
        live = staged[code][p["field"]]
        if hashlib.sha256(live.encode("utf-8")).hexdigest() != p["old_sha256"]:
            raise CureError(f"{code}.{p['field']}: live text moved under the plan")
        staged[code][p["field"]] = p["new"]

    after_cure, after_refused = scan(staged)
    if after_cure:
        raise CureError(f"still stale after the patch: {sorted(after_cure)}")
    if set(after_refused) != set(refused):
        raise CureError("the refusal set changed on codes this cure never touched")

    if not args.apply:
        log.info("DRY-RUN — nothing written. Re-run with --apply.")
        return 0

    if "data" in gold_raw and isinstance(gold_raw["data"], dict):
        gold_raw["data"] = staged
    else:
        gold_raw = staged
    GOLD_PATH.write_text(
        json.dumps(gold_raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log.info("WROTE %s — %d clauses corrected", GOLD_PATH.name, len(patch))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CureError as exc:
        log.error("REFUSED: %s", exc)
        sys.exit(2)
