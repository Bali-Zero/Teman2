"""Heartbeat and exit-code contract for Pro's hourly Sentinel Cell runner."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

# Add the mata-garuda package to sys.path so scripts/ + mata_garuda/ resolve
_PACKAGE_PATH = Path(__file__).resolve().parents[1]
if str(_PACKAGE_PATH) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PATH))

from scripts.run_sentinel_cell import ORGAN_ID, _run_one_pulse  # noqa: E402


def _sidecar(tmp_path: Path) -> dict:
    return json.loads((tmp_path / f"{ORGAN_ID}.json").read_text())


@pytest.mark.asyncio
async def test_green_pulse_exits_zero_and_writes_ok(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    mock_cell = MagicMock()
    mock_result = MagicMock()
    mock_result.pulse_number = 1
    mock_result.health_status = "green"
    mock_result.action_taken = "none"
    mock_result.halted = False
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)

    assert await _run_one_pulse(lambda: mock_cell) == 0
    payload = _sidecar(tmp_path)
    assert payload["status"] == "ok"
    assert "note" not in payload


@pytest.mark.asyncio
async def test_red_pulse_exits_zero_and_writes_warning(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    mock_cell = MagicMock()
    mock_result = MagicMock()
    mock_result.pulse_number = 2
    mock_result.health_status = "red"
    mock_result.action_taken = None
    mock_result.halted = False
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)

    assert await _run_one_pulse(lambda: mock_cell) == 0
    payload = _sidecar(tmp_path)
    assert payload["status"] == "warning"
    assert payload["note"] == "pulse=red action=none pulse=2"


@pytest.mark.asyncio
async def test_red_pulse_action_is_reduced_to_one_note_token(tmp_path, monkeypatch) -> None:
    """An action with spaces, slashes or a newline cannot break the note shape receptor A matches."""
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    mock_cell = MagicMock()
    mock_result = MagicMock()
    mock_result.pulse_number = 4
    mock_result.health_status = "red"
    mock_result.action_taken = "no items/x\nTraceback"
    mock_result.halted = False
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)

    assert await _run_one_pulse(lambda: mock_cell) == 0
    note = _sidecar(tmp_path)["note"]
    assert re.fullmatch(r"pulse=red action=[A-Za-z0-9_.-]+ pulse=4", note), note


def test_organ_id_is_the_registry_entry_for_this_job() -> None:
    """The id the runner writes is the id the registry declares for Pro's hourly job (the drift #8157 cured)."""
    registry = Path(__file__).resolve().parents[3] / "apps" / "organism" / "organism" / "organs_registry.yaml"
    organs = yaml.safe_load(registry.read_text())["organs"]
    entry = next(o for o in organs if o["id"] == ORGAN_ID)
    assert ORGAN_ID == "mata_garuda.sentinel_hourly.pro"
    assert entry["runtime"] == "pro_launchd"
    assert entry["owner_module"] == "apps/mata-garuda/scripts/run_sentinel_cell.py"


@pytest.mark.asyncio
async def test_yellow_pulse_exits_zero_and_writes_ok(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    mock_cell = MagicMock()
    mock_result = MagicMock()
    mock_result.pulse_number = 3
    mock_result.health_status = "yellow"
    mock_result.action_taken = "none"
    mock_result.halted = False
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)

    assert await _run_one_pulse(lambda: mock_cell) == 0
    assert _sidecar(tmp_path)["status"] == "ok"


@pytest.mark.asyncio
async def test_exception_exits_one_and_writes_fail(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    mock_cell = MagicMock()
    mock_cell.single_pulse = AsyncMock(side_effect=RuntimeError("test error"))

    assert await _run_one_pulse(lambda: mock_cell) == 1
    payload = _sidecar(tmp_path)
    assert payload["status"] == "fail"
    assert "note" not in payload


@pytest.mark.asyncio
async def test_a_cell_that_cannot_be_built_exits_one_and_writes_fail(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))

    def broken_factory():
        raise RuntimeError("cell build failed")

    assert await _run_one_pulse(broken_factory) == 1
    assert _sidecar(tmp_path)["status"] == "fail"


@pytest.mark.parametrize("escape", [RuntimeError("loop died"), KeyboardInterrupt()])
def test_anything_escaping_the_pulse_still_writes_fail(tmp_path, monkeypatch, escape) -> None:
    import scripts.run_sentinel_cell as runner

    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["run_sentinel_cell.py"])

    def escaping_run(coro):
        coro.close()
        raise escape

    monkeypatch.setattr(runner.asyncio, "run", escaping_run)
    if isinstance(escape, KeyboardInterrupt):
        assert runner.main() == 130
    else:
        with pytest.raises(RuntimeError):
            runner.main()
    assert _sidecar(tmp_path)["status"] == "fail"
