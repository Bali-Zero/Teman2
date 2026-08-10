"""Guilt + innocence corpus for `clean_response`.

Measured defect (2026-08-10): every monologue filter ran with `re.MULTILINE`,
so `^`-anchored "strip the leading preamble" rules matched at every line start
and deleted lines out of the middle of correct answers. 20 of the 22 fragments
in `LEGITIMATE_ANSWER_FRAGMENTS` below were altered by the pre-cure code and 15
were emptied outright.

The asymmetry that governs this file: a false negative leaks filler, a false
positive deletes advice from an answer that already passed retrieval AND the
abstain gate — and on WhatsApp `wa_inbox_bot` turns an emptied answer into
silence. Innocence therefore comes first here, and guilt exists to stop the
cure from being a blanket "filter nothing".
"""

import re

import pytest

from backend.services.response.cleaner import (
    _ANYWHERE_RE,
    _MARKER_RE,
    _PREAMBLE_RE,
    clean_response,
)

# ---------------------------------------------------------------------------
# INNOCENCE — things a Bali Zero consultant legitimately writes
# ---------------------------------------------------------------------------

LEGITIMATE_ANSWER_FRAGMENTS = [
    # The three that the dropped `^The (power|importance|interplay) of` ate.
    "The power of attorney must be notarised before submission.",
    "The importance of the LKPM deadline cannot be overstated: it is quarterly.",
    "The interplay of BKPM and OSS rules determines the licence path.",
    # Narrowed patterns.
    "Perhaps the most common case is a PT PMA with a single foreign shareholder.",
    "What are we required to file for the SPT Tahunan?",
    "What is the difference between a KITAS and a KITAP?",
    "Let me check: the E33G is valid for 5 years.",
    "The search results confirm the 2026 rate is 11%.",
    "Without any prior context, I would still advise filing before 31 March.",
    "IMPORTANT: the LKPM must be filed quarterly.",
    "CRITICAL: your KITAS expires in 14 days.",
    # An imperative alone does not make a line a system-prompt leak: client
    # warnings are imperative too, and are the whole point of the channel.
    "IMPORTANT: Always carry your KITAS with you.",
    "CRITICAL: Never leave Indonesia without the exit permit.",
    "IMPORTANT: Use form SPT 1770 for personal income.",
    # Dropped patterns.
    "Scenario 1: you already hold a KITAS. Scenario 2: you do not.",
    "Possible Next Steps: 1) collect the akta, 2) file the LKPM.",
    "Provide me with some context about your visa and I can advise.",
    # Anchoring: these were eaten mid-sentence by unanchored stub patterns.
    "Waiting for your passport scan, we can start the application.",
    "No new query is needed - the NIB already covers this KBLI.",
    # Untouched by the cure, pinned so a future widening is caught.
    "Okay. Based on the official documents, the paid-up capital is IDR 2.5 billion.",
    "Humans are remarkably patient with Indonesian bureaucracy, but the deadline is fixed.",
    "I need to answer based on the akta you sent - page 2 lists the directors.",
    "The company must appoint at least one director and one commissioner.",
    "Your NIB already covers KBLI 68111, so no new registration is needed.",
]


@pytest.mark.parametrize("fragment", LEGITIMATE_ANSWER_FRAGMENTS)
def test_a_standalone_legitimate_answer_is_not_emptied(fragment: str) -> None:
    """The measured harm: a one-sentence correct answer cleaned to "".

    Emptying is the only outcome that reaches the client as silence, so it is
    asserted separately from the stricter identity check below.
    """
    assert clean_response(fragment).strip(), f"cleaner emptied a legitimate answer: {fragment!r}"


@pytest.mark.parametrize("fragment", LEGITIMATE_ANSWER_FRAGMENTS)
def test_a_legitimate_line_inside_an_answer_body_survives_verbatim(fragment: str) -> None:
    """MULTILINE is the disease: a preamble rule must never reach line 2.

    This is the sweep that covers every pattern at once — whatever a future
    `^`-anchored rule matches, it may only match the top of the response.
    """
    body = f"Here is the answer for your PT PMA:\n{fragment}\nContact us to proceed."
    cleaned = clean_response(body)
    assert fragment in cleaned, f"line eaten out of the answer body: {fragment!r} -> {cleaned!r}"
    assert "Contact us to proceed." in cleaned


