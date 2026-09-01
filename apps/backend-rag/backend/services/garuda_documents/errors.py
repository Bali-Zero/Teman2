"""Exceptions for request-shape rejections that never reach idempotent processing.

These map to contract error codes DOCUMENT_TOO_LARGE (413) and
UNSUPPORTED_DOCUMENT_MEDIA_TYPE (415). They are raised BEFORE any document row or work
item would be created — the request itself is malformed, not the content of a valid
request. UNREADABLE_DOCUMENT (422) is deliberately NOT an exception here: it is a real,
idempotency-tracked outcome (`models.UnreadableOutcome`) because a corrupt upload still
creates exactly one staff work item and must replay safely (corrupt-photo-upload.feature).
"""

from __future__ import annotations


class DocumentTooLargeError(Exception):
    """Raised when the upload exceeds the governed size bound. Maps to HTTP 413."""


class UnsupportedMediaTypeError(Exception):
    """Raised when the declared media type is not in the allowed set. Maps to HTTP 415."""


class UnreadableDocumentError(Exception):
    """Internal signal used only inside the OCR pipeline to short-circuit to
    `UnreadableOutcome`; never propagated past `service.py` — the service always
    returns an outcome, it does not raise this to its caller.
    """
