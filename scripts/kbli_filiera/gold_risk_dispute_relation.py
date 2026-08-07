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
  and agrees with the record. Also catches "not all scales"/"not every
  scale" ahead of the universal quantifier (round 3).
  DECLARED LIMIT (round 4, zero corpus occurrences today, do not attempt
  general negation semantics): "All scales are not Low Risk." and "Low Risk
  is not applicable at every scale." both parse as POSITIVE claims — the
  negation sits in a different position than "not all scales"/"not every
  scale"/"does not apply", which is what `_NEGATION` actually matches.
  Pinned as a known gap, not fixed.
* HEDGED FORECAST — `60390`: "Likely will be classified as High Risk when PP28
  integration occurs" predicts, on a code whose same text says no assignment
  exists yet.
* CONDITIONAL — "If OSS treats your scope as High Risk, you will need a
  Standard Certificate" states a hypothetical branch, not this code's actual
  tier. Same for "unless ..." and "... where applicable".
  DECLARED LIMIT: this guard is whole-clause and matches bare "if ", so
  "Even if the scope is later expanded, this activity is Low Risk." also
  loses ITS OWN unconditional claim — a known under-match, left as is (round
  3; real conditional-scope parsing is out of bounds for a regex guard).
* ANOTHER CODE'S TIER — `70202`'s baliContext: "you're better off with 70203
  (Low risk...)" asserts a tier about 70203, not 70202. A sentence naming a
  different 5-digit code contributes nothing to THIS code's claim set.
  DECLARED LIMIT: this guard is whole-clause, so "Unlike 70203, KBLI 70202 is
  High Risk." also loses ITS OWN claim — a known under-match, left as is.
* POPULATION TALK — "most consulting codes are Low risk" quantifies over a
  family, not this code.

Clause boundaries also do NOT include `:` — measured and rejected in round 3:
every real universal claim in this corpus is phrased "All scales: <tier>" or
"All scales (<list>): <tier>", so the colon sits BETWEEN the quantifier and
the tier it modifies; splitting there would sever the claim from its own
subject and drop `46100`/`47901`/`71109` from the population.

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
claims a SET of tiers — usually one, occasionally more ("All scales:
Menengah Tinggi and Tinggi") — and is false as soon as that set MISMATCHES
the record's tier set in EITHER direction (round 4, item 3: symmetric `!=`,
not the round-3 one-directional `tier_set - claimed_set` — a claim missing a
record tier is false, and so is a claim naming a tier the record doesn't
have). Evaluated independently of overlap, because a universal claim is
falsified by a single dissenting tier even when part of its claimed set is
also present. The set stays grouped PER CLAUSE, never flattened across
clauses (round 3): a clause naming two tiers together must be judged as one
unit, or a claim that correctly covers a two-tier record would be misread as
false on each tier taken alone. `46100` is the motivating case: gold says
"All scales (Mikro/Kecil/Menengah/Besar): Low Risk (Rendah)" while the
record holds {Menengah Rendah, Menengah Tinggi, Rendah, Tinggi} — the Rendah
overlap hid the false universal claim from `zero_overlap`. A universal claim
whose set EXACTLY EQUALS the record's tiers is innocent — including a plain
negation ("Not all scales are Low Risk" makes no claim at all; see
`_NEGATION`). `zero_overlap` is checked first; a code cannot be both.

A mismatching clause whose claimed set has MORE THAN ONE tier raises instead
of emitting (round 4, item 4, declared limit): the renderer's wording states
ONE tier as applying at every scale, true for all 3 real members today
(each claims exactly one tier) — admitting a multi-tier-claim entry under
that wording would misrepresent the claim. Teach the renderer first.

A record with NO tier rows is a declared gap, not a contradiction — excluded
from both checks.

WHAT THE FRONTEND MAY RENDER FROM THIS
--------------------------------------
The RECORD tiers (structured data), the FACT of divergence, the dispute
`kind` (`zero_overlap` vs `universal_claim` — round 3: the two kinds are
FALSE IN DIFFERENT WAYS and a page that always says "describes a different
tier" lies about the 3 `universal_claim` codes, whose editorial tier IS in
the record; only its claimed UNIVERSALITY is false), and `baliDependsOnTier`
— also structured, computed here from `l4_bali.status` via the shared
`_l4bali_basis.RISK_DERIVED_STATUSES` SSOT (never from prose, never a second
hand-typed list — round 3 caught exactly that drift) — true when the
record's Bali (L4) verdict is derived from the risk tier itself, as opposed
to a status whose basis is a different, intact layer (PMA/sector). 32 of the
33 disputes carry it (all but `79110`, CHIUSO_BALI_PROPOSTO — a proposed,
not tier-derived, closure) — a page cannot show a Bali verdict as settled
while calling its basis disputed. Never the editorial tier list: prose
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

