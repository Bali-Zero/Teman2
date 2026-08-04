"""Guilt + innocence for the unverifiable-tier prose compiler.

This cure DELETES client-facing sentences, which makes its refusals the
interesting behaviour rather than its writes. Three of these tests exist because
of a specific defect rather than for coverage:

  - `test_the_sibling_engine_is_imported_once` — `scripts/kbli_filiera/` is on
    sys.path in script mode, so the sibling engine can be loaded as BOTH
    `cure_l4_withdrawn_umkm_prose` and
    `scripts.kbli_filiera.cure_l4_withdrawn_umkm_prose`: two module objects from
    one file, two distinct `CureError` classes. Measured before this file
    existed: `A is B` was False. A refusal raised through one and caught through
    the other escapes `main`'s `except` and surfaces as a traceback instead of
    the exit-1 a caller reads.

  - `test_refuses_to_delete_the_disclosure_paragraph` — the whole point of this
    cure is that an earlier wave APPENDED an honest disclosure and left the claim
    standing. A spec entry that swallowed that paragraph into its `old` would
    delete the cure while reporting that it deleted the disease, and the page
    would go back to asserting a tier with nothing to qualify it.

  - `test_refuses_when_the_disclosure_marker_is_gone` — the replacement text says
    the tier cannot be verified. If the disclosure lane's marker has since been
    re-derived away, that statement is no longer supported, and writing it would
    be W113 one floor down: a correction that outlives the thing it corrected.
"""

from __future__ import annotations

import copy
import json

import pytest

from scripts.kbli_filiera import cure_l4_withdrawn_umkm_prose as sibling
from scripts.kbli_filiera import cure_prose_unverifiable_tier as cure
from scripts.kbli_filiera.cure_prose_unverifiable_tier import (
    CureError,
    DEFAULT_SPEC,
    apply_patch,
    check_disclosure_marker,
    check_premise,
)

MARKER = {"spec": "l3_prose_gap_disclosure_2026_07_26", "sentence_sha256": "sha256:deadbeef"}

ASSERTING = (
    "In Bali, it is not blocked by the general moratorium but falls under a medium-high to "
    "high risk classification, so registration will depend on the specific location."
    "\n\n**Risk tier under review.** No KBLI-2025 risk scope for this code could be retrieved "
    "from the OSS API when this dataset was built."
)
HONEST = (
    "In Bali, it is not blocked by the general moratorium. Indonesia's OSS portal publishes no "
    "risk classification we can verify for this code, so the tier — and any requirement that "
    "would follow from it — cannot be stated here."
)


def _container(prose: str = ASSERTING) -> dict:
    return {"whatYouNeed": prose, cure.MARKER_FIELD: dict(MARKER)}


