"""Guilt+innocence fixtures for the KBLI dataset lint's shared ownership (L10) and
dead-reference (L3) guards — the ONE SSOT that kbli_apply_editorials.py also imports.

Scar family #3 (guard over-match / under-match): a guard change is only safe when a
GUILT fixture (a genuine defect still trips) and an INNOCENCE fixture (a legitimate
neighbouring case does not) both pass. These cases are drawn verbatim from the LOOP-2
editorial corpus — the editorial register is longer and more narrative than the terse
enriched prose the guards were first tuned on, so the innocence set below is the exact
set of real false positives the hardening removed, and the guilt set is the real
defects (fabricated code 85598, unlabeled dead ref) it must keep catching.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from kbli_dataset_lint import (  # noqa: E402
    l10_ownership_contradiction,
    l3_dead_ref,
)

# maxa_by_code stub: only the codes the fixtures cross-reference need real values.
MAXA = {
    "20115": 100, "20116": 100, "47192": 100,
    "85312": 100, "85402": 100, "85404": 100, "85571": 100,
}
# a small live-catalogue stub for L3 (codes that must count as "in the 2025 catalogue")
LIVE = {
    "85591", "85592", "85593", "85594", "85595", "85596", "85597", "85599",
    "46451", "46452", "71201", "71202", "71204", "85312", "85402",
}


# --------------------------------------------------------------------------- L10
L10_GUILT = [
    # (name, text, code, maxa) — a genuine self-contradiction that MUST be flagged
    ("self 100 vs 0", "This activity is fully open to 100% foreign ownership.", "20119", 0),
    ("self own-up-to 100 vs 0", "Foreign investors can own up to 100% of the equity here.", "84111", 0),
    ("self 49 vs 100", "The code itself is capped at 49% foreign ownership under the list.", "73100", 100),
    ("self 80 no region no sibling", "Foreign ownership of this code is limited to 80%.", "10110", 100),
    ("bare It 100 no sibling named", "This is a government-run activity. It is fully open to 100% foreign ownership.", "85311", 0),
    ("self 0 national no qualifier", "Foreign ownership of this code is 0% — the activity is reserved for nationals.", "10110", 100),
]

L10_INNOCENCE = [
    # (name, text, code, maxa) — a legitimate case that MUST NOT be flagged
    ("adjacent by number", "KBLI 20115 and KBLI 20116 are both fully open to 100% foreign ownership, while this code stays closed.", "20119", 0),
    ("named-adjacent 'a code'", "Public-affairs work falls under general management and business consulting activities, a code fully open to 100% foreign ownership.", "84111", 0),
    ("'that code' steering", "That code is fully open to 100% foreign ownership, which is the route any foreign university uses.", "85401", 0),
    ("pronoun antecedent named sibling", "That separate code is 85312 — the private junior secondary sibling right next to this one in the same group. It is fully open to 100% foreign ownership.", "85311", 0),
    ("Bali cap explicit", "Nationally open, but Bali's own regime caps foreign equity at 67% for building construction.", "41011", 100),
    ("regime layered on top of national", "Bali's regime — layered on top of the national OSS system — caps foreign ownership at 67% for building-construction activities.", "41011", 100),
    ("on-the-ground Bali cap", "On the ground in Bali, the record caps it at 49% foreign shareholding.", "52292", 100),
    ("historical after the figure", "Founders who still hear about a 49% cap on marketing agencies are working from an old briefing; that ceiling closed.", "73100", 100),
    ("in-practice zero", "Foreign ownership (in practice): 0% — no Usaha Besar tier for PT PMA to register against.", "86995", 100),
]


@pytest.mark.parametrize("name,text,code,maxa", L10_GUILT, ids=[c[0] for c in L10_GUILT])
def test_l10_guilt_flags(name, text, code, maxa):
    assert l10_ownership_contradiction(text, code, maxa, MAXA) is not None, (
        f"L10 must FLAG genuine contradiction: {name!r}"
    )


@pytest.mark.parametrize("name,text,code,maxa", L10_INNOCENCE, ids=[c[0] for c in L10_INNOCENCE])
def test_l10_innocence_passes(name, text, code, maxa):
    assert l10_ownership_contradiction(text, code, maxa, MAXA) is None, (
        f"L10 must NOT flag legitimate case: {name!r}"
    )


# ---------------------------------------------------------------------------- L3
L3_GUILT = [
    # (name, text, code) — an unlabeled dead code or a fabricated code MUST be flagged
    ("bare dead code", "The activity previously mapped to 56103 before the reshuffle.", "56303"),
    ("second unlabeled occurrence", "an existing API-U import licence tied to 46421 needs remapping.", "46451"),
    ("fabricated range endpoint", "everything not already covered by codes 85591 through 85598.", "85599"),
]

L3_INNOCENCE = [
    ("used to live under", "this activity used to live under 01270 and was promoted.", "01271"),
    ("old kbli 2020 code", "the old kbli 2020 code 46421 has been split apart.", "46451"),
    ("origin split-from", "KBLI 2020 origin: Split from code 46421 into 46451 + 46452", "46451"),
    ("predecessor label", "Predecessor code: 62014 — KBLI 2020", "62193"),
    ("ex-generic label", "KBLI 2020 equivalent: none — new standalone code, ex-generic 71200", "71203"),
    ("list continuation", "KBLI 2020 codes 02111, 02112, 02113, 02119, 02121 and 02122 all collapse here.", "02102"),
    ("section block ref", "moving it into the 68000 real-estate block under the 2025 catalogue.", "68299"),
    ("live sibling range", "everything not already covered by codes 85591 through 85597.", "85599"),
]


@pytest.mark.parametrize("name,text,code", L3_GUILT, ids=[c[0] for c in L3_GUILT])
def test_l3_guilt_flags(name, text, code):
    assert l3_dead_ref(text, code, LIVE) is not None, (
        f"L3 must FLAG dead/fabricated ref: {name!r}"
    )


@pytest.mark.parametrize("name,text,code", L3_INNOCENCE, ids=[c[0] for c in L3_INNOCENCE])
def test_l3_innocence_passes(name, text, code):
    assert l3_dead_ref(text, code, LIVE) is None, (
        f"L3 must NOT flag legitimate 2020-labeled/live ref: {name!r}"
    )
