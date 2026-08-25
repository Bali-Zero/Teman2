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

# `image/heic` deliberately excluded (refuter finding, 2026-08-25): stock Pillow cannot
# decode HEIC without the optional `pillow-heif` plugin being explicitly registered, and
# even a decoded HEIC would still need transcoding to PNG/JPEG before qwen2.5vl:7b's
# Ollama chat API can read it — sending raw HEIC bytes there fails the OCR call outright.
# An iPhone HEIC upload is correctly rejected at 415 today rather than silently 422/503ing
# later. Re-add only alongside an explicit HEIF-decode + transcode step in this module.
ALLOWED_MEDIA_TYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})

# Governed upload bound (product.yaml has no number for this yet; conservative default
# for a phone-camera photo — flag to orchestrator if a different bound is decided).
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MiB

# A phone photo within MAX_UPLOAD_BYTES decompressed to raw RGB is a few tens of MB; this
# caps it well above any real camera output while rejecting a crafted decompression bomb
# (a small compressed file whose declared dimensions decode to gigabytes of pixel data).
MAX_IMAGE_PIXELS = 40_000_000  # ~40MP, e.g. 8000x5000


def validate_media_type(declared_media_type: str) -> None:
    from backend.services.garuda_documents.errors import UnsupportedMediaTypeError

    if declared_media_type not in ALLOWED_MEDIA_TYPES:
        raise UnsupportedMediaTypeError(declared_media_type)


def validate_size(raw_bytes: bytes) -> None:
    from backend.services.garuda_documents.errors import DocumentTooLargeError

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise DocumentTooLargeError(len(raw_bytes))


def is_readable_image(raw_bytes: bytes) -> bool:
    """Decode the actual pixel data. Returns False for corrupt/truncated/non-image bytes,
    and for a decompression-bomb-shaped file, regardless of what media type was declared
    for the upload — the only thing that counts is whether Pillow can actually load every
    pixel, safely.
    """
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.verify()
        # verify() invalidates the file handle for further use per Pillow docs;
        # re-open to check declared dimensions BEFORE decoding pixels — a crafted file can
        # be a few KB compressed but declare gigabytes of raw pixel data.
        with Image.open(io.BytesIO(raw_bytes)) as img:
            if img.width * img.height > MAX_IMAGE_PIXELS:
                logger.info("garuda_documents: rejecting oversized declared dimensions")
                return False
            img.load()
        return True
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        MemoryError,
    ) as exc:
        logger.info("garuda_documents: unreadable upload bytes (%s)", type(exc).__name__)
        return False
