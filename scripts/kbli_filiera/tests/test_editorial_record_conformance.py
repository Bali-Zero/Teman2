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
    find-and-replace on a field we own and the other needs a human to write a
    sentence — and the live data now proves the split was real rather than
    tidy: the mechanical bucket has been CURED to empty by
    `cure_editorial_cells_from_record.py` while the authored one still holds
    31 codes, untouched, because replacing a sentence means writing one.

    `50135` remains the specimen: clean cells, wrong prose. It was in the
    authored bucket before the cure and it is there now, which is the whole
    point of not having merged the two counts."""
    rep = E.report(E.load_records())
    mech = set(rep["mechanically_correctable"]["codes"])
    auth = set(rep["needs_an_author"]["codes"])
    assert mech == set(), "the mechanical bucket is cured; a new member is a regression"
    assert auth, "the authored backlog is not empty and must not be quietly emptied"
    assert "50135" in auth


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

    # The authored backlog, which only a human can shrink (Legge 5). It went
    # 27 -> 31 when #3673 restricted four codes and left their prose saying the
    # opposite — the cure moved the record and the sentences beside it did not
    # move, which is this module's whole subject.
    assert len(rep["needs_an_author"]["codes"]) == 34

    # WHERE the prose lies. Pinned because the total alone hid the defect that
    # produced these numbers: the first version read three fields and reported
    # 20, and `whatYouNeed` — the field that carries a client's filing
    # instructions — was the largest offender and was never opened.
    assert rep["needs_an_author"]["by_field"] == {
        "editorial.body": 26,
        "whatYouNeed": 23,
        "editorial.headline": 13,
        "editorial.standfirst": 6,
        "whoThisIsFor": 1,
    }


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
    * **L10** is a partial twin: 31 here, 17 there, 14 shared, and each side
      holds real findings the other misses. Asserted in BOTH directions, so
      neither can be retired as redundant on the strength of the other, and the
      three codes only L10 sees stay a declared gap rather than a silent one.

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
    statuses = {
        r["pma_status"]
        for r in records
        if r["kode_kbli_2025"] in mine
    }
    assert "TERBATAS" in statuses, (
        "premise: this module's population is mostly TERBATAS, the status L9's "
        "dangerous-direction test cannot reach"
    )

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

    assert mine & l10, "L10 and this module used to agree on 14 codes; agreeing on none means one went blind"
    assert mine - l10, (
        "this module no longer finds anything L10 misses — if that is real, it is "
        "redundant and should be retired rather than maintained"
    )
    # Was {41011, 52292, 53200}. Widening the claim vocabulary on 2026-08-06
    # closed `53200` — it stated a maximum as a bare number ("the maximum is
    # 100%"), a family the first vocabulary had no word for. The gap SHRANK by
    # being measured, not by being redefined.
    assert l10 - mine == {"41011", "52292"}, (
        "the DECLARED gap in this module — numeric claims L10 catches and a "
        f"sentence-level openness predicate does not: {sorted(l10 - mine)}"
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

    # Umrah/Hajj travel: the CARD is cured, the PROSE still reads as an opening
    # and needs an author. Both halves named, because "79122 is fixed" would be
    # a comfortable half-truth.
    assert "79122" in set(rep["needs_an_author"]["codes"])
