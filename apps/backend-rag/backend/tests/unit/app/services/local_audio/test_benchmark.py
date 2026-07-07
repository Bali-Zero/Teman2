from pathlib import Path

import pytest

from backend.app.services.local_audio import (
    LocalSTTProvider,
    ProviderPolicy,
    ProviderStatus,
    STTResult,
)
from backend.app.services.local_audio.benchmark import STTBenchmarkCase, run_stt_benchmark


class FakeSTTProvider(LocalSTTProvider):
    name = "fake-stt"

    def __init__(
        self,
        *,
        fail: bool = False,
        fail_message: str = "decode failed",
        available: bool = True,
        policy: ProviderPolicy | None = None,
    ) -> None:
        self.fail = fail
        self.fail_message = fail_message
        self.available = available
        self._policy = policy or self.policy
        self.calls: list[tuple[Path, str | None]] = []

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            available=self.available,
            detail="ready" if self.available else "missing runtime",
            policy=self._policy,
        )

    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> STTResult:
        self.calls.append((audio_path, language))
        if self.fail:
            raise RuntimeError(self.fail_message)
        return STTResult(
            text=f"text for {audio_path.name}",
            language=language,
            duration_seconds=None,
            provider=self.name,
        )


def _fake_clock(values: list[float]):
    def clock() -> float:
        return values.pop(0)

    return clock


@pytest.mark.asyncio
async def test_run_stt_benchmark_returns_json_ready_metrics(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"audio")
    provider = FakeSTTProvider()

    report = await run_stt_benchmark(
        provider,
        [STTBenchmarkCase(audio_path=audio, expected_text="text for sample.wav", language="it")],
        clock=_fake_clock([10.0, 10.25]),
    )

    assert provider.calls == [(audio, "it")]
    assert report.provider == "fake-stt"
    assert report.total_cases == 1
    assert report.successful_cases == 1
    assert report.failed_cases == 0
    assert report.average_latency_ms == 250.0
    assert report.results[0].exact_match is True
    assert report.to_json_dict() == {
        "provider": "fake-stt",
        "total_cases": 1,
        "successful_cases": 1,
        "failed_cases": 0,
        "average_latency_ms": 250.0,
        "results": [
            {
                "audio_ref": report.results[0].audio_ref,
                "language": "it",
                "ok": True,
                "latency_ms": 250.0,
                "text_chars": 19,
                "expected_text_chars": 19,
                "exact_match": True,
                "error": None,
            },
        ],
    }
    assert str(audio) not in str(report.to_json_dict())
    assert "text for sample.wav" not in str(report.to_json_dict())
    assert report.to_json_dict(include_raw=True)["results"][0]["audio_path"] == str(audio)
    assert report.to_json_dict(include_raw=True)["results"][0]["text"] == "text for sample.wav"


@pytest.mark.asyncio
async def test_run_stt_benchmark_records_provider_errors(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"audio")

    report = await run_stt_benchmark(
        FakeSTTProvider(fail=True),
        [STTBenchmarkCase(audio_path=audio)],
        clock=_fake_clock([5.0, 5.01]),
    )

    assert report.successful_cases == 0
    assert report.failed_cases == 1
    assert report.average_latency_ms is None
    assert report.results[0].ok is False
    assert report.results[0].error == "stt_provider_error"
    assert report.to_json_dict()["results"][0]["error"] == "stt_provider_error"
    assert report.to_json_dict(include_raw=True)["results"][0]["raw_error"] == "decode failed"


@pytest.mark.asyncio
async def test_run_stt_benchmark_public_json_hides_error_paths(tmp_path: Path) -> None:
    audio = tmp_path / "private-client-audio.wav"
    audio.write_bytes(b"audio")
    provider = FakeSTTProvider(
        fail=True,
        fail_message=f"audio file not found: {audio}",
    )

    report = await run_stt_benchmark(
        provider,
        [STTBenchmarkCase(audio_path=audio)],
        clock=_fake_clock([5.0, 5.01]),
    )

    public_json = report.to_json_dict()
    assert public_json["results"][0]["error"] == "stt_provider_error"
    assert str(audio) not in str(public_json)
    assert report.to_json_dict(include_raw=True)["results"][0]["raw_error"] == (
        f"audio file not found: {audio}"
    )


@pytest.mark.asyncio
async def test_run_stt_benchmark_preflights_provider_availability(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"audio")
    provider = FakeSTTProvider(available=False)

    with pytest.raises(RuntimeError, match="STT provider unavailable"):
        await run_stt_benchmark(provider, [STTBenchmarkCase(audio_path=audio)])

    assert provider.calls == []


@pytest.mark.asyncio
async def test_run_stt_benchmark_rejects_non_local_policy(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"audio")
    provider = FakeSTTProvider(
        policy=ProviderPolicy(
            requires_network=False,
            allows_cloud_fallback=False,
            pii_boundary="external_test",
        ),
    )

    with pytest.raises(RuntimeError, match="policy must be local_only"):
        await run_stt_benchmark(provider, [STTBenchmarkCase(audio_path=audio)])

    assert provider.calls == []
