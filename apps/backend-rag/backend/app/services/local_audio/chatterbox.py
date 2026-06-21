"""Chatterbox provider for local-first text-to-speech."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import multiprocessing as mp
import os
import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

from backend.app.services.local_audio import LocalTTSProvider, ProviderStatus, TTSResult
from backend.app.services.local_audio.runtime_checks import (
    invalid_chatterbox_checkpoint_files,
)
from backend.app.services.local_audio.runtime_checks import (
    missing_chatterbox_checkpoint_files as _runtime_missing_checkpoint_files,
)
from backend.app.services.local_audio.runtime_checks import (
    resolve_chatterbox_t3_model_file as _runtime_resolve_t3_model_file,
)

EMMA_SEED = 42
EMMA_CFG_WEIGHT = 0.30
EMMA_TEMPERATURE = 0.70
EMMA_EXAGGERATION = 0.32
_CHATTERBOX_HF_REPO_CACHE_DIR = "models--ResembleAI--chatterbox"
_OFFLINE_RUNTIME_ENV = {
    "DO_NOT_TRACK": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
}
_LANGUAGE_ID_ALIASES = {
    "bahasa": "ms",
    "bahasa-indonesia": "ms",
    "id": "ms",
    "in": "ms",
    "indonesian": "ms",
}

_CHATTERBOX_MODEL: Any | None = None
_CHATTERBOX_MODEL_KEY: tuple[str, str, str, str] | None = None
_CHATTERBOX_PROCESS_SEMAPHORE = threading.BoundedSemaphore(value=1)


class ChatterboxGenerator(Protocol):
    async def __call__(
        self,
        text: str,
        output_path: Path,
        *,
        module_name: str,
        model_path: Path | None,
        t3_model: str,
        language_id: str,
        timeout_seconds: float,
    ) -> None:
        """Generate a local WAV file."""


class ChatterboxTTSProvider(LocalTTSProvider):
    """Local TTS provider backed by Chatterbox's Python API."""

    name = "chatterbox-v3"

    def __init__(
        self,
        *,
        module_name: str = "chatterbox",
        model_path: Path | None = None,
        t3_model: str = "v3",
        language_id: str = "en",
        timeout_seconds: float = 60.0,
        generator: ChatterboxGenerator | None = None,
    ) -> None:
        self.module_name = module_name
        self.model_path = Path(model_path) if model_path is not None else None
        self.t3_model = t3_model
        self.language_id = language_id
        self.timeout_seconds = timeout_seconds
        self.generator = generator or _generate_chatterbox_wav

    def status(self) -> ProviderStatus:
        module_spec, module_spec_error = _safe_find_spec(self.module_name)
        if module_spec_error is not None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"runtime import failed: {type(module_spec_error).__name__}",
                policy=self.policy,
            )
        if module_spec is None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"runtime not found: {self.module_name}",
                policy=self.policy,
            )
        mtl_spec, mtl_spec_error = _safe_find_spec(f"{self.module_name}.mtl_tts")
        if mtl_spec_error is not None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"runtime import failed: {type(mtl_spec_error).__name__}",
                policy=self.policy,
            )
        if mtl_spec is None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"runtime module not found: {self.module_name}.mtl_tts",
                policy=self.policy,
            )
        import_error = _runtime_import_error(self.module_name)
        if import_error is not None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"runtime import failed: {type(import_error).__name__}",
                policy=self.policy,
            )
        soundfile_spec, soundfile_spec_error = _safe_find_spec("soundfile")
        if soundfile_spec_error is not None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"runtime dependency import failed: {type(soundfile_spec_error).__name__}",
                policy=self.policy,
            )
        if soundfile_spec is None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="runtime dependency not found: soundfile",
                policy=self.policy,
            )
        torch_spec, torch_spec_error = _safe_find_spec("torch")
        if torch_spec_error is not None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"runtime dependency import failed: {type(torch_spec_error).__name__}",
                policy=self.policy,
            )
        if torch_spec is None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="runtime dependency not found: torch",
                policy=self.policy,
            )
        model_path = self._resolve_model_path()
        if model_path is None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="local model path not configured and cache snapshot not found",
                policy=self.policy,
            )
        missing_files = _missing_checkpoint_files(model_path, self.t3_model)
        if missing_files:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"local model checkpoint incomplete: {missing_files[0]}",
                policy=self.policy,
            )
        invalid_files = invalid_chatterbox_checkpoint_files(model_path, self.t3_model)
        if invalid_files:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"local model checkpoint invalid: {invalid_files[0]}",
                policy=self.policy,
            )
        return ProviderStatus(
            name=self.name,
            available=True,
            detail="ready",
            policy=self.policy,
        )

    def warm_status(self) -> ProviderStatus:
        status = self.status()
        if not status.available:
            return status

        model_path = self._resolve_model_path()
        if model_path is None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="local model path not configured and cache snapshot not found",
                policy=self.policy,
            )

        try:
            _get_chatterbox_model(self.module_name, model_path, self.t3_model)
        except BaseException as exc:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"model load failed: {type(exc).__name__}",
                policy=self.policy,
            )

        return ProviderStatus(
            name=self.name,
            available=True,
            detail="model load ready",
            policy=self.policy,
        )

    def _resolve_model_path(self) -> Path | None:
        if self.model_path is not None:
            return self.model_path
        return _find_local_huggingface_checkpoint(self.t3_model)

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        output_path: Path | None = None,
    ) -> TTSResult:
        text_value = text.strip()
        if not text_value:
            raise RuntimeError("text required for Chatterbox synthesis")

        model_path = self._resolve_model_path()
        status = self.status()
        if not status.available:
            raise RuntimeError(status.detail)
        if model_path is None:
            raise RuntimeError("local model path not configured and cache snapshot not found")
        if output_path is None:
            raise RuntimeError("output_path required for Chatterbox synthesis")

        target_path = Path(output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        language_id = _normalize_language_id(
            voice.strip() if voice and voice.strip() else self.language_id,
        )
        await self.generator(
            text_value,
            target_path,
            module_name=self.module_name,
            model_path=model_path,
            t3_model=self.t3_model,
            language_id=language_id,
            timeout_seconds=self.timeout_seconds,
        )
        return TTSResult(
            audio_bytes=None,
            audio_path=target_path,
            mime_type="audio/wav",
            provider=self.name,
        )


async def _generate_chatterbox_wav(
    text: str,
    output_path: Path,
    *,
    module_name: str,
    model_path: Path | None,
    t3_model: str,
    language_id: str,
    timeout_seconds: float,
) -> None:
    if model_path is None:
        raise RuntimeError("local model path not configured")

    await asyncio.to_thread(
        _run_chatterbox_generation_process,
        text,
        output_path,
        module_name=module_name,
        model_path=Path(model_path),
        t3_model=t3_model,
        language_id=language_id,
        timeout_seconds=timeout_seconds,
    )


def _run_chatterbox_generation_process(
    text: str,
    output_path: Path,
    *,
    module_name: str,
    model_path: Path,
    t3_model: str,
    language_id: str,
    timeout_seconds: float,
) -> None:
    if timeout_seconds <= 0:
        raise TimeoutError("Chatterbox generate timeout must be positive")

    acquired = _CHATTERBOX_PROCESS_SEMAPHORE.acquire(timeout=timeout_seconds)
    if not acquired:
        raise TimeoutError("Chatterbox generate concurrency limit reached")

    context = mp.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_run_chatterbox_generation_child,
        args=(
            result_queue,
            text,
            str(output_path),
            module_name,
            str(model_path),
            t3_model,
            language_id,
        ),
    )
    process.daemon = True

    try:
        process.start()
        process.join(timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=1.0)
            raise TimeoutError(f"Chatterbox generate timed out after {timeout_seconds}s")

        try:
            result = result_queue.get_nowait()
        except queue.Empty as exc:
            exit_code = process.exitcode
            raise RuntimeError(
                f"Chatterbox generate process exited without result: {exit_code}",
            ) from exc

        status = result[0]
        if status == "ok":
            return
        if status == "error":
            raise RuntimeError(f"Chatterbox generate failed: {result[1]}")
        raise RuntimeError("Chatterbox generate returned an invalid result")
    finally:
        result_queue.close()
        result_queue.join_thread()
        _CHATTERBOX_PROCESS_SEMAPHORE.release()


