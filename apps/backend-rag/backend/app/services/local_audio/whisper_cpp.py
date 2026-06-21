"""whisper.cpp provider for local-first speech-to-text."""

from __future__ import annotations

import asyncio
import contextlib
import re
from pathlib import Path

from backend.app.services.local_audio import LocalSTTProvider, ProviderStatus, STTResult
from backend.app.services.local_audio.runtime_checks import (
    check_whisper_binary_path,
    check_whisper_model_path,
    check_whisper_model_quality,
)

_TIMESTAMPED_SEGMENT_RE = re.compile(
    r"^\[\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}\]\s*(?P<text>.*)$",
)
_LOG_PREFIXES = (
    "whisper_",
    "ggml_",
    "system_info:",
    "main:",
)


class WhisperCppSTTProvider(LocalSTTProvider):
    """Local STT provider backed by a whisper.cpp command-line binary."""

    name = "whisper.cpp"

    def __init__(
        self,
        *,
        binary_path: Path,
        model_path: Path,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.binary_path = Path(binary_path)
        self.model_path = Path(model_path)
        self.timeout_seconds = timeout_seconds

    def status(self) -> ProviderStatus:
        binary_check = check_whisper_binary_path(self.binary_path)
        if not binary_check.ok:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=binary_check.detail,
                policy=self.policy,
            )
        model_check = check_whisper_model_path(self.model_path)
        if not model_check.ok:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=model_check.detail,
                policy=self.policy,
            )
        quality_check = check_whisper_model_quality(self.model_path)
        if not quality_check.ok:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail=quality_check.detail,
                policy=self.policy,
            )
        return ProviderStatus(
            name=self.name,
            available=True,
            detail="ready",
            policy=self.policy,
        )

    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> STTResult:
        audio = Path(audio_path)
        if not audio.exists():
            raise FileNotFoundError(f"audio file not found: {audio}")

        status = self.status()
        if not status.available:
            raise RuntimeError(status.detail)

        cmd = [
            str(self.binary_path),
            "-m",
            str(self.model_path),
            "-f",
            str(audio),
            "-nt",
        ]
        if language:
            cmd.extend(["-l", language])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"binary not found: {self.binary_path}") from exc

        try:
            stdout_bytes, _stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            await _kill_process(proc)
            raise TimeoutError(f"whisper.cpp timed out after {self.timeout_seconds}s") from exc
        except asyncio.CancelledError:
            await _kill_process(proc)
            raise

        if proc.returncode != 0:
            raise RuntimeError(f"whisper.cpp failed with exit code {proc.returncode}")

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        return STTResult(
            text=_parse_whisper_stdout(stdout),
            language=language,
            duration_seconds=None,
            provider=self.name,
        )


def _parse_whisper_stdout(stdout: str) -> str:
    """Extract transcript text from whisper.cpp stdout."""
    timestamped_segments: list[str] = []
    plain_lines: list[str] = []

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _TIMESTAMPED_SEGMENT_RE.match(line)
        if match:
            text = match.group("text").strip()
            if text:
                timestamped_segments.append(text)
            continue

        if _looks_like_whisper_log(line):
            continue
        plain_lines.append(line)

    if timestamped_segments:
        return " ".join(timestamped_segments).strip()
    return " ".join(plain_lines).strip()


def _looks_like_whisper_log(line: str) -> bool:
    return any(line.startswith(prefix) for prefix in _LOG_PREFIXES)


async def _kill_process(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(Exception):
        await proc.wait()


__all__ = ["WhisperCppSTTProvider", "_parse_whisper_stdout"]
