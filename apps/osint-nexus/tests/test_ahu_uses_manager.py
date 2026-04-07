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