def _run_chatterbox_generation_child(
    result_queue: Any,
    text: str,
    output_path: str,
    module_name: str,
    model_path: str,
    t3_model: str,
    language_id: str,
) -> None:
    try:
        _generate_chatterbox_wav_in_current_process(
            text=text,
            output_path=Path(output_path),
            module_name=module_name,
            model_path=Path(model_path),
            t3_model=t3_model,
            language_id=language_id,
        )
        result_queue.put(("ok", None))
    except BaseException as exc:
        result_queue.put(("error", type(exc).__name__))


def _generate_chatterbox_wav_in_current_process(
    *,
    text: str,
    output_path: Path,
    module_name: str,
    model_path: Path,
    t3_model: str,
    language_id: str,
) -> None:
    with _forced_offline_runtime_env():
        import soundfile as sf  # type: ignore[import-not-found]

        model = _get_chatterbox_model(module_name, Path(model_path), t3_model)
        torch = importlib.import_module("torch")
        torch.manual_seed(EMMA_SEED)
        if torch.backends.mps.is_available():
            torch.mps.manual_seed(EMMA_SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(EMMA_SEED)

        wav = model.generate(
            text=text,
            language_id=language_id,
            exaggeration=EMMA_EXAGGERATION,
            cfg_weight=EMMA_CFG_WEIGHT,
            temperature=EMMA_TEMPERATURE,
        )
        if hasattr(wav, "cpu"):
            wav = wav.cpu().numpy().squeeze()

        mtl_tts = importlib.import_module(f"{module_name}.mtl_tts")
        sf.write(str(output_path), wav, samplerate=mtl_tts.S3GEN_SR, subtype="PCM_16")


def _get_chatterbox_model(
    module_name: str,
    model_path: Path,
    t3_model: str,
) -> Any:
    global _CHATTERBOX_MODEL, _CHATTERBOX_MODEL_KEY

    with _forced_offline_runtime_env():
        torch = importlib.import_module("torch")

        device = _select_device(torch)
        model_key = (module_name, str(model_path), t3_model, device)
        if _CHATTERBOX_MODEL is not None and _CHATTERBOX_MODEL_KEY == model_key:
            return _CHATTERBOX_MODEL

        mtl_tts = importlib.import_module(f"{module_name}.mtl_tts")
        _CHATTERBOX_MODEL = mtl_tts.ChatterboxMultilingualTTS.from_local(
            model_path,
            device=device,
            t3_model=t3_model,
        )
        _CHATTERBOX_MODEL_KEY = model_key

        return _CHATTERBOX_MODEL


def _select_device(torch_module: Any) -> str:
    requested = os.environ.get(
        "VOICE_CONCIERGE_CHATTERBOX_DEVICE",
        os.environ.get("WR3_CHATTERBOX_DEVICE", "cpu"),
    ).lower()
    if requested == "mps" and torch_module.backends.mps.is_available():
        return "mps"
    if requested == "cuda" and torch_module.cuda.is_available():
        return "cuda"
    return "cpu"


def _runtime_import_error(module_name: str) -> BaseException | None:
    try:
        with _forced_offline_runtime_env():
            importlib.import_module(f"{module_name}.mtl_tts")
    except BaseException as exc:
        return exc
    return None


def _safe_find_spec(name: str) -> tuple[Any | None, BaseException | None]:
    try:
        with _forced_offline_runtime_env():
            return importlib.util.find_spec(name), None
    except BaseException as exc:
        return None, exc


@contextmanager
def _forced_offline_runtime_env() -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in _OFFLINE_RUNTIME_ENV}
    try:
        os.environ.update(_OFFLINE_RUNTIME_ENV)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _missing_checkpoint_files(model_path: Path, t3_model: str) -> list[str]:
    if not model_path.exists():
        return [str(model_path.name)]
    if not model_path.is_dir():
        return [str(model_path.name)]
    return _runtime_missing_checkpoint_files(model_path, t3_model)


