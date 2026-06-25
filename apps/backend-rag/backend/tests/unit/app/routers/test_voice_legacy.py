from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.routers import voice
from backend.app.routers.voice import router
from backend.app.services.local_audio import (
    ProviderPolicy,
    ProviderStatus,
    STTResult,
    TTSResult,
)


class _UnsafePolicy:
    requires_network = True
    allows_cloud_fallback = False
    pii_boundary = "local_only"


class _FakeLocalSTTProvider:
    name = "fake-local-stt"

    def __init__(
        self,
        *,
        available: bool = True,
        policy: ProviderPolicy | _UnsafePolicy | None = None,
        status_detail: str = "ready",
        transcribe_error: str | None = None,
    ) -> None:
        self.policy = policy or ProviderPolicy()
        self.available = available
        self.status_detail = status_detail
        self.transcribe_error = transcribe_error
        self.calls: list[tuple[str, str | None, bool]] = []
        self.transcribe_paths: list[str] = []

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            available=self.available,
            detail=self.status_detail,
            policy=self.policy,
        )

    async def transcribe(
        self,
        audio_path,
        *,
        language: str | None = None,
    ) -> STTResult:
        audio_exists = audio_path.exists()
        self.calls.append((audio_path.name, language, audio_exists))
        self.transcribe_paths.append(str(audio_path))
        if self.transcribe_error:
            raise RuntimeError(self.transcribe_error)
        return STTResult(
            text="ciao dal provider locale",
            language=language,
            duration_seconds=None,
            provider=self.name,
        )


class _FakeLocalTTSProvider:
    name = "fake-local-tts"

    def __init__(
        self,
        *,
        available: bool = True,
        policy: ProviderPolicy | _UnsafePolicy | None = None,
        status_detail: str = "ready",
        synthesize_error: str | None = None,
        audio_bytes: bytes | None = None,
    ) -> None:
        self.policy = policy or ProviderPolicy()
        self.available = available
        self.status_detail = status_detail
        self.synthesize_error = synthesize_error
        self.audio_bytes = audio_bytes
        self.calls: list[tuple[str, str | None, bool]] = []
        self.synthesize_paths: list[str] = []

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            available=self.available,
            detail=self.status_detail,
            policy=self.policy,
        )

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        output_path=None,
    ) -> TTSResult:
        output_exists = output_path.exists() if output_path is not None else False
        self.calls.append((text, voice, output_exists))
        if output_path is not None:
            self.synthesize_paths.append(str(output_path))
        if self.synthesize_error:
            raise RuntimeError(self.synthesize_error)
        if self.audio_bytes is not None:
            return TTSResult(
                audio_bytes=self.audio_bytes,
                audio_path=None,
                mime_type="audio/wav",
                provider=self.name,
            )
        output_path.write_bytes(b"local wav")
        return TTSResult(
            audio_bytes=None,
            audio_path=output_path,
            mime_type="audio/wav",
            provider=self.name,
        )


@pytest.fixture(autouse=True)
def _allow_voice_runtime_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice, "_local_audio_runtime_host_allowed", lambda: True)


def _build_voice_app(
    provider: _FakeLocalSTTProvider | None = None,
    tts_provider: _FakeLocalTTSProvider | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    dependency = getattr(voice, "get_local_stt_provider_factory", None)
    if dependency is not None and provider is not None:
        app.dependency_overrides[dependency] = lambda: lambda: provider
    tts_dependency = getattr(voice, "get_local_tts_provider_factory", None)
    if tts_dependency is not None and tts_provider is not None:
        app.dependency_overrides[tts_dependency] = lambda: lambda: tts_provider
    return app


def test_elevenlabs_kbli_audit_webhook_is_retired() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/voice/elevenlabs/kbli-audit",
        json={"query": "Audit KBLI 62010"},
    )

    assert response.status_code == 410
    assert response.json() == {
        "detail": "ElevenLabs KBLI audit webhook retired; use local voice concierge."
    }


def test_local_audio_status_requires_api_key() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/voice/local-audio/status")

    assert response.status_code == 401


