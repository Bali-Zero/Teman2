"""
Unit tests for audio router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.audio import router, get_audio_service


@pytest.fixture
def mock_audio_service():
    """Mock AudioService"""
    service = MagicMock()
    service.transcribe_audio = AsyncMock(return_value="Transcribed text")
    service.generate_speech = AsyncMock(return_value=b"audio content")
    return service


@pytest.fixture
def app(mock_audio_service):
    """Create FastAPI app with router and dependency override"""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_audio_service] = lambda: mock_audio_service
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestAudioRouter:
    """Tests for audio router"""

    def test_get_audio_service(self):
        """Test getting audio service"""
        # Reset global if needed
        import app.services.audio_service as module
        module._audio_service = None
        
        with patch("app.services.audio_service.AudioService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            service = get_audio_service()
            assert service is not None

    def test_transcribe_audio(self, client, mock_audio_service):
        """Test transcribing audio"""
        test_file = ("audio.mp3", b"audio content", "audio/mpeg")
        
        response = client.post(
            "/audio/transcribe",
            files={"file": test_file}
        )
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert data["text"] == "Transcribed text"

    def test_transcribe_audio_with_language(self, client, mock_audio_service):
        """Test transcribing audio with language parameter"""
        test_file = ("audio.mp3", b"audio content", "audio/mpeg")
        
        response = client.post(
            "/audio/transcribe?language=it",
            files={"file": test_file}
        )
        assert response.status_code == 200
        mock_audio_service.transcribe_audio.assert_called_once()

    def test_transcribe_audio_error(self, app, client, mock_audio_service):
        """Test transcribing audio with error"""
        mock_audio_service.transcribe_audio.side_effect = Exception("Transcription error")
        app.dependency_overrides[get_audio_service] = lambda: mock_audio_service
        
        test_file = ("audio.mp3", b"audio content", "audio/mpeg")
        
        response = client.post(
            "/audio/transcribe",
            files={"file": test_file}
        )
        assert response.status_code == 500

    def test_generate_speech(self, client, mock_audio_service):
        """Test generating speech"""
        response = client.post(
            "/audio/speech",
            json={"text": "Hello world", "voice": "alloy", "model": "tts-1"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"

    def test_generate_speech_default_voice(self, client, mock_audio_service):
        """Test generating speech with default voice"""
        response = client.post(
            "/audio/speech",
            json={"text": "Hello world"}
        )
        assert response.status_code == 200
        mock_audio_service.generate_speech.assert_called_once()

    def test_generate_speech_error(self, app, client, mock_audio_service):
        """Test generating speech with error"""
        mock_audio_service.generate_speech.side_effect = Exception("Speech error")
        app.dependency_overrides[get_audio_service] = lambda: mock_audio_service
        
        response = client.post(
            "/audio/speech",
            json={"text": "Hello world"}
        )
        assert response.status_code == 500

