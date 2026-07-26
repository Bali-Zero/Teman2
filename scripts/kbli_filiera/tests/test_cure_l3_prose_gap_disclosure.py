#!/usr/bin/env python3
"""Guilt + innocence for `cure_l3_prose_gap_disclosure.py` (superscar #3 discipline).

This compiler writes CLIENT-FACING prose on 152 published pages, so the cases that
matter are the ones where it must NOT act as much as the ones where it must.

The two that would silently un-cure production if they regressed:
  - the GOLD arm. `kbli-data.server.ts` renders the gold entry INSTEAD OF
    `intel_2026` when one exists — a total mask, not a merge — and 39 of the 152 have
    a gold body. A canonical-only cure reports 152/152 and changes nothing on the
    pages that most needed it.
  - the REWORD path. The adversarial gate rewrote this sentence on day one; without an
    anchored replacement, the next wording change stacks a second paragraph onto the
    first on every one of those pages.

Run:  python3 -m pytest scripts/kbli_filiera/tests/test_cure_l3_prose_gap_disclosure.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_FILIERA_DIR = Path(__file__).resolve().parents[1]
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

import cure_l3_prose_gap_disclosure as cure  # noqa: E402
from _l4bali_basis import DISCLOSURE_PREFIX  # noqa: E402

DISPUTED_TEXT = cure.DISCLOSURE_BY_BASIS[cure.GAP_BASIS_DISPUTED_KEY]
NO_SCOPE_TEXT = cure.DISCLOSURE_BY_BASIS[cure.GAP_BASIS_NO_OSS_SCOPE]


def _record(code: str, *, disclosed: bool = True, basis: str = "disputed_key",
            prose: str = "Body text.", marker: Any = None) -> dict[str, Any]:
    """A canonical record shaped like the real ones the selectors read."""
    rec: dict[str, Any] = {
        "kode_kbli_2025": code,
        "per_skala": [],
        "l4_bali": {
            "status": "CHIUSO_MORATORIA_BALI",
            "reason": (DISCLOSURE_PREFIX if disclosed else "") + "Bali verdict prose.",
        },
        "intel_2026": {"whatYouNeed": prose},
    }
    if basis == "disputed_key":
        rec["per_skala_disputed_pp28_collision"] = [{"skala_usaha": ["Besar"]}]
    elif basis == "no_oss_scope":
        rec["_l2_status"] = "no_oss_risk"
    if marker is not None:
        rec["intel_2026"][cure.MARKER_FIELD] = marker
    return rec


def _plan(records, gold=None):
    return cure.plan(records, gold or {}, None)


# --------------------------------------------------------------------- GUILT

def test_disclosed_record_without_the_paragraph_is_appended():
    plans, stats = _plan([_record("11111")])
    assert stats["population"] == 1
    assert plans[0]["canonical_action"] == "append"
    cure.apply_plan(plans)
    body = plans[0]["record"]["intel_2026"]["whatYouNeed"]
    assert body.count("Risk tier under review.") == 1
    assert body.startswith("Body text.")


def test_gold_entry_is_cured_too_because_it_MASKS_canonical():
    """The consumer-map finding. If this regresses, 39 published pages stay wrong
    while the census still reports full coverage."""
    rec = _record("22222")
    gold = {"22222": {"whatYouNeed": "Gold body."}}
    plans, stats = _plan([rec], gold)
    assert stats["gold_append"] == 1
    cure.apply_plan(plans)
    assert gold["22222"]["whatYouNeed"].count("Risk tier under review.") == 1
    assert isinstance(gold["22222"][cure.MARKER_FIELD], dict)


def test_each_basis_gets_the_sentence_its_evidence_supports():
    plans, _ = _plan([_record("33333", basis="disputed_key"),
                      _record("44444", basis="no_oss_scope")])
    by_code = {p["code"]: p for p in plans}
    assert by_code["33333"]["text"] == DISPUTED_TEXT
    assert by_code["44444"]["text"] == NO_SCOPE_TEXT
    # and the two really are different claims, not a shared generic sentence
    assert DISPUTED_TEXT != NO_SCOPE_TEXT


def test_reword_replaces_an_earlier_wording_instead_of_stacking():
    old = "\n\n**Risk tier under review.** Some older wording that the gate rejected."
    rec = _record("55555", prose="Body text." + old,
                  marker={"spec": cure.SPEC_ID, "basis": "disputed_key",
                          "applied_on": "2026-07-26", "sentence_sha256": "deadbeefdeadbeef"})
    plans, stats = _plan([rec])
    assert stats["canonical_reword"] == 1
    cure.apply_plan(plans)
    body = rec["intel_2026"]["whatYouNeed"]
    assert body.count("Risk tier under review.") == 1, "a reword must replace, never stack"
    assert "older wording that the gate rejected" not in body
    assert body.endswith(DISPUTED_TEXT.strip())


def test_unknown_basis_refuses_instead_of_guessing():
    with pytest.raises(cure.CureError):
        cure.sentence_for("some_basis_nobody_defined")


# ------------------------------------------------------------------ INNOCENCE

def test_a_record_the_field_cure_never_disclosed_is_left_alone():
    """Membership is structural. A record whose prose is FULL of risk-tier talk but
    whose verdict was never flagged is not this cure's business — selecting on the
    prose is the family-#3 trap this whole lane exists to avoid."""
    rec = _record("66666", disclosed=False,
                  prose="Bali classifies it as medium-high to high risk. Its OSS risk class is high.")
    plans, stats = _plan([rec])
    assert plans == []
    assert stats["population"] == 0
    assert "Risk tier under review." not in rec["intel_2026"]["whatYouNeed"]


