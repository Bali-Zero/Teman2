#!/usr/bin/env python3
"""Falsifiable tests for scripts/patch_pricing_contact_block.py.

Run:
    apps/backend-rag/.venv/bin/python -m pytest scripts/test_patch_pricing_contact_block.py -q

Guilt tests (the rewrite MUST fire) — parametrised over EVERY entry in
`STALE_WHATSAPP_NUMBERS`, not just the oldest one, because the collection has
carried more than one wrong number and a guard that only knows the first
reports a clean no-op over the second:
  - A full pricing chunk carrying a stale WhatsApp + Location trailer gets
    BOTH rewritten to the canonical values, price/name/category lines
    untouched.
  - A chunk with only a stale WhatsApp line (Location already canonical)
    still gets that one line rewritten.
Innocence tests (the rewrite MUST NOT fire / MUST NOT clobber):
  - A chunk that already carries the canonical contact block is returned
    byte-identical (idempotent — running the patch twice is a no-op).
  - A chunk from an unrelated collection (no stale marker at all) is
    returned byte-identical.
  - The price line is never touched even when it contains digits that look
    similar to phone-number digits.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import patch_pricing_contact_block as ppcb  # noqa: E402


def _chunk(whatsapp: str, location: str, price: str = "5.800.000 IDR") -> str:
    return (
        "# C22A&B Internship (180 Days)\n"
        "**Category**: Single Entry Visas\n"
        f"**Price**: {price}\n"
        "**Duration**: 180 days\n"
        "\n---\n\n"
        "**Contact**: info@balizero.com\n"
        f"**WhatsApp**: {whatsapp}\n"
        f"**Location**: {location}"
    )


# ---------------------------------------------------------------------------
# Guilt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stale", ppcb.STALE_WHATSAPP_NUMBERS)
def test_stale_contact_block_rewritten_both_lines(stale):
    before = _chunk(stale, ppcb.STALE_LOCATION)
    after = ppcb.rewrite_contact_block(before)

    assert stale not in after
    assert ppcb.STALE_LOCATION not in after
    assert f"**WhatsApp**: {ppcb.CANONICAL_WHATSAPP}" in after
    assert f"**Location**: {ppcb.CANONICAL_LOCATION}" in after

    # Everything above the `---` separator is untouched, verbatim.
    before_header = before.split("\n---\n")[0]
    after_header = after.split("\n---\n")[0]
    assert before_header == after_header


@pytest.mark.parametrize("stale", ppcb.STALE_WHATSAPP_NUMBERS)
def test_stale_whatsapp_only_rewritten_when_location_already_canonical(stale):
    before = _chunk(stale, ppcb.CANONICAL_LOCATION)
    after = ppcb.rewrite_contact_block(before)

    assert f"**WhatsApp**: {ppcb.CANONICAL_WHATSAPP}" in after
    assert f"**Location**: {ppcb.CANONICAL_LOCATION}" in after
    assert stale not in after


# ---------------------------------------------------------------------------
# Innocence
# ---------------------------------------------------------------------------


def test_already_canonical_chunk_is_byte_identical():
    text = _chunk(ppcb.CANONICAL_WHATSAPP, ppcb.CANONICAL_LOCATION)
    assert ppcb.rewrite_contact_block(text) == text


def test_every_historically_wrong_number_is_still_listed_as_stale():
    """Pin the list's CONTENTS by literal, not just its behaviour.

    The guilt tests above are parametrised over STALE_WHATSAPP_NUMBERS, so
    deleting an entry deletes its own test case and the suite stays green
    while the collection silently stops being healed. These literals are the
    numbers this collection is known to have carried; they are historical
    facts and can only ever be appended to.
    """
    for historically_wrong in ("+62 813 3805 1876", "+62 821 3465 159"):
        assert historically_wrong in ppcb.STALE_WHATSAPP_NUMBERS, (
            f"{historically_wrong} was canonical once and may still sit in "
            "the live bali_zero_pricing_hybrid payloads; dropping it from "
            "STALE_WHATSAPP_NUMBERS makes the patch a silent no-op over it."
        )


def test_a_line_carrying_both_stale_numbers_is_fully_replaced():
    """The defect an adversarial seat found in the substring form: a trailer
    naming BOTH retired numbers came out half-rewritten and STABLE — wrong, and
    unchanged by a second pass, so it read as idempotent."""
    both = " / ".join(ppcb.STALE_WHATSAPP_NUMBERS)
    before = _chunk(both, ppcb.STALE_LOCATION)
    after = ppcb.rewrite_contact_block(before)

    assert f"**WhatsApp**: {ppcb.CANONICAL_WHATSAPP}" in after
    for stale in ppcb.STALE_WHATSAPP_NUMBERS:
        assert stale not in after, f"{stale} survived a full-line rewrite"
    assert ppcb.rewrite_contact_block(after) == after


def test_a_line_that_merely_quotes_a_trailer_is_left_alone():
    """`**Notes**: previous payload contained **WhatsApp**: <stale>` is prose
    about a trailer, not a trailer. The substring form rewrote it."""
    stale = ppcb.STALE_WHATSAPP_NUMBERS[0]
    text = (
        "# Some service\n"
        f"**Notes**: previous payload contained **WhatsApp**: {stale}\n"
        "\n---\n\n"
        "**Contact**: info@balizero.com\n"
        f"**WhatsApp**: {stale}\n"
        f"**Location**: {ppcb.CANONICAL_LOCATION}"
    )
    after = ppcb.rewrite_contact_block(text)

    assert f"**Notes**: previous payload contained **WhatsApp**: {stale}" in after, (
        "the Notes line was rewritten — only a line that IS the trailer may move"
    )
    assert f"**WhatsApp**: {ppcb.CANONICAL_WHATSAPP}" in after, (
        "the real trailer was not rewritten"
    )


def test_a_crlf_payload_keeps_its_line_endings_and_indentation():
    """Rebuilding a line from its label alone throws away whatever else the
    line carried. Two things it carried mattered: the CR of a CRLF payload and
    the line's indentation. Dropping either leaves the rewritten line subtly
    unlike its neighbours — a corruption introduced by a repair.
    """
    stale = ppcb.STALE_WHATSAPP_NUMBERS[0]
    crlf = (
        "# Service\r\n"
        "**Contact**: info@balizero.com\r\n"
        f"**WhatsApp**: {stale}\r\n"
        f"**Location**: {ppcb.STALE_LOCATION}\r\n"
    )
    after = ppcb.rewrite_contact_block(crlf)

    assert stale not in after and ppcb.STALE_LOCATION not in after
    for line in after.split("\n")[:-1]:
        assert line.endswith("\r"), f"line lost its CR: {line!r}"

    indented = f"    **WhatsApp**: {stale}"
    assert ppcb.rewrite_contact_block(indented) == (
        f"    **WhatsApp**: {ppcb.CANONICAL_WHATSAPP}"
    ), "the line's indentation was dropped by the rewrite"


def test_canonical_number_is_not_itself_listed_as_stale():
    """The two lists must not overlap, or the rewrite chases its own tail.

    If a future ruling makes today's canonical number stale, it moves INTO
    STALE_WHATSAPP_NUMBERS and a new CANONICAL_WHATSAPP replaces it — it must
    never sit in both, which would make `rewrite_contact_block` fire forever
    on already-correct text and break idempotency.
    """
    assert ppcb.CANONICAL_WHATSAPP not in ppcb.STALE_WHATSAPP_NUMBERS


def test_unrelated_chunk_without_any_stale_marker_is_byte_identical():
    text = "# Some other KBLI chunk\n**Category**: Not pricing at all\nNo contact block here."
    assert ppcb.rewrite_contact_block(text) == text


def test_price_line_never_touched_even_with_lookalike_digits():
    # A price that happens to contain a digit run resembling a phone number
    # must survive untouched — only the labeled WhatsApp/Location lines move.
    before = _chunk(
        ppcb.STALE_WHATSAPP_NUMBERS[0], ppcb.STALE_LOCATION, price="8.133.805 IDR"
    )
    after = ppcb.rewrite_contact_block(before)
    assert "**Price**: 8.133.805 IDR" in after


def test_patch_is_idempotent():
    once = ppcb.rewrite_contact_block(
        _chunk(ppcb.STALE_WHATSAPP_NUMBERS[0], ppcb.STALE_LOCATION)
    )
    twice = ppcb.rewrite_contact_block(once)
    assert once == twice


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
