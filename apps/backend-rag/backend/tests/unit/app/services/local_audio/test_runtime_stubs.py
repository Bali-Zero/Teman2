import os
import subprocess
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.services.local_audio import chatterbox as chatterbox_module
from backend.app.services.local_audio import silero_vad as silero_vad_module
from backend.app.services.local_audio.chatterbox import ChatterboxTTSProvider
from backend.app.services.local_audio.runtime_checks import (
    MIN_CHATTERBOX_JSON_BYTES,
    MIN_CHATTERBOX_WEIGHT_BYTES,
)
from backend.app.services.local_audio.silero_vad import SileroVADProvider


def _write_sized_fixture(path: Path, size_bytes: int) -> None:
    path.write_bytes(b"0")
    with path.open("r+b") as handle:
        handle.truncate(size_bytes)


def _create_chatterbox_checkpoint(tmp_path: Path) -> Path:
    model_path = tmp_path / "chatterbox-model"
    model_path.mkdir()
    for filename in ("ve.pt", "s3gen.pt", "t3_mtl23ls_v3.safetensors"):
        _write_sized_fixture(model_path / filename, MIN_CHATTERBOX_WEIGHT_BYTES)
    _write_sized_fixture(
        model_path / "grapheme_mtl_merged_expanded_v1.json",
        MIN_CHATTERBOX_JSON_BYTES,
    )
    return model_path


def _create_chatterbox_hf_snapshot(tmp_path: Path) -> Path:
    snapshot_path = (
        tmp_path
        / "hf"
        / "hub"
        / "models--ResembleAI--chatterbox"
        / "snapshots"
        / "fixture"
    )
    snapshot_path.mkdir(parents=True)
    for filename in ("ve.pt", "s3gen.pt", "t3_mtl23ls_v3.safetensors"):
        _write_sized_fixture(snapshot_path / filename, MIN_CHATTERBOX_WEIGHT_BYTES)
    _write_sized_fixture(
        snapshot_path / "grapheme_mtl_merged_expanded_v1.json",
        MIN_CHATTERBOX_JSON_BYTES,
    )
    return snapshot_path


def _patch_chatterbox_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    import_error: BaseException | None = None,
) -> None:
    monkeypatch.setattr(
        "backend.app.services.local_audio.chatterbox.importlib.util.find_spec",
        lambda name: ModuleSpec(name=name, loader=None),
    )

    def fake_import_module(name: str):
        if name == "chatterbox.mtl_tts":
            if import_error is not None:
                raise import_error
            return SimpleNamespace(S3GEN_SR=24000)
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(
        "backend.app.services.local_audio.chatterbox.importlib.import_module",
        fake_import_module,
    )


def test_chatterbox_status_unavailable_when_runtime_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.local_audio.chatterbox.importlib.util.find_spec",
        lambda _name: None,
    )

    provider = ChatterboxTTSProvider()
    status = provider.status()

    assert status.available is False
    assert status.policy.allows_cloud_fallback is False
    assert "runtime not found" in status.detail


@pytest.mark.asyncio
async def test_chatterbox_synthesize_fails_closed_when_runtime_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.local_audio.chatterbox.importlib.util.find_spec",
        lambda _name: None,
    )

    provider = ChatterboxTTSProvider()

    with pytest.raises(RuntimeError, match="runtime not found"):
        await provider.synthesize("ciao")


def test_chatterbox_status_requires_local_model_path_when_cache_missing(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_chatterbox_runtime(monkeypatch)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "missing-hf"))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    provider = ChatterboxTTSProvider()

    status = provider.status()
    assert status.available is False
    assert status.detail == "local model path not configured and cache snapshot not found"


