"""Silero VAD adapter for local-first turn detection."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import multiprocessing as mp
import os
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

from backend.app.services.local_audio import ProviderStatus, SpeechSegment, TurnDetector


class SileroDetector(Protocol):
    async def __call__(
        self,
        audio_path: Path,
        *,
        module_name: str,
        sampling_rate: int,
        threshold: float,
        timeout_seconds: float,
    ) -> list[SpeechSegment]:
        """Return local speech segments."""


_SILERO_MODEL: Any | None = None
_SILERO_MODEL_KEY: tuple[str] | None = None
_SILERO_PROCESS_SEMAPHORE = threading.BoundedSemaphore(value=1)
_OFFLINE_RUNTIME_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}


class SileroVADProvider(TurnDetector):
    """Local VAD provider backed by the silero-vad Python package."""

    name = "silero-vad"

    def __init__(
        self,
        *,
        module_name: str = "silero_vad",
        sampling_rate: int = 16000,
        threshold: float = 0.5,
        timeout_seconds: float = 15.0,
        detector: SileroDetector | None = None,
    ) -> None:
        self.module_name = module_name
        self.sampling_rate = sampling_rate
        self.threshold = threshold
        self.timeout_seconds = timeout_seconds
        self.detector = detector or _detect_silero_segments

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
        if self.sampling_rate not in (8000, 16000):
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="unsupported sampling rate",
                policy=self.policy,
            )
        if self.threshold <= 0 or self.threshold >= 1:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="unsupported threshold",
                policy=self.policy,
            )
        if self.timeout_seconds <= 0:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="timeout must be positive",
                policy=self.policy,
            )
        return ProviderStatus(
            name=self.name,
            available=True,
            detail="runtime import ready",
            policy=self.policy,
        )

    def warm_status(self) -> ProviderStatus:
        status = self.status()
        if not status.available:
            return status
        model_load_error = _safe_load_model(self.module_name)
        if model_load_error is not None:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=f"runtime model load failed: {type(model_load_error).__name__}",
                policy=self.policy,
            )
        return ProviderStatus(
            name=self.name,
            available=True,
            detail="runtime model ready",
            policy=self.policy,
        )

    async def detect_segments(self, audio_path: Path) -> list[SpeechSegment]:
        status = self.status()
        if not status.available:
            raise RuntimeError(status.detail)
        return await self.detector(
            audio_path,
            module_name=self.module_name,
            sampling_rate=self.sampling_rate,
            threshold=self.threshold,
            timeout_seconds=self.timeout_seconds,
        )


async def _detect_silero_segments(
    audio_path: Path,
    *,
    module_name: str,
    sampling_rate: int,
    threshold: float,
    timeout_seconds: float,
) -> list[SpeechSegment]:
    segment_bounds = await asyncio.to_thread(
        _run_silero_detection_process,
        audio_path,
        module_name=module_name,
        sampling_rate=sampling_rate,
        threshold=threshold,
        timeout_seconds=timeout_seconds,
    )
    return [
        SpeechSegment(start_seconds=start_seconds, end_seconds=end_seconds)
        for start_seconds, end_seconds in segment_bounds
    ]


def _run_silero_detection_process(
    audio_path: Path,
    *,
    module_name: str,
    sampling_rate: int,
    threshold: float,
    timeout_seconds: float,
) -> list[tuple[float, float]]:
    if timeout_seconds <= 0:
        raise TimeoutError("Silero VAD timeout must be positive")

    acquired = _SILERO_PROCESS_SEMAPHORE.acquire(timeout=timeout_seconds)
    if not acquired:
        raise TimeoutError("Silero VAD concurrency limit reached")

    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="silero-vad-") as tmpdir:
        result_path = Path(tmpdir) / "segments.json"
        result_receiver, result_sender = context.Pipe(duplex=False)
        process = context.Process(
            target=_run_silero_detection_child,
            args=(
                result_sender,
                str(result_path),
                str(audio_path),
                module_name,
                sampling_rate,
                threshold,
            ),
        )
        process.daemon = True

        try:
            process.start()
            result_sender.close()
            process.join(timeout_seconds)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1.0)
                raise TimeoutError(f"Silero VAD timed out after {timeout_seconds}s")

            if not result_receiver.poll():
                exit_code = process.exitcode
                raise RuntimeError(f"Silero VAD process exited without result: {exit_code}")
            try:
                result = result_receiver.recv()
            except EOFError as exc:
                exit_code = process.exitcode
                raise RuntimeError(
                    f"Silero VAD process exited without result: {exit_code}",
                ) from exc

            status = result[0]
            if status == "ok":
                return _read_silero_result_file(result_path)
            if status == "error":
                raise RuntimeError(f"Silero VAD failed: {result[1]}")
            raise RuntimeError("Silero VAD returned an invalid result")
        finally:
            result_receiver.close()
            result_sender.close()
            _SILERO_PROCESS_SEMAPHORE.release()


def _run_silero_detection_child(
    result_sender: Any,
    result_path: str,
    audio_path: str,
    module_name: str,
    sampling_rate: int,
    threshold: float,
) -> None:
    try:
        segments = _detect_silero_segments_in_current_process(
            audio_path=Path(audio_path),
            module_name=module_name,
            sampling_rate=sampling_rate,
            threshold=threshold,
        )
        Path(result_path).write_text(json.dumps(segments), encoding="utf-8")
        result_sender.send(("ok", None))
    except BaseException as exc:
        result_sender.send(("error", type(exc).__name__))
    finally:
        result_sender.close()


def _read_silero_result_file(result_path: Path) -> list[tuple[float, float]]:
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError("Silero VAD process exited without result file") from exc
    if not isinstance(payload, list):
        raise RuntimeError("Silero VAD returned an invalid result file")
    segments: list[tuple[float, float]] = []
    for item in payload:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(value, (int, float)) for value in item)
        ):
            raise RuntimeError("Silero VAD returned an invalid result file")
        segments.append((float(item[0]), float(item[1])))
    return segments


def _detect_silero_segments_in_current_process(
    *,
    audio_path: Path,
    module_name: str,
    sampling_rate: int,
    threshold: float,
) -> list[tuple[float, float]]:
    with _forced_offline_runtime_env():
        silero = importlib.import_module(module_name)
        model = _get_silero_model(module_name)
        wav = silero.read_audio(str(audio_path), sampling_rate=sampling_rate)
        timestamps = silero.get_speech_timestamps(
            wav,
            model,
            sampling_rate=sampling_rate,
            return_seconds=True,
            threshold=threshold,
        )
    return [
        (float(timestamp["start"]), float(timestamp["end"]))
        for timestamp in timestamps
    ]


def _get_silero_model(module_name: str) -> Any:
    global _SILERO_MODEL, _SILERO_MODEL_KEY

    model_key = (module_name,)
    if _SILERO_MODEL is not None and _SILERO_MODEL_KEY == model_key:
        return _SILERO_MODEL

    with _forced_offline_runtime_env():
        silero = importlib.import_module(module_name)
        _SILERO_MODEL = silero.load_silero_vad()
    _SILERO_MODEL_KEY = model_key
    return _SILERO_MODEL


def _safe_load_model(name: str) -> BaseException | None:
    try:
        _get_silero_model(name)
    except BaseException as exc:
        return exc
    return None


def _safe_find_spec(name: str) -> tuple[Any | None, BaseException | None]:
    try:
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
                continue
            os.environ[key] = value


__all__ = ["SileroVADProvider"]
