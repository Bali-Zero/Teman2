from pathlib import Path

import pytest

from backend.app.services.local_audio.runtime_checks import MIN_WHISPER_MODEL_BYTES
from backend.app.services.local_audio.whisper_cpp import (
    WhisperCppSTTProvider,
    _parse_whisper_stdout,
)


class FakeProcess:
    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        timeout: bool = False,
        kill_error: Exception | None = None,
    ) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.timeout = timeout
        self.kill_error = kill_error
        self.killed = False
        self.waited = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self.timeout:
            await asyncio_sleep_forever()
        return self._stdout, self._stderr

    def kill(self) -> None:
        if self.kill_error:
            raise self.kill_error
        self.killed = True

    async def wait(self) -> None:
        self.waited = True


async def asyncio_sleep_forever() -> None:
    import asyncio

    await asyncio.sleep(60)


def _make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)


def _write_valid_whisper_model(path: Path) -> None:
    path.write_bytes(b"0")
    with path.open("r+b") as handle:
        handle.truncate(MIN_WHISPER_MODEL_BYTES)


def test_status_reports_missing_binary(tmp_path: Path) -> None:
    model = tmp_path / "ggml-large-v3-turbo.bin"
    _write_valid_whisper_model(model)

    provider = WhisperCppSTTProvider(
        binary_path=tmp_path / "missing-whisper-cli",
        model_path=model,
    )

    status = provider.status()

    assert status.available is False
    assert status.name == "whisper.cpp"
    assert "binary not found" in status.detail


def test_status_reports_missing_model(tmp_path: Path) -> None:
    binary = tmp_path / "whisper-cli"
    _make_executable(binary)

    provider = WhisperCppSTTProvider(
        binary_path=binary,
        model_path=tmp_path / "missing-model.bin",
    )

    status = provider.status()

    assert status.available is False
    assert "model not found" in status.detail


def test_status_available_when_binary_and_model_exist(tmp_path: Path) -> None:
    binary = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-large-v3-turbo.bin"
    _make_executable(binary)
    _write_valid_whisper_model(model)

    provider = WhisperCppSTTProvider(binary_path=binary, model_path=model)

    assert provider.status().available is True


def test_status_rejects_tiny_model_file(tmp_path: Path) -> None:
    binary = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-large-v3-turbo.bin"
    _make_executable(binary)
    model.write_bytes(b"not-a-real-model")

    provider = WhisperCppSTTProvider(binary_path=binary, model_path=model)

    status = provider.status()
    assert status.available is False
    assert "too small" in status.detail


def test_status_rejects_non_production_model_name(tmp_path: Path) -> None:
    binary = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-small.bin"
    _make_executable(binary)
    _write_valid_whisper_model(model)

    provider = WhisperCppSTTProvider(binary_path=binary, model_path=model)

    status = provider.status()
    assert status.available is False
    assert "large-v3-turbo" in status.detail


def test_parse_whisper_stdout_joins_timestamped_segments() -> None:
    stdout = """
whisper_init_from_file_with_params_no_state: loading model
[00:00:00.000 --> 00:00:01.000] Ciao.
[00:00:01.000 --> 00:00:02.000] Come posso aiutarti?
"""

    assert _parse_whisper_stdout(stdout) == "Ciao. Come posso aiutarti?"


def test_parse_whisper_stdout_accepts_plain_transcript() -> None:
    assert _parse_whisper_stdout("Plain transcript\nsecond line\n") == "Plain transcript second line"


def test_parse_whisper_stdout_preserves_non_timestamp_brackets() -> None:
    assert _parse_whisper_stdout("[inaudible]\n[music]\n") == "[inaudible] [music]"


@pytest.mark.asyncio
async def test_transcribe_invokes_whisper_cli_without_shell(tmp_path: Path, monkeypatch) -> None:
    binary = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-large-v3-turbo.bin"
    audio = tmp_path / "sample.wav"
    _make_executable(binary)
    _write_valid_whisper_model(model)
    audio.write_bytes(b"audio")
    calls: list[tuple[tuple[str, ...], dict]] = []
    process = FakeProcess(
        stdout=(
            b"whisper_init_from_file_with_params_no_state: loading model\n"
            b"[00:00:00.000 --> 00:00:01.000] Ciao mondo.\n"
        ),
    )

    async def fake_create_subprocess_exec(*args: str, **kwargs) -> FakeProcess:
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(
        "backend.app.services.local_audio.whisper_cpp.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    provider = WhisperCppSTTProvider(binary_path=binary, model_path=model, timeout_seconds=5)
    result = await provider.transcribe(audio, language="it")

    assert result.text == "Ciao mondo."
    assert result.language == "it"
    assert result.provider == "whisper.cpp"
    assert result.duration_seconds is None
    args, kwargs = calls[0]
    assert args == (
        str(binary),
        "-m",
        str(model),
        "-f",
        str(audio),
        "-nt",
        "-l",
        "it",
    )
    assert kwargs["stdout"] is not None
    assert kwargs["stderr"] is not None
    assert "shell" not in kwargs


@pytest.mark.asyncio
async def test_transcribe_raises_sanitized_error_on_nonzero_exit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    binary = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-large-v3-turbo.bin"
    audio = tmp_path / "sample.wav"
    _make_executable(binary)
    _write_valid_whisper_model(model)
    audio.write_bytes(b"audio")

    async def fake_create_subprocess_exec(*_args: str, **_kwargs) -> FakeProcess:
        return FakeProcess(
            stdout=b"[00:00:00.000 --> 00:00:01.000] client secret transcript\n",
            stderr=b"failed to decode audio",
            returncode=2,
        )

    monkeypatch.setattr(
        "backend.app.services.local_audio.whisper_cpp.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    provider = WhisperCppSTTProvider(binary_path=binary, model_path=model)

    with pytest.raises(RuntimeError, match="whisper.cpp failed with exit code 2") as exc_info:
        await provider.transcribe(audio)

    assert "client secret transcript" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_transcribe_kills_process_on_timeout(tmp_path: Path, monkeypatch) -> None:
    binary = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-large-v3-turbo.bin"
    audio = tmp_path / "sample.wav"
    _make_executable(binary)
    _write_valid_whisper_model(model)
    audio.write_bytes(b"audio")
    process = FakeProcess(timeout=True)

    async def fake_create_subprocess_exec(*_args: str, **_kwargs) -> FakeProcess:
        return process

    monkeypatch.setattr(
        "backend.app.services.local_audio.whisper_cpp.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    provider = WhisperCppSTTProvider(binary_path=binary, model_path=model, timeout_seconds=0.01)

    with pytest.raises(TimeoutError, match="timed out"):
        await provider.transcribe(audio)

    assert process.killed is True
    assert process.waited is True


@pytest.mark.asyncio
async def test_transcribe_timeout_tolerates_process_lookup_race(
    tmp_path: Path,
    monkeypatch,
) -> None:
    binary = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-large-v3-turbo.bin"
    audio = tmp_path / "sample.wav"
    _make_executable(binary)
    _write_valid_whisper_model(model)
    audio.write_bytes(b"audio")
    process = FakeProcess(timeout=True, kill_error=ProcessLookupError("already exited"))

    async def fake_create_subprocess_exec(*_args: str, **_kwargs) -> FakeProcess:
        return process

    monkeypatch.setattr(
        "backend.app.services.local_audio.whisper_cpp.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    provider = WhisperCppSTTProvider(binary_path=binary, model_path=model, timeout_seconds=0.01)

    with pytest.raises(TimeoutError, match="timed out"):
        await provider.transcribe(audio)

    assert process.waited is True