def test_chatterbox_status_discovers_local_huggingface_checkpoint(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_chatterbox_runtime(monkeypatch)
    snapshot_path = _create_chatterbox_hf_snapshot(tmp_path)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    provider = ChatterboxTTSProvider()

    status = provider.status()
    assert status.available is True
    assert status.detail == "ready"
    assert provider._resolve_model_path() == snapshot_path


def test_chatterbox_status_tolerates_huggingface_cache_race(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_chatterbox_runtime(monkeypatch)
    snapshot_root = (
        tmp_path
        / "hf"
        / "hub"
        / "models--ResembleAI--chatterbox"
        / "snapshots"
    )
    snapshot_root.mkdir(parents=True)
    original_iterdir = Path.iterdir

    def flaky_iterdir(path: Path):
        if path == snapshot_root:
            raise OSError("cache changed during discovery")
        return original_iterdir(path)

    monkeypatch.setattr(chatterbox_module, "_huggingface_hub_cache_dirs", lambda: [tmp_path / "hf" / "hub"])
    monkeypatch.setattr(Path, "iterdir", flaky_iterdir)

    provider = ChatterboxTTSProvider()

    status = provider.status()
    assert status.available is False
    assert status.detail == "local model path not configured and cache snapshot not found"


def test_chatterbox_status_rejects_incomplete_local_checkpoint(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_chatterbox_runtime(monkeypatch)

    provider = ChatterboxTTSProvider(model_path=tmp_path / "missing-model")

    status = provider.status()
    assert status.available is False
    assert "local model checkpoint incomplete" in status.detail


def test_chatterbox_status_rejects_tiny_local_checkpoint(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_chatterbox_runtime(monkeypatch)
    model_path = _create_chatterbox_checkpoint(tmp_path)
    (model_path / "s3gen.pt").write_bytes(b"tiny")

    provider = ChatterboxTTSProvider(model_path=model_path)

    status = provider.status()
    assert status.available is False
    assert "local model checkpoint invalid" in status.detail


def test_chatterbox_status_sanitizes_runtime_import_error(monkeypatch, tmp_path) -> None:
    _patch_chatterbox_runtime(
        monkeypatch,
        import_error=OSError("private failure at /tmp/client/audio"),
    )
    provider = ChatterboxTTSProvider(model_path=_create_chatterbox_checkpoint(tmp_path))

    status = provider.status()
    assert status.available is False
    assert status.detail == "runtime import failed: OSError"
    assert "/tmp/client" not in status.detail


def test_chatterbox_status_sanitizes_dependency_import_error(
    monkeypatch,
    tmp_path,
) -> None:
    def fake_find_spec(name: str):
        if name == "torch":
            raise OSError("private torch failure at /tmp/client/audio")
        return ModuleSpec(name=name, loader=None)

    monkeypatch.setattr(
        "backend.app.services.local_audio.chatterbox.importlib.util.find_spec",
        fake_find_spec,
    )
    monkeypatch.setattr(
        "backend.app.services.local_audio.chatterbox.importlib.import_module",
        lambda _name: SimpleNamespace(S3GEN_SR=24000),
    )
    provider = ChatterboxTTSProvider(model_path=_create_chatterbox_checkpoint(tmp_path))

    status = provider.status()
    assert status.available is False
    assert status.detail == "runtime dependency import failed: OSError"
    assert "/tmp/client" not in status.detail


def test_chatterbox_status_ready_with_importable_runtime_and_local_checkpoint(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_chatterbox_runtime(monkeypatch)

    provider = ChatterboxTTSProvider(model_path=_create_chatterbox_checkpoint(tmp_path))

    status = provider.status()
    assert status.available is True
    assert status.detail == "ready"


@pytest.mark.asyncio
async def test_chatterbox_detected_runtime_generates_local_wav(monkeypatch, tmp_path) -> None:
    _patch_chatterbox_runtime(monkeypatch)
    model_path = _create_chatterbox_checkpoint(tmp_path)
    calls: list[tuple[str, str, str, str, str, str]] = []

    async def fake_generate(
        text: str,
        output_path: Path,
        *,
        module_name: str,
        model_path: Path | None,
        t3_model: str,
        language_id: str,
        timeout_seconds: float,
    ) -> None:
        assert model_path is not None
        calls.append(
            (text, output_path.name, module_name, model_path.name, t3_model, language_id)
        )
        assert timeout_seconds == 7.0
        output_path.write_bytes(b"local wav")

    provider = ChatterboxTTSProvider(
        module_name="chatterbox",
        model_path=model_path,
        t3_model="v3",
        language_id="en",
        timeout_seconds=7.0,
        generator=fake_generate,
    )
    output_path = tmp_path / "out.wav"

    result = await provider.synthesize(" ciao ", voice="it", output_path=output_path)

    assert calls == [("ciao", "out.wav", "chatterbox", "chatterbox-model", "v3", "it")]
    assert result.audio_bytes is None
    assert result.audio_path == output_path
    assert result.mime_type == "audio/wav"
    assert result.provider == "chatterbox-v3"
    assert output_path.read_bytes() == b"local wav"


@pytest.mark.asyncio
async def test_chatterbox_maps_indonesian_to_nearest_local_language(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_chatterbox_runtime(monkeypatch)
    model_path = _create_chatterbox_checkpoint(tmp_path)
    calls: list[str] = []

    async def fake_generate(
        text: str,
        output_path: Path,
        *,
        module_name: str,
        model_path: Path | None,
        t3_model: str,
        language_id: str,
        timeout_seconds: float,
    ) -> None:
        calls.append(language_id)
        output_path.write_bytes(b"local wav")

    provider = ChatterboxTTSProvider(
        model_path=model_path,
        generator=fake_generate,
    )

    await provider.synthesize("halo", voice="id", output_path=tmp_path / "out.wav")

    assert calls == ["ms"]


@pytest.mark.asyncio
async def test_chatterbox_synthesize_uses_discovered_huggingface_checkpoint(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_chatterbox_runtime(monkeypatch)
    snapshot_path = _create_chatterbox_hf_snapshot(tmp_path)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    calls: list[Path] = []

    async def fake_generate(
        text: str,
        output_path: Path,
        *,
        module_name: str,
        model_path: Path | None,
        t3_model: str,
        language_id: str,
        timeout_seconds: float,
    ) -> None:
        assert text == "ciao"
        assert module_name == "chatterbox"
        assert model_path == snapshot_path
        assert t3_model == "v3"
        assert language_id == "it"
        assert timeout_seconds == 60.0
        calls.append(model_path)
        output_path.write_bytes(b"local wav")

    provider = ChatterboxTTSProvider(generator=fake_generate)
    output_path = tmp_path / "out.wav"

    result = await provider.synthesize(" ciao ", voice="it", output_path=output_path)

    assert calls == [snapshot_path]
    assert result.audio_path == output_path
    assert output_path.read_bytes() == b"local wav"


def test_chatterbox_model_loader_uses_local_checkpoint_and_v3_selector(
    monkeypatch,
    tmp_path,
) -> None:
    for key in (
        "DO_NOT_TRACK",
        "HF_DATASETS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
    ):
        monkeypatch.delenv(key, raising=False)

    model_path = _create_chatterbox_checkpoint(tmp_path)
    calls: list[tuple[str, str, str]] = []
    fake_model = object()

    class FakeChatterboxMultilingualTTS:
        @staticmethod
        def from_local(path: Path, *, device: str, t3_model: str):
            assert os.environ["DO_NOT_TRACK"] == "1"
            assert os.environ["HF_DATASETS_OFFLINE"] == "1"
            assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
            assert os.environ["HF_HUB_OFFLINE"] == "1"
            assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
            calls.append((Path(path).name, device, t3_model))
            return fake_model

    fake_torch = SimpleNamespace(
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
        cuda=SimpleNamespace(is_available=lambda: False),
    )

    def fake_import_module(name: str):
        if name == "torch":
            return fake_torch
        if name == "chatterbox.mtl_tts":
            return SimpleNamespace(
                ChatterboxMultilingualTTS=FakeChatterboxMultilingualTTS,
            )
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(chatterbox_module.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(chatterbox_module, "_CHATTERBOX_MODEL", None)
    monkeypatch.setattr(chatterbox_module, "_CHATTERBOX_MODEL_KEY", None)

    model = chatterbox_module._get_chatterbox_model("chatterbox", model_path, "v3")

    assert model is fake_model
    assert calls == [("chatterbox-model", "cpu", "v3")]
    assert "HF_HUB_OFFLINE" not in os.environ


def test_chatterbox_process_timeout_terminates_child(monkeypatch, tmp_path) -> None:
    events: list[str] = []

    class FakeReceiver:
        def poll(self) -> bool:
            return False

        def close(self) -> None:
            events.append("receiver.close")

    class FakeSender:
        def close(self) -> None:
            events.append("sender.close")

    class FakeProcess:
        daemon = False
        exitcode = None

        def __init__(self, *args, **kwargs) -> None:
            self.terminated = False

        def start(self) -> None:
            events.append("process.start")

        def join(self, timeout=None) -> None:
            events.append(f"process.join:{timeout}")

        def is_alive(self) -> bool:
            return not self.terminated

        def terminate(self) -> None:
            self.terminated = True
            events.append("process.terminate")

        def kill(self) -> None:
            events.append("process.kill")

    class FakeContext:
        def Pipe(self, *, duplex: bool) -> tuple[FakeReceiver, FakeSender]:
            assert duplex is False
            return FakeReceiver(), FakeSender()

        def Queue(self, *args, **kwargs) -> None:
            raise AssertionError("Chatterbox process IPC must use Pipe, not Queue")

        def Process(self, *args, **kwargs) -> FakeProcess:
            return FakeProcess()

    monkeypatch.setattr(chatterbox_module.mp, "get_context", lambda _name: FakeContext())

    with pytest.raises(TimeoutError, match="timed out"):
        chatterbox_module._run_chatterbox_generation_process(
            "ciao",
            tmp_path / "out.wav",
            module_name="chatterbox",
            model_path=tmp_path / "model",
            t3_model="v3",
            language_id="en",
            timeout_seconds=0.01,
        )

    assert "process.terminate" in events
    assert "receiver.close" in events
    assert "sender.close" in events


def test_chatterbox_process_missing_pipe_payload_is_sanitized(
    monkeypatch,
    tmp_path,
) -> None:
    class FakeReceiver:
        def poll(self) -> bool:
            return True

        def recv(self):
            raise EOFError

        def close(self) -> None:
            pass

    class FakeSender:
        def close(self) -> None:
            pass

    class FakeProcess:
        daemon = False
        exitcode = 0

        def start(self) -> None:
            pass

        def join(self, timeout=None) -> None:
            pass

        def is_alive(self) -> bool:
            return False

    class FakeContext:
        def Pipe(self, *, duplex: bool) -> tuple[FakeReceiver, FakeSender]:
            assert duplex is False
            return FakeReceiver(), FakeSender()

        def Process(self, *args, **kwargs) -> FakeProcess:
            return FakeProcess()

    monkeypatch.setattr(chatterbox_module.mp, "get_context", lambda _name: FakeContext())

    with pytest.raises(RuntimeError, match="exited without result: 0"):
        chatterbox_module._run_chatterbox_generation_process(
            "ciao",
            tmp_path / "out.wav",
            module_name="chatterbox",
            model_path=tmp_path / "model",
            t3_model="v3",
            language_id="en",
            timeout_seconds=0.01,
        )


def test_silero_status_unavailable_when_runtime_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.util.find_spec",
        lambda _name: None,
    )

    provider = SileroVADProvider()
    status = provider.status()

    assert status.available is False
    assert status.policy.pii_boundary == "local_only"
    assert "runtime not found" in status.detail


@pytest.mark.asyncio
async def test_silero_detect_segments_fails_closed_when_runtime_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.util.find_spec",
        lambda _name: None,
    )

    provider = SileroVADProvider()

    with pytest.raises(RuntimeError, match="runtime not found"):
        await provider.detect_segments(Path("/tmp/sample.wav"))


def test_silero_status_is_static_and_does_not_load_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.util.find_spec",
        lambda name: ModuleSpec(name=name, loader=None),
    )
    calls: list[str] = []

    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.import_module",
        lambda name: calls.append(name),
    )
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL", None)
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL_KEY", None)

    provider = SileroVADProvider()

    status = provider.status()
    assert status.available is True
    assert status.detail == "runtime import ready"
    assert calls == []


def test_silero_warm_status_unavailable_when_model_load_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.util.find_spec",
        lambda name: ModuleSpec(name=name, loader=None),
    )

    def fake_import_module(_name: str):
        def fail_load() -> object:
            raise RuntimeError("network unavailable")

        return SimpleNamespace(load_silero_vad=fail_load)

    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.import_module",
        fake_import_module,
    )
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL", None)
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL_KEY", None)

    provider = SileroVADProvider()

    status = provider.warm_status()
    assert status.available is False
    assert status.detail == "runtime model load failed: RuntimeError"


def test_silero_warm_status_validates_runtime_model_load(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.util.find_spec",
        lambda name: ModuleSpec(name=name, loader=None),
    )
    calls: list[str] = []
    fake_model = object()

    def fake_import_module(name: str):
        calls.append(name)
        return SimpleNamespace(load_silero_vad=lambda: fake_model)

    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.import_module",
        fake_import_module,
    )
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL", None)
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL_KEY", None)

    provider = SileroVADProvider()

    status = provider.warm_status()
    assert status.available is True
    assert status.detail == "runtime model ready"
    assert calls == ["silero_vad"]


@pytest.mark.asyncio
async def test_silero_detected_runtime_returns_speech_segments(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.util.find_spec",
        lambda name: ModuleSpec(name=name, loader=None),
    )
    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.import_module",
        lambda _name: SimpleNamespace(load_silero_vad=lambda: object()),
    )
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL", None)
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL_KEY", None)
    calls: list[tuple[str, str, int, float, float]] = []

    def fake_process_runner(
        audio_path: Path,
        *,
        module_name: str,
        sampling_rate: int,
        threshold: float,
        timeout_seconds: float,
    ) -> list[tuple[float, float]]:
        calls.append(
            (
                str(audio_path),
                module_name,
                sampling_rate,
                threshold,
                timeout_seconds,
            )
        )
        return [(0.12, 0.88)]

    monkeypatch.setattr(
        silero_vad_module,
        "_run_silero_detection_process",
        fake_process_runner,
    )

    provider = SileroVADProvider(
        sampling_rate=16000,
        threshold=0.42,
        timeout_seconds=3.0,
    )

    segments = await provider.detect_segments(Path("/tmp/sample.wav"))

    assert segments[0].start_seconds == 0.12
    assert segments[0].end_seconds == 0.88
    assert calls == [("/tmp/sample.wav", "silero_vad", 16000, 0.42, 3.0)]


