"""Validate stealth patches against bot.sannysoft.com.

Opt-in: pytest -m stealth tests/test_stealth_patches.py
"""
from __future__ import annotations

import pytest

from browser_core import BrowserConfig, BrowserManager

pytestmark = pytest.mark.stealth


@pytest.fixture
async def stealth_manager():
    manager = BrowserManager(BrowserConfig(headless=True))
    try:
        await manager.initialize()
        yield manager
    finally:
        await manager.close()


async def test_webdriver_property_hidden(stealth_manager: BrowserManager) -> None:
    async with stealth_manager.get_page("https://bot.sannysoft.com/") as page:
        await page.wait_for_load_state("networkidle")
        webdriver_value = await page.evaluate("() => navigator.webdriver")
        assert webdriver_value is None or webdriver_value is False, (
            f"navigator.webdriver exposed: {webdriver_value}"
        )


async def test_chrome_runtime_exists(stealth_manager: BrowserManager) -> None:
    async with stealth_manager.get_page("https://bot.sannysoft.com/") as page:
        await page.wait_for_load_state("networkidle")
        has_runtime = await page.evaluate(
            "() => typeof window.chrome !== 'undefined' && typeof window.chrome.runtime !== 'undefined'"
        )
        assert has_runtime is True, "window.chrome.runtime missing"


async def test_navigator_plugins_non_empty(stealth_manager: BrowserManager) -> None:
    async with stealth_manager.get_page("https://bot.sannysoft.com/") as page:
        await page.wait_for_load_state("networkidle")
        plugin_count = await page.evaluate("() => navigator.plugins.length")
        assert plugin_count >= 1, f"navigator.plugins empty: {plugin_count}"


async def test_navigator_languages_set(stealth_manager: BrowserManager) -> None:
    async with stealth_manager.get_page("https://bot.sannysoft.com/") as page:
        await page.wait_for_load_state("networkidle")
        langs = await page.evaluate("() => navigator.languages")
        assert isinstance(langs, list) and len(langs) > 0, f"languages broken: {langs}"
