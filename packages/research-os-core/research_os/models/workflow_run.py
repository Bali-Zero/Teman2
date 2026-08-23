"""Immutable WorkflowRun contract from frozen CONTRACTS.md section 12.

Judgment calls (spec silent, encoded conservatively, flagged for ratification
in the P04-D1 handoff report):

- ``run_revision``/``supersedes_workflow_run_ref`` pairing (revision 1 has no
  predecessor, a later revision must bind one) is inferred from the generic
  "positive integer revision + optional supersedes ref" successor-chain shape
  used throughout CONTRACTS.md; it is not verbatim-stated for section 12
  specifically.
- "A run cannot claim success while any mandatory step is failed, unknown, or
  unreceipted" (section 12 invariants) is deliberately NOT enforced here: the
  wire schema has no ``mandatory`` flag on a step (so "any step failed" would
  over-reach the prose, which explicitly qualifies "mandatory step"), no
  ``unknown`` value in the closed ``workflow_state`` enum, and "unreceipted"
  requires cross-referencing ``OperationalReceipt`` records this object does
  not carry. This is a repository/service-layer check, not a single-object
  validator.
- ``started_at``/``ended_at`` ordering (top-level and per-step) mirrors the
  ``ValidTime`` primitive's own "later than start" check for the same class
  of time-interval field; it is not verbatim-stated for this section either.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import WorkflowState
from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
    Classification,
    ExactObjectRef,
    Extensions,
    FrozenCoreModel,
    Identifier,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    WorkflowRunRef,
    validate_extensions,
)


class WorkflowRef(FrozenCoreModel):
    name: Identifier
    version: str = Field(min_length=1)


class ToolModelRef(FrozenCoreModel):
    name: Identifier
    version: str = Field(min_length=1)


class StepLease(FrozenCoreModel):
    owner_ref: ActorRef | None = None
    acquired_at: UtcDateTime | None = None
    expires_at: UtcDateTime | None = None


class WorkflowStep(FrozenCoreModel):
    step_id: str = Field(min_length=1)
    attempt_ids: tuple[UUID, ...]
    state: WorkflowState
    input_hash: Sha256Hex
    output_hash: Sha256Hex | None = None
    idempotency_key: str = Field(min_length=1)
    lease: StepLease
    tools_models: tuple[ToolModelRef, ...]
    started_at: UtcDateTime | None = None
    ended_at: UtcDateTime | None = None
    error_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_step_interval(self) -> WorkflowStep:
        if (
            self.started_at is not None
            and self.ended_at is not None
            and self.ended_at <= self.started_at
        ):
            raise PydanticCustomError(
                "step_ended_at_not_later",
                "a step's ended_at must be strictly later than its started_at",
            )
        return self


class WorkflowRunCost(FrozenCoreModel):
    unit: str = Field(min_length=1)
    estimated: float
    actual: float | None = None
    ceiling: float


class WorkflowRunLineage(FrozenCoreModel):
    input_hashes: tuple[Sha256Hex, ...]
    code_version: str = Field(min_length=1)
    model_version: str | None = Field(default=None, min_length=1)
    prompt_version: str | None = Field(default=None, min_length=1)


class WorkflowRun(FrozenCoreModel):
    workflow_run_id: UUID
    workflow_run_family_id: RegisteredName
    run_revision: int = Field(gt=0)
    supersedes_workflow_run_ref: WorkflowRunRef | None = None
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    workflow: WorkflowRef
    state: WorkflowState
    inputs: tuple[ExactObjectRef, ...]
    steps: tuple[WorkflowStep, ...]
    cost: WorkflowRunCost
    classification: Classification
    started_at: UtcDateTime
    ended_at: UtcDateTime | None = None
    recorded_at: UtcDateTime
    producer: Producer
    lineage: WorkflowRunLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_run(self) -> WorkflowRun:
        if self.run_revision == 1 and self.supersedes_workflow_run_ref is not None:
            raise PydanticCustomError(
                "first_revision_has_predecessor",
                "run_revision 1 must not bind a supersedes_workflow_run_ref",
            )
        if self.run_revision > 1 and self.supersedes_workflow_run_ref is None:
            raise PydanticCustomError(
                "later_revision_missing_predecessor",
                "run_revision greater than 1 must bind the exact current predecessor",
            )
        if self.ended_at is not None and self.ended_at <= self.started_at:
            raise PydanticCustomError(
                "run_ended_at_not_later",
                "ended_at must be strictly later than started_at",
            )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