def test_silero_current_process_runtime_maps_speech_segments(monkeypatch) -> None:
    calls: list[tuple[str, int, float]] = []
    fake_model = object()

    def fake_import_module(_name: str):
        return SimpleNamespace(
            load_silero_vad=lambda: fake_model,
            read_audio=lambda path, *, sampling_rate: (path, sampling_rate),
            get_speech_timestamps=lambda wav, model, **kwargs: _fake_timestamps(
                wav,
                model,
                kwargs,
                calls,
            ),
        )

    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.import_module",
        fake_import_module,
    )
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL", None)
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL_KEY", None)

    segments = silero_vad_module._detect_silero_segments_in_current_process(
        audio_path=Path("/tmp/sample.wav"),
        module_name="silero_vad",
        sampling_rate=16000,
        threshold=0.42,
    )

    assert segments == [(0.12, 0.88)]
    assert calls == [("/tmp/sample.wav", 16000, 0.42)]


def test_silero_current_process_forces_offline_runtime_env(monkeypatch) -> None:
    snapshots: list[dict[str, str | None]] = []
    fake_model = object()

    def snapshot() -> None:
        snapshots.append(
            {
                "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
                "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
                "HF_HUB_DISABLE_TELEMETRY": os.environ.get(
                    "HF_HUB_DISABLE_TELEMETRY"
                ),
            }
        )

    def fake_import_module(_name: str):
        return SimpleNamespace(
            load_silero_vad=lambda: (snapshot(), fake_model)[1],
            read_audio=lambda path, *, sampling_rate: (
                snapshot(),
                (path, sampling_rate),
            )[1],
            get_speech_timestamps=lambda *_args, **_kwargs: (
                snapshot(),
                [],
            )[1],
        )

    monkeypatch.setattr(
        "backend.app.services.local_audio.silero_vad.importlib.import_module",
        fake_import_module,
    )
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL", None)
    monkeypatch.setattr(silero_vad_module, "_SILERO_MODEL_KEY", None)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    monkeypatch.delenv("HF_HUB_DISABLE_TELEMETRY", raising=False)

    segments = silero_vad_module._detect_silero_segments_in_current_process(
        audio_path=Path("/tmp/sample.wav"),
        module_name="silero_vad",
        sampling_rate=16000,
        threshold=0.42,
    )

    assert segments == []
    assert snapshots == [
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        },
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        },
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        },
    ]


