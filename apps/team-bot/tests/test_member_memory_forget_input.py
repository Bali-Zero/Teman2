""""dimentica X" parsing — guilt/innocence pairs mirroring
`test_confirmation_input.py`'s style for the confirm-code parsers.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from team_bot.memory.forget_input import ForgetRequest, parse_forget_text
from team_bot.memory.store import ForgetScope


# ---------------------------------------------------------------------------
# innocence: real commands parse correctly
# ---------------------------------------------------------------------------


def test_parses_a_client_target_in_italian() -> None:
    result = parse_forget_text("dimentica CL-1042")
    assert result == ForgetRequest(scope=ForgetScope.TARGET, target_id="CL-1042")


def test_parses_a_practice_target_in_english() -> None:
    result = parse_forget_text("please forget PR-3090 for me")
    assert result == ForgetRequest(scope=ForgetScope.TARGET, target_id="PR-3090")


def test_parses_a_practice_target_in_indonesian() -> None:
    result = parse_forget_text("tolong lupakan PR-3090")
    assert result == ForgetRequest(scope=ForgetScope.TARGET, target_id="PR-3090")


def test_parses_everything_in_italian() -> None:
    assert parse_forget_text("dimentica tutto per favore") == ForgetRequest(scope=ForgetScope.MEMBER)


def test_parses_everything_in_english() -> None:
    assert parse_forget_text("forget everything about me") == ForgetRequest(scope=ForgetScope.MEMBER)


def test_parses_everything_in_indonesian() -> None:
    assert parse_forget_text("lupakan semua ya") == ForgetRequest(scope=ForgetScope.MEMBER)


def test_is_case_insensitive_on_keyword_and_normalizes_id_to_uppercase() -> None:
    result = parse_forget_text("DIMENTICA cl-1042")
    assert result == ForgetRequest(scope=ForgetScope.TARGET, target_id="CL-1042")


def test_accepts_an_optional_colon_between_keyword_and_target() -> None:
    result = parse_forget_text("forget: CL-1042")
    assert result == ForgetRequest(scope=ForgetScope.TARGET, target_id="CL-1042")


# ---------------------------------------------------------------------------
# guilt: things that must NOT parse as a forget command
# ---------------------------------------------------------------------------


def test_returns_none_for_a_message_without_the_keyword() -> None:
    assert parse_forget_text("what's the status of CL-1042?") is None


def test_returns_none_when_keyword_is_a_substring_of_a_longer_word() -> None:
    # "dimenticalo" contains "dimentica" but is not the standalone keyword.
    assert parse_forget_text("il cliente ha chiesto di dimenticarlo, CL-1042") is None


def test_returns_none_when_the_target_is_not_adjacent_to_the_keyword() -> None:
    # A real ID appears in the message, but not immediately after the
    # keyword — same adjacency discipline confirmation_input.py enforces.
    assert parse_forget_text("dimentica quello che ti ho detto ieri su CL-1042") is None


def test_returns_none_for_a_bare_id_with_no_keyword() -> None:
    assert parse_forget_text("CL-1042 PR-3090") is None


def test_returns_none_for_an_id_shaped_token_missing_the_letter_prefix() -> None:
    assert parse_forget_text("dimentica 1042") is None


# ---------------------------------------------------------------------------
# ForgetRequest's own invariant (scope <-> target_id)
# ---------------------------------------------------------------------------


def test_forget_request_rejects_target_scope_without_a_target_id() -> None:
    with pytest.raises(ValidationError):
        ForgetRequest(scope=ForgetScope.TARGET, target_id=None)


def test_forget_request_rejects_member_scope_with_a_target_id() -> None:
    with pytest.raises(ValidationError):
        ForgetRequest(scope=ForgetScope.MEMBER, target_id="CL-1042")
