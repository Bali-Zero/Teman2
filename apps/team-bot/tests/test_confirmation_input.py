"""Confirm-code extraction — button postbacks and the strict text fallback.

Includes the REAL collision this module was hardened against while being
built: a naive scan matches the numeric tail of a practice ID (see
confirmation_input.py's module docstring).
"""

from __future__ import annotations

from team_bot.confirmation.confirmation_input import (
    parse_confirmation_button_payload,
    parse_confirmation_text,
)


def test_button_payload_extracts_code() -> None:
    assert parse_confirmation_button_payload("confirm:7F3K") == "7F3K"


def test_button_payload_lowercases_are_normalized_uppercase() -> None:
    assert parse_confirmation_button_payload("confirm:7f3k") == "7F3K"


def test_button_payload_without_prefix_is_none() -> None:
    assert parse_confirmation_button_payload("7F3K") is None


def test_button_payload_pure_digit_code_is_rejected() -> None:
    """A pure-digit code shape fails SHORT_CODE_PATTERN's letter
    requirement — see models.py."""
    assert parse_confirmation_button_payload("confirm:3090") is None


def test_text_with_keyword_and_code_extracts_code() -> None:
    assert parse_confirmation_text("CONFERMA 7F3K") == "7F3K"
    assert parse_confirmation_text("CONFIRM 7F3K") == "7F3K"
    assert parse_confirmation_text("konfirmasi 7F3K") == "7F3K"


def test_text_extracts_only_the_code_ignores_trailing_content() -> None:
    """'CONFERMA 7F3K per giovedì' -> the routing key ONLY; the rest is
    never read, never touches the stored args (F6: 'post-confirmation
    text never touches the arguments')."""
    assert parse_confirmation_text("CONFERMA 7F3K per giovedì") == "7F3K"


def test_text_with_colon_separator() -> None:
    assert parse_confirmation_text("Conferma: 7F3K") == "7F3K"


def test_bare_yes_words_are_never_confirmations() -> None:
    """F6's frozen text requires a CODE even in the fallback path — the
    stricter reading than Kimi's bare-word matcher. See module docstring."""
    for text in ("sì", "si", "ok", "yes", "confermo", "va bene"):
        assert parse_confirmation_text(text) is None


def test_practice_id_mentioned_elsewhere_is_never_mistaken_for_a_code() -> None:
    """The real collision found while building this: a naive scan would
    match '3090' inside 'PR-3090'. Requiring the keyword immediately
    precede the code closes it."""
    assert parse_confirmation_text("Can you check the status of PR-3090?") is None
    assert parse_confirmation_text("I need info on client CL-1042 please") is None


def test_keyword_present_but_code_is_actually_a_hyphenated_id_does_not_match() -> None:
    """Even directly after the keyword, a hyphenated ID token like
    'PR-3090' does not satisfy the bare alnum code shape."""
    assert parse_confirmation_text("Confirm PR-3090 is correct") is None


def test_lookup_summary_mentioning_a_code_shaped_word_elsewhere_is_not_confirmation() -> None:
    """No keyword at all -> never a match, regardless of what looks
    code-shaped elsewhere in the sentence."""
    assert parse_confirmation_text("The batch reference is 7F3K for your records.") is None