def test_silero_process_timeout_terminates_child(monkeypatch) -> None:
    events: list[str] = []

    class FakeReceiver:
        def poll(self) -> bool:
            return False

        def close(self) -> None:
            events.append("receiver.close")

    class FakeSender:
        def close(self) -> None:
            events.append("sender.close")

    class FakeProcess:
        daemon = False
        exitcode = None

        def __init__(self, *args, **kwargs) -> None:
            self.terminated = False

        def start(self) -> None:
            events.append("process.start")

        def join(self, timeout=None) -> None:
            events.append(f"process.join:{timeout}")

        def is_alive(self) -> bool:
            return not self.terminated

        def terminate(self) -> None:
            self.terminated = True
            events.append("process.terminate")

        def kill(self) -> None:
            events.append("process.kill")

    class FakeContext:
        def Pipe(self, *, duplex: bool) -> tuple[FakeReceiver, FakeSender]:
            assert duplex is False
            return FakeReceiver(), FakeSender()

        def Queue(self, *args, **kwargs) -> None:
            raise AssertionError("Silero process IPC must use Pipe, not Queue")

        def Process(self, *args, **kwargs) -> FakeProcess:
            return FakeProcess()

    monkeypatch.setattr(silero_vad_module.mp, "get_context", lambda _name: FakeContext())

    with pytest.raises(TimeoutError, match="timed out"):
        silero_vad_module._run_silero_detection_process(
            Path("/tmp/sample.wav"),
            module_name="silero_vad",
            sampling_rate=16000,
            threshold=0.5,
            timeout_seconds=0.01,
        )

    assert "process.terminate" in events
    assert "receiver.close" in events
    assert "sender.close" in events


