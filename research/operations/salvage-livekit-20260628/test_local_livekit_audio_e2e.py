from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_e2e_module() -> ModuleType:
    backend_root = Path(__file__).resolve().parents[4]
    script_path = backend_root / "scripts" / "local_livekit_audio_e2e.py"
    spec = importlib.util.spec_from_file_location("local_livekit_audio_e2e_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_livekit_e2e_env_rejects_public_cloud_url(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_e2e_module()
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")

    with pytest.raises(module.E2EPreflightError, match="loopback"):
        module.validate_livekit_env()


def test_livekit_e2e_env_accepts_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_e2e_module()
    monkeypatch.setenv("LIVEKIT_URL", "ws://127.0.0.1:7880")
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")

    assert module.validate_livekit_env() == ("ws://127.0.0.1:7880", "devkey", "secret")


def test_livekit_e2e_requires_offline_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_e2e_module()
    for key in module.OFFLINE_ENV_GUARDS:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(module.E2EPreflightError, match="offline guard"):
        module.validate_offline_env()


def test_synthetic_input_wav_is_16bit_mono(tmp_path: Path) -> None:
    module = _load_e2e_module()
    wav_path = tmp_path / "synthetic.wav"

    module.write_synthetic_wav(wav_path, seconds=0.1, sample_rate=16_000)
    info = module.wav_info(wav_path)

    assert info.sample_rate == 16_000
    assert info.channels == 1
    assert info.sample_width == 2
    assert info.frames == 1600
    assert 0.09 < info.duration_seconds < 0.11


def test_livekit_e2e_keeps_provider_stdout_out_of_json(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    module = _load_e2e_module()

    async def fake_run_e2e(_args: object) -> dict[str, object]:
        print("provider noise")
        os.write(1, b"provider fd noise\n")
        return {"ok": True}

    monkeypatch.setattr(module, "run_e2e", fake_run_e2e)

    exit_code = module.main(["--json"])

    assert exit_code == 0
    captured = capfd.readouterr()
    assert json.loads(captured.out) == {"ok": True}
    assert "provider noise" in captured.err
    assert "provider fd noise" in captured.err
