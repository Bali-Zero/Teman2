from __future__ import annotations

from importlib.machinery import ModuleSpec
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.services.local_audio import readiness


def _make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)


def _write_sized_fixture(path: Path, size_bytes: int) -> None:
    path.write_bytes(b"0")
    with path.open("r+b") as handle:
        handle.truncate(size_bytes)


def _create_chatterbox_checkpoint(tmp_path: Path) -> Path:
    model_path = tmp_path / "chatterbox-model"
    model_path.mkdir()
    for filename in (
        "ve.pt",
        "s3gen.pt",
        "t3_mtl23ls_v3.safetensors",
    ):
        _write_sized_fixture(model_path / filename, readiness.MIN_CHATTERBOX_WEIGHT_BYTES)
    _write_sized_fixture(
        model_path / "grapheme_mtl_merged_expanded_v1.json",
        readiness.MIN_CHATTERBOX_JSON_BYTES,
    )
    return model_path


def _settings(
    tmp_path: Path,
    *,
    whisper_model_name: str = "ggml-large-v3-turbo.bin",
    local_audio_enabled: bool = True,
    audio_max_bytes: int = 10 * 1024 * 1024,
) -> SimpleNamespace:
    binary = tmp_path / "whisper-cli"
    model = tmp_path / whisper_model_name
    checkpoint = _create_chatterbox_checkpoint(tmp_path)
    _make_executable(binary)
    _write_sized_fixture(model, readiness.MIN_WHISPER_MODEL_BYTES)

    return SimpleNamespace(
        voice_concierge_local_audio_enabled=local_audio_enabled,
        voice_concierge_local_audio=False,
        voice_concierge_whisper_binary=str(binary),
        voice_concierge_whisper_model=str(model),
        voice_concierge_whisper_timeout_seconds=30.0,
        voice_concierge_audio_max_bytes=audio_max_bytes,
        voice_concierge_tts_max_chars=1200,
        voice_concierge_tts_audio_max_bytes=10 * 1024 * 1024,
        voice_concierge_chatterbox_module="chatterbox",
        voice_concierge_chatterbox_model_path=str(checkpoint),
        voice_concierge_chatterbox_t3_model="v3",
        voice_concierge_chatterbox_language="en",
        voice_concierge_chatterbox_timeout_seconds=60.0,
        voice_concierge_silero_module="silero_vad",
        voice_concierge_silero_sampling_rate=16000,
        voice_concierge_silero_threshold=0.5,
        voice_concierge_silero_timeout_seconds=15.0,
    )


@pytest.fixture(autouse=True)
def _patch_import_specs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        readiness.importlib.util,
        "find_spec",
        lambda name: ModuleSpec(name=name, loader=None),
    )


@pytest.fixture
def _offline_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in readiness.OFFLINE_ENV_GUARDS.items():
        monkeypatch.setenv(key, value)


def _check(report: readiness.ReadinessReport, name: str) -> readiness.ReadinessCheck:
    return report.check(name)


