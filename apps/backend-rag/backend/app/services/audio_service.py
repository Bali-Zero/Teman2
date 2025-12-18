import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class AudioService:
    def __init__(self):
        self.api_key = settings.openai_api_key
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not found. Audio services will be disabled.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)

    async def transcribe_audio(
        self, file_path_or_buffer, model: str = "whisper-1", language: Optional[str] = None
    ):
        """
        Transcribe audio to text using OpenAI Whisper.
        """
        if not self.client:
            raise ValueError("Audio service is not available (missing API key)")

        try:
            # Check if input is a path or buffer-like
            if isinstance(file_path_or_buffer, str):
                file_obj = open(file_path_or_buffer, "rb")
            else:
                file_obj = file_path_or_buffer  # Assumes it's a file-like object with a name attribute or similar

            transcript = await self.client.audio.transcriptions.create(
                model=model, file=file_obj, language=language
            )
            return transcript.text
        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            raise e
        finally:
            if isinstance(file_path_or_buffer, str) and "file_obj" in locals():
                file_obj.close()

    async def generate_speech(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1",
        output_path: Optional[str] = None,
    ):
        """
        Generate speech from text (TTS).
        """
        if not self.client:
            raise ValueError("Audio service is not available (missing API key)")

        try:
            # Map "oracle" personas to voices if needed
            # Voices: alloy, echo, fable, onyx, nova, shimmer
            # DeepThink/Oracle -> Onyx (Deep/Authoritative) or Alloy (Standard)

            response = await self.client.audio.speech.create(model=model, voice=voice, input=text)

            if output_path:
                response.stream_to_file(output_path)
                return output_path
            else:
                # Return raw bytes
                return response.content
        except Exception as e:
            logger.error(f"Speech generation failed: {e}")
            raise e


# Singleton instance
_audio_service = None


def get_audio_service() -> AudioService:
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService()
    return _audio_service
