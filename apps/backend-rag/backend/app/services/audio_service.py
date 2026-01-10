"""
Audio Service with Hybrid Provider Strategy

Priority:
1. Pollinations.ai (FREE, no API key)
2. OpenAI (fallback, requires API key)

This provides cost savings when Pollinations works,
with reliable fallback to OpenAI when needed.
"""

import logging
from urllib.parse import quote

import httpx
from openai import AsyncOpenAI

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Pollinations.ai API endpoints (FREE, no API key required)
POLLINATIONS_TTS_URL = "https://text.pollinations.ai"
POLLINATIONS_STT_URL = "https://text.pollinations.ai/openai"


class AudioService:
    """
    Hybrid Audio Service: Pollinations (free) with OpenAI fallback.

    TTS: Pollinations GET endpoint -> OpenAI fallback (5s timeout for fast response)
    STT: OpenAI Whisper (more reliable for transcription)
    """

    def __init__(self):
        # Short timeout for TTS - fallback to OpenAI quickly if Pollinations is slow
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.tts_timeout = 5.0  # Fast fallback to OpenAI for TTS

        # OpenAI client for fallback and STT
        self.openai_api_key = settings.openai_api_key
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            logger.info("AudioService initialized: Pollinations (primary) + OpenAI (fallback)")
        else:
            self.openai_client = None
            logger.warning("AudioService: OpenAI not available (no API key), Pollinations only")

    async def transcribe_audio(
        self, file_path_or_buffer, model: str = "whisper-1", language: str | None = None
    ) -> str:
        """
        Transcribe audio to text.

        Uses OpenAI Whisper for reliability (STT is critical for user experience).
        """
        if not self.openai_client:
            raise ValueError("STT requires OpenAI API key")

        try:
            # Read audio data
            if isinstance(file_path_or_buffer, str):
                file_obj = open(file_path_or_buffer, "rb")
            else:
                file_obj = file_path_or_buffer

            transcript = await self.openai_client.audio.transcriptions.create(
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
        output_path: str | None = None,
    ) -> bytes:
        """
        Generate speech from text.

        Strategy:
        1. Try Pollinations (FREE)
        2. Fallback to OpenAI if Pollinations fails
        """
        # Validate voice
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if voice not in valid_voices:
            voice = "alloy"

        # Try Pollinations first (FREE)
        try:
            audio_content = await self._pollinations_tts(text, voice)
            if audio_content:
                logger.info(f"TTS via Pollinations (FREE): {len(text)} chars, voice={voice}")
                if output_path:
                    with open(output_path, "wb") as f:
                        f.write(audio_content)
                    return output_path
                return audio_content
        except Exception as e:
            logger.warning(f"Pollinations TTS failed, trying OpenAI fallback: {e}")

        # Fallback to OpenAI
        if self.openai_client:
            try:
                audio_content = await self._openai_tts(text, voice, model)
                logger.info(f"TTS via OpenAI (fallback): {len(text)} chars, voice={voice}")
                if output_path:
                    with open(output_path, "wb") as f:
                        f.write(audio_content)
                    return output_path
                return audio_content
            except Exception as e:
                logger.error(f"OpenAI TTS also failed: {e}")
                raise e
        else:
            raise ValueError("All TTS providers failed and OpenAI fallback not available")

    async def _pollinations_tts(self, text: str, voice: str) -> bytes | None:
        """
        Generate speech using Pollinations.ai (FREE).

        Note: Pollinations has rate limits and may be unreliable.
        Returns None if request fails.
        """
        try:
            # URL encode the text - use safe chars for better compatibility
            encoded_text = quote(text, safe="")

            # Build TTS URL
            url = f"{POLLINATIONS_TTS_URL}/{encoded_text}"
            params = {"model": "openai-audio", "voice": voice}

            logger.debug(f"Pollinations TTS request: voice={voice}, text_len={len(text)}")

            response = await self.http_client.get(url, params=params, timeout=self.tts_timeout)

            if response.status_code != 200:
                logger.warning(f"Pollinations TTS returned {response.status_code}")
                return None

            # Verify it's actually audio (not JSON error)
            content_type = response.headers.get("content-type", "")
            if "audio" not in content_type and "octet-stream" not in content_type:
                # Might be JSON error response
                try:
                    error_data = response.json()
                    logger.warning(f"Pollinations returned JSON instead of audio: {error_data}")
                except (ValueError, httpx.DecodingError):
                    logger.debug("Pollinations returned non-audio, non-JSON response")
                return None

            return response.content

        except httpx.TimeoutException:
            logger.warning("Pollinations TTS timeout")
            return None
        except Exception as e:
            logger.warning(f"Pollinations TTS error: {e}")
            return None

    async def _openai_tts(self, text: str, voice: str, model: str = "tts-1") -> bytes:
        """
        Generate speech using OpenAI TTS.
        """
        response = await self.openai_client.audio.speech.create(
            model=model, voice=voice, input=text
        )
        return response.content

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()


# Singleton instance
_audio_service: AudioService | None = None


def get_audio_service() -> AudioService:
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService()
    return _audio_service
