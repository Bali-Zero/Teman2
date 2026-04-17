"""Tests for WindsurfAdapter (S11 solidification)."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.services import windsurf_adapter as mod
from backend.agents.services.windsurf_adapter import WindsurfAdapter


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    mod._windsurf_adapter = None


def _ok_run(stdout: bytes = b"windsurf 1.0\n"):
    return MagicMock(returncode=0, stdout=stdout)


class TestWindsurfDiscovery:
    def test_find_windsurf_returns_first_working_path(self) -> None:
        with patch(
            "backend.agents.services.windsurf_adapter.os.path.exists", return_value=True,
        ), patch(
            "backend.agents.services.windsurf_adapter.subprocess.run",
            return_value=_ok_run(),
        ):
            adapter = WindsurfAdapter()
            assert adapter.windsurf_cmd.endswith("/windsurf") or adapter.windsurf_cmd == "windsurf"
            assert adapter.available is True

    def test_find_windsurf_tolerates_file_not_found(self) -> None:
        with patch(
            "backend.agents.services.windsurf_adapter.os.path.exists", return_value=False,
        ), patch(
            "backend.agents.services.windsurf_adapter.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            adapter = WindsurfAdapter()
            assert adapter.available is False

    def test_find_windsurf_tolerates_timeout(self) -> None:
        with patch(
            "backend.agents.services.windsurf_adapter.os.path.exists", return_value=True,
        ), patch(
            "backend.agents.services.windsurf_adapter.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="windsurf", timeout=5),
        ):
            adapter = WindsurfAdapter()
            assert adapter.available is False


class TestWindsurfOpenOps:
    def _make(self) -> WindsurfAdapter:
        with patch(
            "backend.agents.services.windsurf_adapter.os.path.exists", return_value=True,
        ), patch(
            "backend.agents.services.windsurf_adapter.subprocess.run", return_value=_ok_run(),
        ):
            return WindsurfAdapter()

    def test_open_file_returns_false_on_file_not_found(self) -> None:
        adapter = self._make()
        with patch(
            "backend.agents.services.windsurf_adapter.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            assert adapter.open_file("/tmp/x.py") is False

    def test_open_folder_returns_false_on_timeout(self) -> None:
        adapter = self._make()
        with patch(
            "backend.agents.services.windsurf_adapter.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="windsurf", timeout=10),
        ):
            assert adapter.open_folder("/tmp") is False

    def test_open_file_propagates_keyboard_interrupt(self) -> None:
        adapter = self._make()
        with patch(
            "backend.agents.services.windsurf_adapter.subprocess.run",
            side_effect=KeyboardInterrupt(),
        ):
            with pytest.raises(KeyboardInterrupt):
                adapter.open_file("/tmp/x.py")


@pytest.mark.asyncio
class TestGenerate:
    async def test_generate_raises_when_unavailable(self) -> None:
        with patch(
            "backend.agents.services.windsurf_adapter.os.path.exists", return_value=False,
        ), patch(
            "backend.agents.services.windsurf_adapter.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            adapter = WindsurfAdapter()
        with pytest.raises(RuntimeError, match="Windsurf not available"):
            await adapter.generate("hi")
