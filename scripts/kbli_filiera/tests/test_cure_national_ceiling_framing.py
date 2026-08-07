"""Guilt + innocence for the national-ceiling framing compiler.

Three of these tests exist because of a specific defect rather than for coverage:

  - `test_the_sibling_engine_is_imported_once` — `scripts/kbli_filiera/` sits on
    sys.path in script mode, so the sibling engine can be loaded as BOTH
    `cure_l4_withdrawn_umkm_prose` and its package path: two module objects from
    one file, two distinct `CureError` classes. A refusal raised through one and
    caught through the other escapes `main`'s `except` and surfaces as a
    traceback instead of the exit-1 a caller reads.

  - `test_refuses_a_percentage_the_record_does_not_support` — this whole lane
    exists because pages print an ownership number nobody granted. A cure that
    can invent its own number has the disease it treats (W113: the sentence you
    write while correcting another is a new claim, and it is the one nobody
    grades).

  - `test_refuses_when_the_ownership_fields_have_since_been_corrected` — the
    defect IS the disagreement between the verdict and the ownership fields. If
    a later lane fixes `pma_status`, prose saying "the national position is
    closed" would be arguing with a data layer that already agrees, and the
    reader would get a correction of something no longer on the page.
"""

from __future__ import annotations

import copy
import json

import pytest

from scripts.kbli_filiera import cure_l4_withdrawn_umkm_prose as sibling
from scripts.kbli_filiera import cure_national_ceiling_framing as cure
from scripts.kbli_filiera.cure_national_ceiling_framing import (
    CureError,
    DEFAULT_SPEC,
    apply_patch,
    check_new_percentages,
    check_premise,
    split_field,
)

PREMISE = {
    "expect_l4_status": "CHIUSO_SEKTORAL",
    "expect_l4_blocked": True,
    "expect_pma_status": "TERBUKA",
    "expect_pma_max_asing": 100,
}


def _record(reason: str = "klinik: max 67% WNA") -> dict:
    return {
        "kode_kbli_2025": "86102",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "l4_bali": {"status": "CHIUSO_SEKTORAL", "blocked": True, "reason": reason},
        "intel_2026": {
            "whatItMeans": "In Bali, a foreign investor cannot register this activity.",
            "editorial": {
                "headline": "Open Nationally, Closed in Bali",
                "byTheNumbers": [
                    {"label": "National PMA status", "value": "TERBUKA"},
                    {"label": "Foreign-ownership ceiling", "value": "100%"},
                ],
            },
        },
    }


