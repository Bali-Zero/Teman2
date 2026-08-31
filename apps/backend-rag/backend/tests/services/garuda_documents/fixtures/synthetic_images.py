"""Synthetic (non-PII, generated) image fixtures for garuda_documents tests.

Per the L5 mandate's PII boundary, no real document image is ever used here — every
"passport" in this module is a rendered placeholder with fabricated data, generated fresh
by each test run.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw


def valid_png_bytes(width: int = 40, height: int = 30, color: tuple[int, int, int] = (10, 40, 90)) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def truncated_png_bytes() -> bytes:
    """A structurally-valid-looking PNG header followed by garbage — the shape corrupt-
    photo-upload.feature targets: declared media type is fine, bytes are not decodable.
    """
    full = valid_png_bytes(width=200, height=150)
    return full[: len(full) // 3]


def non_image_bytes_with_image_extension() -> bytes:
    return b"this is not an image at all, just plain bytes\x00\x01\x02" * 20


def synthetic_passport_biodata_png(
    full_name: str = "TEST TRAVELER SAMPLE",
    passport_number: str = "X0000000",
    nationality: str = "TESTLANDIA",
    passport_expiry_date: str = "2030-01-01",
) -> bytes:
    """Renders a plain, clearly-fake passport biodata page for exercising the real OCR
    pipeline in a live/manual test — never a real document. Intentionally low-fidelity;
    OCR on a genuine passport photo differs, this only proves the pipeline is wired
    correctly end-to-end (bytes -> Ollama -> parsed JSON -> classification).
    """
    img = Image.new("RGB", (800, 500), color=(245, 245, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(20, 20), (780, 480)], outline=(0, 0, 0), width=3)
    lines = [
        "SPECIMEN / NOT A REAL DOCUMENT",
        f"Name: {full_name}",
        f"Passport No: {passport_number}",
        f"Nationality: {nationality}",
        f"Date of Expiry: {passport_expiry_date}",
    ]
    y = 60
    for line in lines:
        draw.text((50, y), line, fill=(0, 0, 0))
        y += 60
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
