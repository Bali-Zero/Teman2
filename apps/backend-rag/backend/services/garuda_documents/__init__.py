"""GARUDA VOA — lane L5: document upload + local-first OCR.

This package is the storage-agnostic core of the customer document intake pipeline
described in `products/garuda-voa/journeys/corrupt-photo-upload.feature` and
`.../uncertain-ocr.feature`. It deliberately owns no HTTP route (L2 owns the router)
and no database migration (L1 owns `migrations_v2/`); it is wired into both once
those lanes land, via the `DocumentStorePort` protocol in `ports.py`.

Guardrail G-OCR-LOCAL (product.yaml): OCR runs local-first on qwen2.5vl:7b. Cloud
reinforcement, if ever enabled, may only see redacted material and only reinforces —
it never replaces local evidence or customer confirmation (see `redaction.py`).
"""

from backend.services.garuda_documents.errors import (
    DocumentTooLargeError,
    UnreadableDocumentError,
    UnsupportedMediaTypeError,
)
from backend.services.garuda_documents.models import (
    DocumentOutcome,
    LowConfidenceOutcome,
    PassportReviewFieldName,
    ProcessingOutcome,
    ProcessingState,
    ReadyOutcome,
    ReviewField,
    UncertainReviewField,
    UnreadableOutcome,
)
from backend.services.garuda_documents.service import (
    DocumentIntakeService,
    DocumentProcessingUnavailableError,
)

__all__ = [
    "DocumentIntakeService",
    "DocumentOutcome",
    "DocumentProcessingUnavailableError",
    "DocumentTooLargeError",
    "LowConfidenceOutcome",
    "PassportReviewFieldName",
    "ProcessingOutcome",
    "ProcessingState",
    "ReadyOutcome",
    "ReviewField",
    "UncertainReviewField",
    "UnreadableDocumentError",
    "UnreadableOutcome",
    "UnsupportedMediaTypeError",
]
