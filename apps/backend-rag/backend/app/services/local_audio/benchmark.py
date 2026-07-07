"""Benchmark helpers for local audio providers."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from backend.app.services.local_audio import LocalSTTProvider, ProviderStatus


@dataclass(frozen=True)
class STTBenchmarkCase:
    audio_path: Path
    expected_text: str | None = None
    language: str | None = None


@dataclass(frozen=True)
class STTBenchmarkResult:
    audio_path: Path
    language: str | None
    ok: bool
    latency_ms: float
    text: str | None = None
    expected_text: str | None = None
    exact_match: bool | None = None
    error: str | None = None
    raw_error: str | None = None

    @property
    def text_chars(self) -> int:
        return len(self.text or "")

    @property
    def expected_text_chars(self) -> int:
        return len(self.expected_text or "")

    @property
    def audio_ref(self) -> str:
        return sha256(str(self.audio_path).encode("utf-8")).hexdigest()[:16]

    def to_json_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "audio_ref": self.audio_ref,
            "language": self.language,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "text_chars": self.text_chars,
            "expected_text_chars": self.expected_text_chars,
            "exact_match": self.exact_match,
            "error": self.error,
        }
        if include_raw:
            payload.update(
                {
                    "audio_path": str(self.audio_path),
                    "text": self.text,
                    "expected_text": self.expected_text,
                    "raw_error": self.raw_error,
                },
            )
        return payload


@dataclass(frozen=True)
class STTBenchmarkReport:
    provider: str
    results: list[STTBenchmarkResult]

    @property
    def total_cases(self) -> int:
        return len(self.results)

    @property
    def successful_cases(self) -> int:
        return sum(1 for result in self.results if result.ok)

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.successful_cases

    @property
    def average_latency_ms(self) -> float | None:
        successful_latencies = [result.latency_ms for result in self.results if result.ok]
        if not successful_latencies:
            return None
        return round(sum(successful_latencies) / len(successful_latencies), 3)

    def to_json_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "total_cases": self.total_cases,
            "successful_cases": self.successful_cases,
            "failed_cases": self.failed_cases,
            "average_latency_ms": self.average_latency_ms,
            "results": [result.to_json_dict(include_raw=include_raw) for result in self.results],
        }


def _assert_local_provider_ready(status: ProviderStatus) -> None:
    if not status.available:
        raise RuntimeError("STT provider unavailable")
    if status.policy.requires_network:
        raise RuntimeError("STT provider policy must not require network access")
    if status.policy.allows_cloud_fallback:
        raise RuntimeError("STT provider policy must not allow cloud fallback")
    if status.policy.pii_boundary != "local_only":
        raise RuntimeError("STT provider policy must be local_only")


def _public_error_code(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "audio_file_not_found"
    if isinstance(exc, TimeoutError):
        return "stt_timeout"
    return "stt_provider_error"


async def run_stt_benchmark(
    provider: LocalSTTProvider,
    cases: Sequence[STTBenchmarkCase],
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> STTBenchmarkReport:
    _assert_local_provider_ready(provider.status())
    results: list[STTBenchmarkResult] = []

    for case in cases:
        start = clock()
        try:
            result = await provider.transcribe(case.audio_path, language=case.language)
        except Exception as exc:
            latency_ms = round((clock() - start) * 1000, 3)
            results.append(
                STTBenchmarkResult(
                    audio_path=case.audio_path,
                    language=case.language,
                    ok=False,
                    latency_ms=latency_ms,
                    expected_text=case.expected_text,
                    error=_public_error_code(exc),
                    raw_error=str(exc)[:300],
                ),
            )
            continue

        latency_ms = round((clock() - start) * 1000, 3)
        exact_match = None
        if case.expected_text is not None:
            exact_match = result.text.strip() == case.expected_text.strip()
        results.append(
            STTBenchmarkResult(
                audio_path=case.audio_path,
                language=result.language,
                ok=True,
                latency_ms=latency_ms,
                text=result.text,
                expected_text=case.expected_text,
                exact_match=exact_match,
            ),
        )

    return STTBenchmarkReport(provider=provider.name, results=results)


__all__ = [
    "STTBenchmarkCase",
    "STTBenchmarkReport",
    "STTBenchmarkResult",
    "run_stt_benchmark",
]
