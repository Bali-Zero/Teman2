"""Tests for the GARUDA VOA magic-link preview masking rule.

Each guard here is proven to bite: broken then restored, with the literal
red/green recorded in the PR description (modus VERIFY discipline).
"""

from __future__ import annotations

import pytest

from backend.services.garuda_portal.masking import mask_email


@pytest.mark.parametrize(
    "email,expected",
    [
        ("johndoe@example.com", "jo***@example.com"),
        ("abc@example.com", "ab***@example.com"),
    ],
)
def test_reveals_only_the_first_two_characters_of_a_normal_local_part(email, expected):
    assert mask_email(email) == expected


def test_one_character_local_part_reveals_nothing():
    """The naive 'reveal all but the last character' rule would show the
    whole local part here (0 characters left to mask) -- full disclosure."""
    assert mask_email("a@example.com") == "***@example.com"


def test_two_character_local_part_reveals_nothing():
    """The naive rule would reveal half the local part ('a*') here -- this
    module treats anything at or below the threshold as fully opaque."""
    assert mask_email("ab@example.com") == "***@example.com"


def test_mask_width_is_fixed_not_proportional_to_local_part_length():
    """A variable-width mask leaks the local part's LENGTH, which narrows a
    guess even when no characters are shown directly."""
    short = mask_email("jo@example.com")
    long_local = mask_email("johnjohnjohn@example.com")
    assert short.count("*") == long_local.count("*")


def test_domain_is_never_masked():
    assert mask_email("john@example.com").endswith("@example.com")


def test_never_leaks_the_raw_local_part():
    masked = mask_email("johndoe@example.com")
    assert "johndoe" not in masked


def test_malformed_input_masks_to_the_fixed_sentinel_rather_than_raising():
    assert mask_email("not-an-email") == "***"


def test_trailing_at_with_no_domain_masks_to_the_fixed_sentinel():
    assert mask_email("johndoe@") == "***"
