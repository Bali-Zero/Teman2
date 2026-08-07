#!/usr/bin/env python3
"""Where the GOLD editorial layer and the OSS record disagree on the risk tier.

`/kbli/82990` prints "Risk Level: High (Tinggi)" in the licensing panel — read
from the record's `per_skala` rows — while the gold editorial two sections up
says "low risk at every scale". One page, two verdicts, and nothing on the page
says they disagree. Measured on 2026-08-07: 33 of the 428 gold entries assert a
risk tier the record's per_skala rows contradict — 30 by sharing NOTHING with
the record's tier set, and 3 more (`46100`, `47901`, `71109`) by a universal
"this code is X at every scale" claim that a multi-tier record falsifies even
when X itself is among the record's tiers (see WHAT COUNTS AS A DISPUTE).

THIS MODULE PICKS NO WINNER — that is the whole point of its shape.
Both sides cite PP 28/2025-era data and there is no arbiter on disk
(`pp28_2025_risk_mapping.json` holds ONE code, and the risk fact lives on the
(scope, scala) PAIR — 634 codes carry more than one scope, 525 more than one
tier — so "the" tier of a code is often not a single value at all). Aligning
gold to canonical would manufacture agreement, not truth. What CAN be shipped
honestly is the divergence itself: the page must say the two sources disagree
instead of serving both as settled fact. This compiler emits the population;
the frontend renders the disclosure; a freshness test makes it impossible for
either dataset to change without the artifact following in the same commit.

WHAT COUNTS AS A CLAIM (superscar #3 — the sentence is the entity)
------------------------------------------------------------------
The tier vocabulary is closed (Rendah / Menengah Rendah / Menengah Tinggi /
Tinggi + their English forms), compound forms matched before simple ones so
"Menengah Tinggi" never also counts as "Tinggi". A mention only becomes a
CLAIM when the CLAUSE around it survives five guards, each grown from a real
sentence that changed the count when it was finally read (the lesson this lane
paid for repeatedly in one session — the number is not the finding, the
sentence is). "Clause", not "sentence": candidates are split on `.!?\n`, `;`,
AND a spaced em-dash, so a guard fires on its own clause only — "The automatic
Low-Risk route does not apply; this activity is High Risk." still convicts
Tinggi, because the negation in clause 1 cannot reach clause 2 (2026-08-07 gate
finding #4; the earlier whole-sentence split was itself an over-match):

* NEGATION — `46206`: "Rendah/Otomatis does NOT apply here" DENIES the tier,
  and agrees with the record.
* HEDGED FORECAST — `60390`: "Likely will be classified as High Risk when PP28
  integration occurs" predicts, on a code whose same text says no assignment
  exists yet.
* CONDITIONAL — "If OSS treats your scope as High Risk, you will need a
  Standard Certificate" states a hypothetical branch, not this code's actual
  tier. Same for "unless ..." and "... where applicable".
* ANOTHER CODE'S TIER — `70202`'s baliContext: "you're better off with 70203
  (Low risk...)" asserts a tier about 70203, not 70202. A sentence naming a
  different 5-digit code contributes nothing to THIS code's claim set.
  DECLARED LIMIT: this guard is whole-clause, so "Unlike 70203, KBLI 70202 is
  High Risk." also loses ITS OWN claim — a known under-match, left as is.
* POPULATION TALK — "most consulting codes are Low risk" quantifies over a
  family, not this code.

These guard lists are grown from observed instances (W113: a pattern written
from the instance you found catches the instance you found). The safety net is
not the lists — it is the freshness test: any change to gold or canonical that
shifts the population turns CI red until the artifact is regenerated, so every
NEW member gets a human read before it renders.

WHAT COUNTS AS A DISPUTE — two independent kinds
--------------------------------------------------
`zero_overlap` (the original rule): claimed-tiers non-empty AND record-tiers
non-empty AND intersection EMPTY. Zero overlap is deliberately the strongest
form: on a multi-tier record a partial overlap can be two truths about two
scopes (the no-arbiter zone), so it is NOT reported on its own. That gap is
declared, not closed.

`universal_claim` (2026-08-07): a CLAUSE quantifying over ALL scales ("all
scales", "every scale", optionally followed by a parenthesized scale list)
that claims tier X is false as soon as the record holds ANY tier other than
X — evaluated independently of overlap, because a universal claim is falsified
by a single dissenting tier even when X is also present. `46100` is the
motivating case: gold says "All scales (Mikro/Kecil/Menengah/Besar): Low Risk
(Rendah)" while the record holds {Menengah Rendah, Menengah Tinggi, Rendah,
Tinggi} — the Rendah overlap hid the false universal claim from `zero_overlap`.
A universal claim whose X equals the record's ONLY tier is innocent (nothing
else to contradict it). `zero_overlap` is checked first; a code cannot be both.

A record with NO tier rows is a declared gap, not a contradiction — excluded
from both checks.

WHAT THE FRONTEND MAY RENDER FROM THIS
--------------------------------------
The RECORD tiers (structured data), the FACT of divergence, and
`baliDependsOnTier` — also structured, computed here from `l4_bali.status`
(never from prose) — true when the record's Bali (L4) verdict is one of the
statuses DERIVED from the risk tier itself (`OK_or_HIGHER_RISK`,
`APERTO_BALI_RISCHIO_ALTO`, `BLOCCATO_CLASSE_RISCHIO`,
`CHIUSO_MORATORIA_BALI`), as opposed to a PMA/sector-derived status that holds
regardless of which tier wins. 29 of the 30 `zero_overlap` disputes and all 3
`universal_claim` disputes carry it — a page cannot show a Bali verdict as
settled while calling its basis disputed. Never the editorial tier list: prose
evidence can carry junk (another code's tier that slipped a guard), and a
disclosure that enumerates wrong tiers would be a new client-facing lie
manufactured by the cure. `editorial_mentions` is audit evidence, kept in the
artifact for humans, not for the page.

IT REPORTS AND EMITS; IT DOES NOT DECIDE. `--check` exits 0 while disputes
exist (a divergence with its disclosure rendered is the DESIGNED state, not a
failure). `--check-artifact` exits 1 when the emitted artifact no longer
matches a recomputation — that is the arm CI holds.
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
GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
ARTIFACT = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-risk-disputes.json"

# Prose fields read for a tier claim about THIS code. `youllAlsoNeed` is
# excluded by design — it is a list of OTHER codes. `whatChanged` is crosswalk
# narrative about the 2020->2025 transition, not a licensing claim.
PROSE_FIELDS = ("whatYouNeed", "zantaraOpener", "whatItMeans", "baliContext")

# Compound forms FIRST — masked out of the sentence before simple forms run,
# so "Menengah Tinggi" is never also a "Tinggi" claim.
_TIER_COMPOUND = [
    ("Menengah Tinggi", re.compile(r"menengah\s+tinggi|medium[-\s]high\s+risk", re.I)),
    ("Menengah Rendah", re.compile(r"menengah\s+rendah|medium[-\s]low\s+risk", re.I)),
]
_TIER_SIMPLE = [
    ("Tinggi", re.compile(r"\btinggi\b|\bhigh[-\s]risk\b|\bhigh\s+risk\b", re.I)),
    ("Rendah", re.compile(r"\brendah\b|\blow[-\s]risk\b|\blow\s+risk\b", re.I)),
]

# A sentence containing any of these does not CLAIM the tier it mentions.
_NEGATION = re.compile(r"\b(does\s+not\s+apply|do(es)?n'?t\s+apply|not\s+apply)\b", re.I)
_HEDGE = re.compile(
    r"\b(likely|will\s+be\s+classified|would\s+be|expected\s+to|once\s+pp\s*28|when\s+pp\s*28)\b",
    re.I,
)
# Quantification over a family of codes rather than this one.
_POPULATION = re.compile(r"\b(most|other|all)\s+[a-z]*\s*codes\b", re.I)
# CONDITIONAL — "If OSS treats your scope as High Risk, you will need a
# Standard Certificate" is a hypothetical branch, not an assertion about this
# code's actual tier. Same for "unless ..." and "... where applicable".
_CONDITIONAL = re.compile(r"\b(?:if|unless)\s|where\s+applicable", re.I)

# Candidate boundaries for a CLAIM, not just a sentence: "The automatic
# Low-Risk route does not apply; this activity is High Risk." is one sentence
# but two clauses, and the negation in the first must not reach into the
# second (W105-class over-match — the guard would otherwise convict the
# WHOLE sentence innocent because ONE clause is negated). Split on sentence
# punctuation, `;`, and a spaced em-dash in addition.
_SENTENCE_SPLIT = re.compile(r"[.!?\n;]+|\s+—\s+")
_FIVE_DIGIT = re.compile(r"\b(\d{5})\b")

# UNIVERSAL QUANTIFIER over scales — "All scales (Mikro/Kecil/Menengah/Besar):
# Low Risk" / "at every scale" claims ONE tier for the WHOLE code, which a
# multi-tier record can falsify even when that one tier happens to be among
# the record's tiers (46100: gold says "All scales: Low Risk (Rendah)" while
# the record holds {Menengah Rendah, Menengah Tinggi, Rendah, Tinggi} — the
# Rendah overlap hides the false universal claim from the zero-overlap rule,
# which only fires on NO overlap at all).
_UNIVERSAL_QUANTIFIER = re.compile(
    r"\b(?:at\s+)?(?:all\s+scales|every\s+scale)\b(?:\s*\([^)]*\))?", re.I
)


def load_canonical(path: Path = CANONICAL) -> list[dict[str, Any]]:
    return json.loads(path.read_text())["data"]


def load_gold(path: Path = GOLD) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text())


def record_tiers(record: dict[str, Any]) -> list[str]:
    """Distinct kategori_risiko across the record's per_skala rows, sorted."""
    return sorted(
        {
            row.get("kategori_risiko")
            for row in record.get("per_skala") or []
            if row.get("kategori_risiko")
        }
    )


