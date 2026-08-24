"""Shared enums, ID patterns, and the common tool-response envelope.

Frozen per docs/plans/2026-08-25-due-bot-live/MANDATE.md F5 ("Schemas: enums
not free text, IDs not names ... common envelope with audit_ref") and
research/operations/2026-08-25-due-bot-7-lens-research.md §4 (Qwen §4)'s
"Common enums" / "Common response envelope" sections — this module IS that
starting contract, transcribed verbatim (see ../../README.md's naming note
for why this package follows Qwen §4's wire-level shapes literally rather
than the MANDATE prose's dotted-namespace shorthand).

pydantic v2 house style, matching backend/services/client_bot/*: extra
"forbid", frozen=True for immutable facts, model_validator for cross-field
invariants JSON Schema itself cannot express (grammar constraints only
enforce a SUBSET of JSON Schema per the brief's own constraint — pattern/
minLength/maxLength/maxItems are NOT grammar-enforced, so anything these
carry must be re-validated after generation, not merely declared).

Author: Claude Sonnet 5 (lane B3 — team-bot tool registry)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "CLIENT_ID_PATTERN",
    "PRACTICE_ID_PATTERN",
    "STAFF_ID_PATTERN",
    "TARGET_ID_PATTERN",
    "DocumentType",
    "Priority",
    "PracticeStatus",
    "PracticeType",
    "ReasonCode",
    "ReminderType",
    "SourceChannel",
    "ToolError",
    "ToolResult",
]

# F5: "IDs not names (^PR-, ^CL-, ^USR- patterns)" — verbatim from Qwen §4.
CLIENT_ID_PATTERN = r"^CL-[0-9]{4,10}$"
PRACTICE_ID_PATTERN = r"^PR-[0-9]{4,10}$"
STAFF_ID_PATTERN = r"^USR-[0-9]{3,8}$"
# create_reminder's target_id (Qwen §4 tool 8): a practice OR a client.
TARGET_ID_PATTERN = r"^(PR|CL)-[0-9]{4,10}$"


class PracticeStatus(StrEnum):
    DRAFT = "draft"
    DOC_COLLECTION = "doc_collection"
    READY_TO_SUBMIT = "ready_to_submit"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class PracticeType(StrEnum):
    VISIT_VISA = "visit_visa"
    LIMITED_STAY_KITAS = "limited_stay_kitas"
    PERMANENT_STAY_KITAP = "permanent_stay_kitap"
    WORK_PERMIT = "work_permit"
    COMPANY_SETUP = "company_setup"
    TAX_REGISTRATION = "tax_registration"
    COMPLIANCE_CHANGE = "compliance_change"


class DocumentType(StrEnum):
    PASSPORT = "passport"
    PASSPORT_PHOTO = "passport_photo"
    KTP = "ktp"
    NPWP = "npwp"
    BIRTH_CERTIFICATE = "birth_certificate"
    DEED_OF_ESTABLISHMENT = "deed_of_establishment"
    DOMICILE_LETTER = "domicile_letter"
    SPONSOR_LETTER = "sponsor_letter"
    BANK_STATEMENT = "bank_statement"
    TAX_REPORT = "tax_report"
    OTHER_DOCUMENT = "other_document"


class ReminderType(StrEnum):
    DOCUMENT_MISSING = "document_missing"
    APPOINTMENT = "appointment"
    FOLLOW_UP = "follow_up"
    PAYMENT = "payment"
    RENEWAL = "renewal"
    AUTHORITY_RESPONSE = "authority_response"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class SourceChannel(StrEnum):
    """``open_practice``'s ``source_channel`` (Qwen §4 tool 10) — NOT the same
    vocabulary as ``mark_document_received``'s ``source`` field (tool 7),
    which uses ``courier`` where this enum uses ``meeting`` and has no
    ``in_person``/``meeting`` overlap otherwise. See ``tools.py``'s
    ``_DOCUMENT_RECEIVED_SOURCES`` for the deliberately separate constant —
    merging the two would silently accept/reject the wrong values for
    whichever tool borrowed the other's list.
    """

    WHATSAPP = "whatsapp"
    EMAIL = "email"
    PORTAL = "portal"
    IN_PERSON = "in_person"
    MEETING = "meeting"


class ReasonCode(StrEnum):
    DOCS_COMPLETE = "docs_complete"
    DOCS_MISSING = "docs_missing"
    CLIENT_NO_RESPONSE = "client_no_response"
    AUTHORITY_QUERY = "authority_query"
    PAYMENT_PENDING = "payment_pending"
    COMPLETED = "completed"
    DUPLICATE = "duplicate"
    DATA_ERROR = "data_error"


class ToolError(BaseModel):
    """Qwen §4 common-envelope error shape, verbatim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")]
    message: Annotated[str, Field(min_length=1, max_length=500)]
    retryable: bool


class ToolResult(BaseModel):
    """Qwen §4 common response envelope, verbatim shape.

    ``data`` stays a loose ``dict[str, object]`` deliberately: each tool's
    result SHAPE is documented informally in ``tools.py`` (each Qwen §4
    "Returns:" example), mirroring how the frozen client-bot contract's
    ``PricingSnapshot.items`` handles a per-item payload it does not own the
    type of (``client_bot/contracts.py`` — "the concrete per-item pydantic
    model belongs to PricingTool itself ... This is the transport shape").
    Re-typing ten distinct result shapes as ten more frozen models is out of
    scope for a registry unit whose executor does not exist yet; the
    envelope's own invariants (below) are what this unit can actually own.

    ``audit_ref`` is NOT enforced as required here even when ``ok`` is true
    — R0 reads have nothing to audit. Mutation tools (R1-R3, see
    ``ToolSpec.kind``) SHOULD populate it on every successful call; that
    requirement is documented at the tool level, not mechanically enforced
    by this generic envelope, which has no way to know which tool produced
    a given result.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    data: dict[str, object] | None = None
    warnings: tuple[Annotated[str, Field(max_length=300)], ...] = Field(default=(), max_length=20)
    audit_ref: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    error: ToolError | None = None

    @model_validator(mode="after")
    def _ok_constrains_payload(self) -> ToolResult:
        if self.ok and self.error is not None:
            raise ValueError("error must be unset when ok is true")
        if not self.ok and self.error is None:
            raise ValueError("error is required when ok is false")
        return self
