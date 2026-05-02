"""Unit tests for intel-scraper-cell event_bridge.

Mocks ObservedShellBus with AsyncMock — exercises the contract layer,
not the bus internals (those have their own tests in
``apps/backend-rag/backend/tests/services/events/test_observed_shell.py``).
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.cell.event_bridge import (
    ALLOWED_STATUSES,
    IntelScraperEventBridge,
)


def _make_kwargs(**overrides):
    base = {
        "trace_id": "intel-scraper-test-1",
        "status": "ok",
        "sources_attempted": 4,
        "articles_found": 12,
        "scars_added": 0,
        "hgt_published_count": 1,
        "duration_ms": 4321,
        "started_at": "2026-05-02T03:00:00+00:00",
        "finished_at": "2026-05-02T03:00:04+00:00",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_emit_run_calls_bus_with_correct_contract() -> None:
    fake_bus = AsyncMock()
    bridge = IntelScraperEventBridge(fake_bus)
    await bridge.emit_run(**_make_kwargs())

    fake_bus.emit.assert_awaited_once()
    kwargs = fake_bus.emit.await_args.kwargs
    assert kwargs["automation_name"] == "intel.scraper.run"
    assert kwargs["status"] == "ok"
    assert kwargs["trace_id"] == "intel-scraper-test-1"
    payload = kwargs["payload"]
    assert payload == {
        "sources_attempted": 4,
        "articles_found": 12,
        "scars_added": 0,
        "hgt_published_count": 1,
        "duration_ms": 4321,
        "started_at": "2026-05-02T03:00:00+00:00",
        "finished_at": "2026-05-02T03:00:04+00:00",
    }


@pytest.mark.asyncio
async def test_emit_run_status_typo_raises_value_error() -> None:
    """Cell-level event contract is narrower than ObservedShellBus
    VALID_STATUSES — typos surface as ValueError, not silent coercion."""
    fake_bus = AsyncMock()
    bridge = IntelScraperEventBridge(fake_bus)
    with pytest.raises(ValueError, match="status must be one of"):
        await bridge.emit_run(**_make_kwargs(status="OKAY"))
    fake_bus.emit.assert_not_called()


@pytest.mark.asyncio
async def test_emit_run_coerces_floats_to_ints() -> None:
    fake_bus = AsyncMock()
    bridge = IntelScraperEventBridge(fake_bus)
    await bridge.emit_run(**_make_kwargs(
        sources_attempted=4.0,
        articles_found=12.7,
        scars_added=0.0,
        hgt_published_count=1.9,
        duration_ms=4321.5,
    ))
    payload = fake_bus.emit.await_args.kwargs["payload"]
    assert isinstance(payload["sources_attempted"], int)
    assert isinstance(payload["articles_found"], int)
    assert isinstance(payload["scars_added"], int)
    assert isinstance(payload["hgt_published_count"], int)
    assert isinstance(payload["duration_ms"], int)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ALLOWED_STATUSES)
async def test_emit_run_accepts_each_allowed_status(status: str) -> None:
    fake_bus = AsyncMock()
    bridge = IntelScraperEventBridge(fake_bus)
    await bridge.emit_run(**_make_kwargs(status=status))
    fake_bus.emit.assert_awaited_once()


@pytest.mark.asyncio
async def test_emit_run_propagates_bus_exception() -> None:
    """The bridge does NOT swallow bus exceptions — that's the runner's
    job. ObservedShellBus is supposed to swallow internally; if it
    doesn't, the bridge layer raises and the runner catches at finally."""
    fake_bus = AsyncMock()
    fake_bus.emit = AsyncMock(side_effect=RuntimeError("bus down"))
    bridge = IntelScraperEventBridge(fake_bus)
    with pytest.raises(RuntimeError, match="bus down"):
        await bridge.emit_run(**_make_kwargs())
