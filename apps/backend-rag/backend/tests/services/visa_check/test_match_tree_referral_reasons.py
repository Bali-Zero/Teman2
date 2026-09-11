"""Every WhatsApp referral must carry a specific, actionable explanation.

Ruled by Zero on 2026-08-28: *«ogni volta che si rimanda a whatsapp deve
esserci la spiegazione per la quale. una spiegazione precisa.»*

The rule is trivial to satisfy today and trivial to break tomorrow: a referral
branch added six months from now with a placeholder sentence would ship
silently and nobody would see it, because the funnel stays green either way.
So this file does not pin the five sentences that happen to exist right now —
it sweeps the reachable input space and asserts a *property* of every referral
it can produce.

The property is **specificity**: the explanation must quote something drawn
from this request or this catalogue — the stay length the visitor typed, the
purpose they picked, or a real IDR figure. Generic prose about forms and
15-minute calls does not qualify, however long it is.
`test_the_retired_vague_sentences_would_fail_this_gate` is the proof that the
gate has teeth: it feeds the two sentences this PR deleted through the same
checker and requires them to FAIL.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from backend.services.visa_check import match_tree
from backend.services.visa_check.catalogue import VisaType
from backend.services.visa_check.match_tree import (
    BudgetBand,
    MatchResult,
    Purpose,
    recommend_visa,
)

# An IDR figure written as "IDR 50M", "IDR 2,000,000,000" or "IDR 50".
_IDR_AMOUNT = re.compile(r"IDR\s?[\d,]+", re.IGNORECASE)

# The two sentences this PR retired. Kept verbatim so the gate can be shown to
# reject them — and so neither can quietly return.
RETIRED_VAGUE_SENTENCES = (
    "Your case has specifics we don't capture in a 4-step form. "
    "A 15-minute WhatsApp review with our visa team is faster than "
    "any guess we could make here.",
    "No visa in our catalogue matches this combination cleanly. "
    "Let's review the details on WhatsApp.",
)


def _is_specific(reason: str, *, purpose: Purpose, months: int) -> bool:
    """True when the explanation quotes a fact from this request or catalogue.

    Three accepted anchors, any one of which is enough:
      * the stay length the visitor actually entered ("12-month");
      * the human label of the purpose they picked ("tourism", "investment");
      * a concrete IDR amount ("IDR 50M", "IDR 2,000,000,000").
    """
    haystack = reason.lower()
    return (
        f"{months}-month" in haystack
        or match_tree._PURPOSE_LABEL[purpose].lower() in haystack
        or bool(_IDR_AMOUNT.search(reason))
    )


def _call(
    *, purpose: Purpose, duration_months: int, budget_band: BudgetBand
) -> MatchResult:
    return recommend_visa(
        nationality="USA",
        purpose=purpose,
        duration_months=duration_months,
        budget_band=budget_band,
    )


# --------------------------------------------------------------------------
# The gate itself
# --------------------------------------------------------------------------


def test_the_retired_vague_sentences_would_fail_this_gate() -> None:
    """Guilt half of the pair: prove the checker rejects what we removed.

    Without this, `_is_specific` could be a rubber stamp and every other test
    in the file would still pass. Note both retired sentences DO contain
    digits ("4-step", "15-minute") — a naive "has a number" check would have
    waved them straight through, which is exactly why the anchors are tied to
    the request rather than to punctuation.
    """
    for sentence in RETIRED_VAGUE_SENTENCES:
        assert not _is_specific(sentence, purpose=Purpose.OTHER, months=12), (
            "the specificity checker accepted a sentence this PR deleted for "
            f"being unspecific — the gate is not discriminating: {sentence!r}"
        )


@pytest.mark.parametrize("purpose", list(Purpose))
@pytest.mark.parametrize("months", [1, 3, 6, 7, 12, 24, 60])
@pytest.mark.parametrize("band", list(BudgetBand))
def test_every_referral_in_the_input_space_explains_itself(
    purpose: Purpose, months: int, band: BudgetBand
) -> None:
    """Innocence half: every referral the tree can reach names its own cause."""
    result = _call(purpose=purpose, duration_months=months, budget_band=band)
    if not result.referral_mode:
        return

    reason = (result.referral_reason or "").strip()
    assert reason, f"referral with no explanation at all: {purpose}/{months}m/{band}"
    assert reason not in RETIRED_VAGUE_SENTENCES, (
        f"a retired vague sentence came back for {purpose}/{months}m/{band}"
    )
    assert _is_specific(reason, purpose=purpose, months=months), (
        f"referral for {purpose.value}/{months}m/{band.value} explains nothing "
        f"specific — it quotes neither the stay length, nor the purpose, nor an "
        f"IDR figure: {reason!r}"
    )
    # Naming the blocker is only half the job — a diagnosis with no exit leaves
    # the visitor stuck. Caught live on 2026-08-28: the tourism-over-6-months
    # referral explained the 180-day cap perfectly and then simply stopped.
    assert "whatsapp" in reason.lower(), (
        f"referral for {purpose.value}/{months}m/{band.value} diagnoses the "
        f"problem but never tells the visitor where to go: {reason!r}"
    )


# --------------------------------------------------------------------------
# The two causes behind an empty ranking, which used to share one sentence
# --------------------------------------------------------------------------


def test_catalogue_gap_and_budget_wall_do_not_share_one_sentence() -> None:
    """They mean opposite things: "we don't cover this" vs "you can't afford it"."""
    gap = match_tree._explain_empty_ranking(
        Purpose.STUDENT, 12, BudgetBand.MID_50_500M
    )
    wall = match_tree._explain_empty_ranking(
        Purpose.INVESTOR, 12, BudgetBand.UNDER_50M
    )
    assert gap != wall


def test_the_empty_ranking_branch_is_actually_wired_to_the_explainer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the CALL SITE, not just the helper.

    Found by an independent verifier on 2026-08-28: with the real `VISA_META`,
    `recommend_visa`'s `if not ranking:` catch-all is unreachable — an
    instrumented sweep of 168 input combinations produced 40 referrals and
    every one came from the three early-return branches. So the parametrised
    sweep above cannot see this branch, and the two `_explain_empty_ranking`
    unit tests below call the helper directly: between them, a hardcoded vague
    string planted at the call site would have shipped green.

    Emptying the catalogue makes the branch reachable, and comparing against
    the helper's own output pins the wiring rather than the wording.
    """
    monkeypatch.setattr(match_tree, "_get_visa_meta", dict)

    result = _call(
        purpose=Purpose.STUDENT,
        duration_months=12,
        budget_band=BudgetBand.MID_50_500M,
    )

    assert result.referral_mode, "an empty catalogue must refer, not answer"
    assert result.referral_reason == match_tree._explain_empty_ranking(
        Purpose.STUDENT, 12, BudgetBand.MID_50_500M
    ), (
        "the empty-ranking branch no longer routes through _explain_empty_ranking "
        f"— it is returning something else: {result.referral_reason!r}"
    )
    assert result.referral_reason not in RETIRED_VAGUE_SENTENCES


