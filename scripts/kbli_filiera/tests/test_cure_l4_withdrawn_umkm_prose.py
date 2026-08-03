"""Guilt + innocence for the withdrawn-UMKM prose compiler.

The compiler rewrites client-facing regulatory prose on the canonical dataset, so
the interesting behaviour is not "does it replace a string" — it is every state in
which it must REFUSE. A cure that guesses at an ambiguous record is worse than one
that stops, because the thing it guesses at is what a client reads.

Two of these tests exist because of specific scars:

  - `test_refuses_when_the_premise_moved` — the entire reason this backlog exists
    is that a verdict changed on 2026-08-03 and the prose explaining it did not.
    Prose graded against `NON_CLASSIFICABILE` must not be written onto a record
    that has since become something else (W113: a replacement is a new claim, and
    it is a claim about a premise).
  - `test_the_spec_never_re_asserts_the_withdrawn_inference` — the cure must not
    reintroduce the disease it cures. The first version of the overlay cure used
    one template for every code and would have inverted a TRUE closure; this pins
    the spec's own text against the argument being retired.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.kbli_filiera.cure_l4_withdrawn_umkm_prose import (
    CureError,
    DEFAULT_SPEC,
    apply_patch,
    check_premise,
)

WITHDRAWN_CLAIM = re.compile(
    r"no Usaha Besar scale row"
    r"|reserved for UMKM"
    r"|reserved for micro, small and medium enterprises",
    re.IGNORECASE,
)


def _record(body: str = "Alpha. The stated reason is structural. Omega.") -> dict:
    return {
        "kode_kbli_2025": "99999",
        "l4_bali": {"status": "NON_CLASSIFICABILE", "blocked": True},
        "intel_2026": {"editorial": {"body": body}},
    }


PATCH = {
    "field": "editorial.body",
    "old": "The stated reason is structural.",
    "new": "The position cannot be stated; it is treated as blocked until verified case by case.",
}


# ── the happy path, so the refusals below mean something ────────────────────────

def test_applies_when_the_old_text_occurs_exactly_once():
    rec = _record()
    assert apply_patch(rec, "99999", PATCH) is True
    body = rec["intel_2026"]["editorial"]["body"]
    assert PATCH["new"] in body
    assert PATCH["old"] not in body
    assert body.startswith("Alpha.") and body.endswith("Omega.")


def test_idempotent_when_already_applied():
    rec = _record(f"Alpha. {PATCH['new']} Omega.")
    assert apply_patch(rec, "99999", PATCH) is False


# ── guilt: every state the spec does not describe must be fatal ─────────────────

def test_refuses_when_the_old_text_occurs_twice():
    rec = _record(f"{PATCH['old']} Middle. {PATCH['old']}")
    with pytest.raises(CureError, match="exactly once"):
        apply_patch(rec, "99999", PATCH)


def test_refuses_when_neither_old_nor_new_is_present():
    rec = _record("Alpha. Something else entirely. Omega.")
    with pytest.raises(CureError, match="refusing"):
        apply_patch(rec, "99999", PATCH)


def test_refuses_a_missing_field_and_says_it_is_missing():
    """An absent field and a wrong-typed field must not share a message: a
    diagnosis that names the wrong cause sends the reader away from it (W106)."""
    rec = _record()
    with pytest.raises(CureError, match="field does not exist"):
        apply_patch(rec, "99999", {**PATCH, "field": "editorial.pullQuote"})

    typed = _record()
    typed["intel_2026"]["editorial"]["pullQuote"] = ["not", "a", "string"]
    with pytest.raises(CureError, match="holds list, not a string"):
        apply_patch(typed, "99999", {**PATCH, "field": "editorial.pullQuote"})


def test_refuses_a_missing_parent_path():
    rec = _record()
    with pytest.raises(CureError, match="does not exist \\(stopped at"):
        apply_patch(rec, "99999", {**PATCH, "field": "nosuch.body"})


def test_refuses_when_the_premise_moved():
    """The prose was graded against NON_CLASSIFICABILE. If the verdict has since
    moved, writing it would put a sentence about one world onto a record
    describing another — the exact failure this whole cure is repairing."""
    entry = {"expect_l4_status": "NON_CLASSIFICABILE", "expect_l4_blocked": True}
    moved = _record()
    moved["l4_bali"]["status"] = "CHIUSO_PMA_NO_BESAR"
    with pytest.raises(CureError, match="premise moved"):
        check_premise(moved, "99999", entry)

    unblocked = _record()
    unblocked["l4_bali"]["blocked"] = False
    with pytest.raises(CureError, match="premise moved"):
        check_premise(unblocked, "99999", entry)


# ── innocence: an unchanged premise passes, and a sibling field is untouched ────

def test_accepts_the_pinned_premise():
    """INNOCENCE for the premise check: an unmoved verdict must pass. "Does not
    raise" is asserted rather than merely relied on — a test whose whole content
    is a call reads identically to a test of nothing."""
    entry = {"expect_l4_status": "NON_CLASSIFICABILE", "expect_l4_blocked": True}
    assert check_premise(_record(), "99999", entry) is None

    # And it is the PAIR that is checked, not either half: a record matching only
    # the status, or only the flag, is still a moved premise.
    for field, value in (("status", "CHIUSO_MORATORIA_BALI"), ("blocked", False)):
        rec = _record()
        rec["l4_bali"][field] = value
        with pytest.raises(CureError):
            check_premise(rec, "99999", entry)


def test_does_not_touch_a_sibling_field():
    rec = _record()
    rec["intel_2026"]["whatYouNeed"] = PATCH["old"]
    apply_patch(rec, "99999", PATCH)
    assert rec["intel_2026"]["whatYouNeed"] == PATCH["old"], (
        "the patch reached outside its declared field"
    )


# ── the shipped spec itself ────────────────────────────────────────────────────

def _spec() -> dict:
    return json.loads(DEFAULT_SPEC.read_text(encoding="utf-8"))


def test_the_spec_is_there_and_its_population_is_pinned():
    """A suite that silently reads an empty spec reports a clean world (W84)."""
    spec = _spec()
    assert len(spec["codes"]) == 13
    assert sum(len(e["patches"]) for e in spec["codes"].values()) == 17


def test_the_spec_never_re_asserts_the_withdrawn_inference():
    offenders = [
        f"{code}.{p['field']}"
        for code, entry in _spec()["codes"].items()
        for p in entry["patches"]
        if WITHDRAWN_CLAIM.search(p["new"])
    ]
    assert offenders == [], (
        f"the cure re-asserts the very inference it retires, in {offenders}. "
        "Every `old` in this spec is guilty of that claim by construction; a `new` "
        "that repeats it makes the cure a no-op wearing a diff."
    )


def test_every_code_states_the_precautionary_block_somewhere():
    """These records are `blocked: true`. Prose that only says "we cannot state a
    position" reads, on a page whose badge says blocked, as though the block were
    a mistake. The cross-family grader caught this on 7 of 13 in round one."""
    for code, entry in _spec()["codes"].items():
        joined = " ".join(p["new"] for p in entry["patches"])
        assert "blocked until verified" in joined, (
            f"{code}: no replacement sentence says the code is still treated as blocked "
            "pending verification — a reader would conclude the opposite of the badge."
        )


def test_every_old_string_actually_carries_the_withdrawn_claim():
    """Innocence for the SELECTION: this cure is only entitled to rewrite prose
    that argues the retired inference. A spec entry whose `old` does not is a
    rewrite of something else, smuggled in on this cure's authority."""
    innocent = [
        f"{code}.{p['field']}"
        for code, entry in _spec()["codes"].items()
        for p in entry["patches"]
        if not WITHDRAWN_CLAIM.search(p["old"])
    ]
    assert innocent == [], f"spec rewrites prose that does not carry the claim: {innocent}"
