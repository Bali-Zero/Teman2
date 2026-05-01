"""Tests for pulse.single_pulse fire-and-forget observatory hook (BLOCKER B2 fix).

Verifies:
1. When CELL_OBSERVATORY_EMIT=true, single_pulse schedules emit_pulse_observed.
2. A slow observatory emit does NOT delay the pulse cycle return (<1s).
3. When CELL_OBSERVATORY_EMIT is unset, no emit task is scheduled.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from conftest import (
    FakeActor, FakeEpisodic, FakeLTM, FakeSensor, FakeSTM, FakeThinker,
)
from cell_core.types import CellConfig, SafetyCheckResult


def _make_pulse_loop(config=None, sensors=None):
    """Minimal PulseLoop for observatory hook tests."""
    from cell_core.pulse import PulseLoop
    from cell_core.lifecycle import Maturation
    from cell_core.homeostasis import HomeostaticController

    if config is None:
        config = CellConfig(
            name="test-cell",
            dna_path="/tmp/fake-dna.yaml",
            birth_date=datetime.now(timezone.utc) - timedelta(days=50),
        )

    class FakeSafetyGate:
        async def check(self):
            return SafetyCheckResult(can_proceed=True)

    return PulseLoop(
        config=config,
        sensors=sensors or [FakeSensor()],
        thinker=FakeThinker(),
        actor=FakeActor(),
        stm=FakeSTM(),
        ltm=FakeLTM(),
        episodic=FakeEpisodic(),
        lifecycle=Maturation(config.birth_date),
        safety=FakeSafetyGate(),
        homeostasis=HomeostaticController(config.sleep_hours),
    )


@pytest.mark.asyncio
async def test_single_pulse_emits_to_observatory_when_enabled(monkeypatch):
    """When CELL_OBSERVATORY_EMIT=true, single_pulse schedules a fire-and-forget emit."""
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")

    from cell_core import observatory

    fake_emit = AsyncMock()
    monkeypatch.setattr(observatory, "emit_pulse_observed", fake_emit)
    monkeypatch.setattr(observatory, "is_enabled", lambda: True)

    loop = _make_pulse_loop()
    result = await loop.single_pulse()

    # Allow the fire-and-forget create_task to run
    await asyncio.sleep(0)

    fake_emit.assert_called_once()
    call_kwargs = fake_emit.call_args.kwargs
    assert call_kwargs["cell_id"] == "test-cell"
    assert call_kwargs["pulse_id"] == result.pulse_id
    assert call_kwargs["cell_kind"] == "cell"
    assert call_kwargs["phase"] == "active"
    assert isinstance(call_kwargs["sensors"], list)
    assert "classifier_self" in call_kwargs["pulse_result"]


@pytest.mark.asyncio
async def test_single_pulse_does_not_block_on_emit(monkeypatch):
    """A slow observatory emit MUST NOT delay the pulse cycle return (<1s)."""
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")

    from cell_core import observatory

    async def slow_emit(**kw):
        await asyncio.sleep(5.0)

    monkeypatch.setattr(observatory, "emit_pulse_observed", slow_emit)
    monkeypatch.setattr(observatory, "is_enabled", lambda: True)

    loop = _make_pulse_loop()

    start = time.monotonic()
    await loop.single_pulse()
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"pulse blocked on observatory: {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_single_pulse_no_emit_when_disabled(monkeypatch):
    """When CELL_OBSERVATORY_EMIT is unset, NO emit task is scheduled."""
    monkeypatch.delenv("CELL_OBSERVATORY_EMIT", raising=False)

    from cell_core import observatory

    fake_emit = AsyncMock()
    monkeypatch.setattr(observatory, "emit_pulse_observed", fake_emit)
    monkeypatch.setattr(observatory, "is_enabled", lambda: False)

    loop = _make_pulse_loop()
    await loop.single_pulse()
    await asyncio.sleep(0)

    fake_emit.assert_not_called()
