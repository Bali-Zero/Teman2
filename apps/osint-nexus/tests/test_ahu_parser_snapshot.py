"""Snapshot test: AHU parser logic against a saved HTML fixture.

No network required. We launch Playwright against a file:// URL pointing
to the fixture, then exercise row-iteration and cell-extraction logic.

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


async def test_ahu_parser_extracts_all_rows(local_browser: BrowserManager) -> None:
    """Row iteration finds all 3 synthetic PT rows."""
    file_url = f"file://{FIXTURE_PATH}"
    # Use get_page() without URL to avoid HTTP-status check on file:// URLs,
    # then navigate manually inside the context.
    async with local_browser.get_page() as page:
        await page.goto(file_url)

        rows = await page.locator("table tbody tr").all()
        assert len(rows) == 3, f"expected 3 rows, got {len(rows)}"

        cells_r1 = await rows[0].locator("td").all()
        nama_r1 = (await cells_r1[0].inner_text()).strip()
        assert nama_r1 == "PT ASTRA INTERNATIONAL TBK"

        nomor_r1 = (await cells_r1[1].inner_text()).strip()
        assert "AHU-12345" in nomor_r1

        status_r1 = (await cells_r1[2].inner_text()).strip()
        assert status_r1 == "AKTIF"

        link_r1 = await rows[0].locator("a").first.get_attribute("href")
        assert link_r1 == "/pencarian/detail-pt/ASTRA-12345"


async def test_ahu_parser_handles_all_three_pts(local_browser: BrowserManager) -> None:
    """All three synthetic PTs are named correctly."""
    expected_names = {
        "PT ASTRA INTERNATIONAL TBK",
        "PT UNILEVER INDONESIA TBK",
        "PT TELKOM INDONESIA",
    }
    file_url = f"file://{FIXTURE_PATH}"
    async with local_browser.get_page() as page:
        await page.goto(file_url)

        rows = await page.locator("table tbody tr").all()
        names: set[str] = set()
        for row in rows:
            cells = await row.locator("td").all()
            if len(cells) >= 1:
                names.add((await cells[0].inner_text()).strip())

        assert names == expected_names, f"mismatch: {names ^ expected_names}"
