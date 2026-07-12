from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_server_module() -> ModuleType:
    backend_root = Path(__file__).resolve().parents[4]
    script_path = backend_root / "scripts" / "run_local_livekit_server.py"
    spec = importlib.util.spec_from_file_location("run_local_livekit_server_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_livekit_server_command_uses_loopback_bind(tmp_path: Path) -> None:
    module = _load_server_module()
    binary = tmp_path / "livekit-server"

    command = module.build_livekit_server_command(binary=binary, bind_host="127.0.0.1")

    assert command == [str(binary), "--dev", "--bind", "127.0.0.1"]


def test_livekit_server_rejects_wildcard_bind() -> None:
    module = _load_server_module()

    with pytest.raises(module.PreflightError, match="loopback"):
        module.validate_loopback_bind("0.0.0.0")


def test_livekit_url_must_be_loopback() -> None:
    module = _load_server_module()

    with pytest.raises(module.PreflightError, match="loopback"):
        module.validate_livekit_url("wss://example.livekit.cloud", "127.0.0.1")


def test_livekit_url_accepts_loopback() -> None:
    module = _load_server_module()

    result = module.validate_livekit_url("ws://127.0.0.1:7880", "127.0.0.1")
    assert result is None

