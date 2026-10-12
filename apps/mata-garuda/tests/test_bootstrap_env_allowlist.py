"""Tests for the LaunchAgent environment bootstrap allow-list."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest


@pytest.fixture
def bootstrap_env_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[ModuleType]:
    """Load the bootstrap module with HOME isolated from real secret files.

    bootstrap_env writes os.environ directly (the imported key, its done flag,
    the canonical defaults); monkeypatch.delenv on an absent key records no
    undo, so the whole environment is restored here or the placeholder key
    leaks into later tests and lets them reach the real email sender.
    """
    saved = dict(os.environ)
    monkeypatch.setenv("HOME", str(tmp_path))
    yield importlib.import_module("mata_garuda._bootstrap_env")
    os.environ.clear()
    os.environ.update(saved)


def test_bootstrap_env_imports_allowed_brevo_key_only(
    bootstrap_env_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    brevo_key = "xkeysib-" + "placeholder"
    unrelated_value = "unrelated-" + "placeholder"
    secrets_path = tmp_path / "secrets.env"
    secrets_path.write_text(
        f"BREVO_API_KEY={brevo_key}\n"
        f"UNRELATED_SECRET={unrelated_value}\n"
    )
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    monkeypatch.delenv("UNRELATED_SECRET", raising=False)
    monkeypatch.delenv(bootstrap_env_module._DONE_FLAG, raising=False)

    bootstrap_env_module.bootstrap_env(secrets_path=secrets_path)

    assert bootstrap_env_module.os.environ["BREVO_API_KEY"] == brevo_key
    assert "UNRELATED_SECRET" not in bootstrap_env_module.os.environ


def test_bootstrap_env_preserves_existing_brevo_key(
    bootstrap_env_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    existing_key = "xkeysib-" + "existing-placeholder"
    secrets_path = tmp_path / "secrets.env"
    secrets_path.write_text("BREVO_API_KEY=" + "xkeysib-" + "file-placeholder\n")
    monkeypatch.setenv("BREVO_API_KEY", existing_key)
    monkeypatch.delenv(bootstrap_env_module._DONE_FLAG, raising=False)

    bootstrap_env_module.bootstrap_env(secrets_path=secrets_path)

    assert bootstrap_env_module.os.environ["BREVO_API_KEY"] == existing_key
