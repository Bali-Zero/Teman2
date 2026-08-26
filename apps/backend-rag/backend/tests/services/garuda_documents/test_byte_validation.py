from __future__ import annotations

import pytest

from backend.services.garuda_documents import byte_validation
from backend.services.garuda_documents.errors import (
    DocumentTooLargeError,
    UnsupportedMediaTypeError,
)
from backend.tests.services.garuda_documents.fixtures.synthetic_images import (
    non_image_bytes_with_image_extension,
    truncated_png_bytes,
    valid_png_bytes,
)


def test_valid_png_is_readable():
    assert byte_validation.is_readable_image(valid_png_bytes()) is True


def test_truncated_png_is_not_readable():
    # This is the corrupt-photo-upload.feature shape: declared media type is fine
    # (image/png), but the bytes behind it are not decodable.
    assert byte_validation.is_readable_image(truncated_png_bytes()) is False


def test_non_image_bytes_are_not_readable():
    assert byte_validation.is_readable_image(non_image_bytes_with_image_extension()) is False


def test_declared_media_type_alone_does_not_bypass_byte_validation():
    """The guarding property corrupt-photo-upload.feature exists to protect: a caller
    that only checks `validate_media_type` (declared type) and skips `is_readable_image`
    (actual bytes) would wrongly accept a corrupt upload. This test fails if someone
    "fixes" a future red by relaxing `is_readable_image` instead of the real bug.
    """
    corrupt = truncated_png_bytes()
    byte_validation.validate_media_type("image/png")  # declared type passes
    assert byte_validation.is_readable_image(corrupt) is False  # actual bytes do not


def test_unsupported_media_type_rejected():
    with pytest.raises(UnsupportedMediaTypeError):
        byte_validation.validate_media_type("application/pdf")


def test_oversized_upload_rejected():
    oversized = b"0" * (byte_validation.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(DocumentTooLargeError):
        byte_validation.validate_size(oversized)


def test_upload_at_bound_is_accepted():
    at_bound = b"0" * byte_validation.MAX_UPLOAD_BYTES
    try:
        byte_validation.validate_size(at_bound)
    except DocumentTooLargeError:
        pytest.fail("validate_size rejected an upload exactly at MAX_UPLOAD_BYTES")