def test_static_readiness_passes_for_complete_local_stack(
    tmp_path: Path,
    _offline_env: None,
) -> None:
    report = readiness.build_local_audio_readiness_report(
        mode="static",
        settings=_settings(tmp_path),
        hostname="Nuzantara",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is True
    assert _check(report, "local_audio_enabled").status == "pass"
    assert _check(report, "whisper_model_quality").status == "pass"
    assert _check(report, "chatterbox_checkpoint").status == "pass"
    assert _check(report, "silero_import").status == "pass"


def test_static_readiness_accepts_dotted_mini_hostname(
    tmp_path: Path,
    _offline_env: None,
) -> None:
    report = readiness.build_local_audio_readiness_report(
        mode="static",
        settings=_settings(tmp_path),
        hostname="Mini-Pro2.local",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is True
    assert _check(report, "host_role").status == "pass"
    assert _check(report, "host_role").metadata["normalized_hostname"] == "Mini-Pro2"


def test_static_readiness_requires_whisper_large_v3_turbo(tmp_path: Path) -> None:
    report = readiness.build_local_audio_readiness_report(
        mode="static",
        settings=_settings(tmp_path, whisper_model_name="ggml-small.bin"),
        hostname="Nuzantara",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is False
    assert _check(report, "whisper_model_quality").status == "fail"
    assert "large-v3-turbo" in _check(report, "whisper_model_quality").detail


def test_static_readiness_rejects_tiny_whisper_model(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    Path(settings.voice_concierge_whisper_model).write_bytes(b"not-a-model")

    report = readiness.build_local_audio_readiness_report(
        mode="static",
        settings=settings,
        hostname="Nuzantara",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is False
    assert _check(report, "whisper_model").status == "fail"
    assert "too small" in _check(report, "whisper_model").detail


def test_static_readiness_rejects_tiny_chatterbox_checkpoint(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    Path(settings.voice_concierge_chatterbox_model_path, "s3gen.pt").write_bytes(b"tiny")

    report = readiness.build_local_audio_readiness_report(
        mode="static",
        settings=settings,
        hostname="Nuzantara",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is False
    assert _check(report, "chatterbox_checkpoint").status == "fail"
    assert "not plausible" in _check(report, "chatterbox_checkpoint").detail


def test_static_readiness_sanitizes_chatterbox_import_spec_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_find_spec(name: str):
        if name == "chatterbox.mtl_tts":
            raise OSError("private failure at /tmp/client/audio")
        return ModuleSpec(name=name, loader=None)

    monkeypatch.setattr(readiness.importlib.util, "find_spec", fake_find_spec)

    report = readiness.build_local_audio_readiness_report(
        mode="static",
        settings=_settings(tmp_path),
        hostname="Nuzantara",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is False
    assert _check(report, "chatterbox_import").status == "fail"
    assert _check(report, "chatterbox_import").detail == (
        "module spec lookup failed for chatterbox.mtl_tts: OSError"
    )
    assert "/tmp/client" not in _check(report, "chatterbox_import").detail


def test_static_readiness_does_not_load_deep_runtime_providers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class ExplodingSilero:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("static readiness must not instantiate Silero")

    class ExplodingWhisper:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("static readiness must not instantiate Whisper")

    class ExplodingChatterbox:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("static readiness must not instantiate Chatterbox")

    monkeypatch.setattr(readiness, "SileroVADProvider", ExplodingSilero)
    monkeypatch.setattr(readiness, "WhisperCppSTTProvider", ExplodingWhisper)
    monkeypatch.setattr(readiness, "ChatterboxTTSProvider", ExplodingChatterbox)

    report = readiness.build_local_audio_readiness_report(
        mode="static",
        settings=_settings(tmp_path),
        hostname="Nuzantara",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is True


def test_deep_readiness_fails_without_offline_guards_before_provider_load(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class ExplodingProvider:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("deep readiness must not load providers when static gate fails")

    for key in readiness.OFFLINE_ENV_GUARDS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(readiness, "SileroVADProvider", ExplodingProvider)
    monkeypatch.setattr(readiness, "WhisperCppSTTProvider", ExplodingProvider)
    monkeypatch.setattr(readiness, "ChatterboxTTSProvider", ExplodingProvider)

    report = readiness.build_local_audio_readiness_report(
        mode="deep",
        settings=_settings(tmp_path),
        hostname="Nuzantara",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is False
    assert _check(report, "offline_env").status == "fail"
    assert _check(report, "deep_static_gate").status == "fail"


def test_deep_readiness_fails_on_air_without_loading_runtime_providers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class ExplodingProvider:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("Air-M5 must not run deep provider checks")

    monkeypatch.setattr(readiness, "SileroVADProvider", ExplodingProvider)
    monkeypatch.setattr(readiness, "WhisperCppSTTProvider", ExplodingProvider)
    monkeypatch.setattr(readiness, "ChatterboxTTSProvider", ExplodingProvider)

    report = readiness.build_local_audio_readiness_report(
        mode="deep",
        settings=_settings(tmp_path),
        hostname="Air-M5",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is False
    assert _check(report, "host_role").status == "fail"
    with pytest.raises(KeyError):
        report.check("whisper_binary")


def test_static_readiness_fails_invalid_audio_caps(tmp_path: Path) -> None:
    report = readiness.build_local_audio_readiness_report(
        mode="static",
        settings=_settings(tmp_path, audio_max_bytes=0),
        hostname="Nuzantara",
        python_prefix="/tmp/venv",
        python_base_prefix="/usr",
    )

    assert report.ok is False
    assert _check(report, "capacity_limits").status == "fail"
