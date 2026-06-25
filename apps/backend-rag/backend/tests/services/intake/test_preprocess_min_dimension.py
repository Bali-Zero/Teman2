"""Guard for the qwen2.5vl sub-28px SmartResize panic (TAC 2026-06-19 #16).

A vision image whose smallest side is < 28px makes Ollama's qwen2.5vl
ImageProcessor.SmartResize panic, killing the whole vision runner and taking
down every queued OCR request with it. `_normalize_image_sync` must upscale
such images so they never reach the model below the floor.
"""

from __future__ import annotations

import io

from PIL import Image

from backend.services.intake.preprocess import (
    MIN_OCR_DIMENSION,
    _normalize_image_sync,
)


def _png_bytes(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


def _dims(png: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(png)) as im:
        return im.size


def test_tiny_image_is_upscaled_above_floor() -> None:
    """An 8x8 image (the exact panic repro) is upscaled to >= the floor."""
    out = _normalize_image_sync(_png_bytes(8, 8))
    assert out is not None
    w, h = _dims(out)
    assert min(w, h) >= MIN_OCR_DIMENSION


def test_thin_strip_smallest_side_lifted() -> None:
    """A 4x500 strip: only the small side is below the floor; it gets lifted,
    aspect ratio preserved (width grows proportionally)."""
    out = _normalize_image_sync(_png_bytes(4, 500))
    assert out is not None
    w, h = _dims(out)
    assert min(w, h) >= MIN_OCR_DIMENSION
    assert h > w  # portrait orientation preserved


def test_normal_image_is_not_resized() -> None:
    """A comfortably-large image passes through untouched (no needless resize)."""
    out = _normalize_image_sync(_png_bytes(800, 600))
    assert out is not None
    assert _dims(out) == (800, 600)


def test_exactly_at_floor_is_untouched() -> None:
    """28x28 is exactly the floor — must NOT be upscaled (boundary)."""
    out = _normalize_image_sync(_png_bytes(MIN_OCR_DIMENSION, MIN_OCR_DIMENSION))
    assert out is not None
    assert _dims(out) == (MIN_OCR_DIMENSION, MIN_OCR_DIMENSION)
