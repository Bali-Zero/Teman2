"""Immutable ObjectSuccessorEdge contract from frozen section 3.1."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import model_validator
from pydantic_core import PydanticCustomError

from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
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


class ObjectSuccessorEdge(FrozenCoreModel):
    object_successor_edge_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    object_kind: Identifier
    family_id: RegisteredName
    predecessor_ref: ExactObjectRef
    successor_ref: ExactObjectRef
    reason_code: RegisteredName
    recorded_at: UtcDateTime
    actor_ref: ActorRef | None = None
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_edge(self) -> ObjectSuccessorEdge:
        if self.predecessor_ref == self.successor_ref:
            raise PydanticCustomError(
                "successor_ref_same_as_predecessor",
                "predecessor_ref and successor_ref must differ",
            )
        if (
            self.predecessor_ref.object_kind != self.object_kind
            or self.successor_ref.object_kind != self.object_kind
        ):
            raise PydanticCustomError(
                "object_kind_mismatch",
                "edge and both exact references must have the same object_kind",
            )
        validate_extensions(self.extensions)

        # FREEZE-CONFLICT: section 3.1's exact_object_ref has no tenant,
        # family_id, or recorded_at fields. Those frozen cross-object
        # invariants cannot be checked on this wire object without adding
        # noncanonical fields, so graph.select_current_member enforces them
        # against the referenced complete members instead.
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
