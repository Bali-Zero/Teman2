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


def test_known_limit_the_capped_narrowing_changes_no_live_verdict_today():
    """Honest statement of how much the fix above is currently worth: on the
    live catalogue, NOTHING. Every record that the old over-broad predicate
    would additionally admit (TERBATAS or TERTUTUP at a 100% ceiling) happens to
    carry a negated sentence, so the negation guard already acquits it and both
    predicates report the same twenty codes.

    Pinned rather than glossed, because the alternative is a reader believing
    the narrowing is load-bearing on today's data when it is a guard against a
    record shape that does not exist yet — and because if this assertion ever
    fails, the narrowing has started to matter and someone should read why.
    """
    records = E.load_records()
    narrow = {r["code"] for r in map(E.classify, records) if r["body_asserts_national_openness"]}

    def broad(record):
        cap, status = record.get("pma_max_asing"), (record.get("pma_status") or "").upper()
        if not (status in {"TERBATAS", "TERTUTUP"} or (isinstance(cap, int) and cap < 100)):
            return False
        for sentence in E._SENTENCE.findall(E._body(record)):
            if (
                E._NATIONAL_SCOPE.search(sentence)
                and E._OPENNESS_CLAIM.search(sentence)
                and not E._NEGATION.search(sentence)
            ):
                return True
        return False

    assert {r["kode_kbli_2025"] for r in records if broad(r)} == narrow


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
# THE LIVE CATALOGUE — populations, and the separation that is the product
# --------------------------------------------------------------------------


def test_the_two_buckets_are_reported_separately_and_are_not_the_same_set():
    """A single "N codes are wrong" would hide that one bucket is a
    find-and-replace on a field we own and the other needs a human to write a
    sentence. `50135` is the proof they are different sets: clean cells, wrong
    prose."""
    rep = E.report(E.load_records())
    mech = set(rep["mechanically_correctable"]["codes"])
    auth = set(rep["needs_an_author"]["codes"])
    assert mech and auth
    assert auth - mech, "if every prose case had a bad cell, one check would do"
    assert "50135" in auth - mech


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
    assert len(rep["mechanically_correctable"]["codes"]) == 27
    assert rep["mechanically_correctable"]["ceiling_cells"] == 27
    assert rep["mechanically_correctable"]["status_cells"] == 7
    assert len(rep["needs_an_author"]["codes"]) == 20


def test_the_worst_members_are_named_not_counted():
    """A population with only a size cannot be closed by the pass that comes for
    it. These three are the ones a client acts on money with."""
    rep = E.report(E.load_records())
    mech = set(rep["mechanically_correctable"]["codes"])
    # arms and ammunition, capped at 49% — sidebar says 100%
    assert "25200" in mech
    # military vehicles, capped at 49%
    assert "30400" in mech
    # Umrah/Hajj travel, capped at 0% — its prose still reads as an opening
    assert "79122" in set(rep["needs_an_author"]["codes"])