def sentence_claims(sentence: str, own_code: str) -> set[str]:
    """Tiers this clause asserts about `own_code` — empty when a guard fires.

    Despite the name, the caller now passes CLAUSES (post `_SENTENCE_SPLIT`,
    which also breaks on `;` and ` — `), so a guard firing here kills only
    its own clause, never a sibling clause of the same sentence.
    """
    if _NEGATION.search(sentence) or _HEDGE.search(sentence):
        return set()
    if _CONDITIONAL.search(sentence):
        return set()
    if _POPULATION.search(sentence):
        return set()
    # DECLARED LIMIT (do not fix here): this guard is whole-clause — ANY
    # other 5-digit code mentioned anywhere in the clause voids the WHOLE
    # claim set, including a legitimate assertion about own_code sitting in
    # the same clause. "Unlike 70203, KBLI 70202 is High Risk." mentions
    # 70203 and is about 70202 — the guard discards the Tinggi claim it
    # should have kept. Known under-match, left as is.
    other_codes = set(_FIVE_DIGIT.findall(sentence)) - {own_code}
    if other_codes:
        return set()
    claims: set[str] = set()
    rest = sentence
    for name, pat in _TIER_COMPOUND:
        if pat.search(rest):
            claims.add(name)
            rest = pat.sub(" ", rest)
    for name, pat in _TIER_SIMPLE:
        if pat.search(rest):
            claims.add(name)
    return claims


