import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.audio_service import AudioService, get_audio_service

router = APIRouter(prefix="/audio", tags=["Audio"])
logger = logging.getLogger(__name__)


class SpeechRequest(BaseModel):
    text: str
    voice: Optional[str] = "alloy"  # alloy, echo, fable, onyx, nova, shimmer
    model: Optional[str] = "tts-1"


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    audio_service: AudioService = Depends(get_audio_service),
    # current_user = Depends(get_current_user) # Optional: Enable auth
):
    """
    Transcribe uploaded audio file to text.
    """
    try:
        # Read file into memory
        content = await file.read()
        file_obj = io.BytesIO(content)
        file_obj.name = file.filename  # helper for openai client to guess format

        text = await audio_service.transcribe_audio(file_obj, language=language)
        return {"text": text}
    except Exception as e:
        logger.error(f"Transcribe endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/speech")
async def generate_speech(
    request: SpeechRequest,
    audio_service: AudioService = Depends(get_audio_service),
    # current_user = Depends(get_current_user) # Optional: Enable auth
):
    """
    Generate speech from text (TTS). Returns audio/mpeg stream.
    """
    try:
        # Generate audio content (bytes)
        audio_content = await audio_service.generate_speech(
            text=request.text, voice=request.voice, model=request.model
        )

        # Return as streaming response
        return StreamingResponse(io.BytesIO(audio_content), media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Speech endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
