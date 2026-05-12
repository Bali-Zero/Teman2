"""Phase 3 TICKET C EXECUTION — run_sentinel_cell shim tests.

4 unit tests with concrete mocks (per spec v2 CORR-C5):
- _run_one_pulse returns 0 on health='green'
- _run_one_pulse returns 1 on health='red' (cron alerts on non-zero)
- _run_one_pulse returns 0 on health='yellow' (only red triggers alert)
- _run_one_pulse returns 1 on single_pulse() exception
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the mata-garuda package to sys.path so scripts/ + mata_garuda/ resolve
_PACKAGE_PATH = Path(__file__).resolve().parents[1]
if str(_PACKAGE_PATH) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PATH))

# Import the shim module (triggers its own sys.path insert as side effect)
from scripts.run_sentinel_cell import _run_one_pulse  # noqa: E402


@pytest.mark.asyncio
async def test_run_one_pulse_returns_0_on_green_health() -> None:
    """health='green' → _run_one_pulse() returns 0."""
    mock_cell = MagicMock()
    mock_result = MagicMock()
    mock_result.pulse_number = 1
    mock_result.health_status = "green"
    mock_result.action_taken = "none"
    mock_result.halted = False
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)

    with patch(
        "mata_garuda.cells.sentinel_cell.create_sentinel_cell",
        return_value=mock_cell,
    ):
        assert await _run_one_pulse() == 0


@pytest.mark.asyncio
async def test_run_one_pulse_returns_1_on_red_health() -> None:
    """health='red' → _run_one_pulse() returns 1 (cron alerts on non-zero)."""
    mock_cell = MagicMock()
    mock_result = MagicMock()
    mock_result.pulse_number = 2
    mock_result.health_status = "red"
    mock_result.action_taken = None
    mock_result.halted = False
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)

    with patch(
        "mata_garuda.cells.sentinel_cell.create_sentinel_cell",
        return_value=mock_cell,
    ):
        assert await _run_one_pulse() == 1


@pytest.mark.asyncio
async def test_run_one_pulse_returns_0_on_yellow_health() -> None:
    """health='yellow' → _run_one_pulse() returns 0 (only red triggers alert)."""
    mock_cell = MagicMock()
    mock_result = MagicMock()
    mock_result.pulse_number = 3
    mock_result.health_status = "yellow"
    mock_result.action_taken = "none"
    mock_result.halted = False
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)

    with patch(
        "mata_garuda.cells.sentinel_cell.create_sentinel_cell",
        return_value=mock_cell,
    ):
        assert await _run_one_pulse() == 0


@pytest.mark.asyncio
async def test_run_one_pulse_returns_1_on_single_pulse_exception() -> None:
    """single_pulse() raises → _run_one_pulse() returns 1, no propagation."""
    mock_cell = MagicMock()
    mock_cell.single_pulse = AsyncMock(side_effect=RuntimeError("test error"))

    with patch(
        "mata_garuda.cells.sentinel_cell.create_sentinel_cell",
        return_value=mock_cell,
    ):
        assert await _run_one_pulse() == 1
