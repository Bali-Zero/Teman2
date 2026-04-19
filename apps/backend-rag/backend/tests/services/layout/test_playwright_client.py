"""Tests for PlaywrightClient (without installing real browser).

We only test the parts that don't require an installed browser:
- data URL helper
- graceful error when screenshot called without start()
"""

from __future__ import annotations

import pytest

from backend.services.layout.playwright_client import (
    PlaywrightClient,
    _html_to_data_url,
)


def test_html_to_data_url_base64_encodes():
    url = _html_to_data_url("<html><body>hi</body></html>")
    assert url.startswith("data:text/html;base64,")
    import base64

    encoded = url.removeprefix("data:text/html;base64,")
    decoded = base64.b64decode(encoded).decode("utf-8")
    assert "hi" in decoded


def test_html_to_data_url_unicode():
    url = _html_to_data_url("<p>città — àèìòù</p>")
    import base64

    encoded = url.removeprefix("data:text/html;base64,")
    decoded = base64.b64decode(encoded).decode("utf-8")
    assert "città" in decoded


@pytest.mark.asyncio
async def test_screenshot_without_start_returns_error():
    client = PlaywrightClient()
    # no start() called
    result = await client.screenshot("<html></html>", width=1080, height=1350)
    assert result.ok is False
    assert "browser not started" in (result.error or "").lower()
    assert result.width == 1080


@pytest.mark.asyncio
async def test_screenshot_once_returns_error_if_playwright_missing(monkeypatch):
    """If the playwright package is absent, screenshot_once returns a clean
    :class:`ScreenshotResult` with ``ok=False`` rather than crashing."""
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "playwright.async_api":
            raise ImportError("simulated missing playwright")
        if name.startswith("playwright"):
            raise ImportError("simulated missing playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)

    client = PlaywrightClient()
    result = await client.screenshot_once(
        "<html></html>", width=1080, height=1350,
    )
    assert result.ok is False
    assert "playwright" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_stop_safe_when_not_started():
    client = PlaywrightClient()
    # Should not raise
    await client.stop()
