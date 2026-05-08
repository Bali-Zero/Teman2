from __future__ import annotations

import pytest

from backend.services.notifications import email_http


@pytest.fixture(autouse=True)
async def reset_email_client() -> None:
    await email_http.close_email_client()
    yield
    await email_http.close_email_client()


@pytest.mark.asyncio
async def test_get_email_client_reuses_open_singleton() -> None:
    first = await email_http.get_email_client()
    second = await email_http.get_email_client()

    assert first is second
    assert not first.is_closed


@pytest.mark.asyncio
async def test_get_email_client_recreates_closed_singleton() -> None:
    first = await email_http.get_email_client()
    await first.aclose()

    second = await email_http.get_email_client()

    assert second is not first
    assert not second.is_closed


@pytest.mark.asyncio
async def test_close_email_client_clears_singleton() -> None:
    first = await email_http.get_email_client()

    await email_http.close_email_client()

    assert first.is_closed
    assert email_http._client is None