# Sibling-module import: works both when this file is executed directly (Python
# auto-adds its own directory to sys.path[0]) and when a test has already
# inserted this directory (same pattern as emit_l4bali_gap_disclosure_spec.py).
# The tier-derived/non-tier-derived classification of every l4_bali.status
# lives in ONE module shared with the census/emitter and the sanctioned L4
# writer, so this compiler can never disagree with them about which statuses
# rest on the risk-tier layer (2026-08-07 round-3 BLOCKER 2 — a second,
# hand-typed list here had already drifted from that SSOT).
_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

from _l4bali_basis import (  # noqa: E402
    NON_RISK_DERIVED_STATUSES,
    RISK_DERIVED_STATUSES,
)

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
# "not all scales"/"not every scale" (2026-08-07 round-3 finding #3) is a
# SEPARATE phrasing from "X does not apply" — "Not all scales are Low Risk"
# denies the UNIVERSAL claim without ever saying "apply". Folded into the
# same guard (not a parallel one) so both `gold_claims` and
# `universal_claim_sets` — which both route through `sentence_claims` —
# inherit the fix identically; a plain claim from this clause would be just
# as wrong as a universal one.
#
# DECLARED LIMIT (round 4, zero corpus occurrences today, do not fix): "All
# scales are not Low Risk." and "Low Risk is not applicable at every scale."
# both put the negation somewhere this regex doesn't reach — neither matches
# "not all scales"/"not every scale" (quantifier immediately after "not") nor
# "does not apply" (verb immediately after "not"). Both still parse as
# POSITIVE claims today. General negation-position semantics is out of
# bounds for a regex guard — pinned as a known gap, not attempted.
_NEGATION = re.compile(
    r"\b(does\s+not\s+apply|do(es)?n'?t\s+apply|not\s+apply"
    r"|not\s+all\s+scales|not\s+every\s+scale)\b",
    re.I,
)
_HEDGE = re.compile(
    r"\b(likely|will\s+be\s+classified|would\s+be|expected\s+to|once\s+pp\s*28|when\s+pp\s*28)\b",
    re.I,
)
# Quantification over a family of codes rather than this one.
_POPULATION = re.compile(r"\b(most|other|all)\s+[a-z]*\s*codes\b", re.I)
# CONDITIONAL — "If OSS treats your scope as High Risk, you will need a
# Standard Certificate" is a hypothetical branch, not an assertion about this
# code's actual tier. Same for "unless ..." and "... where applicable".
# DECLARED LIMIT (round-3, do not fix): this guard is whole-clause and
# matches bare "if ", so "Even if the scope is later expanded, this activity
# is Low Risk." also loses its OWN unconditional assertion — "Even if X, Y"
# states Y unconditionally; the guard cannot tell that apart from a true
# conditional. Known under-match, same treatment as the cross-code guard's
# declared limit in `sentence_claims` below. Real conditional semantics
# (parsing which clause the "if" actually scopes over) is out of bounds for
# a regex guard — left as is.
_CONDITIONAL = re.compile(r"\b(?:if|unless)\s|where\s+applicable", re.I)

# Candidate boundaries for a CLAIM, not just a sentence: "The automatic
# Low-Risk route does not apply; this activity is High Risk." is one sentence
# but two clauses, and the negation in the first must not reach into the
# second (W105-class over-match — the guard would otherwise convict the
# WHOLE sentence innocent because ONE clause is negated). Split on sentence
# punctuation, `;`, and a spaced em-dash in addition.
#
# DECLARED LIMIT (round-3, measured and rejected, do not add): `:` looks like
# a cheap fourth splitter but MEASURABLY BREAKS the universal-quantifier rule
# — "All scales (Mikro/Kecil/Menengah/Besar): Low Risk (Rendah)" would split
# into "All scales (...)" (quantifier, no tier) and " Low Risk (Rendah)"
# (tier, no quantifier), severing the phrase from the tier it modifies.
# Measured: adding `:` here drops `46100`/`47901`/`71109` out of the
# population entirely (33 -> 30). Every real universal claim in this corpus
# is written "All scales: <tier>" or "All scales (<list>): <tier>" — i.e.
# the colon is structurally load-bearing for THIS guard, not incidental
# punctuation to split on. Left out.
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


