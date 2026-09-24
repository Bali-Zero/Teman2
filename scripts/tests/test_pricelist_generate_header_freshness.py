"""L1738: the price-list generator's header must never drift stale.

`docs/pricing/Bali_Zero_Price_List_2026.md` used to forward the JSON's
hand-edited `metadata.last_updated` verbatim — a regeneration that added
rows left the header's freshness claim untouched. The header is now stamped
from the run date (never older than it, never older than the JSON's own
claim either, guarding a wrong system clock).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.pricelist_2026.generate import _stamp_last_updated, render_markdown  # noqa: E402

_BASE_DATA = {
    "version": "2026.1",
    "effective_date": "2026-01-01",
    "metadata": {
        "currency": "IDR",
        "contact": {
            "email": "zero@balizero.com",
            "whatsapp": "+62 821 3454 721",
            "wa_link": "https://wa.me/628213454721",
            "location": "Kerobokan, Bali, Indonesia",
            "website": "balizero.com",
        },
        "last_updated": "2026-05-06",
    },
    "services": {},
}


def test_the_header_stamps_the_run_date_even_when_metadata_is_stale():
    stamped = _stamp_last_updated(_BASE_DATA, run_date=date(2026, 9, 24))
    assert stamped == "2026-09-24", (
        "regenerating on a later date must bump the header, not forward the "
        "JSON's stale metadata.last_updated"
    )


def test_the_header_never_reads_older_than_the_json_s_own_claim():
    # a wrong/rolled-back system clock must not regress the header below
    # what the JSON source already declares
    stamped = _stamp_last_updated(_BASE_DATA, run_date=date(2020, 1, 1))
    assert stamped == "2026-05-06"


def test_render_markdown_writes_the_stamped_date_not_the_stale_metadata_one(tmp_path):
    out = tmp_path / "Bali_Zero_Price_List_2026.md"
    render_markdown(_BASE_DATA, out, run_date=date(2026, 9, 24))
    text = out.read_text()
    assert "**Last updated:** 2026-09-24" in text
    assert "**Last updated:** 2026-05-06" not in text