def test_silero_process_missing_pipe_payload_is_sanitized(monkeypatch) -> None:
    class FakeReceiver:
        def poll(self) -> bool:
            return True

        def recv(self):
            raise EOFError

        def close(self) -> None:
            pass

    class FakeSender:
        def close(self) -> None:
            pass

    class FakeProcess:
        daemon = False
        exitcode = 0

        def start(self) -> None:
            pass

        def join(self, timeout=None) -> None:
            pass

        def is_alive(self) -> bool:
            return False

    class FakeContext:
        def Pipe(self, *, duplex: bool) -> tuple[FakeReceiver, FakeSender]:
            assert duplex is False
            return FakeReceiver(), FakeSender()

        def Process(self, *args, **kwargs) -> FakeProcess:
            return FakeProcess()

    monkeypatch.setattr(silero_vad_module.mp, "get_context", lambda _name: FakeContext())

    with pytest.raises(RuntimeError, match="exited without result: 0"):
        silero_vad_module._run_silero_detection_process(
            Path("/tmp/sample.wav"),
            module_name="silero_vad",
            sampling_rate=16000,
            threshold=0.5,
            timeout_seconds=0.01,
        )


def test_optional_silero_runtime_import_smoke() -> None:
    if os.environ.get("VOICE_CONCIERGE_RUNTIME_SMOKE") != "1":
        pytest.skip("set VOICE_CONCIERGE_RUNTIME_SMOKE=1 to run local runtime smoke")

    script = """
import importlib.metadata as md
import silero_vad
import torch
import torchaudio

assert hasattr(silero_vad, "load_silero_vad")
assert hasattr(silero_vad, "read_audio")
assert hasattr(silero_vad, "get_speech_timestamps")
print("torch", torch.__version__)
print("torchaudio", torchaudio.__version__)
print("silero-vad", md.version("silero-vad"))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def _fake_timestamps(
    wav: tuple[str, int],
    model: object,
    kwargs: dict,
    calls: list[tuple[str, int, float]],
) -> list[dict[str, float]]:
    calls.append((wav[0], kwargs["sampling_rate"], kwargs["threshold"]))
    assert model is silero_vad_module._SILERO_MODEL
    assert kwargs["return_seconds"] is True
    return [{"start": 0.12, "end": 0.88}]