def gold_claims(entry: dict[str, Any], own_code: str) -> dict[str, list[str]]:
    """Tier -> sorted list of fields whose clauses claim it."""
    found: dict[str, set[str]] = {}
    for field in PROSE_FIELDS:
        text = entry.get(field) or ""
        for clause in _SENTENCE_SPLIT.split(text):
            for tier in sentence_claims(clause, own_code):
                found.setdefault(tier, set()).add(field)
    return {tier: sorted(fields) for tier, fields in sorted(found.items())}


def universal_claims(entry: dict[str, Any], own_code: str) -> set[str]:
    """Tiers claimed by a clause that quantifies over ALL scales.

    Distinct from `gold_claims`: only clauses matching `_UNIVERSAL_QUANTIFIER`
    count. A universal "this code is X at every scale" claim is falsified by
    ANY other tier in the record — even when X itself is also in the record
    (that partial overlap is what let 46100 slip past the zero-overlap rule).
    """
    found: set[str] = set()
    for field in PROSE_FIELDS:
        text = entry.get(field) or ""
        for clause in _SENTENCE_SPLIT.split(text):
            if not _UNIVERSAL_QUANTIFIER.search(clause):
                continue
            found |= sentence_claims(clause, own_code)
    return found


# l4_bali.status values DERIVED from the record's risk tier (the OSS-risk /
# moratorium-vs-tier logic) — as opposed to PMA/sector-derived statuses
# (CHIUSO_PMA_NO_BESAR, TERTUTUP, CHIUSO_REGOLATORE_SETTORIALE, ...) that
# would hold regardless of which tier wins. A page showing a Bali verdict
# built on a DISPUTED tier is asserting settled fact on a disputed basis.
_BALI_TIER_DERIVED_STATUSES = frozenset(
    {
        "OK_or_HIGHER_RISK",
        "APERTO_BALI_RISCHIO_ALTO",
        "BLOCCATO_CLASSE_RISCHIO",
        "CHIUSO_MORATORIA_BALI",
    }
)


