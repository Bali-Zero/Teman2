"""Snapshot test: AHU parser logic against a saved HTML fixture.

No network required. We launch Playwright against a file:// URL pointing
to the fixture, then exercise card-iteration and field-extraction logic
matching the real ahu.go.id DOM structure (div cards, not table rows).

Opt-in: pytest -m integration tests/test_ahu_parser_snapshot.py
"""
from __future__ import annotations

from pathlib import Path

import pytest

from browser_core import BrowserConfig, BrowserManager

FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "ahu_search_results.html"
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def local_browser():
    manager = BrowserManager(BrowserConfig(headless=True))
    try:
        await manager.initialize()
        yield manager
    finally:
        await manager.close()


async def test_ahu_parser_extracts_all_cards(local_browser: BrowserManager) -> None:
    """Card iteration finds all 3 synthetic PT cards in section#hasil_cari."""
    file_url = f"file://{FIXTURE_PATH}"
    async with local_browser.get_page() as page:
        await page.goto(file_url)

        # div[class^='cl'] matches cl0, cl1, AND clearfix — filter to only those with strong.judul
        all_divs = await page.locator("section#hasil_cari div[class^='cl']").all()
        cards = [d for d in all_divs if await d.locator("strong.judul").count() > 0]
        assert len(cards) == 3, f"expected 3 cards with judul, got {len(cards)}"

        # First card: PT Astra International
        nama_el = cards[0].locator("strong.judul")
        nama = (await nama_el.inner_text()).strip()
        assert "Astra International" in nama

        data_id = await nama_el.get_attribute("data-id")
        assert data_id == "25690"

        alamat = (await cards[0].locator("div.alamat").inner_text()).strip()
        assert "MENARA ASTRA" in alamat

        kabpro = (await cards[0].locator("div.kabpro").inner_text()).strip()
        assert "Jakarta Pusat" in kabpro


async def test_ahu_parser_extracts_all_three_names(local_browser: BrowserManager) -> None:
    """All three synthetic PT names are extracted correctly."""
    expected_names = {
        "PT Astra International",
        "PT Astra International Trading",
        "PT Telkom Indonesia",
    }
    file_url = f"file://{FIXTURE_PATH}"
    async with local_browser.get_page() as page:
        await page.goto(file_url)

        cards = await page.locator("section#hasil_cari div[class^='cl']").all()
        names: set[str] = set()
        for card in cards:
            nama_el = card.locator("strong.judul")
            if await nama_el.count():
                names.add((await nama_el.inner_text()).strip())

        assert names == expected_names, f"mismatch: {names ^ expected_names}"


async def test_ahu_parser_extracts_data_ids(local_browser: BrowserManager) -> None:
    """All data-id attributes are extracted for URL construction."""
    expected_ids = {"25690", "1155044", "9999999"}
    file_url = f"file://{FIXTURE_PATH}"
    async with local_browser.get_page() as page:
        await page.goto(file_url)

        cards = await page.locator("section#hasil_cari div[class^='cl']").all()
        ids: set[str] = set()
        for card in cards:
            nama_el = card.locator("strong.judul")
            if await nama_el.count():
                data_id = await nama_el.get_attribute("data-id")
                if data_id:
                    ids.add(data_id)

        assert ids == expected_ids, f"mismatch: {ids ^ expected_ids}"