def _patch(**kw) -> dict:
    base = {
        "surface": "canonical",
        "field": "whatYouNeed",
        "old": "but falls under a medium-high to high risk classification, so registration will "
               "depend on the specific location.",
        "new": "and the risk tier cannot be verified from our sources.",
        "why": "removes a tier the record declares unverifiable",
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
# Guilt — it does the work
# --------------------------------------------------------------------------- #

def test_applies_a_patch_that_occurs_exactly_once():
    c = _container()
    assert apply_patch(c, "85581", _patch()) is True
    assert "medium-high to high risk classification" not in c["whatYouNeed"]
    assert "cannot be verified from our sources" in c["whatYouNeed"]


def test_the_disclosure_paragraph_survives_the_patch():
    """The claim goes; the qualification stays. Deleting both would leave the
    page silent about the gap it has."""
    c = _container()
    apply_patch(c, "85581", _patch())
    assert cure.DISCLOSURE_OPENER in c["whatYouNeed"]


def test_patches_the_gold_surface_too():
    """Gold MASKS canonical on the rendered page, so a canonical-only cure changes
    nothing a reader sees on the codes that have gold prose."""
    c = _container()
    assert apply_patch(c, "85581", _patch(surface="gold")) is True
    assert "medium-high to high risk classification" not in c["whatYouNeed"]


# --------------------------------------------------------------------------- #
# Innocence — it does not fire on the legitimate neighbours
# --------------------------------------------------------------------------- #

def test_already_applied_is_skipped_not_an_error():
    c = _container(HONEST + "\n\n" + cure.DISCLOSURE_OPENER + " ...")
    p = _patch(new="risk tier cannot be verified")
    c["whatYouNeed"] = "x risk tier cannot be verified y"
    assert apply_patch(c, "85581", p) is False


def test_a_record_whose_premise_still_holds_passes():
    """INNOCENCE. The subject is "accepts and changes nothing" — asserted rather
    than left to the absence of an exception, so the test states what it checks."""
    record = {"l4_bali": {"status": "OK_or_HIGHER_RISK", "blocked": False}}
    before = copy.deepcopy(record)
    assert check_premise(record, "85581", {"expect_l4_status": "OK_or_HIGHER_RISK",
                                           "expect_l4_blocked": False}) is None
    assert record == before, "the premise check must not mutate the record it reads"


def test_a_surface_that_still_carries_the_marker_passes():
    """INNOCENCE, same shape: a surface that still carries the disclosure marker is
    accepted, and reading it leaves it untouched."""
    container = _container()
    before = copy.deepcopy(container)
    assert check_disclosure_marker(container, "85581", "canonical") is None
    assert container == before, "the marker check must not mutate the surface it reads"


# --------------------------------------------------------------------------- #
# Refusals — every state the spec does not describe
# --------------------------------------------------------------------------- #

def test_refuses_to_delete_the_disclosure_paragraph():
    c = _container()
    bad = _patch(old="**Risk tier under review.** No KBLI-2025 risk scope for this code could "
                     "be retrieved from the OSS API when this dataset was built.",
                 new="")
    with pytest.raises(CureError, match="disclosure paragraph"):
        apply_patch(c, "85581", bad)


def test_refuses_when_old_occurs_twice():
    c = _container("the tier is high. the tier is high." + "\n\n" + cure.DISCLOSURE_OPENER)
    with pytest.raises(CureError, match="occurs 2x"):
        apply_patch(c, "85581", _patch(old="the tier is high.", new="the tier is unverified."))


def test_refuses_when_neither_old_nor_new_is_present():
    c = _container()
    with pytest.raises(CureError, match="occurs 0x"):
        apply_patch(c, "85581", _patch(old="a sentence never in this text", new="something else"))


def test_refuses_an_empty_old():
    c = _container()
    with pytest.raises(CureError, match="empty `old`"):
        apply_patch(c, "85581", _patch(old="", new="anything"))


@pytest.mark.parametrize("root", sorted(cure.FORBIDDEN_ROOTS))
def test_refuses_to_write_the_verdict_or_the_government_data(root: str):
    """Prose only. Restating a settled verdict is how a correction becomes a new
    claim, and `per_skala`/`pma_status` are government data this cure never owns."""
    c = {root: "whatever", cure.MARKER_FIELD: dict(MARKER)}
    with pytest.raises(CureError, match="verdict/government layer"):
        apply_patch(c, "85581", _patch(field=root))


def test_refuses_when_the_premise_moved():
    record = {"l4_bali": {"status": "CHIUSO_MORATORIA_BALI", "blocked": True}}
    with pytest.raises(CureError, match="premise moved"):
        check_premise(record, "85581", {"expect_l4_status": "OK_or_HIGHER_RISK",
                                        "expect_l4_blocked": False})


def test_refuses_when_the_disclosure_marker_is_gone():
    c = {"whatYouNeed": ASSERTING}
    with pytest.raises(CureError, match="no longer carries"):
        check_disclosure_marker(c, "85581", "canonical")


# --------------------------------------------------------------------------- #
# The real spec — assertions about what actually ships
# --------------------------------------------------------------------------- #

def _spec() -> dict:
    if not DEFAULT_SPEC.exists():
        pytest.skip("spec not authored yet")
    return json.loads(DEFAULT_SPEC.read_text(encoding="utf-8"))


def test_the_spec_never_targets_the_verdict_or_government_data():
    spec = _spec()
    offenders = [
        (code, p["field"])
        for code, entry in spec["codes"].items()
        for p in entry["patches"]
        if p["field"].split(".")[0].split("[")[0] in cure.FORBIDDEN_ROOTS
    ]
    assert offenders == [], f"spec writes a non-prose layer: {offenders}"


def test_no_replacement_asserts_a_risk_tier():
    """The disease is asserting a tier that cannot be verified. A cure that names
    a tier in its replacement has the disease it treats — and a SOFTENED tier is
    still a tier (W113: a weakened claim is still a claim)."""
    import re

    tier = re.compile(
        r"\b(low|medium|medium[- ]high|medium[- ]to[- ]high|high)\b[^.]{0,40}\brisk\b"
        r"|\brisk\b[^.]{0,40}\b(low|medium|high)\b",
        re.IGNORECASE,
    )
    # "risk classification cannot be verified" is the point of the cure, so the
    # probe must not convict it: it names no tier.
    assert tier.search("the risk classification cannot be verified for this code") is None
    assert tier.search("it falls under a medium-high risk classification") is not None

    spec = _spec()
    offenders = [
        (code, p["field"], p["new"][:120])
        for code, entry in spec["codes"].items()
        for p in entry["patches"]
        if tier.search(p["new"])
    ]
    assert offenders == [], f"a replacement names a risk tier: {offenders}"


def test_every_entry_pins_the_premise_it_was_graded_against():
    spec = _spec()
    missing = [c for c, e in spec["codes"].items()
               if "expect_l4_status" not in e or "expect_l4_blocked" not in e]
    assert missing == [], f"entries with no pinned premise: {missing}"


def test_the_spec_records_who_graded_it():
    """Every replacement is a new claim. An unattributed one is an unverified one."""
    spec = _spec()
    meta = spec.get("_meta") or {}
    assert meta.get("graded_by"), "no _meta.graded_by — the grader must be named"
    assert meta.get("population_basis"), "no _meta.population_basis — membership must be stated"