def _patch(**kw) -> dict:
    base = {
        "field": "canonical:intel_2026.whatItMeans",
        "old": "In Bali, a foreign investor cannot register this activity.",
        "new": "A foreign investor cannot register this activity.",
        "why": "the restriction is not specific to Bali",
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# The import trap
# --------------------------------------------------------------------------- #

def test_the_sibling_engine_is_imported_once():
    """One file must not become two classes. See module docstring."""
    assert cure.CureError is sibling.CureError
    assert cure._dig is sibling._dig


# --------------------------------------------------------------------------- #
# split_field — the surface lives IN the key
# --------------------------------------------------------------------------- #

def test_a_well_formed_canonical_key_resolves():
    """INNOCENCE, stated rather than left to the absence of an exception."""
    assert split_field("86102", "canonical:intel_2026.editorial.headline") == (
        "canonical", "intel_2026.editorial.headline"
    )


def test_a_well_formed_gold_key_resolves():
    """INNOCENCE: gold prose keys are bare — gold entries have no intel_2026."""
    assert split_field("86102", "gold:whatYouNeed") == ("gold", "whatYouNeed")


def test_a_stat_card_value_resolves():
    """INNOCENCE: the card index is part of the path, not a separate field."""
    assert split_field("86102", "canonical:intel_2026.editorial.byTheNumbers[1].value") == (
        "canonical", "intel_2026.editorial.byTheNumbers[1].value"
    )


def test_refuses_a_field_with_no_surface_prefix():
    with pytest.raises(CureError, match="no surface prefix"):
        split_field("86102", "intel_2026.whatItMeans")


def test_refuses_an_unknown_surface():
    with pytest.raises(CureError, match="unknown surface"):
        split_field("86102", "qdrant:intel_2026.whatItMeans")


@pytest.mark.parametrize("root", sorted(cure.FORBIDDEN_ROOTS))
def test_refuses_to_write_the_verdict_or_the_government_data(root: str):
    """`pma_status`/`pma_max_asing` are wrong on these records too — and fixing
    them is a different lane with a four-store propagation. A prose compiler that
    can reach them would quietly become that lane."""
    with pytest.raises(CureError, match="verdict/government layer"):
        split_field("86102", f"canonical:{root}.anything")


def test_refuses_a_canonical_path_outside_the_prose_object():
    with pytest.raises(CureError, match="must address prose under 'intel_2026.'"):
        split_field("86102", "canonical:judul")


def test_refuses_to_rewrite_a_stat_card_label():
    """A card's LABEL says what is being measured; its VALUE is the claim. This
    cure corrects claims — renaming the measurement would hide the error rather
    than fix it."""
    with pytest.raises(CureError, match="stat-card LABEL"):
        split_field("86102", "canonical:intel_2026.editorial.byTheNumbers[1].label")


# --------------------------------------------------------------------------- #
# check_new_percentages — the cure may not invent the number it is removing
# --------------------------------------------------------------------------- #

def test_a_percentage_the_reason_supports_passes():
    """INNOCENCE: 67% is in the reason, and reading it changes nothing."""
    record = _record()
    before = copy.deepcopy(record)
    patch = _patch(new="Foreign ownership is capped at 67%.")
    assert check_new_percentages(record, "86102", patch) is None
    assert record == before, "the percentage check must not mutate the record it reads"


def test_a_replacement_with_no_percentage_passes():
    """INNOCENCE: most replacements delete a number rather than state one."""
    assert check_new_percentages(_record(), "86102", _patch()) is None


def test_refuses_a_percentage_the_record_does_not_support():
    patch = _patch(new="Foreign ownership is capped at 49%.")
    with pytest.raises(CureError, match="does not support that figure"):
        check_new_percentages(_record(), "86102", patch)


def test_a_percentage_carried_over_from_the_old_text_passes():
    """INNOCENCE, and it is the case that actually bit: 95291's replacement copies
    the record's existing opening — "fully open (100%)" — and changes only the
    sentence after it. Convicting that figure is the guard judging the FORM (a
    digit in `new`) instead of the ENTITY (a figure asserted for the first time),
    and this lane deliberately does not touch the ownership data layer."""
    record = _record(reason="Allocated to Koperasi/UMKM by Perpres 49/2021 Lampiran II")
    patch = _patch(
        old="Nationally this is fully open (100%). In Bali, a PT PMA cannot register it.",
        new="Nationally this is fully open (100%). But a PT PMA cannot register it at all.",
    )
    assert check_new_percentages(record, "95291", patch) is None


def test_still_refuses_a_percentage_introduced_alongside_one_carried_over():
    """The carry-over exemption must not become a laundering channel: quoting a
    supported figure does not license a second, unsupported one in the same span."""
    record = _record(reason="Allocated to Koperasi/UMKM by Perpres 49/2021 Lampiran II")
    patch = _patch(
        old="Nationally this is fully open (100%).",
        new="Nationally this is fully open (100%), but foreigners may hold only 49%.",
    )
    with pytest.raises(CureError, match="introduces 49%"):
        check_new_percentages(record, "95291", patch)


def test_zero_percent_is_allowed_when_the_reason_states_a_closure():
    """INNOCENCE for the one number a closure legitimately produces: a card
    reading 0% on a TERTUTUP code is the record's own verdict, not an invention."""
    record = _record(reason="TERTUTUP to WNA under Kemenkes health law")
    patch = _patch(field="canonical:intel_2026.editorial.byTheNumbers[1].value",
                   old="100%", new="0%")
    assert check_new_percentages(record, "86201", patch) is None


def test_refuses_zero_percent_when_the_reason_is_only_a_cap():
    """A cap is not a closure. "klinik: max 67% WNA" cannot produce a 0% card."""
    patch = _patch(field="canonical:intel_2026.editorial.byTheNumbers[1].value",
                   old="100%", new="0%")
    with pytest.raises(CureError, match="does not support that figure"):
        check_new_percentages(_record(), "86102", patch)


# --------------------------------------------------------------------------- #
# apply_patch
# --------------------------------------------------------------------------- #

def test_applies_a_patch_that_occurs_exactly_once():
    rec = _record()
    assert apply_patch(rec, "86102", "intel_2026.whatItMeans", _patch()) is True
    assert rec["intel_2026"]["whatItMeans"] == "A foreign investor cannot register this activity."


def test_patches_a_stat_card_value():
    """The cards live IN THE DATA, not in a component — the "100%" a reader sees
    is this string, and a prose-only cure would leave it printing."""
    rec = _record()
    p = _patch(field="canonical:intel_2026.editorial.byTheNumbers[1].value",
               old="100%", new="Restricted")
    assert apply_patch(rec, "86102", "intel_2026.editorial.byTheNumbers[1].value", p) is True
    assert rec["intel_2026"]["editorial"]["byTheNumbers"][1]["value"] == "Restricted"
    assert rec["intel_2026"]["editorial"]["byTheNumbers"][0]["value"] == "TERBUKA", \
        "patching one card must not disturb its neighbour"


def test_already_applied_is_skipped_not_an_error():
    rec = _record()
    rec["intel_2026"]["whatItMeans"] = "A foreign investor cannot register this activity."
    assert apply_patch(rec, "86102", "intel_2026.whatItMeans", _patch()) is False


def test_refuses_when_old_occurs_twice():
    rec = _record()
    rec["intel_2026"]["whatItMeans"] = "closed here. closed here."
    p = _patch(old="closed here.", new="shut.")
    with pytest.raises(CureError, match="occurs 2x"):
        apply_patch(rec, "86102", "intel_2026.whatItMeans", p)


def test_refuses_when_neither_old_nor_new_is_present():
    with pytest.raises(CureError, match="occurs 0x"):
        apply_patch(_record(), "86102", "intel_2026.whatItMeans",
                    _patch(old="a sentence never in this text", new="something else"))


def test_refuses_an_empty_old():
    with pytest.raises(CureError, match="empty `old`"):
        apply_patch(_record(), "86102", "intel_2026.whatItMeans", _patch(old=""))


def test_refuses_a_field_that_does_not_exist():
    with pytest.raises(CureError, match="does not exist"):
        apply_patch(_record(), "86102", "intel_2026.whoThisIsFor", _patch())


# --------------------------------------------------------------------------- #
# check_premise — all four pins
# --------------------------------------------------------------------------- #

def test_a_record_whose_premise_still_holds_passes():
    """INNOCENCE: accepts, and reading leaves the record untouched."""
    record = _record()
    before = copy.deepcopy(record)
    assert check_premise(record, "86102", dict(PREMISE)) is None
    assert record == before, "the premise check must not mutate the record it reads"


def test_refuses_when_the_verdict_moved():
    record = _record()
    record["l4_bali"]["blocked"] = False
    with pytest.raises(CureError, match="premise moved"):
        check_premise(record, "86102", dict(PREMISE))


def test_refuses_when_the_ownership_fields_have_since_been_corrected():
    """The data-layer lane running first is the GOOD outcome — and it makes this
    prose wrong. See module docstring."""
    record = _record()
    record["pma_status"] = "TERBATAS"
    record["pma_max_asing"] = 67
    with pytest.raises(CureError, match="premise moved"):
        check_premise(record, "86102", dict(PREMISE))


def test_refuses_an_entry_that_forgot_to_pin_a_premise():
    """Fail-closed: an unpinned expectation reads as None and cannot match a real
    record, so a spec entry missing a pin is refused rather than waved through."""
    partial = {k: v for k, v in PREMISE.items() if k != "expect_pma_max_asing"}
    with pytest.raises(CureError, match="premise moved"):
        check_premise(_record(), "86102", partial)


# --------------------------------------------------------------------------- #
# The real spec — assertions about what actually ships
# --------------------------------------------------------------------------- #

def _spec() -> dict:
    if not DEFAULT_SPEC.exists():
        pytest.skip("spec not authored yet")
    return json.loads(DEFAULT_SPEC.read_text(encoding="utf-8"))


def test_the_spec_only_ever_targets_prose():
    spec = _spec()
    offenders = []
    for code, entry in spec["codes"].items():
        for p in entry["patches"]:
            try:
                split_field(code, p["field"])
            except CureError as exc:
                offenders.append((code, p["field"], str(exc)))
    assert offenders == [], f"spec writes a non-prose layer: {offenders}"


def test_every_entry_pins_all_four_premises():
    spec = _spec()
    missing = [
        c for c, e in spec["codes"].items()
        if not all(k in e for k in
                   ("expect_l4_status", "expect_l4_blocked",
                    "expect_pma_status", "expect_pma_max_asing"))
    ]
    assert missing == [], f"entries with an unpinned premise: {missing}"


def test_the_spec_records_who_graded_it_and_what_it_refused():
    """Every replacement is a new claim; an unattributed one is unverified. And a
    lane that drops codes must NAME them — a silent drop reads as coverage."""
    meta = _spec().get("_meta") or {}
    assert meta.get("graded_by"), "no _meta.graded_by — the grader must be named"
    assert meta.get("population_basis"), "no _meta.population_basis"
    assert meta.get("dropped_not_cured"), "no _meta.dropped_not_cured — name what was refused"
    assert meta.get("dropped_why"), "no _meta.dropped_why — a drop needs its reason on the record"


def test_no_replacement_reintroduces_a_bali_only_framing():
    """The disease is a nationwide restriction sold as a Bali one. A replacement
    that still scopes the restriction to Bali has not cured anything.

    The probe is checked against a positive and a negative first, because a
    pattern that convicts everything discriminates nothing: mentioning Bali is
    fine (these are Bali-facing pages), LIMITING the restriction to Bali is not.
    """
    import re
    bali_limited = re.compile(
        r"\b(?:only|just|solely)\s+in\s+Bali\b"
        r"|\bin\s+Bali\b[^.]{0,60}\b(?:but|whereas|while)\b[^.]{0,60}\b(?:elsewhere|nationally)\b"
        r"|\bnationally\s+(?:open|available)\b[^.]{0,40}\bbut\b[^.]{0,40}\bin\s+Bali\b",
        re.IGNORECASE,
    )
    assert bali_limited.search("It is nationally open but cannot be registered in Bali") is not None
    assert bali_limited.search("In Bali, as everywhere in Indonesia, this is reserved") is None

    spec = _spec()
    offenders = [
        (code, p["field"], p["new"][:120])
        for code, entry in spec["codes"].items()
        for p in entry["patches"]
        if bali_limited.search(p["new"])
    ]
    assert offenders == [], f"a replacement still frames the closure as Bali-only: {offenders}"