@pytest.mark.parametrize("fragment", LEGITIMATE_ANSWER_FRAGMENTS)
def test_a_legitimate_opening_sentence_survives_when_more_answer_follows(fragment: str) -> None:
    """The only construction that can actually catch a WIDENED preamble rule.

    Mutation-measured: widening `^Perhaps I (should|...)` back to
    `^Perhaps (the|I|we)` killed ZERO tests, and so did three other widenings.
    Both other innocence families are structurally blind to it —
    `..._is_not_emptied` because the never-empty net restores a fragment the
    filters consumed whole, and `..._inside_an_answer_body_...` because
    start-of-string anchoring already stops a preamble rule from reaching
    line 2. Put the fragment FIRST with a second sentence behind it and the
    deletion is both reachable and visible.
    """
    answer = f"{fragment} The paid-up capital requirement is IDR 2.5 billion."
    cleaned = clean_response(answer)
    assert fragment in cleaned, f"opening sentence deleted: {fragment!r} -> {cleaned!r}"


def test_a_numbered_multi_paragraph_answer_is_untouched() -> None:
    answer = (
        "PT PMA timeline:\n\n"
        "1. Notarial deed (akta pendirian) - 3 working days.\n"
        "2. SK Kemenkumham approval - 2 working days.\n"
        "3. NIB via OSS - same day.\n\n"
        "The paid-up capital requirement is IDR 2.5 billion per BKPM 5/2025."
    )
    assert clean_response(answer) == answer


# ---------------------------------------------------------------------------
# GUILT — monologue that must still be stripped
# ---------------------------------------------------------------------------

MONOLOGUE_CASES = [
    ("THOUGHT: I should search the KB.\nThe answer is 11%.", "THOUGHT:"),
    ("Thought : let me think.\nThe answer is 11%.", "Thought"),
    ("Observation: no results found.\nThe answer is 11%.", "Observation:"),
    ("Next thought: ask the user.\nThe answer is 11%.", "Next thought:"),
    ("ACTION: vector_search(query='kbli')\nThe code is 68111.", "ACTION:"),
    ("ACTION: No tool call needed here.\nThe code is 68111.", "No tool call needed"),
    ("vector_search(query='kitas')\nThe code is 68111.", "vector_search("),
    ("User Query: what is the LKPM deadline?\nIt is quarterly.", "User Query:"),
    ("Zantara has provided the final answer. The fee is IDR 12,000,000.", "provided the final"),
    ("(No further action needed at this stage) The fee is IDR 12,000,000.", "No further action"),
    ("Final Answer: IDR 12,000,000.", "Final Answer:"),
    ("FINAL ANSWER: IDR 12,000,000.", "FINAL ANSWER:"),
    (
        "CRITICAL: You must never invent a price.\nThe fee is IDR 12,000,000.",
        "You must never invent",
    ),
    (
        "IMPORTANT: Always cite the regulation.\nThe fee is IDR 12,000,000.",
        "Always cite the regulation",
    ),
    (
        "Okay, since there is no prior observation, I will offer a general thought. "
        "The fee is IDR 12,000,000.",
        "no prior observation",
    ),
    ("What should I do next? The fee is IDR 12,000,000.", "What should I do next"),
    ("Perhaps I should search the knowledge base. The fee is IDR 12,000,000.", "Perhaps I should"),
    (
        "In the absence of an observation I will generalise. The fee is IDR 12,000,000.",
        "In the absence of an observation",
    ),
    (
        "Without any specific observation I cannot be precise. The fee is IDR 12,000,000.",
        "Without any specific observation",
    ),
    (
        "Without any prior context, I can only provide a generic outline. "
        "The fee is IDR 12,000,000.",
        "I can only provide a generic outline",
    ),
    (
        "The search results don't contain that regulation. The fee is IDR 12,000,000.",
        "search results don't contain",
    ),
    ("Let me check the knowledge base. The fee is IDR 12,000,000.", "Let me check the knowledge"),
    (
        "Fammi controllare il database. La tariffa e IDR 12.000.000.",
        "Fammi controllare il database",
    ),
    ("My next thought is to solicit input from the user. The fee is IDR 12.", "solicit input"),
    ("I need to answer based on nothing at all. The fee is IDR 12,000,000.", "based on nothing"),
    (
        "I don't need additional thoughts here. The fee is IDR 12,000,000.",
        "don't need additional thoughts",
    ),
    ("But there are still things I am unsure about. The fee is IDR 12.", "still things I am"),
]


@pytest.mark.parametrize(("raw", "leak"), MONOLOGUE_CASES)
def test_internal_monologue_is_still_stripped(raw: str, leak: str) -> None:
    cleaned = clean_response(raw)
    assert leak not in cleaned, f"monologue survived: {leak!r} still in {cleaned!r}"


