"""Real byte-level validation of uploaded images.

corrupt-photo-upload.feature is explicit: "no fixture may bypass byte validation" — a
declared-correct media type (e.g. `image/jpeg`) proves nothing about the bytes behind it.
This module actually decodes the pixel data (`Image.load()`, not just `Image.open()`,
which only reads the header) so a truncated or corrupted file is caught here rather than
surfacing later as a confusing OCR failure.
"""

from __future__ import annotations

import io
import logging

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

ALLOWED_MEDIA_TYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp", "image/heic"})

# Governed upload bound (product.yaml has no number for this yet; conservative default
# for a phone-camera photo — flag to orchestrator if a different bound is decided).
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MiB


def validate_media_type(declared_media_type: str) -> None:
    from backend.services.garuda_documents.errors import UnsupportedMediaTypeError

    if declared_media_type not in ALLOWED_MEDIA_TYPES:
        raise UnsupportedMediaTypeError(declared_media_type)


def validate_size(raw_bytes: bytes) -> None:
    from backend.services.garuda_documents.errors import DocumentTooLargeError

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise DocumentTooLargeError(len(raw_bytes))


def is_readable_image(raw_bytes: bytes) -> bool:
    """Decode the actual pixel data. Returns False for corrupt/truncated/non-image bytes
    regardless of what media type was declared for the upload — the only thing that
    counts is whether Pillow can actually load every pixel.
    """
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.verify()
        # verify() invalidates the file handle for further use per Pillow docs;
        # re-open and fully decode to catch truncation verify() alone can miss.
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.load()
        return True
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        logger.info("garuda_documents: unreadable upload bytes (%s)", type(exc).__name__)
        return False
