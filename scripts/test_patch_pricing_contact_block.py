#!/usr/bin/env python3
"""Falsifiable tests for scripts/patch_pricing_contact_block.py.

Run:
    apps/backend-rag/.venv/bin/python -m pytest scripts/test_patch_pricing_contact_block.py -q

Guilt tests (the rewrite MUST fire):
  - A full pricing chunk carrying the retired WhatsApp + Location trailer
    gets BOTH rewritten to the canonical values, price/name/category lines
    untouched.
  - A chunk with only the stale WhatsApp line (no Location line at all)
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


def test_stale_contact_block_rewritten_both_lines():
    before = _chunk(ppcb.STALE_WHATSAPP, ppcb.STALE_LOCATION)
    after = ppcb.rewrite_contact_block(before)

    assert ppcb.STALE_WHATSAPP not in after
    assert ppcb.STALE_LOCATION not in after
    assert f"**WhatsApp**: {ppcb.CANONICAL_WHATSAPP}" in after
    assert f"**Location**: {ppcb.CANONICAL_LOCATION}" in after

    # Everything above the `---` separator is untouched, verbatim.
    before_header = before.split("\n---\n")[0]
    after_header = after.split("\n---\n")[0]
    assert before_header == after_header


def test_stale_whatsapp_only_rewritten_when_location_already_canonical():
    before = _chunk(ppcb.STALE_WHATSAPP, ppcb.CANONICAL_LOCATION)
    after = ppcb.rewrite_contact_block(before)

    assert f"**WhatsApp**: {ppcb.CANONICAL_WHATSAPP}" in after
    assert f"**Location**: {ppcb.CANONICAL_LOCATION}" in after
    assert ppcb.STALE_WHATSAPP not in after


# ---------------------------------------------------------------------------
# Innocence
# ---------------------------------------------------------------------------


def test_already_canonical_chunk_is_byte_identical():
    text = _chunk(ppcb.CANONICAL_WHATSAPP, ppcb.CANONICAL_LOCATION)
    assert ppcb.rewrite_contact_block(text) == text


def test_unrelated_chunk_without_any_stale_marker_is_byte_identical():
    text = "# Some other KBLI chunk\n**Category**: Not pricing at all\nNo contact block here."
    assert ppcb.rewrite_contact_block(text) == text


def test_price_line_never_touched_even_with_lookalike_digits():
    # A price that happens to contain a digit run resembling a phone number
    # must survive untouched — only the labeled WhatsApp/Location lines move.
    before = _chunk(ppcb.STALE_WHATSAPP, ppcb.STALE_LOCATION, price="8.133.805 IDR")
    after = ppcb.rewrite_contact_block(before)
    assert "**Price**: 8.133.805 IDR" in after


def test_patch_is_idempotent():
    once = ppcb.rewrite_contact_block(_chunk(ppcb.STALE_WHATSAPP, ppcb.STALE_LOCATION))
    twice = ppcb.rewrite_contact_block(once)
    assert once == twice


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
