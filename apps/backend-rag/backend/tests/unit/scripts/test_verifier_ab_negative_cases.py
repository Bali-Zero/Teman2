"""The A/B harness must be able to SEE a false accept.

Born 2026-08-09 from adversarial review (Codex) of the LLM cost/quality lane.
Every curated triple is a vetted answer checked against itself — a positive —
so a harness built only from them can observe disagreement and false rejects
and never the one error that matters: a corrupted draft the candidate model
waves through. The stated decision rule ("switch only if zero false accepts")
was therefore untestable by the very harness meant to test it.

Two traps this file exists to catch:

* a "corrupted" draft that is in fact still faithful (a negative that is
  secretly a positive silently inflates every model's safety score);
* a scorer that averages the two error types together, hiding an accept
  behind a pile of correct rejects.
"""

import pytest

from scripts.verifier_model_ab import (
    SYNTHETIC_TRIPLES,
    build_labelled_cases,
    corrupt_number,
    corrupt_with_invented_requirement,
    score_against_truth,
)

# ── corruption actually corrupts ────────────────────────────────────────────


def test_number_corruption_changes_the_answer():
    """GUILT: the whole point is a draft that contradicts its own context."""
    answer = "The minimum paid-up capital for a PT PMA is IDR 2.5 billion."
    corrupted = corrupt_number(answer)
    assert corrupted is not None
    assert corrupted != answer


def test_number_corruption_declines_when_there_is_no_number():
    """INNOCENCE — the load-bearing one.

    An answer with no figure cannot be made unfaithful by changing a figure.
    Returning the text unchanged would mint a "negative" the verifier is RIGHT
    to accept, and every model would then look like it had false accepts.
    """
    assert corrupt_number("A valid KITAS is generally accepted by Indonesian banks.") is None
    assert corrupt_number("") is None


@pytest.mark.parametrize(
    "answer",
    [
        "The filings are: (1) LKPM quarterly, (2) SPT annually.",
        "Step 3 is submitting the form.",
        "See section 2 below.",
    ],
)
def test_number_corruption_ignores_enumerators_and_bare_ordinals(answer):
    """INNOCENCE, learned the hard way (2026-08-09).

    The first version mutated ANY digit, so on a real curated answer it turned
    "(1) LKPM" into "(7) LKPM" — a list label, not a fact. The verifier scored
    it 0.95 and called it "a minor numbering typo", which is correct; the
    harness recorded that correct behaviour as a false accept and would have
    convicted the incumbent on it. A number only counts when changing it
    changes a claim.
    """
    assert corrupt_number(answer) is None


@pytest.mark.parametrize(
    "answer",
    [
        "The minimum paid-up capital is IDR 2.5 billion.",
        "Semester I is due 15 July each year.",
        "The permit is valid for 5 years.",
        "A withholding rate of 20% applies.",
    ],
)
def test_number_corruption_fires_on_figures_that_carry_meaning(answer):
    """GUILT: currency, date, duration and rate must still be corruptible —
    these ARE the hallucinations that reach a client."""
    corrupted = corrupt_number(answer)
    assert corrupted is not None and corrupted != answer


def test_invented_requirement_adds_a_claim_absent_from_context():
    answer = "The visa is valid for five years."
    corrupted = corrupt_with_invented_requirement(answer)
    assert corrupted.startswith(answer)
    assert len(corrupted) > len(answer)


def test_corruption_output_is_pinned_not_merely_stable():
    """A rerun must be comparable to the run before it: no RNG, no clock.

    Pinned to the exact expected string rather than asserting
    ``f(x) == f(x)`` — that shape catches randomness but nothing else, and
    reads as a tautology to the anti-reward-hacking linter (rightly). The
    literal also documents what a corruption looks like.
    """
    assert (
        corrupt_number("The minimum paid-up capital is IDR 2.5 billion.")
        == "The minimum paid-up capital is IDR 7.5 billion."
    )
    corrupted = corrupt_with_invented_requirement(SYNTHETIC_TRIPLES[0][1])
    assert "Ministerial Regulation 41/2023" in corrupted


# ── the case set ────────────────────────────────────────────────────────────


def test_every_negative_draft_differs_from_its_own_context():
    """The context stays the VETTED answer, so a negative is a contradiction
    by construction — but only if the draft actually changed."""
    cases = build_labelled_cases(4)
    negatives = [c for c in cases if not c[3]]
    assert negatives, "no negative cases were built"
    for _query, draft, context, _should_accept, kind in negatives:
        assert draft not in context, kind


def test_faithful_cases_are_still_present_and_unmodified():
    """INNOCENCE: adding negatives must not disturb the positives — false
    REJECT rate is measured on them."""
    cases = build_labelled_cases(4)
    faithful = [c for c in cases if c[3]]
    assert len(faithful) == 4
    for _query, draft, context, _should_accept, kind in faithful:
        assert kind == "faithful"
        assert draft in context


# ── the scorer keeps the two errors apart ───────────────────────────────────


def _case(should_accept: bool, kind: str = "k"):
    return ("q", "draft", ["ctx"], should_accept, kind)


def test_accepting_a_corrupted_draft_is_a_false_accept():
    """GUILT: the decisive failure must be counted, and named by kind."""
    result = score_against_truth([_case(False, "wrong-number")], [True])
    assert result["false_accept"] == ["wrong-number"]
    assert result["false_reject"] == 0


def test_rejecting_a_faithful_draft_is_only_a_false_reject():
    """INNOCENCE: a cautious model costs a rewrite — it must NEVER be reported
    in the same bucket as one that ships an unfaithful answer."""
    result = score_against_truth([_case(True)], [False])
    assert result["false_accept"] == []
    assert result["false_reject"] == 1


@pytest.mark.parametrize(("should_accept", "verdict"), [(True, True), (False, False)])
def test_correct_verdicts_are_not_errors(should_accept, verdict):
    result = score_against_truth([_case(should_accept)], [verdict])
    assert result["false_accept"] == []
    assert result["false_reject"] == 0
    assert result["graded"] == 1


def test_unavailable_verdicts_are_not_graded_as_correct():
    """A degraded call is an absence of evidence, not evidence of safety —
    counting it as a pass is how a fully-broken run reports zero false accepts.
    """
    result = score_against_truth([_case(False), _case(True)], [None, None])
    assert result == {"graded": 0, "false_accept": [], "false_reject": 0}
