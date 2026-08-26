"""Domain types for GARUDA VOA document intake.

Mirrors `products/garuda-voa/contracts/openapi.yaml` components
(`DocumentUploadRequest`, `ReadyDocument`, `ProcessingDocument`, `LowConfidenceDocument`,
`PassportReviewFieldName`) exactly — these are frozen, this module does not invent shapes.
The frozen contract has no schema for the 422 UNREADABLE_DOCUMENT success-shaped body (it is
an error response), so `UnreadableOutcome` here is domain-internal: it lets the service track
idempotency and the one staff work item across a retried upload without ever being serialized
by that shape. The router (L2) is responsible for mapping it to the 422 error envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PassportReviewFieldName(str, Enum):
    """Closed authenticated passport-review vocabulary (contract: PassportReviewFieldName)."""

    FULL_NAME = "full_name"
    PASSPORT_NUMBER = "passport_number"
    NATIONALITY = "nationality"
    PASSPORT_EXPIRY_DATE = "passport_expiry_date"


class ProcessingState(str, Enum):
    PROCESSING = "PROCESSING"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"


class DocumentKind(str, Enum):
    """Only member the contract's `DocumentUploadRequest.document_kind` const allows today."""

    PASSPORT_BIODATA = "PASSPORT_BIODATA"


@dataclass(frozen=True)
class ReviewField:
    field_path: PassportReviewFieldName
    value: str
    confirmation_required: bool

    def __post_init__(self) -> None:
        if len(self.value) > 512:
            raise ValueError("ReviewField.value exceeds contract maxLength 512")


@dataclass(frozen=True)
class UncertainReviewField:
    field_path: PassportReviewFieldName
    confirmation_required: bool = True

    def __post_init__(self) -> None:
        if not self.confirmation_required:
            raise ValueError("UncertainReviewField.confirmation_required is a const true")


@dataclass(frozen=True)
class ReadyOutcome:
    document_id: str
    review_fields: tuple[ReviewField, ...]
    processing_state: ProcessingState = field(default=ProcessingState.READY_FOR_REVIEW, init=False)


@dataclass(frozen=True)
class ProcessingOutcome:
    document_id: str
    processing_state: ProcessingState = field(default=ProcessingState.PROCESSING, init=False)


@dataclass(frozen=True)
class LowConfidenceOutcome:
    document_id: str
    uncertain_fields: tuple[UncertainReviewField, ...]
    processing_state: ProcessingState = field(default=ProcessingState.LOW_CONFIDENCE, init=False)

    def __post_init__(self) -> None:
        if not self.uncertain_fields:
            raise ValueError("LowConfidenceOutcome requires minItems: 1 uncertain_fields")


@dataclass(frozen=True)
class UnreadableOutcome:
    """Domain-internal terminal state for the 422 UNREADABLE_DOCUMENT path (see module docstring)."""

    document_id: str


DocumentOutcome = ReadyOutcome | ProcessingOutcome | LowConfidenceOutcome | UnreadableOutcome
