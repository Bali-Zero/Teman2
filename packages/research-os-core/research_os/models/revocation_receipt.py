"""Immutable RevocationReceipt and idempotent replay resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence
from uuid import UUID

from pydantic import Field, ValidationInfo, model_validator
from pydantic_core import PydanticCustomError

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
class RevocationAuthority(FrozenCoreModel):
    role: Identifier
    scope: str = Field(min_length=1)
    verified_at: UtcDateTime


class PropagationTarget(FrozenCoreModel):
    system: Identifier
    object_ref: ExactObjectRef


class RevocationReceipt(FrozenCoreModel):
    revocation_receipt_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    target_ref: ExactObjectRef
    reason_code: RegisteredName
    authority: RevocationAuthority
    actor_ref: ActorRef
    required_propagation_targets: tuple[PropagationTarget, ...]
    classification: Classification
    issued_at: UtcDateTime
    idempotency_key: str = Field(min_length=1)
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    def invalidates(self, reference: ExactObjectRef) -> bool:
        """Return true only for the exact immutable target revision."""

        return reference == self.target_ref

    @model_validator(mode="after")
    def validate_receipt(self, info: ValidationInfo) -> RevocationReceipt:
        validate_extensions(self.extensions, core_fields=set(type(self).model_fields))
        if not (info.context or {}).get("skip_object_hash_check", False):
            expected = object_hash(self)
            if self.object_hash != expected:
                raise PydanticCustomError(
                    "object_hash_mismatch",
                    "object_hash does not match the canonical object",
                )
        return self


@dataclass(frozen=True)
class ResolvedRevocation:
    receipt: RevocationReceipt


@dataclass(frozen=True)
class QuarantinedRevocations:
    reason_codes: tuple[str, ...]
    receipts: tuple[RevocationReceipt, ...]


def resolve_revocation_replay(
    receipts: Sequence[RevocationReceipt],
) -> ResolvedRevocation | QuarantinedRevocations:
    """Resolve replay or quarantine a conflicting idempotency-key claim."""

    if not receipts:
        return QuarantinedRevocations(("missing_receipt",), ())
    first = receipts[0]
    for candidate in receipts[1:]:
        conflict = (
            candidate.idempotency_key != first.idempotency_key
            or candidate.target_ref != first.target_ref
            or candidate.authority != first.authority
            or candidate.reason_code != first.reason_code
        )
        if conflict:
            return QuarantinedRevocations(
                ("conflicting_idempotency_key",),
                tuple(receipts),
            )
    return ResolvedRevocation(first)
