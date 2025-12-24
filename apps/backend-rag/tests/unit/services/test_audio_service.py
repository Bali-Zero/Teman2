"""
Comprehensive unit tests for app/services/audio_service.py
Target: 90%+ coverage
"""

import os
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open

import pytest

# Setup path to backend
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.services.audio_service import AudioService, get_audio_service


class TestAudioServiceInitialization:
    """Test AudioService initialization scenarios"""

    def test_init_with_api_key(self):
        """Test initialization with valid API key"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test_api_key"
            with patch("app.services.audio_service.AsyncOpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                service = AudioService()

                assert service.api_key == "test_api_key"
                assert service.client is not None
                mock_openai.assert_called_once_with(api_key="test_api_key")

    def test_init_without_api_key(self, caplog):
        """Test initialization without API key"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = None

            service = AudioService()

            assert service.api_key is None
            assert service.client is None
            assert "OPENAI_API_KEY not found" in caplog.text

    def test_init_with_empty_api_key(self, caplog):
        """Test initialization with empty string API key"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = ""

            service = AudioService()

            assert service.api_key == ""
            assert service.client is None
            assert "Audio services will be disabled" in caplog.text


class TestAudioServiceTranscribeAudio:
    """Test AudioService.transcribe_audio method"""

    @pytest.fixture
    def service_with_client(self):
        """Create AudioService instance with mocked client"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test_api_key"
            with patch("app.services.audio_service.AsyncOpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                service = AudioService()
                return service

    @pytest.fixture
    def service_without_client(self):
        """Create AudioService instance without client"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = None
            service = AudioService()
            return service

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_file_path_success(self, service_with_client):
        """Test transcribe_audio with file path - success case"""
        mock_transcript = MagicMock()
        mock_transcript.text = "This is the transcribed text"

        mock_audio = MagicMock()
        mock_transcriptions = MagicMock()
        mock_transcriptions.create = AsyncMock(return_value=mock_transcript)
        mock_audio.transcriptions = mock_transcriptions
        service_with_client.client.audio = mock_audio

        mock_file = MagicMock()
        mock_file.read.return_value = b"audio data"

        with patch("builtins.open", mock_open(read_data=b"audio data")) as mock_file_open:
            result = await service_with_client.transcribe_audio("/path/to/audio.mp3")

            assert result == "This is the transcribed text"
            mock_file_open.assert_called_once_with("/path/to/audio.mp3", "rb")
            mock_transcriptions.create.assert_called_once()
            call_kwargs = mock_transcriptions.create.call_args.kwargs
            assert call_kwargs["model"] == "whisper-1"
            assert call_kwargs["language"] is None

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_file_path_and_language(self, service_with_client):
        """Test transcribe_audio with file path and language parameter"""
        mock_transcript = MagicMock()
        mock_transcript.text = "Ini adalah teks yang ditranskripsikan"

        mock_audio = MagicMock()
        mock_transcriptions = MagicMock()
        mock_transcriptions.create = AsyncMock(return_value=mock_transcript)
        mock_audio.transcriptions = mock_transcriptions
        service_with_client.client.audio = mock_audio

        with patch("builtins.open", mock_open(read_data=b"audio data")):
            result = await service_with_client.transcribe_audio(
                "/path/to/audio.mp3", language="id"
            )

            assert result == "Ini adalah teks yang ditranskripsikan"
            call_kwargs = mock_transcriptions.create.call_args.kwargs
            assert call_kwargs["language"] == "id"

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_custom_model(self, service_with_client):
        """Test transcribe_audio with custom model parameter"""
        mock_transcript = MagicMock()
        mock_transcript.text = "Custom model transcription"

        mock_audio = MagicMock()
        mock_transcriptions = MagicMock()
        mock_transcriptions.create = AsyncMock(return_value=mock_transcript)
        mock_audio.transcriptions = mock_transcriptions
        service_with_client.client.audio = mock_audio

        with patch("builtins.open", mock_open(read_data=b"audio data")):
            result = await service_with_client.transcribe_audio(
                "/path/to/audio.mp3", model="whisper-2"
            )

            assert result == "Custom model transcription"
            call_kwargs = mock_transcriptions.create.call_args.kwargs
            assert call_kwargs["model"] == "whisper-2"

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_file_buffer(self, service_with_client):
        """Test transcribe_audio with file-like buffer object"""
        mock_transcript = MagicMock()
        mock_transcript.text = "Buffer transcription"

        mock_audio = MagicMock()
        mock_transcriptions = MagicMock()
        mock_transcriptions.create = AsyncMock(return_value=mock_transcript)
        mock_audio.transcriptions = mock_transcriptions
        service_with_client.client.audio = mock_audio

        # Create a file-like buffer
        buffer = BytesIO(b"audio data")
        buffer.name = "test.mp3"

        result = await service_with_client.transcribe_audio(buffer)

        assert result == "Buffer transcription"
        mock_transcriptions.create.assert_called_once()
        call_kwargs = mock_transcriptions.create.call_args.kwargs
        assert call_kwargs["file"] == buffer

    @pytest.mark.asyncio
    async def test_transcribe_audio_without_client(self, service_without_client):
        """Test transcribe_audio without initialized client"""
        with pytest.raises(ValueError, match="Audio service is not available"):
            await service_without_client.transcribe_audio("/path/to/audio.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_audio_api_exception(self, service_with_client, caplog):
        """Test transcribe_audio when API raises exception"""
        mock_audio = MagicMock()
        mock_transcriptions = MagicMock()
        mock_transcriptions.create = AsyncMock(side_effect=Exception("API Error"))
        mock_audio.transcriptions = mock_transcriptions
        service_with_client.client.audio = mock_audio

        with patch("builtins.open", mock_open(read_data=b"audio data")):
            with pytest.raises(Exception, match="API Error"):
                await service_with_client.transcribe_audio("/path/to/audio.mp3")

            assert "Audio transcription failed" in caplog.text

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_closes_on_success(self, service_with_client):
        """Test that file is properly closed after successful transcription"""
        mock_transcript = MagicMock()
        mock_transcript.text = "Transcription"

        mock_audio = MagicMock()
        mock_transcriptions = MagicMock()
        mock_transcriptions.create = AsyncMock(return_value=mock_transcript)
        mock_audio.transcriptions = mock_transcriptions
        service_with_client.client.audio = mock_audio

        mock_file = MagicMock()
        mock_file.read.return_value = b"audio data"

        with patch("builtins.open", return_value=mock_file) as mock_open_func:
            await service_with_client.transcribe_audio("/path/to/audio.mp3")
            mock_file.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_closes_on_exception(self, service_with_client):
        """Test that file is properly closed even when exception occurs"""
        mock_audio = MagicMock()
        mock_transcriptions = MagicMock()
        mock_transcriptions.create = AsyncMock(side_effect=Exception("Error"))
        mock_audio.transcriptions = mock_transcriptions
        service_with_client.client.audio = mock_audio

        mock_file = MagicMock()

        with patch("builtins.open", return_value=mock_file):
            with pytest.raises(Exception):
                await service_with_client.transcribe_audio("/path/to/audio.mp3")
            mock_file.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_audio_buffer_not_closed(self, service_with_client):
        """Test that buffer objects are not closed (only file paths are closed)"""
        mock_transcript = MagicMock()
        mock_transcript.text = "Buffer transcription"

        mock_audio = MagicMock()
        mock_transcriptions = MagicMock()
        mock_transcriptions.create = AsyncMock(return_value=mock_transcript)
        mock_audio.transcriptions = mock_transcriptions
        service_with_client.client.audio = mock_audio

        buffer = BytesIO(b"audio data")
        buffer.name = "test.mp3"
        buffer.close = MagicMock()  # Mock close to verify it's not called

        await service_with_client.transcribe_audio(buffer)

        # Buffer.close should NOT be called since we didn't open it
        buffer.close.assert_not_called()


class TestAudioServiceGenerateSpeech:
    """Test AudioService.generate_speech method"""

    @pytest.fixture
    def service_with_client(self):
        """Create AudioService instance with mocked client"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test_api_key"
            with patch("app.services.audio_service.AsyncOpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                service = AudioService()
                return service

    @pytest.fixture
    def service_without_client(self):
        """Create AudioService instance without client"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = None
            service = AudioService()
            return service

    @pytest.mark.asyncio
    async def test_generate_speech_success_with_output_path(self, service_with_client):
        """Test generate_speech with output path - success case"""
        mock_response = MagicMock()
        mock_response.stream_to_file = MagicMock()

        mock_speech = MagicMock()
        mock_speech.create = AsyncMock(return_value=mock_response)
        mock_audio = MagicMock()
        mock_audio.speech = mock_speech
        service_with_client.client.audio = mock_audio

        result = await service_with_client.generate_speech(
            "Hello world", output_path="/output/audio.mp3"
        )

        assert result == "/output/audio.mp3"
        mock_speech.create.assert_called_once()
        call_kwargs = mock_speech.create.call_args.kwargs
        assert call_kwargs["model"] == "tts-1"
        assert call_kwargs["voice"] == "alloy"
        assert call_kwargs["input"] == "Hello world"
        mock_response.stream_to_file.assert_called_once_with("/output/audio.mp3")

    @pytest.mark.asyncio
    async def test_generate_speech_success_without_output_path(self, service_with_client):
        """Test generate_speech without output path - returns bytes"""
        mock_response = MagicMock()
        mock_response.content = b"audio bytes content"

        mock_speech = MagicMock()
        mock_speech.create = AsyncMock(return_value=mock_response)
        mock_audio = MagicMock()
        mock_audio.speech = mock_speech
        service_with_client.client.audio = mock_audio

        result = await service_with_client.generate_speech("Hello world")

        assert result == b"audio bytes content"
        mock_speech.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_speech_with_custom_voice(self, service_with_client):
        """Test generate_speech with custom voice parameter"""
        mock_response = MagicMock()
        mock_response.content = b"audio bytes"

        mock_speech = MagicMock()
        mock_speech.create = AsyncMock(return_value=mock_response)
        mock_audio = MagicMock()
        mock_audio.speech = mock_speech
        service_with_client.client.audio = mock_audio

        result = await service_with_client.generate_speech("Hello", voice="onyx")

        assert result == b"audio bytes"
        call_kwargs = mock_speech.create.call_args.kwargs
        assert call_kwargs["voice"] == "onyx"

    @pytest.mark.asyncio
    async def test_generate_speech_with_custom_model(self, service_with_client):
        """Test generate_speech with custom model parameter"""
        mock_response = MagicMock()
        mock_response.content = b"audio bytes"

        mock_speech = MagicMock()
        mock_speech.create = AsyncMock(return_value=mock_response)
        mock_audio = MagicMock()
        mock_audio.speech = mock_speech
        service_with_client.client.audio = mock_audio

        result = await service_with_client.generate_speech("Hello", model="tts-1-hd")

        assert result == b"audio bytes"
        call_kwargs = mock_speech.create.call_args.kwargs
        assert call_kwargs["model"] == "tts-1-hd"

    @pytest.mark.asyncio
    async def test_generate_speech_with_all_voices(self, service_with_client):
        """Test generate_speech with all available voice options"""
        voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

        for voice in voices:
            mock_response = MagicMock()
            mock_response.content = b"audio bytes"

            mock_speech = MagicMock()
            mock_speech.create = AsyncMock(return_value=mock_response)
            mock_audio = MagicMock()
            mock_audio.speech = mock_speech
            service_with_client.client.audio = mock_audio

            result = await service_with_client.generate_speech("Test", voice=voice)

            assert result == b"audio bytes"
            call_kwargs = mock_speech.create.call_args.kwargs
            assert call_kwargs["voice"] == voice

    @pytest.mark.asyncio
    async def test_generate_speech_without_client(self, service_without_client):
        """Test generate_speech without initialized client"""
        with pytest.raises(ValueError, match="Audio service is not available"):
            await service_without_client.generate_speech("Hello world")

    @pytest.mark.asyncio
    async def test_generate_speech_api_exception(self, service_with_client, caplog):
        """Test generate_speech when API raises exception"""
        mock_speech = MagicMock()
        mock_speech.create = AsyncMock(side_effect=Exception("TTS API Error"))
        mock_audio = MagicMock()
        mock_audio.speech = mock_speech
        service_with_client.client.audio = mock_audio

        with pytest.raises(Exception, match="TTS API Error"):
            await service_with_client.generate_speech("Hello world")

        assert "Speech generation failed" in caplog.text

    @pytest.mark.asyncio
    async def test_generate_speech_long_text(self, service_with_client):
        """Test generate_speech with long text input"""
        long_text = "This is a very long text. " * 100  # ~2600 characters

        mock_response = MagicMock()
        mock_response.content = b"long audio bytes"

        mock_speech = MagicMock()
        mock_speech.create = AsyncMock(return_value=mock_response)
        mock_audio = MagicMock()
        mock_audio.speech = mock_speech
        service_with_client.client.audio = mock_audio

        result = await service_with_client.generate_speech(long_text)

        assert result == b"long audio bytes"
        call_kwargs = mock_speech.create.call_args.kwargs
        assert call_kwargs["input"] == long_text

    @pytest.mark.asyncio
    async def test_generate_speech_empty_text(self, service_with_client):
        """Test generate_speech with empty text"""
        mock_response = MagicMock()
        mock_response.content = b""

        mock_speech = MagicMock()
        mock_speech.create = AsyncMock(return_value=mock_response)
        mock_audio = MagicMock()
        mock_audio.speech = mock_speech
        service_with_client.client.audio = mock_audio

        result = await service_with_client.generate_speech("")

        assert result == b""

    @pytest.mark.asyncio
    async def test_generate_speech_unicode_text(self, service_with_client):
        """Test generate_speech with Unicode text"""
        unicode_text = "Selamat pagi! 你好! こんにちは! 🎉"

        mock_response = MagicMock()
        mock_response.content = b"unicode audio bytes"

        mock_speech = MagicMock()
        mock_speech.create = AsyncMock(return_value=mock_response)
        mock_audio = MagicMock()
        mock_audio.speech = mock_speech
        service_with_client.client.audio = mock_audio

        result = await service_with_client.generate_speech(unicode_text)

        assert result == b"unicode audio bytes"
        call_kwargs = mock_speech.create.call_args.kwargs
        assert call_kwargs["input"] == unicode_text


class TestGetAudioServiceSingleton:
    """Test get_audio_service singleton function"""

    def test_get_audio_service_returns_instance(self):
        """Test that get_audio_service returns an AudioService instance"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test_key"
            with patch("app.services.audio_service.AsyncOpenAI"):
                # Reset singleton
                import app.services.audio_service
                app.services.audio_service._audio_service = None

                service = get_audio_service()

                assert isinstance(service, AudioService)

    def test_get_audio_service_singleton_behavior(self):
        """Test that get_audio_service returns the same instance"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test_key"
            with patch("app.services.audio_service.AsyncOpenAI"):
                # Reset singleton
                import app.services.audio_service
                app.services.audio_service._audio_service = None

                service1 = get_audio_service()
                service2 = get_audio_service()

                assert service1 is service2

    def test_get_audio_service_without_api_key(self):
        """Test get_audio_service when API key is not available"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = None

            # Reset singleton
            import app.services.audio_service
            app.services.audio_service._audio_service = None

            service = get_audio_service()

            assert isinstance(service, AudioService)
            assert service.client is None


class TestAudioServiceEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_open_exception(self):
        """Test transcribe_audio when file cannot be opened"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test_key"
            with patch("app.services.audio_service.AsyncOpenAI"):
                service = AudioService()

                with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
                    with pytest.raises(FileNotFoundError):
                        await service.transcribe_audio("/nonexistent/file.mp3")

    @pytest.mark.asyncio
    async def test_generate_speech_stream_to_file_exception(self, caplog):
        """Test generate_speech when stream_to_file raises exception"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test_key"
            with patch("app.services.audio_service.AsyncOpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                service = AudioService()

                mock_response = MagicMock()
                mock_response.stream_to_file = MagicMock(
                    side_effect=IOError("Cannot write to file")
                )

                mock_speech = MagicMock()
                mock_speech.create = AsyncMock(return_value=mock_response)
                mock_audio = MagicMock()
                mock_audio.speech = mock_speech
                service.client.audio = mock_audio

                with pytest.raises(IOError, match="Cannot write to file"):
                    await service.generate_speech("Test", output_path="/invalid/path.mp3")

                assert "Speech generation failed" in caplog.text

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_various_file_extensions(self):
        """Test transcribe_audio with different audio file extensions"""
        file_extensions = [".mp3", ".wav", ".m4a", ".flac", ".ogg"]

        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test_key"
            with patch("app.services.audio_service.AsyncOpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                service = AudioService()

                mock_transcript = MagicMock()
                mock_transcript.text = "Transcription"

                mock_audio = MagicMock()
                mock_transcriptions = MagicMock()
                mock_transcriptions.create = AsyncMock(return_value=mock_transcript)
                mock_audio.transcriptions = mock_transcriptions
                service.client.audio = mock_audio

                for ext in file_extensions:
                    with patch("builtins.open", mock_open(read_data=b"audio data")):
                        result = await service.transcribe_audio(f"/path/to/file{ext}")
                        assert result == "Transcription"

    @pytest.mark.asyncio
    async def test_generate_speech_special_characters_in_path(self):
        """Test generate_speech with special characters in output path"""
        with patch("app.services.audio_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test_key"
            with patch("app.services.audio_service.AsyncOpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                service = AudioService()

                mock_response = MagicMock()
                mock_response.stream_to_file = MagicMock()

                mock_speech = MagicMock()
                mock_speech.create = AsyncMock(return_value=mock_response)
                mock_audio = MagicMock()
                mock_audio.speech = mock_speech
                service.client.audio = mock_audio

                special_path = "/path/with spaces/and-dashes/file_name.mp3"
                result = await service.generate_speech("Test", output_path=special_path)

                assert result == special_path
                mock_response.stream_to_file.assert_called_once_with(special_path)
