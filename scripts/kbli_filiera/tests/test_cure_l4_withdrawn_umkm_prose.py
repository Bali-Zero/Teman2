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

# The ENTITLEMENT pattern, and it is deliberately wider than the one above.
#
# The pattern above is the shipped corpus guard's (test_withdrawn_umkm_inference_absent.py):
# narrow on purpose, because it ratchets over 1,559 records and a false positive there
# accuses the corpus of telling the truth. It is the WRONG predicate for asking "was this
# cure entitled to rewrite this string", because the sentences a wide per-record sweep
# turns up are, by construction, the ones the narrow pattern cannot see — "A PT PMA is
# legally an Usaha Besar, so it cannot register this KBLI anywhere in Indonesia" argues
# the withdrawn inference and matches none of the three phrases above.
#
# What this is NOT: a corpus detector. It certifies that the strings THIS spec rewrites
# carry the retired reasoning; it makes no claim to catch a future wording, and widening
# it from the instances in hand cannot (W113). Innocence is asserted below so it cannot
# grow into something that convicts the legitimate annex closure.
WITHDRAWN_REASONING = re.compile(
    r"no Usaha Besar scale row"
    r"|reserved for UMKM"
    r"|reserved for micro, small and medium enterprises"
    r"|reserved for local micro"
    r"|(?:is|as)\s+(?:legally\s+|by law\s+)?(?:an?\s+)?Usaha Besar"
    r"|treated (?:by law )?as \*{0,2}(?:an )?Usaha Besar"
    r"|by law, a large-scale \(Besar\) entity"
    r"|no Besar scale"
    r"|carry a Besar scale"
    r"|absence of an Usaha Besar"
    r"|no large-enterprise \(Besar\) scale"
    r"|only provides it for UMKM"
    r"|larger-business row"
    r"|not at the large-business scale"
    r"|intended for micro and small enterprises"
    r"|Indonesian-owned \(UMKM\) operator",
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


def test_reaches_a_string_inside_a_list_and_leaves_its_siblings_alone():
    """The stat cards live in a list. Reaching them is the only reason indexed
    paths exist, so the happy path is asserted with the neighbours named: an
    off-by-one here would rewrite a different card and still look like a success."""
    rec = _record()
    rec["intel_2026"]["editorial"]["byTheNumbers"] = [
        {"label": "National ceiling", "value": "100%"},
        {"label": "Bali status", "value": PATCH["old"]},
        {"label": "Open scales", "value": "Mikro, Kecil, Menengah"},
    ]
    patch = {**PATCH, "field": "editorial.byTheNumbers[1].value"}
    assert apply_patch(rec, "99999", patch) is True
    cards = rec["intel_2026"]["editorial"]["byTheNumbers"]
    assert cards[1]["value"] == PATCH["new"]
    assert cards[0]["value"] == "100%"
    assert cards[2]["value"] == "Mikro, Kecil, Menengah"
    assert cards[1]["label"] == "Bali status", "the patch reached a sibling key"


def test_refuses_an_index_past_the_end_of_the_list():
    """The position of a card is NOT stable across records — one of the thirteen
    carries no Bali-status card at all. If the list shrank, writing to whatever
    now sits nearby is worse than stopping."""
    rec = _record()
    rec["intel_2026"]["editorial"]["byTheNumbers"] = [{"value": PATCH["old"]}]
    with pytest.raises(CureError, match="out of range"):
        apply_patch(rec, "99999", {**PATCH, "field": "editorial.byTheNumbers[3].value"})


def test_refuses_an_index_applied_to_something_that_is_not_a_list():
    rec = _record()
    with pytest.raises(CureError, match="not a list"):
        apply_patch(rec, "99999", {**PATCH, "field": "editorial[0].body"})


def test_an_unindexed_path_still_resolves_the_plain_key():
    """INNOCENCE for the index parser: adding `name[i]` support must not change
    how `name` behaves. A field whose name merely CONTAINS a digit is not an
    index, and the twelve dotted paths in the shipped spec are unindexed."""
    rec = _record()
    rec["intel_2026"]["editorial"]["body2"] = PATCH["old"]
    assert apply_patch(rec, "99999", {**PATCH, "field": "editorial.body2"}) is True
    assert rec["intel_2026"]["editorial"]["body2"] == PATCH["new"]
    assert rec["intel_2026"]["editorial"]["body"] == _record()["intel_2026"]["editorial"]["body"]


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
    assert len(spec["codes"]) == 26  # 13 NON_CLASSIFICABILE + 13 CHIUSO_MORATORIA_BALI
    assert sum(len(e["patches"]) for e in spec["codes"].values()) == 75


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


# What each badge obliges the prose to say. Every record here is `blocked: true`,
# but they are blocked for different reasons and the honest sentence differs:
# NON_CLASSIFICABILE means "we hold no verified rows, so we treat it as blocked
# until someone checks", while CHIUSO_MORATORIA_BALI is a settled provincial
# block. Asserting the precautionary wording on a moratorium code would UNDERSTATE
# a real block; asserting the moratorium on a NON_CLASSIFICABILE code would invent
# a cause. One test, keyed on the status the spec pinned.
BADGE_OBLIGATION = {
    "NON_CLASSIFICABILE": "blocked until verified",
    "CHIUSO_MORATORIA_BALI": "moratorium",
}


def test_every_code_states_its_own_kind_of_block_somewhere():
    """These records are `blocked: true`. Prose that leaves the block unstated —
    or states the wrong kind — reads, on a page whose badge says blocked, as
    though the block were a mistake. The cross-family grader caught the first
    shape on 7 of 13 in batch one; the second is why this is keyed on status."""
    for code, entry in _spec()["codes"].items():
        status = entry["expect_l4_status"]
        assert status in BADGE_OBLIGATION, (
            f"{code} pins status {status!r}, which no obligation is defined for. Add one "
            "deliberately: a status with no obligation passes this test by default."
        )
        joined = " ".join(p["new"] for p in entry["patches"]).lower()
        needle = BADGE_OBLIGATION[status]
        assert needle in joined, (
            f"{code} ({status}): no replacement sentence carries {needle!r}, so a reader "
            "would conclude something other than what the badge on the same page says."
        )


def test_every_old_string_actually_carries_the_withdrawn_reasoning():
    """Innocence for the SELECTION: this cure is only entitled to rewrite prose
    that argues the retired inference. A spec entry whose `old` does not is a
    rewrite of something else, smuggled in on this cure's authority."""
    innocent = [
        f"{code}.{p['field']}"
        for code, entry in _spec()["codes"].items()
        for p in entry["patches"]
        if not WITHDRAWN_REASONING.search(p["old"])
    ]
    assert innocent == [], f"spec rewrites prose that does not carry the reasoning: {innocent}"


@pytest.mark.parametrize(
    "sentence",
    [
        # The one closure that survives the withdrawal must stay sayable, or the
        # cheapest way to satisfy this file is to delete the true closures too.
        "Allocated to Koperasi/UMKM by Perpres 49/2021 Lampiran II (dialokasikan column): "
        "a PT PMA cannot take this bidang usaha.",
        "Reserved to Koperasi/UMKM only as to a NAMED sub-activity per Pasal 5(5).",
        "Nationally this KBLI is TERTUTUP: 0% foreign ownership, so a PT PMA cannot register "
        "it anywhere in Indonesia — Bali included.",
        "Blocked in Bali by the provincial PMA moratorium, independent of national opening.",
        # Descriptive statements of the licensing annex's own scale rows. These are
        # grounded in `per_skala` and were deliberately LEFT in the corpus; a pattern
        # that convicted them would be demanding the cure delete true data.
        "The activity is open to micro and small enterprises.",
        "The registration scales named for the activity are Micro, Small and Medium.",
    ],
)
def test_the_entitlement_pattern_does_not_convict_legitimate_prose(sentence: str):
    assert WITHDRAWN_REASONING.search(sentence) is None
