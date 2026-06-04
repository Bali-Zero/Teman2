from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from browser_core import BrowserManager


@pytest.mark.asyncio
async def test_get_page_allows_navigation_without_response() -> None:
    """Playwright may return None for same-document or about:blank navigations."""
    manager = BrowserManager()
    page = MagicMock()
    page.goto = AsyncMock(return_value=None)
    page.close = AsyncMock()

    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)

    @asynccontextmanager
    async def fake_context(*args, **kwargs):
        yield context

    manager.get_context = fake_context  # type: ignore[method-assign]

    async with manager.get_page("about:blank") as returned_page:
        assert returned_page is page

    page.close.assert_awaited_once()