@pytest.mark.parametrize(("raw", "leak"), MONOLOGUE_CASES)
def test_stripping_monologue_keeps_the_substantive_sentence(raw: str, leak: str) -> None:
    """A correct clean removes the scaffolding and leaves the answer standing."""
    cleaned = clean_response(raw)
    assert cleaned.strip(), f"clean emptied {raw!r}"


def test_a_marker_can_still_be_stripped_from_the_middle_of_a_leaked_monologue() -> None:
    """Markers keep MULTILINE on purpose - they legitimately start any line."""
    raw = (
        "THOUGHT: the user asks about tax.\n"
        "Observation: found 3 chunks.\n"
        "Final Answer: the rate is 11%."
    )
    cleaned = clean_response(raw)
    assert "THOUGHT:" not in cleaned
    assert "Observation:" not in cleaned
    assert "Final Answer:" not in cleaned
    # Sentence case restored because the prefix strip chopped the opening.
    assert cleaned == "The rate is 11%."


def test_stacked_preamble_sentences_are_all_peeled() -> None:
    raw = (
        "Okay, given the observation, I need more input. "
        "Perhaps I should search the knowledge base. "
        "The paid-up capital is IDR 2.5 billion."
    )
    cleaned = clean_response(raw)
    assert cleaned == "The paid-up capital is IDR 2.5 billion."


# ---------------------------------------------------------------------------
# THE NET — a filter may never turn an answer into silence
# ---------------------------------------------------------------------------


def test_a_response_the_filters_consume_entirely_is_returned_unfiltered() -> None:
    """`wa_inbox_bot` sends nothing for an empty answer, so emptying is silence.

    A whole-answer match is a pattern defect by construction: this input is
    100% monologue, and even then the caller is better served by the raw text
    plus a warning than by an empty string it has no branch for.
    """
    raw = "Observation: nothing found.\n"
    assert clean_response(raw) == raw.strip()


def test_the_net_does_not_resurrect_content_the_filters_correctly_removed() -> None:
    """Innocence for the net itself: it must not fire when an answer remains."""
    raw = "THOUGHT: searching.\nThe fee is IDR 12,000,000."
    cleaned = clean_response(raw)
    assert cleaned == "The fee is IDR 12,000,000."
    assert "THOUGHT:" not in cleaned


def test_the_filler_opener_goes_and_the_request_behind_it_stays() -> None:
    """Deliberate prefix strip, asserted by expected output rather than by
    membership - `LEGITIMATE_ANSWER_FRAGMENTS` means "not one character lost",
    and this one is a character we mean to lose."""
    assert clean_response("How can I be helpful here? Tell me which visa you hold.") == (
        "Tell me which visa you hold."
    )


def test_a_prefix_strip_restores_sentence_case() -> None:
    """`Final Answer: the fee is ...` must not reach the client lowercase."""
    assert clean_response("Final Answer: the fee is IDR 12,000,000.") == (
        "The fee is IDR 12,000,000."
    )
    assert clean_response("Based on the search results, the KBLI code is 68111.") == (
        "The KBLI code is 68111."
    )


def test_an_answer_that_genuinely_opens_lowercase_is_left_alone() -> None:
    """Innocence for the case-restore: only OUR chop earns a capital."""
    assert clean_response("e-KTP holders are exempt.") == "e-KTP holders are exempt."


def test_blank_input_stays_empty() -> None:
    assert clean_response("") == ""
    assert clean_response("   \n  ") == ""


# ---------------------------------------------------------------------------
# STRUCTURAL — stop the disease being re-introduced by appending to a list
# ---------------------------------------------------------------------------


def test_only_marker_patterns_are_compiled_with_multiline() -> None:
    """MULTILINE on a preamble rule is exactly the defect this file cures."""
    for regex in _PREAMBLE_RE:
        assert not regex.flags & re.MULTILINE, (
            f"preamble pattern compiled with MULTILINE - it can now eat a line out of "
            f"the middle of an answer: {regex.pattern!r}"
        )
    for regex in _ANYWHERE_RE:
        assert not regex.flags & re.MULTILINE, regex.pattern
    assert _MARKER_RE, "marker class must not be empty"
    for regex in _MARKER_RE:
        assert regex.flags & re.MULTILINE, regex.pattern


def test_no_anywhere_pattern_is_line_anchored() -> None:
    """A start-anchored rule in the unanchored tuple belongs in the preamble one.

    Anchored means a leading `^`, NOT the `^` inside a negated character class:
    the first draft of this check asserted `"^" not in pattern` and flagged
    `[^.]*`, i.e. the probe had the very over-match it exists to catch.
    """
    for regex in _ANYWHERE_RE:
        assert not regex.pattern.startswith("^"), (
            f"anchored pattern in the unanchored class: {regex.pattern!r}"
        )
