"""Local-first audio provider contracts for the voice concierge runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ProviderPolicy:
    requires_network: bool = False
    allows_cloud_fallback: bool = False
    pii_boundary: Literal["local_only"] = "local_only"

    def __post_init__(self) -> None:
        if self.pii_boundary == "local_only" and self.requires_network:
            raise ValueError("local_only providers must not require network")
        if self.pii_boundary == "local_only" and self.allows_cloud_fallback:
            raise ValueError("local_only providers must not allow cloud fallback")


LOCAL_ONLY_PROVIDER_POLICY = ProviderPolicy()


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    available: bool
    detail: str
    policy: ProviderPolicy = LOCAL_ONLY_PROVIDER_POLICY


@dataclass(frozen=True)
class STTResult:
    text: str
    language: str | None
    duration_seconds: float | None
    provider: str


@dataclass(frozen=True)
class TTSResult:
    audio_bytes: bytes | None
    audio_path: Path | None
    mime_type: str
    provider: str

    def __post_init__(self) -> None:
        if self.audio_bytes is None and self.audio_path is None:
            raise ValueError("audio_bytes or audio_path is required")


@dataclass(frozen=True)
class SpeechSegment:
    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        if not isfinite(self.start_seconds) or not isfinite(self.end_seconds):
            raise ValueError("speech segment timestamps must be finite")
        if self.start_seconds < 0:
            raise ValueError("start_seconds must be non-negative")
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")


class LocalSTTProvider(ABC):
    name: str
    policy: ProviderPolicy = LOCAL_ONLY_PROVIDER_POLICY

    @abstractmethod
    def status(self) -> ProviderStatus:
        """Return local provider readiness without making a paid/cloud call."""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> STTResult:
        """Transcribe local audio into text."""


class LocalTTSProvider(ABC):
    name: str
    policy: ProviderPolicy = LOCAL_ONLY_PROVIDER_POLICY

    @abstractmethod
    def status(self) -> ProviderStatus:
        """Return local provider readiness without making a paid/cloud call."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        output_path: Path | None = None,
    ) -> TTSResult:
        """Synthesize local speech audio from text."""


class TurnDetector(ABC):
    name: str
    policy: ProviderPolicy = LOCAL_ONLY_PROVIDER_POLICY

    @abstractmethod
    def status(self) -> ProviderStatus:
        """Return local provider readiness without making a paid/cloud call."""

    @abstractmethod
    async def detect_segments(self, audio_path: Path) -> list[SpeechSegment]:
        """Return detected speech ranges for local audio."""


__all__ = [
    "LOCAL_ONLY_PROVIDER_POLICY",
    "LocalSTTProvider",
    "LocalTTSProvider",
    "ProviderPolicy",
    "ProviderStatus",
    "STTResult",
    "SpeechSegment",
    "TTSResult",
    "TurnDetector",
]
