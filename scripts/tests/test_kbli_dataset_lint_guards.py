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
    l12_full_ownership_claim,
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
    # cap ASSERTED (no negation) — must still flag despite the cap-denial innocence class
    ("real cap asserted with ceiling noun", "This activity is capped at 67%; the foreign stake hits that ceiling and no further.", "73100", 100),
    ("real cap limited-to with noun", "The record limits the foreign stake to a 49% ceiling for this code.", "73100", 100),
    # region named AFTER the figure — commentary on a national claim, not a regional cap.
    # The word "Bali" anywhere in the +-80 window used to exonerate these outright, on a
    # catalogue where every page mentions Bali (superscar #3, under-match form).
    ("region named after the figure", "Nationally, this activity is 100% open to foreign ownership. However, in Bali, the OSS system blocks it.", "16221", 0),
    ("Bali trailing the claim", "KBLI 41018 is nationally open to foreign ownership up to 100%, and the Bali field does not block PMA registration.", "41018", 0),
    # a ceiling stated without ever using the word "foreign"
    ("bare national ceiling idiom", "The national 100% ceiling does not automatically produce a Bali registration route.", "55105", 0),
    ("ownership ceiling noun", "Nationally, the PMA status is open, with a foreign-ownership ceiling of 100%.", "50221", 49),
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
    # cap-denial enumeration (01622 class): the prose lists caps only to DENY them
    ("cap-denial enumeration", "There is no capped foreign stake to explain here: the record does not impose a 67%, 49%, or minority ceiling.", "01622", 100),
    ("no-cap-here", "For this activity there is no 67% cap and no minority-partner rule — the national ceiling is the only figure.", "01622", 100),
    # the region PRECEDES the figure, so it genuinely scopes it — including when an
    # introductory adverbial puts a comma in between. A first draft of the precedence
    # rule also demanded no clause break and these two said no immediately.
    ("Bali precedes with comma", "In Bali, the applicable ceiling on foreign ownership is 49%.", "52292", 100),
    ("provincial regime precedes", "The provincial regime sets an ownership ceiling of 67% here.", "41011", 100),
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


# --------------------------------------------------------------------------- L12
# v2 (Codex FIX-FIRST, 2026-09-25): L12 flags an AFFIRMATIVE PERMISSION of
# full foreign ownership — a permission predicate (can/may/is allowed to/is
# granted…) GOVERNING a full-ownership object — not a token window. A
# 25-sentence adversarial probe (Codex) found 12 false negatives and 9 false
# positives in v1's window design; v2 is the grammar-anchored rewrite. Full
# spec in `l12_full_ownership_claim`'s docstring.
L12_GUILT = [
    # (name, text, maxa) — a genuine full-ownership overclaim that MUST be flagged
    (
        "50134 exact sentence",
        "Foreign-owned PMA companies can fully own this business in Bali, "
        "as it's not blocked by local moratoriums.",
        49,
    ),
    ("synthetic own outright", "A foreign investor can own this business outright.", 49),
    (
        "synthetic without indonesian partner",
        "Foreign owners may hold it without an Indonesian partner.",
        49,
    ),
    # adversarial probe 2026-09-25 (v1 round): a negator TWO CLAUSES back
    # must NOT exonerate a live claim in the current clause (scar #3 under-match)
    (
        "adversarial not-scopes-earlier-clause 1",
        "Bali does not block it, and foreign investors can fully own the business.",
        49,
    ),
    (
        "adversarial not-scopes-earlier-clause 2",
        "With no moratorium in the way, a foreign company can fully own this activity.",
        49,
    ),
    (
        "adversarial not-scopes-earlier-clause 3",
        "It is not blocked in Bali, so full foreign ownership is available.",
        49,
    ),
    # v2 Codex probe (25 sentences, 2026-09-25) — permission predicates in
    # every shape the spec promises to catch
    ("v2 be 100 percent foreign owned", "This business may be 100 percent foreign owned.", 49),
    ("v2 permitted complete ownership", "Foreign investors are permitted complete ownership of the company.", 49),
    ("v2 may be the sole foreign owner", "You may be the sole foreign owner of this business.", 49),
    ("v2 may own all the shares", "Foreign investors may own all the shares in this company.", 49),
    ("v2 can hold the entire equity", "Foreign investors can hold the entire equity of this company.", 49),
    ("v2 may own the whole company", "Foreign investors may own the whole company.", 49),
    ("v2 can be entirely owned by foreign shareholders", "The business can be entirely owned by foreign shareholders.", 49),
    ("v2 no indonesian shareholder needed", "No Indonesian shareholder is needed for foreign investors to operate this company.", 49),
    ("v2 can be 100% foreign owned", "This company can be 100% foreign owned.", 49),
    ("v2 can fully own, unrelated trailing negation", "Foreign investors can fully own the company and cannot be forced to sell.", 49),
    ("v2 not only granted full ownership", "Foreign investors are not only granted full ownership but also unrestricted voting rights.", 49),
    ("v2 full foreign ownership by an entity, not a person, is allowed", "Full foreign ownership by an Indonesian incorporated PT PMA is allowed.", 49),
    ("v2 can own outright, unrelated trailing self-object", "Foreign investors can own this company outright; no local equity is required.", 49),
    ("v2 no moratorium, can fully own", "Bali has no moratorium and foreigners can fully own this company.", 49),
    ("v2 can fully own, comma-interrupted", "Foreigners can fully own, and independently manage, the company.", 49),
    # fresh-Opus gate 2026-09-25, finding 4: object spellings the v2 patterns missed
    ("gate hold all OF the shares", "Foreign investors can hold all of the shares in this company.", 49),
    ("gate wholly-owned hyphen", "This company can be wholly-owned by foreign investors.", 49),
    ("gate fully-owned hyphen", "The business can be fully-owned by a foreign company.", 49),
    ("gate 100%-foreign-owned hyphens", "This company can be 100%-foreign-owned.", 49),
    # conductor probe 2026-09-25 on the gate cure: the new innocence routes
    # must not swallow a foreign owner or a later clause about something else
    ("only-to in a later clause about land", "Foreigners can fully own this company, although land rights are available only to Indonesian citizens.", 49),
    ("only-to after an 'and' clause", "Foreign investors can fully own this company and the licence is issued only to Indonesian citizens later.", 49),
    ("trailing predicate names foreigners, only-to after comma", "Full ownership is available to foreign investors, and the land title only to Indonesian citizens.", 49),
    ("Indonesians and foreigners alike", "Indonesians and foreigners alike can fully own this company.", 49),
    ("Indonesian citizens and foreign investors alike", "Indonesian citizens and foreign investors alike can fully own this company.", 49),
    ("unlike Indonesian citizens, foreigners can", "Unlike Indonesian citizens, foreigners can fully own this company.", 49),
    ("since May (month) then a real can", "Since May, foreigners can fully own this company.", 49),
]