def universal_claim_sets(entry: dict[str, Any], own_code: str) -> list[set[str]]:
    """Per-CLAUSE tier-sets from clauses that quantify over ALL scales.

    Distinct from `gold_claims`: only clauses matching `_UNIVERSAL_QUANTIFIER`
    count, and each clause's claimed tiers stay grouped as ONE set rather than
    flattening into a single set across the whole entry (2026-08-07 round-3
    finding #3). The grouping matters: "All scales: Menengah Tinggi and
    Tinggi" on a record holding exactly {Menengah Tinggi, Tinggi} is a TRUE
    universal claim — the clause names both tiers together. Flattened, the
    caller would wrongly test each tier alone ("is there a tier other than
    Menengah Tinggi?" — yes, Tinggi — false positive) instead of testing
    whether the CLAUSE's whole claim set covers the record.
    """
    sets: list[set[str]] = []
    for field in PROSE_FIELDS:
        text = entry.get(field) or ""
        for clause in _SENTENCE_SPLIT.split(text):
            if not _UNIVERSAL_QUANTIFIER.search(clause):
                continue
            claimed = sentence_claims(clause, own_code)
            if claimed:
                sets.append(claimed)
    return sets


def bali_depends_on_tier(record: dict[str, Any]) -> bool:
    """True when this record's Bali (L4) verdict is derived from its risk tier.

    DERIVES from `_l4bali_basis.RISK_DERIVED_STATUSES` — the shared SSOT the
    census/emitter and the sanctioned L4 writer already use to answer this
    exact question — rather than hand-maintaining a second classification
    here (2026-08-07 round-3 finding, BLOCKER 2: a hand-typed 4-status list
    both omitted `BLOCCATO_DIPENDE_SCOPE` and `CHIUSO_PMA_NO_BESAR`, which
    ARE tier-derived per that module — a fact its own `reason` text states
    outright for BLOCCATO_DIPENDE_SCOPE — and a second list answering one
    fact is exactly the drift this dataset has scarred on before, W105).

    A `status` present but in NEITHER `RISK_DERIVED_STATUSES` NOR
    `NON_RISK_DERIVED_STATUSES` raises (round 4, MAJOR): `_l4bali_basis`
    enumerates every status it knows about EXPLICITLY (its own docstring:
    "so a new status added upstream fails the completeness check instead of
    being silently ignored") — silently falling through to `False` here
    would defeat that completeness property one layer up, exactly the class
    of bug the SSOT exists to prevent. A MISSING verdict (no `l4_bali` key,
    or a `status` of `None`) is a different fact — "no verdict yet", not "an
    unclassified one" — and returns `False` without raising; every record in
    the live canonical carries a non-None status today (measured), but a
    record legitimately awaiting L4 resolution should not crash this
    compiler.
    """
    status = (record.get("l4_bali") or {}).get("status")
    if status is None:
        return False
    if status in RISK_DERIVED_STATUSES:
        return True
    if status in NON_RISK_DERIVED_STATUSES:
        return False
    raise ValueError(
        f"bali_depends_on_tier: unclassified l4_bali.status {status!r} — not "
        "in _l4bali_basis.RISK_DERIVED_STATUSES or NON_RISK_DERIVED_STATUSES; "
        "classify it there before this compiler can judge whether the Bali "
        "verdict depends on the disputed risk tier"
    )


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
        # rule independently: it convicts a CLAUSE's whole claimed-tier set
        # on any MISMATCH with the record's tier set — either direction
        # (round 4, item 3: a claim missing a record tier is false, and so
        # is a claim naming a tier the record doesn't have — `!=`, not the
        # one-directional `tier_set - claimed_set` round 3 shipped) — not on
        # the absence of overlap (a clause naming ALL of a multi-tier
        # record's tiers together must NOT convict — round-3 finding #3).
        tier_set = set(tiers)
        for claimed_set in universal_claim_sets(entry, code):
            if tier_set == claimed_set:
                continue  # exact match — a TRUE universal claim
            if len(claimed_set) > 1:
                # DECLARED LIMIT (round 4, do not fix here): the renderer's
                # universal_claim sentence states ONE risk tier as applying
                # at every scale — true for every real member today
                # (46100/47901/71109 each claim exactly one tier). Emitting
                # an entry whose claimed set has more than one tier would
                # misrepresent the claim itself under that wording. Fail
                # loudly here rather than silently emit a mismatched
                # sentence; teach the renderer multi-tier phrasing first.
                raise ValueError(
                    f"{code}: universal_claim clause claims "
                    f"{sorted(claimed_set)} (>1 tier) against a record "
                    "mismatch — the renderer's wording assumes a single "
                    "claimed tier; teach the renderer before admitting this "
                    "entry (declared limit, round 4)"
                )
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
                "Codes whose gold editorial prose contradicts the record's "
                "per_skala tier set — kind='zero_overlap' (prose tier shares "
                "NOTHING with the record) or kind='universal_claim' (prose "
                "claims one tier applies at EVERY scale, false as soon as the "
                "record holds any other tier — the editorial tier CAN still "
                "be among the record's tiers for this kind; only its claimed "
                "universality is false). No winner is picked; the page "
                "renders a kind-specific divergence disclosure. "
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