def _find_local_huggingface_checkpoint(t3_model: str) -> Path | None:
    for hub_dir in _huggingface_hub_cache_dirs():
        snapshot_root = hub_dir / _CHATTERBOX_HF_REPO_CACHE_DIR / "snapshots"
        if not snapshot_root.exists() or not snapshot_root.is_dir():
            continue

        try:
            snapshots = [path for path in snapshot_root.iterdir() if path.is_dir()]
        except OSError:
            continue
        snapshots.sort(key=_path_mtime, reverse=True)
        for snapshot in snapshots:
            if not _missing_checkpoint_files(snapshot, t3_model):
                return snapshot
    return None


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _huggingface_hub_cache_dirs() -> list[Path]:
    candidates: list[Path] = []

    hub_cache = os.environ.get("HUGGINGFACE_HUB_CACHE")
    if hub_cache:
        candidates.append(Path(hub_cache).expanduser())

    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        candidates.append(Path(hf_home).expanduser() / "hub")

    candidates.append(Path.home() / ".cache" / "huggingface" / "hub")

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _resolve_t3_model_file(t3_model: str) -> str:
    return _runtime_resolve_t3_model_file(t3_model)


def _normalize_language_id(language_id: str) -> str:
    normalized = language_id.strip().lower()
    return _LANGUAGE_ID_ALIASES.get(normalized, normalized or "en")


__all__ = ["ChatterboxTTSProvider"]