# claims moved OUT of promise: a case that reads as a full-ownership
# assertion in prose but carries NO recognised permission predicate (v2 is
# opt-in on a governing predicate, not flag-by-default like v1 was) — moved
# here per the v2 spec review rather than bending the spec to keep it guilty.
L12_OUT_OF_PROMISE = [
    # "is not restricted" is not one of the enumerated PERMISSION or
    # negated-PERMISSION predicates (allowed/permitted/available/possible/
    # granted/given/entitled/free/able). v1 flagged this NP object by
    # default because nothing in its window matched a specific negation; v2
    # never flags an object with no governing predicate at all — precision-
    # first, per the OUT-OF-PROMISE note in the function docstring.
    ("nominal claim, no permission predicate at all", "Full foreign ownership is not restricted here.", 49),
    # fresh-Opus gate 2026-09-25, finding 8: a positive permission word more
    # than 4 words before the object does not govern it — the LEAD adjacency
    # budget is exactly 4 filler words, and "also, subject to the usual OSS
    # registration steps," is 8.
    (
        "permission word more than 4 words before the object",
        "The company can also, subject to the usual OSS registration steps, "
        "fully own this business.",
        49,
    ),
]

L12_INNOCENCE = [
    # (name, text, maxa) — a legitimate negation that MUST NOT be flagged
    (
        "50113 not fully foreign-owned",
        "That ceiling matters because it describes a structure with permitted "
        "foreign participation, not a fully foreign-owned operation.",
        49,
    ),
    (
        "50122 cannot be wholly foreign-owned",
        "Foreign ownership is capped at 49%, which means a PMA structure "
        "cannot be wholly foreign-owned under this activity.",
        49,
    ),
    (
        "50126 fully foreign-owned PMA cannot hold",
        "International special-cargo sea transport requires an Indonesian "
        "majority shareholder, so a fully foreign-owned PMA cannot hold this "
        "code directly.",
        49,
    ),
    (
        "65112 not full ownership",
        "The recorded national ceiling is 80% of paid-up capital, not full ownership.",
        80,
    ),
    (
        "65121 below full ownership",
        "The national record sets a foreign-share cap below full ownership "
        "for this activity.",
        80,
    ),
    (
        "65201 not a minority stake and not full ownership",
        "A foreign investor is therefore constrained to that 80% ceiling "
        "recorded here, not a minority stake and not full ownership.",
        80,
    ),
    (
        "84124 below full ownership to navigate",
        "There is therefore no foreign-equity structure to interpret or "
        "percentage below full ownership to navigate; the national ceiling "
        "is simply 0%.",
        0,
    ),
    (
        "79110 up to 100% foreign ownership, cap 100 out of scope",
        "Nationally, this KBLI allows up to 100% foreign ownership under certain conditions.",
        100,
    ),
    (
        "50142 can hold 100%, cap 100 out of scope",
        "Nationally, a foreign-owned PT PMA can hold 100% of this KBLI.",
        100,
    ),
    ("maxa is None", "Foreign-owned PMA companies can fully own this business.", None),
    # adversarial probe 2026-09-25 (v1 round): the claim attributes ownership
    # to INDONESIANS, not to a foreigner (scar family #3 over-match)
    (
        "adversarial owned-by-indonesian 1",
        "The business must be wholly owned by Indonesian citizens.",
        49,
    ),
    (
        "adversarial owned-by-indonesian 2",
        "Full ownership by an Indonesian shareholder is required.",
        49,
    ),
    # adversarial probe round 2 (v1): an availability-denying predicate after the claim
    ("adversarial not available after", "Full ownership is not available; the cap is 49%.", 49),
    ("adversarial isn't possible after", "Full foreign ownership isn't possible here.", 49),
    # v2 Codex probe (25 sentences, 2026-09-25) — every innocence class (a)-(d)
    ("v2 indonesian citizens can fully own", "Indonesian citizens can fully own this business.", 49),
    ("v2 can be wholly owned by citizens of indonesia", "This company can be wholly owned by citizens of Indonesia.", 49),
    ("v2 reserved exclusively for indonesian shareholders", "Full ownership is reserved exclusively for Indonesian shareholders.", 49),
    ("v2 prohibited from acquiring full ownership", "Foreign investors are prohibited from acquiring full ownership.", 49),
    ("v2 may not under any circumstances fully own", "Foreign investors may not, under any circumstances, fully own this company.", 49),
    ("v2 full foreign ownership is forbidden", "Full foreign ownership is forbidden.", 49),
    ("v2 denial frame it is not true that", "It is not true that foreign investors may fully own this business.", 49),
    ("v2 cannot legally or beneficially fully own", "Foreigners cannot legally or beneficially fully own this company.", 49),
    ("v2 indonesian shareholders may own outright", "Indonesian shareholders may own this business outright.", 49),
    ("v2 full foreign ownership cannot be permitted", "Full foreign ownership cannot be permitted under the cap.", 49),
    # fresh-Opus gate 2026-09-25 — 4 blocking + 4 hardening findings
    ("gate negated grant: not granted", "Foreign investors are not granted full ownership of this company.", 49),
    ("gate negated grant: never given", "Foreign investors are never given full ownership of this company.", 49),
    ("gate May the month, not the modal", "Since May 2026, full ownership is only possible for Indonesian citizens.", 49),
    ("gate Indonesians bare subject", "Only Indonesians can fully own this business.", 49),
    ("gate Indonesians bare by-clause", "This company can be wholly owned by Indonesians.", 49),
    ("gate maxa is bool True", "Foreign-owned PMA companies can fully own this business.", True),
    ("gate maxa is a non-int string", "Foreign-owned PMA companies can fully own this business.", "special"),
    (
        "gate question with a following answer",
        "Can foreigners fully own this business? No -- the cap is 49%.",
        49,
    ),
    ("gate question alone", "Can foreigners fully own this business?", 49),
    ("gate trailing only-to indonesian attribution", "Full ownership is available only to Indonesian citizens.", 49),
    ("only-to after a parenthetical comma", "Full ownership, however, is available only to Indonesian citizens.", 49),
    ("day-number May is the month", "As of 13 May full ownership is only possible for Indonesian citizens.", 49),
    ("Indonesian citizens, not foreigners", "Indonesian citizens, not foreigners, can fully own this company.", 49),
    ("rather than foreign investors", "Indonesian citizens rather than foreign investors may fully own this company.", 49),
    ("never foreigners", "Only Indonesian shareholders, never foreigners, can hold all of the shares.", 49),
]


@pytest.mark.parametrize("name,text,maxa", L12_GUILT, ids=[c[0] for c in L12_GUILT])
def test_l12_guilt_flags(name, text, maxa):
    assert l12_full_ownership_claim(text, maxa) is not None, (
        f"L12 must FLAG genuine full-ownership overclaim: {name!r}"
    )


@pytest.mark.parametrize(
    "name,text,maxa", L12_OUT_OF_PROMISE, ids=[c[0] for c in L12_OUT_OF_PROMISE]
)
def test_l12_out_of_promise_not_flagged(name, text, maxa):
    assert l12_full_ownership_claim(text, maxa) is None, (
        f"L12 v2 is precision-first and does not promise this case: {name!r}"
    )


@pytest.mark.parametrize("name,text,maxa", L12_INNOCENCE, ids=[c[0] for c in L12_INNOCENCE])
def test_l12_innocence_passes(name, text, maxa):
    assert l12_full_ownership_claim(text, maxa) is None, (
        f"L12 must NOT flag legitimate case: {name!r}"
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