def test_rerun_with_the_same_wording_is_a_no_op():
    rec = _record("77777")
    plans, _ = _plan([rec])
    cure.apply_plan(plans)
    first = rec["intel_2026"]["whatYouNeed"]

    plans2, stats2 = _plan([rec])
    assert stats2["canonical_already_disclosed"] == 1
    assert plans2[0]["canonical_action"] == "already_disclosed"
    cure.apply_plan(plans2)
    assert rec["intel_2026"]["whatYouNeed"] == first


def test_a_body_hand_touched_after_the_append_is_reported_not_reshaped():
    """The anchor is end-of-string on purpose. If someone edited the page after the
    cure ran, the paragraph is no longer last and this tool must not guess where it
    ended — same rule as `cure_l4bali_disclosure.LEGACY_SUFFIX_RE`."""
    body = ("Body text."
            "\n\n**Risk tier under review.** An older wording."
            "\n\nA human added this paragraph afterwards.")
    rec = _record("88888", prose=body,
                  marker={"spec": cure.SPEC_ID, "basis": "disputed_key",
                          "applied_on": "2026-07-26", "sentence_sha256": "deadbeefdeadbeef"})
    plans, stats = _plan([rec])
    assert stats["canonical_wording_drift_unanchored"] == 1
    cure.apply_plan(plans)
    assert rec["intel_2026"]["whatYouNeed"] == body, "an unanchored body must be untouched"


def test_a_record_with_no_prose_is_reported_never_invented():
    rec = _record("99999", prose="")
    plans, stats = _plan([rec])
    assert stats["canonical_missing_prose"] == 1
    cure.apply_plan(plans)
    assert rec["intel_2026"]["whatYouNeed"] == ""


def test_a_lot_compiler_rewriting_the_body_does_not_destroy_the_disclosure():
    """THE INTERACTION. `intel_2026.whatYouNeed` has two writers.

    The lot compilers own the BODY and their contract is "equals the spec text
    verbatim"; this cure APPENDS. Measured before the shared rule existed, the lot-2
    compiler reported `42999: intel_2026.whatYouNeed -> honest-gap` after this cure
    ran — its next apply would have rewritten the body back to the spec text and
    deleted the disclosure, silently, on a page that needs it. A cure reverting a cure.

    Both writers now read `_prose_disclosure`, so a body rewrite carries the appendix
    across. This asserts the property directly rather than trusting that both modules
    happen to agree.
    """
    from _prose_disclosure import reattach, split_disclosure

    rec = _record("12121", prose="Spec honest-gap text.")
    plans, _ = _plan([rec])
    cure.apply_plan(plans)
    after_append = rec["intel_2026"]["whatYouNeed"]

    # what a lot compiler does: compare, then write, its own half
    base, appendix = split_disclosure(after_append)
    assert base == "Spec honest-gap text.", "the lot compiler must see its own text unchanged"
    assert appendix, "the appendix must be separable, not fused into the body"

    rewritten = reattach("A NEWER spec honest-gap text.", appendix)
    rec["intel_2026"]["whatYouNeed"] = rewritten
    assert rewritten.startswith("A NEWER spec honest-gap text.")
    assert rewritten.count("Risk tier under review.") == 1, "the disclosure must survive"

    # …and this cure still reads the rewritten body as already disclosed
    plans2, stats2 = _plan([rec])
    assert stats2["canonical_already_disclosed"] == 1


def test_the_sentence_never_asserts_what_the_regulator_published():
    """F12. Every variant speaks about OUR retrieval; none claims the regulator has
    not published something, and none names an internal field at the reader."""
    for text in cure.DISCLOSURE_BY_BASIS.values():
        low = text.lower()
        for forbidden in ("not published", "does not exist", "no licensing exists",
                          "per_skala", "_l2_status", "kategori_risiko", "l4_bali"):
            assert forbidden not in low, f"{forbidden!r} leaked into client prose: {text}"
        assert "oss.go.id" in low, "the reader must be pointed at the authority"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
