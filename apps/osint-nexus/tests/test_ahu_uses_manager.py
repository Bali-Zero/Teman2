"""Regression: AHUScraper must use shared browser-core, not raw Playwright.

The current code imports `async_playwright` directly, bypassing stealth
patches (webdriver hide, canvas noise, chrome.runtime, navigator, permissions).
This test fails today. It passes after Task 4.
"""
from __future__ import annotations

import ast
from pathlib import Path


AHU_PATH = Path(__file__).resolve().parents[1] / "osint_nexus" / "scrapers" / "ahu.py"


def test_ahu_does_not_import_async_playwright_directly() -> None:
    """Must NOT import `async_playwright` from playwright.async_api."""
    source = AHU_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    offending: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "playwright.async_api":
            for alias in node.names:
                if alias.name == "async_playwright":
                    offending.append(f"line {node.lineno}")

    assert not offending, (
        f"AHU imports async_playwright directly, bypassing stealth: {offending}"
    )


def test_ahu_source_imports_from_browser_core() -> None:
    """Positive check: AHU must import from browser_core (Strategy B)."""
    source = AHU_PATH.read_text(encoding="utf-8")
    has_browser_core_import = (
        "from browser_core import" in source
        or "import browser_core" in source
    )
    assert has_browser_core_import, "AHU does not import from browser_core"


# --- Task 9 additions ---


def test_ahu_instantiable_without_network() -> None:
    """Importing AHUScraper must not trigger browser initialization."""
    from osint_nexus.scrapers.ahu import AHUScraper, _browser_instance
    scraper = AHUScraper()
    assert scraper.name == "ahu"
    assert _browser_instance is None, (
        "Lazy init violated — _browser_instance should be None on import"
    )


def test_ahu_detail_opens_fresh_page() -> None:
    """Regression for DOM-clobber bug: _fetch_detail must open new page."""
    source = AHU_PATH.read_text(encoding="utf-8")
    assert "context.new_page()" in source, (
        "_fetch_detail must open a fresh page from the context, not reuse "
        "the search-results page"
    )


def test_ahu_has_atexit_shutdown_hook() -> None:
    """atexit hook must be registered for browser cleanup."""
    source = AHU_PATH.read_text(encoding="utf-8")
    assert "atexit.register" in source, "Missing atexit hook"
    assert "_shutdown_browser" in source, "Missing _shutdown_browser function"
