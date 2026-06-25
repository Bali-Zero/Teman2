from pathlib import Path

import pytest

from backend.app.services.local_audio import (
    LOCAL_ONLY_PROVIDER_POLICY,
    LocalSTTProvider,
    LocalTTSProvider,
    ProviderPolicy,
    ProviderStatus,
    SpeechSegment,
    STTResult,
    TTSResult,
    TurnDetector,
)


def test_provider_contracts_are_abstract() -> None:
    with pytest.raises(TypeError):
        LocalSTTProvider()

    with pytest.raises(TypeError):
        LocalTTSProvider()

    with pytest.raises(TypeError):
        TurnDetector()


def test_local_provider_policy_is_machine_readable() -> None:
    assert LOCAL_ONLY_PROVIDER_POLICY == ProviderPolicy(
        requires_network=False,
        allows_cloud_fallback=False,
        pii_boundary="local_only",
    )
    assert LocalSTTProvider.policy == LOCAL_ONLY_PROVIDER_POLICY
    assert LocalTTSProvider.policy == LOCAL_ONLY_PROVIDER_POLICY
    assert TurnDetector.policy == LOCAL_ONLY_PROVIDER_POLICY


@pytest.mark.parametrize(
    "kwargs",
    [
        {"requires_network": True},
        {"allows_cloud_fallback": True},
    ],
)
def test_local_provider_policy_rejects_remote_escape_hatches(kwargs: dict[str, bool]) -> None:
    with pytest.raises(ValueError, match="local_only providers must not"):
        ProviderPolicy(**kwargs)


def test_speech_segment_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="end_seconds must be greater"):
        SpeechSegment(start_seconds=1.0, end_seconds=0.5)


@pytest.mark.parametrize(
    ("start_seconds", "end_seconds", "message"),
    [
        (-0.1, 0.5, "start_seconds must be non-negative"),
        (float("nan"), 0.5, "speech segment timestamps must be finite"),
        (0.0, float("inf"), "speech segment timestamps must be finite"),
    ],
)
def test_speech_segment_rejects_unsafe_timestamps(
    start_seconds: float,
    end_seconds: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        SpeechSegment(start_seconds=start_seconds, end_seconds=end_seconds)


def test_tts_result_requires_playable_output() -> None:
    with pytest.raises(ValueError, match="audio_bytes or audio_path is required"):
        TTSResult(
            audio_bytes=None,
            audio_path=None,
            mime_type="audio/wav",
            provider="fake-tts",
        )


@pytest.mark.asyncio
async def test_concrete_providers_can_return_structured_results() -> None:
    class FakeSTT(LocalSTTProvider):
        name = "fake-stt"

        def status(self) -> ProviderStatus:
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
            return STTResult(
                text=f"transcribed {audio_path.name}",
                language=language,
                duration_seconds=1.25,
                provider=self.name,
            )

    class FakeTTS(LocalTTSProvider):
        name = "fake-tts"

        def status(self) -> ProviderStatus:
            return ProviderStatus(
                name=self.name,
                available=True,
                detail="ready",
                policy=self.policy,
            )

        async def synthesize(
            self,
            text: str,
            *,
            voice: str | None = None,
            output_path: Path | None = None,
        ) -> TTSResult:
            return TTSResult(
                audio_bytes=text.encode(),
                audio_path=output_path,
                mime_type="audio/wav",
                provider=self.name,
            )

    class FakeTurnDetector(TurnDetector):
        name = "fake-vad"

        def status(self) -> ProviderStatus:
            return ProviderStatus(
                name=self.name,
                available=True,
                detail="ready",
                policy=self.policy,
            )

        async def detect_segments(self, audio_path: Path) -> list[SpeechSegment]:
            return [SpeechSegment(start_seconds=0.0, end_seconds=0.8)]

    stt = FakeSTT()
    tts = FakeTTS()
    vad = FakeTurnDetector()

    assert stt.status().available is True
    assert stt.status().policy.requires_network is False
    assert stt.status().policy.allows_cloud_fallback is False
    assert stt.status().policy.pii_boundary == "local_only"
    assert tts.status().detail == "ready"
    assert vad.name == "fake-vad"

    stt_result = await stt.transcribe(Path("/tmp/sample.wav"), language="it")
    tts_result = await tts.synthesize("ciao", output_path=Path("/tmp/out.wav"))
    segments = await vad.detect_segments(Path("/tmp/sample.wav"))

    assert stt_result.text == "transcribed sample.wav"
    assert stt_result.language == "it"
    assert tts_result.audio_bytes == b"ciao"
    assert tts_result.audio_path == Path("/tmp/out.wav")
    assert segments == [SpeechSegment(start_seconds=0.0, end_seconds=0.8)]
