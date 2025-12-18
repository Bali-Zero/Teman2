import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from services.image_generation_service import ImageGenerationService

router = APIRouter(prefix="/media", tags=["media"])
logger = logging.getLogger(__name__)


class ImagePrompt(BaseModel):
    prompt: str


@router.post("/generate-image")
async def generate_image(request: ImagePrompt):
    """
    Generate an image from a text prompt.
    """
    try:
        service = ImageGenerationService()
        result = await service.generate_image(request.prompt)

        if result["success"]:
            return {
                "success": True,
                "url": result["url"],
                "prompt": result.get("prompt"),
                "service": result.get("service", "unknown"),
            }
        else:
            # Return proper HTTP status codes for different error types
            if "not configured" in result["error"]:
                raise HTTPException(status_code=503, detail=result)
            elif "Invalid prompt" in result["error"]:
                raise HTTPException(status_code=400, detail=result)
            else:
                raise HTTPException(status_code=500, detail=result)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": "Internal server error", "details": str(e)},
        ) from e


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file (image, audio, doc) to the server.
    Returns the URL/path to the file.
    """
    try:
        # Create uploads directory if not exists
        upload_dir = Path("static/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        file_ext = Path(file.filename).suffix
        filename = f"{uuid.uuid4()}{file_ext}"
        file_path = upload_dir / filename

        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # In a real app, you'd return a public URL.
        # For now, we return the relative static path we can serve.
        # Assuming '/static' is mounted.
        # If not, we might need to adjust or return just the path for internal use.
        return {
            "success": True,
            "filename": file.filename,
            "url": f"/static/uploads/{filename}",
            "type": file.content_type,
        }

    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": "Upload failed", "details": str(e)},
        )
