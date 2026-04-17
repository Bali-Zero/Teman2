"""Tests for GoogleColabAdapter and GoogleCloudShellAdapter (S11)."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.services import google_cloud_shell_adapter as gcs_mod
from backend.agents.services import google_colab_adapter as colab_mod
from backend.agents.services.google_cloud_shell_adapter import (
    GoogleCloudShellAdapter,
    get_cloud_shell_adapter,
)
from backend.agents.services.google_colab_adapter import (
    GoogleColabAdapter,
    get_colab_adapter,
)


@pytest.fixture(autouse=True)
def _reset_singletons() -> None:
    colab_mod._colab_adapter = None
    gcs_mod._cloud_shell_adapter = None


class TestColabAdapter:
    def test_availability_true_when_pip_shows_package(self) -> None:
        with patch(
            "backend.agents.services.google_colab_adapter.subprocess.run",
            return_value=MagicMock(returncode=0),
        ):
            adapter = GoogleColabAdapter()
            assert adapter.available is True

    def test_availability_false_when_pip_missing(self) -> None:
        with patch(
            "backend.agents.services.google_colab_adapter.subprocess.run",
            side_effect=FileNotFoundError("pip not in PATH"),
        ):
            adapter = GoogleColabAdapter()
            assert adapter.available is False

    def test_availability_false_on_timeout(self) -> None:
        with patch(
            "backend.agents.services.google_colab_adapter.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=5),
        ):
            adapter = GoogleColabAdapter()
            assert adapter.available is False

    def test_check_availability_propagates_keyboard_interrupt(self) -> None:
        with patch(
            "backend.agents.services.google_colab_adapter.subprocess.run",
            side_effect=KeyboardInterrupt(),
        ):
            with pytest.raises(KeyboardInterrupt):
                GoogleColabAdapter()

    @pytest.mark.asyncio
    async def test_generate_raises_when_unavailable(self) -> None:
        with patch(
            "backend.agents.services.google_colab_adapter.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            adapter = GoogleColabAdapter()
        with pytest.raises(RuntimeError, match="Colab non disponibile"):
            await adapter.generate("hi")

    def test_singleton(self) -> None:
        with patch(
            "backend.agents.services.google_colab_adapter.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            a = get_colab_adapter()
            b = get_colab_adapter()
        assert a is b


class TestCloudShellAdapter:
    def test_availability_true_with_version_output(self) -> None:
        with patch(
            "backend.agents.services.google_cloud_shell_adapter.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=b"Google Cloud SDK 456.0\n"),
        ):
            adapter = GoogleCloudShellAdapter()
            assert adapter.available is True

    def test_availability_false_when_gcloud_missing(self) -> None:
        with patch(
            "backend.agents.services.google_cloud_shell_adapter.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            adapter = GoogleCloudShellAdapter()
            assert adapter.available is False

    def test_check_propagates_keyboard_interrupt(self) -> None:
        with patch(
            "backend.agents.services.google_cloud_shell_adapter.subprocess.run",
            side_effect=KeyboardInterrupt(),
        ):
            with pytest.raises(KeyboardInterrupt):
                GoogleCloudShellAdapter()

    @pytest.mark.asyncio
    async def test_generate_raises_when_unavailable(self) -> None:
        with patch(
            "backend.agents.services.google_cloud_shell_adapter.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            adapter = GoogleCloudShellAdapter()
        with pytest.raises(RuntimeError, match="Cloud Shell"):
            await adapter.generate("hi")

    def test_singleton(self) -> None:
        with patch(
            "backend.agents.services.google_cloud_shell_adapter.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            a = get_cloud_shell_adapter()
            b = get_cloud_shell_adapter()
        assert a is b