def test_catalogue_gap_names_the_purpose_it_cannot_cover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No visa carries this purpose → say so, and say it about THIS purpose."""
    monkeypatch.setattr(match_tree, "_get_visa_meta", dict)

    reason = match_tree._explain_empty_ranking(
        Purpose.RETIREMENT, 24, BudgetBand.OVER_500M
    )

    assert "retirement" in reason.lower()
    assert "catalogue" in reason.lower()
    assert "whatsapp" in reason.lower()


def test_budget_wall_quotes_the_cheapest_minimum_the_visitor_missed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every route priced out → name the cheapest threshold, not "no match"."""
    real = match_tree._get_visa_meta()
    template = real[VisaType.E33G]
    stub = {
        VisaType.E33G: replace(
            template,
            purposes=frozenset({Purpose.STUDENT}),
            min_budget_idr=750_000_000,
        ),
    }
    monkeypatch.setattr(match_tree, "_get_visa_meta", lambda: stub)

    reason = match_tree._explain_empty_ranking(
        Purpose.STUDENT, 12, BudgetBand.MID_50_500M
    )

    assert "IDR 750,000,000" in reason, (
        "the visitor is told they cannot afford anything without being told "
        f"what the bar actually is: {reason!r}"
    )
    assert "study" in reason.lower()


# --------------------------------------------------------------------------
# Drift guards on the machinery the explanations are built from
# --------------------------------------------------------------------------


def test_every_purpose_has_a_label() -> None:
    """A purpose without a label renders "None" into a visitor-facing string."""
    missing = [p.value for p in Purpose if p not in match_tree._PURPOSE_LABEL]
    assert not missing, f"Purpose values with no human label: {missing}"


def test_covered_purposes_sentence_lists_every_rankable_purpose() -> None:
    """The OTHER referral tells the visitor what the form DOES cover.

    Derived from the enum on purpose: hardcoding the list is how that sentence
    becomes a lie the day a ninth purpose is added.
    """
    sentence = match_tree._covered_purposes_sentence()
    for purpose in Purpose:
        if purpose is Purpose.OTHER:
            continue
        assert match_tree._PURPOSE_LABEL[purpose] in sentence, (
            f"{purpose.value} is rankable but the OTHER referral does not "
            f"mention it: {sentence!r}"
        )
    assert match_tree._PURPOSE_LABEL[Purpose.OTHER] not in sentence