def bali_depends_on_tier(record: dict[str, Any]) -> bool:
    """True when this record's Bali (L4) verdict is derived from its risk tier."""
    status = (record.get("l4_bali") or {}).get("status")
    return status in _BALI_TIER_DERIVED_STATUSES


def compute_disputes(
    canonical: list[dict[str, Any]], gold: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    records = {r["kode_kbli_2025"]: r for r in canonical}
    disputes: dict[str, dict[str, Any]] = {}
    for code in sorted(gold):
        record = records.get(code)
        if record is None:
            continue
        tiers = record_tiers(record)
        if not tiers:
            continue  # declared gap, not a contradiction
        entry = gold[code]
        claims = gold_claims(entry, code)
        if claims and not (set(claims) & set(tiers)):
            disputes[code] = {
                "record": tiers,
                "kind": "zero_overlap",
                "editorial_mentions": claims,
                "baliDependsOnTier": bali_depends_on_tier(record),
            }
            continue
        # Zero-overlap didn't fire (a partial overlap can be two truths about
        # two scopes — the no-arbiter zone). Check the universal-quantifier
        # rule independently: it convicts on ANY other tier being present,
        # not on the absence of overlap.
        tier_set = set(tiers)
        for claimed_tier in sorted(universal_claims(entry, code)):
            if tier_set - {claimed_tier}:
                disputes[code] = {
                    "record": tiers,
                    "kind": "universal_claim",
                    "editorial_mentions": claims,
                    "baliDependsOnTier": bali_depends_on_tier(record),
                }
                break
    return disputes


def build_artifact(disputes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "_meta": {
            "generated_by": "scripts/kbli_filiera/gold_risk_dispute_relation.py --emit",
            "note": (
                "Codes whose gold editorial prose claims a risk tier sharing "
                "NOTHING with the record's per_skala tier set. No winner is "
                "picked; the page renders a divergence disclosure. "
                "editorial_mentions is audit evidence — never render it."
            ),
            "count": len(disputes),
        },
        "disputes": disputes,
    }


def _serialize(artifact: dict[str, Any]) -> str:
    return json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--emit", action="store_true", help=f"write {ARTIFACT}")
    parser.add_argument(
        "--check-artifact",
        action="store_true",
        help="exit 1 when the emitted artifact no longer matches a recomputation",
    )
    parser.add_argument("--canonical", type=Path, default=CANONICAL)
    parser.add_argument("--gold", type=Path, default=GOLD)
    parser.add_argument("--artifact", type=Path, default=ARTIFACT)
    args = parser.parse_args(argv)

    disputes = compute_disputes(load_canonical(args.canonical), load_gold(args.gold))
    artifact = build_artifact(disputes)

    if args.check_artifact:
        if not args.artifact.exists():
            print(f"ARTIFACT MISSING: {args.artifact}", file=sys.stderr)
            return 1
        on_disk = args.artifact.read_text()
        if on_disk != _serialize(artifact):
            print(
                "ARTIFACT STALE: recomputation differs — re-run "
                "gold_risk_dispute_relation.py --emit and commit the result "
                "in the SAME change that touched gold/canonical",
                file=sys.stderr,
            )
            return 1
        print(f"artifact fresh: {len(disputes)} disputes")
        return 0

    if args.emit:
        args.artifact.write_text(_serialize(artifact))
        print(f"wrote {args.artifact} ({len(disputes)} disputes)")
        return 0

    if args.json:
        print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"gold entries asserting a tier the record contradicts: {len(disputes)}")
    for code, entry in disputes.items():
        mentions = ", ".join(
            f"{tier} ({'/'.join(fields)})"
            for tier, fields in entry["editorial_mentions"].items()
        )
        bali = " bali_depends_on_tier" if entry["baliDependsOnTier"] else ""
        print(
            f"  {code} [{entry['kind']}]: record={entry['record']} "
            f"editorial: {mentions}{bali}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
