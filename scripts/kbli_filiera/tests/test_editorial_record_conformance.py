"""Guilt and innocence for the article-versus-record detector.

This module's whole risk is convicting a page that is RIGHT. The first draft did
exactly that — twice, on the live catalogue — and both cases are pinned below as
innocence tests, because a guard that has already over-matched once and been
fixed without a test is a guard that will over-match again.

The dangerous direction is not symmetric and the tests are shaped around it. A
missed contradiction leaves a wrong number on a page that is already wrong. A
false conviction sends someone to rewrite prose that was correct, and — if it
were ever wired to a cure — would replace a true sentence with a "corrected"
false one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_FILIERA = str(Path(__file__).resolve().parents[1])
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)

import editorial_record_conformance as E  # noqa: E402


def rec(code="01111", status="TERBUKA", cap=100, cells=None, headline="", body=""):
    return {
        "kode_kbli_2025": code,
        "pma_status": status,
        "pma_max_asing": cap,
        "intel_2026": {
            "editorial": {
                "headline": headline,
                "standfirst": "",
                "body": body,
                "byTheNumbers": cells or [],
            }
        },
    }


# --------------------------------------------------------------------------
# CELLS — a stale copy of a field we own
# --------------------------------------------------------------------------


def test_guilt_a_ceiling_cell_that_contradicts_the_record_is_caught():
    r = rec(cap=0, status="TERBATAS", cells=[{"label": "Foreign-ownership ceiling", "value": "100%"}])
    out = E.classify(r)
    assert out["ceiling_cells"] == [
        {"label": "Foreign-ownership ceiling", "says": "100%", "record_says": 0}
    ]


def test_guilt_a_status_cell_that_contradicts_the_record_is_caught():
    r = rec(cap=0, status="TERBATAS", cells=[{"label": "National PMA status", "value": "TERBUKA"}])
    out = E.classify(r)
    assert out["status_cells"][0]["says"] == "TERBUKA"
    assert out["status_cells"][0]["record_says"] == "TERBATAS"


def test_innocence_a_cell_that_agrees_with_the_record_is_left_alone():
    r = rec(cap=49, status="TERBATAS", cells=[{"label": "Foreign ownership ceiling", "value": "49%"}])
    out = E.classify(r)
    assert out["ceiling_cells"] == [] and out["status_cells"] == []


def test_innocence_a_bali_scoped_cell_is_not_judged_against_the_national_field():
    """THE reason this module exists in the shape it does. A closed Bali layer
    over an open national one is lawful and the catalogue says so explicitly.
    Matching "PMA status" anywhere in a label convicts 132 lawful cells."""
    r = rec(
        cap=100,
        status="TERBUKA",
        cells=[{"label": "Bali PMA status", "value": "TERTUTUP"}],
    )
    out = E.classify(r)
    assert out["status_cells"] == []
    assert out["bali_scoped_skipped"] == 1, "and the skip must be COUNTED, not silent"


def test_a_cell_with_no_percentage_cannot_contradict_a_number():
    """`special` is a real value in this catalogue — a cap that is not a
    percentage. Reading it as 0 would invent a contradiction."""
    r = rec(cap=0, status="TERBATAS", cells=[{"label": "Foreign ownership ceiling", "value": "special"}])
    assert E.classify(r)["ceiling_cells"] == []


# --------------------------------------------------------------------------
# BODIES — the two live pages the first draft wrongly convicted
# --------------------------------------------------------------------------


def test_innocence_a_negated_openness_sentence_is_not_an_openness_claim():
    """Live case `59121`. The body says "this is NOT an activity open to foreign
    ownership at the national level" — correct, and the first draft's proximity
    rule ("national" within 80 chars of "open") convicted it. It matched the
    words instead of the assertion."""
    r = rec(
        cap=0,
        status="TERTUTUP",
        body="For a founder assessing a foreign-investment structure, the conclusion is "
        "direct: this is not an activity open to foreign ownership at the national level.",
    )
    assert E.classify(r)["body_asserts_national_openness"] is False


def test_innocence_terbatas_at_one_hundred_percent_may_truthfully_say_one_hundred():
    """Live case `79110`. TERBATAS with a cap of 100 means restricted by
    conditions that are not a percentage, so "a 100% national foreign-ownership
    ceiling" is TRUE of it. The first draft's predicate was `status in
    {TERBATAS, TERTUTUP} or cap < 100`, which convicted the status word.

    The live sentence on that page reads "...but a 100% national foreign-ownership
    ceiling DOES NOT settle the Bali question", and using it verbatim here made
    this test pass for the wrong reason: the negation guard acquitted it and the
    predicate under test was never exercised. Mutation found that — restoring the
    old predicate left all thirteen tests green. The sentence below is therefore
    stripped of its negation, so `capped` is the only thing that can acquit it.
    """
    r = rec(
        cap=100,
        status="TERBATAS",
        body="A 100% national foreign-ownership ceiling applies to this activity.",
    )
    assert E.classify(r)["body_asserts_national_openness"] is False


def test_the_capped_narrowing_now_protects_exactly_one_live_code():
    """It used to be worth nothing on live data. Reading the fields apart changed that.

    This test previously asserted the OPPOSITE — that the `capped` narrowing
    changed no live verdict, because every record the broad predicate would
    additionally admit (TERBATAS/TERTUTUP at a 100% ceiling) happened to carry a
    negated sentence somewhere in the JOINED headline+standfirst+body blob, so
    the negation guard acquitted it either way. Its docstring said that if the
    assertion ever failed, the narrowing had started to matter and someone
    should read why. Judging each field on its own made it fail, and this is the
    why.

    `79110` is TERBATAS with a ceiling of 100. Its denial and its openness
    sentence live in DIFFERENT fields, so once the fields stopped being glued
    together the denial could no longer acquit the claim — and the claim is
    TRUE of it: restricted by conditions that are not a percentage still means a
    100% foreign-ownership ceiling. Only `capped` keeps it innocent now, which
    is precisely the record shape the narrowing was written for.

    Kept as an equality against a NAMED set rather than a count, so that a
    second code drifting into this position is a failure someone must read
    rather than a number quietly becoming two.
    """
    records = E.load_records()
    narrow = {r["code"] for r in map(E.classify, records) if r["body_asserts_national_openness"]}

    def broad(record):
        cap, status = record.get("pma_max_asing"), (record.get("pma_status") or "").upper()
        if not (status in {"TERBATAS", "TERTUTUP"} or (isinstance(cap, int) and cap < 100)):
            return False
        for _path, text in E._prose_fields(record):
            for sentence in E._SENTENCE.findall(text):
                if not (
                    E._NATIONAL_SCOPE.search(sentence) and E._OPENNESS_CLAIM.search(sentence)
                ) or E._NEGATION.search(sentence):
                    continue
                contrast = E._CONTRAST.search(sentence)
                if contrast and not E._OPENNESS_CLAIM.search(sentence[: contrast.start()]):
                    continue
                return True
        return False

    protected = {r["kode_kbli_2025"] for r in records if broad(r)} - narrow
    assert protected == {"79110"}, (
        "the `capped` narrowing is the only thing standing between these codes "
        "and a conviction — read each one before changing this set"
    )
    assert [r for r in records if r["kode_kbli_2025"] == "79110"][0][
        "pma_max_asing"
    ] == 100, "premise: 79110 is capped at 100, so an openness claim is true of it"


def test_guilt_a_body_denying_the_cap_in_words_is_caught_even_when_the_cells_agree():
    """Live case `50135`: every sidebar cell agrees with the record, and the
    prose still tells the reader he may hold the activity outright. The cells
    and the body are separate assertions and a check on one is not a check on
    the other."""
    r = rec(
        cap=49,
        status="TERBATAS",
        cells=[{"label": "Foreign ownership ceiling", "value": "49%"}],
        body="The national reading is direct: a foreign-owned company may hold the "
        "activity with full foreign ownership, rather than under a lower foreign-equity ceiling.",
    )
    out = E.classify(r)
    assert out["ceiling_cells"] == []
    assert out["body_asserts_national_openness"] is True


def test_innocence_an_open_code_saying_it_is_open_is_not_a_contradiction():
    r = rec(cap=100, status="TERBUKA", body="This activity is nationally open to full foreign ownership.")
    assert E.classify(r)["body_asserts_national_openness"] is False


# --------------------------------------------------------------------------
# THE TWO FIELDS-OF-THIRTEEN DEFECTS
# --------------------------------------------------------------------------


def test_guilt_a_sibling_prose_key_is_read_not_just_the_editorial_block():
    """`whatYouNeed` reaches Qdrant exactly as the body does, and held MORE lies.

    The first version read `editorial.{headline,standfirst,body}` and called
    the result "the bodies". `intel_2026` carries eight further prose keys, all
    stringified into the embedding text by `reindex_kbli_2025_final.py`. On the
    live catalogue eighteen offending sentences sit in `whatYouNeed` — the
    field that tells a client what to file — and none of them were ever read.
    """
    r = rec(cap=0, status="TERTUTUP")
    r["intel_2026"]["whatYouNeed"] = (
        "Nationally, 100% foreign ownership is permitted for this activity."
    )
    out = E.classify(r)
    assert out["body_asserts_national_openness"] is True
    assert [f["field"] for f in out["offending_fields"]] == ["whatYouNeed"]


def test_guilt_a_headline_is_judged_alone_not_glued_to_the_standfirst():
    """A headline has no full stop, so joining made it one sentence with the next.

    The splitter breaks on `.!?\\n`. `"Open to Foreign Ownership Nationally" + " "
    + standfirst` is therefore a SINGLE sentence, and a standfirst that opens
    with the Bali caveat supplies a negation — which acquitted the headline on
    the strength of a denial belonging to a different assertion. Three headlines
    on the live catalogue were acquitted exactly this way.
    """
    r = rec(
        cap=0,
        status="TERTUTUP",
        headline="Open Nationally to Full Foreign Ownership",
        body="Bali does not permit it.",
    )
    r["intel_2026"]["editorial"]["standfirst"] = (
        "Bali is not the same question, and permission does not follow."
    )
    out = E.classify(r)
    assert out["body_asserts_national_openness"] is True
    assert "editorial.headline" in [f["field"] for f in out["offending_fields"]]


def test_innocence_a_negation_still_acquits_within_its_own_field():
    """The fix must not turn every caveat into a conviction.

    Splitting the fields apart makes each denial local. A field whose sentence
    denies openness is still innocent — that is `59121` above — and this pins
    that the per-field change did not quietly drop the negation guard."""
    r = rec(cap=0, status="TERTUTUP")
    r["intel_2026"]["whatYouNeed"] = (
        "This is not an activity open to foreign ownership at the national level."
    )
    assert E.classify(r)["body_asserts_national_openness"] is False


def test_the_walk_reaches_prose_nested_below_the_top_level():
    """Depth is not a reason to be unread: `tkaInfo` is a dict of dicts.

    A key list would have to be extended for every new nesting; the walk covers
    them the day they appear, which is the point of walking instead of listing.
    """
    r = rec(cap=0, status="TERTUTUP")
    r["intel_2026"]["tkaInfo"] = {
        "positions": [{"note": "Nationally open to full foreign ownership."}]
    }
    out = E.classify(r)
    assert out["body_asserts_national_openness"] is True
    assert out["offending_fields"][0]["field"] == "tkaInfo.positions[0].note"


# --------------------------------------------------------------------------
# THE CLAIM VOCABULARY — widened from the corpus, not from imagination
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        # the status word asserted bare — 18 live sentences, the largest family
        "Nationally, the foreign-investment position is clean: the record marks the activity as TERBUKA",
        # a maximum stated as a number, with no "open to" anywhere
        "Nationally, the code is PMA-open up to 100%",
        "For a foreign-owned registration, the national picture is simple: it is open and the maximum is 100%",
        # "fully open"
        "Nationally, foreign ownership is fully open",
        # openness as a NOUN
        "That is the real line between a national opening and a Bali filing",
    ],
)
def test_guilt_the_four_phrasings_the_first_vocabulary_had_no_words_for(sentence):
    """Each of these is live text on a capped record, and each used to pass.

    The first claim list was assembled from the sentences it already caught,
    which cannot find a family it has no word for — a pattern written from the
    instances you found catches the instances you found (W113). These five come
    from reading the sentences on capped records that the predicate did NOT
    flag, which is the only place a missing family can be seen.
    """
    r = rec(cap=0, status="TERTUTUP", body=sentence + ".")
    assert E.classify(r)["body_asserts_national_openness"] is True


@pytest.mark.parametrize(
    "sentence",
    [
        # THE live sentence that made the negation list grow with the claim list
        "Nationally, the activity is TERBATAS: foreign ownership is capped at 49%, "
        "rather than being fully open",
        "The national position is a 49% cap instead of full foreign ownership",
        "It is treated as restricted, as opposed to nationally open",
    ],
)
def test_innocence_english_denies_by_contrast_as_well_as_by_not(sentence):
    """Widening the claim list without handling contrast convicts correct prose.

    `50126` says the true thing — capped at 49%, RATHER THAN fully open — and
    `fully\\s+open` made it newly catchable. But a BLANKET acquittal on the
    contrastive marker was itself an over-match, caught by this file's own
    `50135` test: there the same two words introduce the REJECTED alternative,
    so "full foreign ownership, rather than a lower ceiling" asserts openness.
    The marker is therefore read positionally — see `_CONTRAST` — and these
    three are innocent because the claim sits AFTER it.
    """
    r = rec(cap=49, status="TERBATAS", body=sentence + ".")
    assert E.classify(r)["body_asserts_national_openness"] is False


@pytest.mark.parametrize(
    ("sentence", "code"),
    [
        # military combat vehicles, capped at 49% by Perpres 49/2021
        (
            "KBLI 30400 covers the manufacture and rebuilding of military combat "
            "vehicles, nationally open to PMA and not blocked by Bali's moratorium record",
            "30400",
        ),
        # Umrah and Hajj travel, capped at 0%
        (
            "This activity covers the assembly and sale of Umrah and special-Hajj "
            "travel packages, with a fully open national foreign-ownership position "
            "and no Bali moratorium block",
            "79122",
        ),
        # couriers, capped at 49%
        (
            "From parcel pickup to doorstep delivery, this activity spans domestic "
            "and international courier work across every listed scale, with full "
            "foreign ownership open nationally and no Bali moratorium block",
            "53200",
        ),
    ],
)
def test_guilt_a_later_unrelated_negation_does_not_acquit_the_claim(sentence, code):
    """The largest blind spot this module ever had, and it was found by accident.

    A cross-family reviewer, asked to attack the CONTRAST rule, noted in passing
    that scanning the whole sentence for a negation lets an unrelated clause
    acquit the claim. The house style of this catalogue puts the two facts side
    by side — "nationally open to PMA AND NOT blocked by Bali's moratorium" —
    so the sentence asserts the falsehood in its first half and is excused by
    its innocent second.

    Measured before the rule changed: 42 sentences on 22 codes, every one a
    genuine assertion of national openness on a record capped at 0 or 49, and
    not one a denial. These three are live text, on codes whose caps come from
    the Perpres annex adjudicated by this lane.
    """
    assert E.classify(rec(cap=49, body=sentence + "."))["body_asserts_national_openness"] is True


@pytest.mark.parametrize(
    "sentence",
    [
        "There is no national opening for a PT PMA that a Bali registration narrows",
        "This activity is not open to foreign ownership nationally",
        "That ceiling is the national limit: foreign participation is possible only "
        "within that stated maximum, not on an unrestricted basis",
    ],
)
def test_innocence_a_negation_that_precedes_the_claim_still_acquits(sentence):
    """The other half of the same rule, and the reason it is POSITIONAL.

    A negation before the claim is denying it; a negation after it is talking
    about something else. All three of these are live text — `95291` and
    `50121` say the true thing and must not be sent to an author.
    """
    assert E.classify(rec(cap=0, body=sentence + "."))["body_asserts_national_openness"] is False


@pytest.mark.parametrize(
    "sentence",
    [
        "Rather than being capped, this activity is nationally open to full foreign ownership",
        "The record, rather than confirming a cap, shows the activity is nationally "
        "open to foreign investment",
        # live on 41020: the contrast is between "aligned" and "contradictory",
        # and a colon ends it before the openness is reached
        "The honest conclusion is aligned rather than contradictory: nationally "
        "open, and not blocked for PMA registration in Bali",
    ],
)
def test_guilt_a_contrast_that_does_not_govern_the_claim_does_not_acquit_it(sentence):
    """"After the marker" was not enough, and English is why.

    The fronted contrast — "RATHER THAN being capped, this activity is
    nationally open" — is ordinary English, not an edge case, and it puts the
    ASSERTED side after the marker. What ends the contrast is a clause boundary:
    a comma for the fronted form, a colon for `41020`. So the marker must
    DIRECTLY govern the claim, with nothing between them that closes its clause.
    """
    assert E.classify(rec(cap=49, body=sentence + "."))["body_asserts_national_openness"] is True


@pytest.mark.parametrize(
    "sentence",
    [
        "The national position is anything but open to foreign ownership",
        "The national picture is hardly open to foreign ownership",
        "Without being nationally open, the activity operates under a special permit",
    ],
)
def test_innocence_english_also_denies_by_degree_not_only_by_not(sentence):
    """Downtoners read as assertions to a pattern that only knows "not".

    These acquit ZERO live sentences today — they are relief for prose not yet
    written, and they are here rather than in a ledger because the alternative
    is discovering them when a correct sentence is sent to an author. `without`
    is deliberately only in its `without being` form: bare `without` would
    acquit "without a local partner, this is nationally open to 100%", which is
    the dangerous direction.
    """
    assert E.classify(rec(cap=49, body=sentence + "."))["body_asserts_national_openness"] is False


@pytest.mark.parametrize(
    "sentence",
    [
        "The national rule per art. 12 states the activity is open to foreign ownership",
        "Under national regulation No. 7 of 2025, the activity is open to foreign ownership",
        "The national rate is 3.5 and the activity is open to foreign ownership",
    ],
)
def test_guilt_an_abbreviation_or_a_decimal_does_not_end_the_sentence(sentence):
    """A period that is not a full stop split the claim away from its scope.

    This predicate needs the national scope word and the openness claim in the
    SAME sentence, so "Perpres No. 7 of 2025" or "3.5" between them was a silent
    miss — in the one direction that reaches a client. The corpus is regulatory
    prose: 50 abbreviation dots and 109 decimal dots live.

    The `No.` case is here for a second reason. Masking abbreviations so the
    splitter keeps them newly put "regulation No. 7" INSIDE the sentence, where
    a bare `\\bno\\b` read the regulation NUMBER as the word "no" and acquitted
    the claim after it. Curing one half of superscar #3 handed the other half a
    fresh instance in the same edit — so `no` now refuses a following period.
    """
    assert E.classify(rec(cap=49, body=sentence + "."))["body_asserts_national_openness"] is True


def test_a_bali_sentence_that_also_states_the_national_position_is_still_guilty():
    """Not an over-match, and worth pinning because it looks like one.

    "Nationally TERBUKA, but blocked in Bali" on a capped record is making the
    false national claim inside a sentence whose subject is Bali. The Bali
    exclusion in this module is about CELL LABELS — a `Bali PMA status` cell
    describes a different fact — and does not extend to prose that asserts the
    national position while discussing Bali."""
    r = rec(
        cap=0,
        status="TERBATAS",
        body="Nationally the activity is TERBUKA, but Bali blocks PMA registration.",
    )
    assert E.classify(r)["body_asserts_national_openness"] is True


# --------------------------------------------------------------------------
# THE LIVE CATALOGUE — populations, and the separation that is the product
# --------------------------------------------------------------------------


def test_the_two_buckets_are_reported_separately_and_are_not_the_same_set():
    """A single "N codes are wrong" would hide that one bucket is a
    find-and-replace on a field we own and the other needs a sentence written.

    BOTH buckets are now empty on the live catalogue — the mechanical one by
    `cure_editorial_cells_from_record.py`, the authored one by the four prose
    lots of `cure_prose_national_openness.py`. That is the good news and it is
    also the danger this test now has to survive: two empty sets are equal, so
    an assertion that they DIFFER would pass on a detector that had gone blind.
    The separation is therefore proved on constructed records, where each
    bucket can be entered on purpose, and the live catalogue is asserted as a
    tripwire at zero rather than as a specimen.

    The specimen this test used to name went `50135` -> `84231` as each was
    cured; there is no third, because there is no live member left to name."""
    rep = E.report(E.load_records())
    mech = set(rep["mechanically_correctable"]["codes"])
    auth = set(rep["needs_an_author"]["codes"])
    assert mech == set(), "the mechanical bucket is cured; a new member is a regression"
    assert auth == set(), "the authored backlog is cured; a new member is a regression"

    # The split itself, on records built to enter one bucket and not the other.
    # A wrong CELL with honest prose is mechanical; wrong PROSE with honest
    # cells needs an author. If these ever collapse into one bucket the report
    # above stops meaning anything, and two empty sets would not have said so.
    mechanical_only = E.classify(
        rec(cap=49, status="TERBATAS", cells=[{"label": "Foreign ceiling", "value": "100%"}])
    )
    assert mechanical_only["ceiling_cells"] != []
    assert mechanical_only["body_asserts_national_openness"] is False

    authored_only = E.classify(
        rec(
            cap=49,
            status="TERBATAS",
            cells=[{"label": "Foreign ceiling", "value": "49%"}],
            body="The national reading is direct: a foreign-owned company may "
            "hold the activity with full foreign ownership, rather than under a "
            "lower foreign-equity ceiling.",
        )
    )
    assert authored_only["ceiling_cells"] == []
    assert authored_only["body_asserts_national_openness"] is True


def _mine_and_l10(record, lint_mod):
    """Both predicates' verdicts on ONE record, so their reach can be compared
    without a live population to compare it on."""
    caps = {record["kode_kbli_2025"]: record.get("pma_max_asing")}
    mine = E.classify(record)["body_asserts_national_openness"]
    l10 = any(
        lint_mod.l10_ownership_contradiction(
            text, record["kode_kbli_2025"], record.get("pma_max_asing"), caps
        )
        for _field, text in lint_mod.iter_prose(record)
    )
    return mine, l10


def test_the_bali_exclusion_is_large_enough_to_matter_and_is_declared():
    """If this were near zero the scope split would be theoretical. It is not:
    132 lawful Bali-scoped cells would be convicted by a label substring."""
    rep = E.report(E.load_records())
    assert rep["bali_scoped_cells_excluded"] > 100


def test_the_live_populations_are_pinned():
    """Measured, not carried over from a plan. These may only SHRINK as cures
    land; a rise means a new contradiction was authored, which is the whole
    thing this file is about."""
    rep = E.report(E.load_records())

    # ZERO, and this is a tripwire rather than a backlog size now: the 31 stale
    # cells this module first reported were cured by
    # `cure_editorial_cells_from_record.py`, so any number above zero means a
    # NEW stale copy was authored or a cure moved a field and left the card
    # behind. That is exactly how these 31 were born.
    assert rep["mechanically_correctable"]["codes"] == []
    assert rep["mechanically_correctable"]["ceiling_cells"] == 0
    assert rep["mechanically_correctable"]["status_cells"] == 0

    # The authored backlog. It went 27 -> 31 when #3673 restricted four codes and
    # left their prose saying the opposite, then 31 -> 34 when the claim
    # vocabulary was widened to what the corpus actually says — and now 34 -> 28,
    # the first six replaced by `cure_prose_national_openness.py`.
    #
    # "Only a human can shrink this" was the standing note here and it was WRONG,
    # or rather it had stopped being true: 27 of the 31 bodies carry
    # `_l3_regen.model = deepseek-v4-pro` at `confidence: LOW`. No human wrote
    # them. The deference that left them standing was protecting an authorship
    # that does not exist, and Zero withdrew it on 2026-08-06.
    #
    # 7 -> 0 with the fourth and last lot. This is now a TRIPWIRE, not a
    # backlog: any number above zero is a contradiction authored after the
    # lane closed. It is deliberately an equality — `<= 7` would have let the
    # backlog refill halfway and still read green.
    assert len(rep["needs_an_author"]["codes"]) == 0

    # WHERE the prose lies, and this is the number that matters — not the code
    # count above. A cross-family refutation left that count UNMOVED at 34 while
    # changing what a cure would have to touch by half:
    #
    #     editorial.standfirst   6 -> 22
    #     editorial.pullQuote    0 -> 11      (an entire field, invisible)
    #     whatYouNeed           23 -> 26
    #     total field-hits      69 -> 102
    #
    # The 34 codes were already known. What was hidden is that most of them lie
    # in MORE THAN ONE field, and a cure driven by the pre-refutation verdict
    # would have rewritten 69 sentences and left 33 standing ON THE SAME PAGES —
    # a page that reads cured with its standfirst still asserting the opposite.
    # Pinned by field for that reason: the total alone hid the first defect too,
    # when three fields were read and reported as "the bodies".
    #
    # 102 -> 81 -> 60 -> 20 as `cure_prose_national_openness.py` replaced 21 fields
    # on six codes, 21 more on seven, then 51 on the fourteen transport codes whose
    # ceiling is 49%. The dict below is the CURRENT state, re-derived from the live
    # catalogue rather than arithmetic on the previous one — two branches moving the
    # same monotone number conflict textually even when both are right, and the
    # resolution is to re-measure, never to pick a side (W109b).
    #
    # This histogram counts only what THIS module's predicate sees. The transport
    # batch was cured against the UNION of this predicate and the lint's numeric
    # one, because four of its fields — a "By the numbers" cell, a standfirst
    # reading "full national foreign ownership", two pull quotes — carried the
    # falsehood in a form no sentence-level openness predicate matches. A pin on
    # one predicate is a pin on one predicate.
    # 102 -> 81 -> 60 -> 20 -> 0. The histogram is empty because the population
    # is, and it stays here rather than being deleted: an empty dict asserted
    # by EQUALITY is the only form of this pin that still fails when a single
    # field starts lying again. A deleted histogram would fail nothing.
    assert rep["needs_an_author"]["by_field"] == {}


def test_the_relationship_to_both_existing_lint_rules_is_pinned():
    """Two lint rules could be this module's twin. One is not; one partly is.

    This test was first written as "not a twin of L9" and stopped there, because
    L9 is the rule whose NAME matches (`validate_pma_consistency`). The rule
    whose BEHAVIOUR matches is L10, and it was not opened at all — so the
    conclusion drawn was true about L9 and misleading about the lint.

    Both are pinned now:

    * **L9** is disjoint. Its reachable half of the dangerous direction needs
      `pma_status == "TERTUTUP"` AND the literal "100% foreign", which no live
      record satisfies; its two findings are the mirror case.
    * **L10** is a partial twin: it was 31 here, 17 there, 14 shared, and each
      side held real findings the other missed.

    THE OVERLAP IS NO LONGER MEASURABLE ON LIVE DATA, and pretending otherwise
    is how this test would rot. This module's live population is now zero, so
    every `mine & l10` / `mine - l10` assertion that used to carry the claim is
    vacuously true or trivially false — an empty set intersects nothing and
    subtracts to nothing. The complementary blind spots are therefore asserted
    on CONSTRUCTED records, where each predicate's reach is permanent, and the
    live catalogue keeps only the assertions that still have something to say:
    this module clean, L9's two findings, L10's three.

    A failure here means the tools have started answering one question two ways
    (W105); the response is to make the lint consume this report, not to delete
    whichever assertion has become inconvenient.
    """
    scripts_dir = str(Path(__file__).resolve().parents[2])
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from kbli_enrich_validate import validate_pma_consistency

    records = E.load_records()
    mine = {r["code"] for r in map(E.classify, records) if r["body_asserts_national_openness"]}
    l9 = {
        r["kode_kbli_2025"]
        for r in records
        if isinstance(r.get("intel_2026"), dict)
        and r["kode_kbli_2025"] != "69101"  # the lint's documented profession-law override
        and validate_pma_consistency(r["intel_2026"], r)
    }

    assert mine & l9 == set(), (
        "L9 and this module now report overlapping codes — reconcile them so one "
        f"consumes the other rather than both judging: {sorted(mine & l9)}"
    )
    assert l9 == {"43110", "86201"}, f"L9's live findings moved: {sorted(l9)}"
    assert mine == set(), (
        "this module's live population is zero and the assertions below are "
        f"written for that: {sorted(mine)}"
    )

    # The premise that used to be checked here — "this module's population is
    # mostly TERBATAS, the status L9's dangerous-direction test cannot reach" —
    # read the statuses of `mine`, so with `mine` empty it asserted membership
    # in an empty set and could only fail. Kept as a property of L9's REACH
    # instead, which is what it was always about: a TERBATAS record stating full
    # foreign ownership in words is invisible to L9, whatever else is true.
    l9_blind = rec(
        cap=49,
        status="TERBATAS",
        body="The national reading is direct: a foreign-owned company may hold "
        "the activity with full foreign ownership, rather than under a lower "
        "foreign-equity ceiling.",
    )
    assert not validate_pma_consistency(l9_blind["intel_2026"], l9_blind)
    assert E.classify(l9_blind)["body_asserts_national_openness"] is True

    # L10 is the rule that actually resembles this module, and the first version
    # of this test did not look at it — it checked the rule whose NAME matched
    # and missed the one whose BEHAVIOUR matched. Pinned as a partial twin with
    # complementary blind spots, in BOTH directions, so neither can be retired as
    # redundant on the strength of the other.
    import kbli_dataset_lint as lint

    maxa_by_code = {r["kode_kbli_2025"]: r.get("pma_max_asing") for r in records}
    l10 = set()
    for record in records:
        code, maxa = record["kode_kbli_2025"], record.get("pma_max_asing")
        if code in lint.L10_SECTOR_LAW_OVERRIDE or not isinstance(maxa, int):
            continue
        if any(
            lint.l10_ownership_contradiction(text, code, maxa, maxa_by_code)
            for _field, text in lint.iter_prose(record)
        ):
            l10.add(code)

    # The two blind spots, on records built to sit in exactly one predicate.
    # These used to be read off the live overlap (14 shared, 3 only-L10); with
    # this module's population at zero that reading is gone, and asserting
    # `mine & l10` on an empty set would fail for a reason that has nothing to
    # do with either rule. Constructed, the property is permanent — and it is
    # the property that justifies keeping both rules.
    only_mine = rec(
        cap=49,
        status="TERBATAS",
        body="The national reading is direct: a foreign-owned company may hold "
        "the activity with full foreign ownership, rather than under a lower "
        "foreign-equity ceiling.",
    )
    assert _mine_and_l10(only_mine, lint) == (True, False), (
        "this module no longer finds what L10 misses — a claim carried in WORDS "
        "with no percentage. If that is real it is redundant and should be "
        "retired rather than maintained"
    )

    only_l10 = rec(
        cap=49,
        status="TERBATAS",
        body="Foreign investors may hold up to 100% of the equity in this line "
        "of business.",
    )
    assert _mine_and_l10(only_l10, lint) == (False, True), (
        "L10 no longer finds what this module misses — a percentage stated with "
        "no national-scope word beside it. Agreeing everywhere means one of the "
        "two went blind"
    )
    # Was {41011, 52292, 53200}. Widening the claim vocabulary on 2026-08-06
    # closed `53200` — it stated a maximum as a bare number ("the maximum is
    # 100%"), a family the first vocabulary had no word for. The gap SHRANK by
    # being measured, not by being redefined.
    #
    # It then briefly grew to include `55105`, and THAT is what this pin is for.
    # The prose cure corrected 55105's standfirst and body, and its `whatYouNeed`
    # went on saying "**PMA Status:** Fully open (Terbuka) — 100% foreign
    # ownership" — no "national" anywhere near it, so this module cannot see the
    # sentence at all. L10 reads for a PERCENTAGE and caught it. A page that
    # reads cured while still printing the number a client acts on is the worst
    # of the three states, and only the disagreement between two rules surfaced
    # it. Cured; the pin is back to the two codes that run the OPPOSITE direction
    # (prose more restrictive than the record), which is a different adjudication.
    # With `mine` empty this is now just L10's live population, and it is
    # asserted as such rather than dressed up as a difference. `86201` joined
    # 41011 and 52292 when the transport lot landed: all three ran the OPPOSITE
    # direction — prose MORE restrictive than the record — which is a different
    # adjudication and deliberately not cured by THAT lane.
    #
    # `41011` left the set on 2026-08-08 (the sector-law DO-NOT-SHIP fix-pack,
    # item A), and this time it WAS the cure, not a mirror-direction adjudication
    # left standing: 41011's editorial prose asserted a flat "67%" cap the
    # adjudication itself had already withdrawn (canonical stays TERBUKA/100 —
    # the real constraint is a Lampiran II madya-segment reservation, not a
    # whole-code percentage). `cure_canonical_sector_law_prosepack.py` rewrote
    # `l4_bali.reason`, `whatYouNeed`, every `editorial.*` field and `whoThisIsFor`
    # to state the segment reservation in words, with no percentage anywhere in
    # the record — so `L10_PCT` has nothing left to match and L10 correctly
    # stops finding it. `86201` also steers a foreign doctor to "code 86103
    # (klinik) … 67%", and 86103's cap is 100 — untouched by this fix-pack,
    # still the mirror-direction case L10 exists to catch.
    assert l10 == {"52292", "86201"}, (
        "L10's live findings moved — these are the mirror-direction cases this "
        f"lane declared rather than cured: {sorted(l10)}"
    )


def test_the_worst_members_are_named_not_counted():
    """A population with only a size cannot be closed by the pass that comes for
    it. These three are the ones a client acts on money with."""
    records = E.load_records()
    rep = E.report(records)
    by_code = {r["kode_kbli_2025"]: r for r in records}

    def ceiling_cells(code):
        editorial = (by_code[code].get("intel_2026") or {}).get("editorial") or {}
        return [
            c
            for c in (editorial.get("byTheNumbers") or [])
            if isinstance(c, dict)
            and "ceiling" in str(c.get("label", "")).lower()
            and "bali" not in str(c.get("label", "")).lower()
        ]

    # The three a client acts on money with. Asserted by CONTENT rather than by
    # absence from a bucket — "not in the mechanical list" would also be true if
    # the detector had gone blind, which is the failure this file exists to
    # catch (W107: the probe can carry the disease it measures).
    for code, expected in (("25200", "49%"), ("30400", "49%"), ("79122", "0%")):
        cells = ceiling_cells(code)
        assert cells, f"{code} lost its national ceiling card entirely"
        assert all(c["value"] == expected for c in cells), (
            f"{code} ceiling card says {[c['value'] for c in cells]}, record says {expected}"
        )
    assert set(rep["mechanically_correctable"]["codes"]) == set()

    # Umrah/Hajj travel: the card was cured first and the prose stood for
    # weeks — "79122 is fixed" was the comfortable half-truth this line was
    # written to refuse. Both halves are cured now, so the assertion inverts,
    # and it is asserted by CONTENT on the page rather than by absence from a
    # bucket, for the same reason as the cards above.
    prose_79122 = json.dumps(by_code["79122"]["intel_2026"], ensure_ascii=False).lower()
    assert "79122" not in set(rep["needs_an_author"]["codes"])
    assert "0%" in prose_79122 or "no foreign" in prose_79122 or "closed" in prose_79122, (
        "79122's prose no longer states the closure anywhere a client reads"
    )
