"""Immutable VerificationReceipt contract from frozen CONTRACTS.md section 14.

Judgment calls (spec silent, encoded conservatively, flagged for ratification
in the P04-D1 handoff report):

- "A verifier cannot approve an object hash it generated when the gate
  requires independence" is NOT enforced here: this object carries
  ``verifier.independence_class`` (an open string, not a section-3 closed
  enum) and ``target_objects``, but never the *producer* of the target
  object it is verifying, so there is no field on this wire object that lets
  a single-object validator compare "who verified" against "who produced".
  This is a cross-object, repository-level check.
- ``verifier.independence_class`` has no registered value set anywhere in
  section 3's closed enum table, unlike every other classification-style
  field in this spec; it is typed as an open string here rather than an
  invented closed enum.
- ``limits`` is wire-typed only as bare ``[]`` with no item shape shown. This
  file reads it as a tuple of short non-empty strings (consistent with the
  ``reasons: [code]`` shape used for the same kind of field elsewhere in
  CONTRACTS.md), not as a stronger structured object -- flagged as
  underspecified.
- "``pass_with_limits`` cannot be interpreted as unrestricted approval" is
  interpretive/consumer-facing guidance, not a schema-shape requirement; it
  is deliberately NOT read as "``limits`` must be non-empty when
  ``verdict == pass_with_limits``" because a limit could equally be recorded
  per-check via ``note_code`` rather than in the top-level ``limits`` array,
  and the prose never says which.
- "Domain findings ... live in a namespaced extension; they never redefine
  the canonical verdict" is satisfied by construction (``extra="forbid"`` on
  every core object plus the extension-payload core-field jail in
  ``primitives.validate_extensions``); no additional validator is needed for
  it.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import GateDisposition, VerificationVerdict
from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
    Classification,
    ExactObjectRef,
    Extensions,
    FrozenCoreModel,
    Identifier,
    Lineage,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)


class VerificationReceiptRef(FrozenCoreModel):
    verification_receipt_id: UUID
    object_hash: Sha256Hex


class VerifierRef(FrozenCoreModel):
    name: Identifier
    version: str = Field(min_length=1)
    actor_ref: ActorRef | None = None
    independence_class: str = Field(min_length=1)


class TemporalScope(FrozenCoreModel):
    target_valid_from: UtcDateTime | None = None
    target_valid_to: UtcDateTime | None = None
    source_cutoff_at: UtcDateTime | None = None
    checked_at: UtcDateTime


class VerificationCheck(FrozenCoreModel):
    check_id: str = Field(min_length=1)
    result: GateDisposition
    evidence_refs: tuple[ExactObjectRef, ...]
    note_code: str | None = Field(default=None, min_length=1)


class SourceVersionRef(FrozenCoreModel):
    source_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    content_hash: Sha256Hex


class VerificationReceipt(FrozenCoreModel):
    verification_receipt_id: UUID
    verification_receipt_family_id: RegisteredName
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    supersedes_verification_receipt_ref: VerificationReceiptRef | None = None
    target_objects: tuple[ExactObjectRef, ...]
    verification_type: RegisteredName
    verifier: VerifierRef
    criteria_version: str = Field(min_length=1)
    temporal_scope: TemporalScope
    checks: tuple[VerificationCheck, ...]
    verdict: VerificationVerdict
    limits: tuple[str, ...]
    source_versions: tuple[SourceVersionRef, ...]
    classification: Classification
    issued_at: UtcDateTime
    recorded_at: UtcDateTime
    expires_at: UtcDateTime | None = None
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_receipt(self) -> VerificationReceipt:
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