def test_local_audio_status_disabled_is_sanitized(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", False)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get(
        "/api/voice/local-audio/status",
        headers={"X-API-Key": "test_api_key_1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["ready"] is False
    assert body["roundtrip_ready"] is False
    assert body["turn_detection_ready"] is False
    assert body["providers"]["stt"]["name"] == "whisper.cpp"
    assert body["providers"]["stt"]["detail"] == "local audio disabled"
    assert body["providers"]["stt"]["policy"] == {
        "requires_network": False,
        "allows_cloud_fallback": False,
        "pii_boundary": "local_only",
    }


def test_local_audio_status_redacts_whisper_paths(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(
        settings,
        "voice_concierge_whisper_binary",
        "/private/client-folder/whisper-cli",
    )
    monkeypatch.setattr(
        settings,
        "voice_concierge_whisper_model",
        "/private/client-folder/ggml-large-v3-turbo.bin",
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get(
        "/api/voice/local-audio/status",
        headers={"X-API-Key": "test_api_key_1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["ready"] is False
    assert body["roundtrip_ready"] is False
    assert body["turn_detection_ready"] is False
    assert body["providers"]["stt"]["detail"] == "binary not found"
    assert "/private" not in str(body)


def test_local_audio_status_rejects_unapproved_runtime_host(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(voice, "_local_audio_runtime_host_allowed", lambda: False)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get(
        "/api/voice/local-audio/status",
        headers={"X-API-Key": "test_api_key_1"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local audio runtime host not approved"}


def test_local_audio_status_ready_requires_stt_vad_and_tts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(settings, "voice_concierge_tts_profile", "high_quality_offline")

    class FakeUnavailableVAD:
        name = "silero-vad"

        def __init__(
            self,
            *,
            module_name: str,
            sampling_rate: int,
            threshold: float,
            timeout_seconds: float,
        ) -> None:
            self.module_name = module_name
            self.sampling_rate = sampling_rate
            self.threshold = threshold
            self.timeout_seconds = timeout_seconds

        def status(self) -> ProviderStatus:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="runtime detected but adapter not wired",
                policy=ProviderPolicy(),
            )

    class FakeReadyTTS:
        name = "chatterbox-v3"

        def __init__(
            self,
            *,
            module_name: str,
            model_path: Path | None,
            t3_model: str,
            language_id: str,
            timeout_seconds: float,
        ) -> None:
            self.module_name = module_name
            self.model_path = model_path
            self.t3_model = t3_model
            self.language_id = language_id
            self.timeout_seconds = timeout_seconds

        def status(self) -> ProviderStatus:
            return ProviderStatus(
                name=self.name,
                available=True,
                detail="ready",
                policy=ProviderPolicy(),
            )

    monkeypatch.setattr(
        voice,
        "_whisper_status",
        lambda: ProviderStatus(
            name="whisper.cpp",
            available=True,
            detail="ready",
            policy=ProviderPolicy(),
        ),
    )
    monkeypatch.setattr(voice, "SileroVADProvider", FakeUnavailableVAD)
    monkeypatch.setattr(voice, "ChatterboxTTSProvider", FakeReadyTTS)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get(
        "/api/voice/local-audio/status",
        headers={"X-API-Key": "test_api_key_1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["roundtrip_ready"] is True
    assert body["turn_detection_ready"] is False
    assert body["providers"]["vad"]["available"] is False
    assert body["tts_profile"]["active_profile"] == "high_quality_offline"
    assert body["tts_profile"]["active_provider"] == "chatterbox-v3"
    assert body["tts_profile"]["quality"] == "high_quality"
    assert body["tts_profile"]["latency_class"] == "offline"
    assert body["tts_profile"]["fallback_policy"] == "fail_closed"
    assert "ready_requires_stt_vad_tts" in body["constraints"]


def test_local_audio_status_exposes_browser_realtime_tts_profile(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(settings, "voice_concierge_tts_profile", "browser_realtime")
    monkeypatch.setattr(
        settings,
        "voice_concierge_realtime_tts_provider",
        "browser-web-speech-local",
    )
    monkeypatch.setattr(
        voice,
        "_whisper_status",
        lambda: ProviderStatus(
            name="whisper.cpp",
            available=True,
            detail="ready",
            policy=ProviderPolicy(),
        ),
    )

    class FakeUnavailableVAD:
        name = "silero-vad"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def status(self) -> ProviderStatus:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="adapter not wired",
                policy=ProviderPolicy(),
            )

    class FakeUnavailableChatterbox:
        name = "chatterbox-v3"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def status(self) -> ProviderStatus:
            return ProviderStatus(
                name=self.name,
                available=False,
                detail="too slow for realtime",
                policy=ProviderPolicy(),
            )

    monkeypatch.setattr(voice, "SileroVADProvider", FakeUnavailableVAD)
    monkeypatch.setattr(voice, "ChatterboxTTSProvider", FakeUnavailableChatterbox)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get(
        "/api/voice/local-audio/status",
        headers={"X-API-Key": "test_api_key_1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tts_profile"]["active_profile"] == "browser_realtime"
    assert body["tts_profile"]["active_provider"] == "browser-web-speech-local"
    assert body["tts_profile"]["quality"] == "realtime"
    assert body["tts_profile"]["latency_class"] == "interactive"
    assert body["tts_profile"]["fallback_policy"] == "fail_closed"
    assert body["tts_profile"]["profiles"]["browser_realtime"]["policy"] == {
        "requires_network": False,
        "allows_cloud_fallback": False,
        "pii_boundary": "local_only",
    }
    assert body["tts_profile"]["profiles"]["browser_realtime"]["available"] is False


def test_local_audio_transcribe_requires_api_key() -> None:
    app = _build_voice_app()
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        files={"file": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 401


def test_local_audio_transcribe_rejects_disabled_stack(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", False)
    monkeypatch.setattr(settings, "voice_concierge_local_audio", False)
    app = _build_voice_app(_FakeLocalSTTProvider())
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"file": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local audio disabled"}


def test_local_audio_transcribe_checks_disabled_stack_before_provider(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", False)
    monkeypatch.setattr(settings, "voice_concierge_local_audio", False)
    monkeypatch.setattr(settings, "voice_concierge_whisper_binary", None)
    monkeypatch.setattr(settings, "voice_concierge_whisper_model", None)
    app = _build_voice_app()
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"file": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local audio disabled"}


def test_local_audio_transcribe_rejects_unapproved_runtime_host(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(voice, "_local_audio_runtime_host_allowed", lambda: False)
    provider = _FakeLocalSTTProvider()
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"file": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local audio runtime host not approved"}
    assert provider.calls == []


def test_local_audio_transcribe_rejects_unavailable_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalSTTProvider(available=False, status_detail="provider missing")
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"file": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local STT provider unavailable"}
    assert provider.calls == []


def test_local_audio_transcribe_rejects_cloud_policy(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalSTTProvider(policy=_UnsafePolicy())
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"file": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local STT provider violates local-only policy"}
    assert provider.calls == []


def test_local_audio_transcribe_rejects_non_audio_mime(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalSTTProvider()
    closed_files: list[str | None] = []
    original_close = voice.UploadFile.close

    async def close_and_record(file: voice.UploadFile) -> None:
        closed_files.append(file.filename)
        await original_close(file)

    monkeypatch.setattr(voice.UploadFile, "close", close_and_record)
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"file": ("note.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "unsupported audio content type"}
    assert provider.calls == []
    assert closed_files == ["note.txt"]


def test_local_audio_transcribe_accepts_audio_mime_with_parameters(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalSTTProvider()
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"file": ("sample.webm", b"audio", "audio/webm;codecs=opus")},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "ciao dal provider locale"
    assert provider.calls == [("voice-concierge-upload.webm", None, True)]


def test_local_audio_transcribe_rejects_oversized_audio(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(settings, "voice_concierge_audio_max_bytes", 3, raising=False)
    provider = _FakeLocalSTTProvider()
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"file": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "audio payload too large"}
    assert provider.calls == []


def test_local_audio_transcribe_requires_declared_content_length(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalSTTProvider()
    app = _build_voice_app(provider)
    client = TestClient(app)
    body = (
        b"--voice-boundary\r\n"
        b'Content-Disposition: form-data; name="file"; filename="sample.wav"\r\n'
        b"Content-Type: audio/wav\r\n"
        b"\r\n"
        b"audio\r\n"
        b"--voice-boundary--\r\n"
    )

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={
            "X-API-Key": "test_api_key_1",
            "Content-Type": "multipart/form-data; boundary=voice-boundary",
        },
        content=iter([body]),
    )

    assert response.status_code == 411
    assert response.json() == {"detail": "content length required"}
    assert provider.calls == []


def test_local_audio_transcribe_rejects_extra_file_parts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalSTTProvider()
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files=[
            ("file", ("sample.wav", b"audio", "audio/wav")),
            ("extra", ("second.wav", b"audio2", "audio/wav")),
        ],
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "exactly one audio file is required"}
    assert provider.calls == []


def test_local_audio_transcribe_closes_wrong_field_upload(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalSTTProvider()
    closed_files: list[str | None] = []
    original_close = voice.UploadFile.close

    async def close_and_record(file: voice.UploadFile) -> None:
        closed_files.append(file.filename)
        await original_close(file)

    monkeypatch.setattr(voice.UploadFile, "close", close_and_record)
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"wrong": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "exactly one audio file is required"}
    assert provider.calls == []
    assert closed_files == ["sample.wav"]


def test_local_audio_transcribe_deletes_temp_audio_after_success(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalSTTProvider()
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        data={"language": "it"},
        files={"file": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "text": "ciao dal provider locale",
        "language": "it",
        "duration_seconds": None,
        "provider": "fake-local-stt",
        "constraints": [
            "local_only",
            "no_cloud_audio_fallback",
            "no_raw_audio_persistence",
        ],
    }
    assert provider.calls == [("voice-concierge-upload.wav", "it", True)]
    assert not provider.transcribe_paths[0].endswith("sample.wav")
    assert "/private" not in str(body)
    assert not Path(provider.transcribe_paths[0]).exists()


def test_local_audio_transcribe_deletes_temp_audio_after_provider_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalSTTProvider(transcribe_error="private failure /tmp/client.wav")
    app = _build_voice_app(provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/transcribe",
        headers={"X-API-Key": "test_api_key_1"},
        files={"file": ("sample.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "local STT transcription failed"}
    assert provider.calls == [("voice-concierge-upload.wav", None, True)]
    assert "/tmp/client.wav" not in str(response.json())
    assert not Path(provider.transcribe_paths[0]).exists()


def test_local_audio_synthesize_requires_api_key() -> None:
    app = _build_voice_app(tts_provider=_FakeLocalTTSProvider())
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 401


def test_local_audio_synthesize_rejects_invalid_api_key() -> None:
    provider = _FakeLocalTTSProvider()
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "invalid"},
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 403
    assert provider.calls == []


def test_local_audio_synthesize_rejects_disabled_stack(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", False)
    monkeypatch.setattr(settings, "voice_concierge_local_audio", False)
    provider = _FakeLocalTTSProvider()
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local audio disabled"}
    assert provider.calls == []


def test_local_audio_synthesize_rejects_unapproved_runtime_host(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(voice, "_local_audio_runtime_host_allowed", lambda: False)
    provider = _FakeLocalTTSProvider()
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local audio runtime host not approved"}
    assert provider.calls == []


def test_local_audio_synthesize_rejects_unavailable_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalTTSProvider(available=False, status_detail="provider missing")
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local TTS provider unavailable"}
    assert provider.calls == []


def test_local_audio_synthesize_rejects_cloud_policy(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalTTSProvider(policy=_UnsafePolicy())
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "local TTS provider violates local-only policy"}
    assert provider.calls == []


def test_local_audio_synthesize_rejects_empty_text(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalTTSProvider()
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "   "},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "text required"}
    assert provider.calls == []


def test_local_audio_synthesize_rejects_oversized_text(monkeypatch) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(settings, "voice_concierge_tts_max_chars", 4, raising=False)
    provider = _FakeLocalTTSProvider()
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "troppo lungo"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "text payload too large"}
    assert provider.calls == []


def test_local_audio_synthesize_returns_local_wav_and_deletes_temp_output(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalTTSProvider()
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello", "voice": "en"},
    )

    assert response.status_code == 200
    assert response.content == b"local wav"
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-voice-provider"] == "fake-local-tts"
    assert response.headers["x-voice-constraints"] == (
        "local_only,no_cloud_audio_fallback,no_raw_audio_persistence"
    )
    assert provider.calls == [("Ciao Antonello", "en", False)]
    assert not Path(provider.synthesize_paths[0]).exists()


def test_local_audio_synthesize_rejects_browser_realtime_profile_before_provider(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(settings, "voice_concierge_tts_profile", "browser_realtime")
    provider = _FakeLocalTTSProvider()
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "backend TTS disabled for realtime browser profile"}
    assert provider.calls == []


def test_local_audio_synthesize_accepts_language_alias_for_voice(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalTTSProvider(audio_bytes=b"local wav")
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello", "language": "it"},
    )

    assert response.status_code == 200
    assert response.content == b"local wav"
    assert provider.calls == [("Ciao Antonello", "it", False)]


def test_local_audio_synthesize_rejects_oversized_audio_bytes(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(settings, "voice_concierge_tts_audio_max_bytes", 3, raising=False)
    provider = _FakeLocalTTSProvider(audio_bytes=b"local wav")
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "audio payload too large"}
    assert provider.calls == [("Ciao Antonello", None, False)]


def test_local_audio_synthesize_rejects_oversized_audio_file(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    monkeypatch.setattr(settings, "voice_concierge_tts_audio_max_bytes", 3, raising=False)
    provider = _FakeLocalTTSProvider()
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "audio payload too large"}
    assert provider.calls == [("Ciao Antonello", None, False)]
    assert not Path(provider.synthesize_paths[0]).exists()


def test_local_audio_synthesize_deletes_temp_output_after_provider_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "voice_concierge_local_audio_enabled", True)
    provider = _FakeLocalTTSProvider(synthesize_error="private failure /tmp/client.wav")
    app = _build_voice_app(tts_provider=provider)
    client = TestClient(app)

    response = client.post(
        "/api/voice/local-audio/synthesize",
        headers={"X-API-Key": "test_api_key_1"},
        json={"text": "Ciao Antonello"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "local TTS synthesis failed"}
    assert provider.calls == [("Ciao Antonello", None, False)]
    assert "/tmp/client.wav" not in str(response.json())
    assert not Path(provider.synthesize_paths[0]).exists()
