"""Immutable RevocationReceipt and idempotent replay resolution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
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
    def validate_receipt(self) -> RevocationReceipt:
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self


@dataclass(frozen=True)
class ResolvedRevocation:
    receipts: tuple[RevocationReceipt, ...]

    @property
    def receipt(self) -> RevocationReceipt:
        """Return the receipt when resolution produced exactly one identity."""
        if len(self.receipts) != 1:
            raise ValueError("resolved batch contains multiple independent receipts")
        return self.receipts[0]


@dataclass(frozen=True)
class QuarantinedRevocations:
    reason_codes: tuple[str, ...]
    receipts: tuple[RevocationReceipt, ...]


def resolve_revocation_replay(
    receipts: Sequence[RevocationReceipt],
) -> ResolvedRevocation | QuarantinedRevocations:
    """Resolve independent claims and exact replays, or quarantine an identity conflict."""

    if not receipts:
        return QuarantinedRevocations(("missing_receipt",), ())

    grouped: dict[tuple[str, str, str], list[RevocationReceipt]] = {}
    for receipt in receipts:
        replay_identity = (
            receipt.target_ref.object_kind,
            receipt.target_ref.object_id,
            receipt.idempotency_key,
        )
        grouped.setdefault(replay_identity, []).append(receipt)

    resolved: list[RevocationReceipt] = []
    for claims in grouped.values():
        canonical_receipt = claims[0]
        if any(claim != canonical_receipt for claim in claims[1:]):
            return QuarantinedRevocations(
                ("conflicting_idempotency_key",),
                tuple(receipts),
            )
        resolved.append(canonical_receipt)
    return ResolvedRevocation(tuple(resolved))
