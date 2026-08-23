"""Immutable OperationalReceipt contract from frozen CONTRACTS.md section 13.5.

Purpose, verbatim: "record an immutable execution result or other typed
operational acknowledgment without updating the originating attempt or
action." This is the chain's closing link: "a typed terminal
``OperationalReceipt`` closes it" (packet brief). Two shared invariants do
the real work and are both implemented below:

- "An ``execution.result`` receipt requires the exact attempt ID/hash and
  one terminal outcome. There is one current result per attempt; retries
  create new numbered attempts. Duplicate idempotency resolves to the same
  receipt."
- "A queue-only triage, assignment, snooze, rejection, split,
  merge-duplicate, evidence-request, or closure ... carries no
  ``ExecutionAttempt`` ... and cannot authorize a downstream effect."
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import EffectStatus, ExecutionTerminalOutcome, ReconciliationState
from research_os.hashing import object_hash
from research_os.models.execution_attempt import ExecutionAttempt
from research_os.primitives import (
    ActorRef,
    Classification,
    ExactObjectRef,
    Extensions,
    FrozenCoreModel,
    Lineage,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)

# Section 13.5 body: "The v1 registry includes at least ..." -- the MINIMUM
# registry, transcribed verbatim. Domain packets may register more through
# Packet 04 compatibility review (rule 1.10), so `receipt_type` is typed as
# an open `RegisteredName`, not a closed enum -- this list is a reachability
# floor these invariants can name, not a ceiling on what may appear on the
# wire.
MINIMUM_OPERATIONAL_RECEIPT_TYPES: frozenset[str] = frozenset(
    {
        "execution.result",
        "team.acknowledgment",
        "team.partial",
        "team.completion",
        "team.blocked",
        "team.cancelled",
        "team.superseded",
        "routing.assignment",
        "queue.triage",
        "queue.rejected",
        "queue.snoozed",
        "queue.split",
        "queue.merge_duplicate",
        "queue.evidence_requested",
        "revocation.propagation",
    }
)

# INTERPRETATION: section 13, shared invariants: "A queue-only triage,
# assignment, snooze, rejection, split, merge-duplicate, evidence-request,
# or closure atomically appends the next ActionItem revision ... carries no
# ExecutionAttempt, has no ApprovalReceipt subject, and cannot authorize a
# downstream effect." That sentence names 7 queue actions; mapped onto the
# v1 receipt-type registry above by name, "assignment" is `routing.assignment`
# and the rest are their `queue.*` siblings. "closure" has no dedicated v1
# receipt_type (an ActionItem closure is recorded on the ActionItem revision
# itself via `close_reason`, not a distinct OperationalReceipt type), so it
# is not in this set.
QUEUE_ONLY_RECEIPT_TYPES: frozenset[str] = frozenset(
    {
        "routing.assignment",
        "queue.triage",
        "queue.rejected",
        "queue.snoozed",
        "queue.split",
        "queue.merge_duplicate",
        "queue.evidence_requested",
    }
)

_EXECUTION_RESULT_RECEIPT_TYPE = "execution.result"


class OperationalReceiptRef(FrozenCoreModel):
    operational_receipt_id: UUID
    object_hash: Sha256Hex


class ExecutionAttemptRef(FrozenCoreModel):
    execution_attempt_id: UUID
    object_hash: Sha256Hex


class Effect(FrozenCoreModel):
    effect_type: RegisteredName
    target_ref: ExactObjectRef | None = None
    status: EffectStatus


class Reconciliation(FrozenCoreModel):
    state: ReconciliationState
    checked_at: UtcDateTime | None = None
    evidence_refs: tuple[ExactObjectRef, ...]


class ActorOrExecutor(FrozenCoreModel):
    producer: Producer
    actor_ref: ActorRef | None = None


class OperationalReceipt(FrozenCoreModel):
    operational_receipt_id: UUID
    operational_receipt_family_id: RegisteredName
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    receipt_type: RegisteredName
    supersedes_operational_receipt_ref: OperationalReceiptRef | None = None
    subject_refs: tuple[ExactObjectRef, ...] = Field(min_length=1)
    execution_attempt_ref: ExecutionAttemptRef | None = None
    classification: Classification
    actor_or_executor: ActorOrExecutor
    terminal_outcome: ExecutionTerminalOutcome | None = None
    outcome_code: RegisteredName
    effects: tuple[Effect, ...]
    artifact_refs: tuple[ExactObjectRef, ...]
    evidence_refs: tuple[ExactObjectRef, ...]
    observed_at: UtcDateTime
    recorded_at: UtcDateTime
    idempotency_key: str = Field(min_length=1)
    reconciliation: Reconciliation
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_operational_receipt(self) -> OperationalReceipt:
        if (
            self.supersedes_operational_receipt_ref is not None
            and self.supersedes_operational_receipt_ref.operational_receipt_id
            == self.operational_receipt_id
        ):
            raise PydanticCustomError(
                "supersedes_ref_is_self",
                "supersedes_operational_receipt_ref cannot name this same operational_receipt_id",
            )
        if self.receipt_type == _EXECUTION_RESULT_RECEIPT_TYPE:
            if self.execution_attempt_ref is None:
                raise PydanticCustomError(
                    "execution_result_missing_attempt_ref",
                    "receipt_type=execution.result requires execution_attempt_ref",
                )
            if self.terminal_outcome is None:
                raise PydanticCustomError(
                    "execution_result_missing_terminal_outcome",
                    "receipt_type=execution.result requires terminal_outcome",
                )
        if self.receipt_type in QUEUE_ONLY_RECEIPT_TYPES and self.execution_attempt_ref is not None:
            raise PydanticCustomError(
                "queue_only_receipt_carries_attempt_ref",
                "a queue-only receipt_type cannot carry execution_attempt_ref",
            )
        # INTERPRETATION: not a transcribed clause -- `terminal_outcome`'s
        # own type, `ExecutionTerminalOutcome` (succeeded/failed/cancelled/
        # unknown), is shaped for an execution's result, not a
        # general-purpose "this receipt is final" flag any receipt_type
        # could set. The `execution.result` branch above already requires
        # both fields TOGETHER; this is that requirement's converse --
        # terminal_outcome never appears without the attempt it describes,
        # on ANY receipt_type (not just the queue-only ones), so a
        # queue/team/routing/revocation receipt cannot smuggle in a claim
        # about an execution it never named.
        if self.terminal_outcome is not None and self.execution_attempt_ref is None:
            raise PydanticCustomError(
                "terminal_outcome_without_attempt_ref",
                "terminal_outcome requires execution_attempt_ref",
            )
        if self.observed_at > self.recorded_at:
            raise PydanticCustomError(
                "observed_at_after_recorded_at",
                "observed_at cannot be later than the system-time recorded_at that filed it",
            )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self


def close_execution_attempt(receipt: OperationalReceipt, attempt: ExecutionAttempt) -> None:
    """The chain's closing gate: "a typed terminal OperationalReceipt closes
    it [the ExecutionAttempt]." Raises ``ValueError`` naming the exact
    mismatch; returns ``None`` when ``receipt`` is a valid
    ``execution.result`` for exactly this ``attempt``, observed no earlier
    than the attempt started.
    """

    if receipt.receipt_type != _EXECUTION_RESULT_RECEIPT_TYPE:
        raise ValueError("receipt_type is not execution.result")
    if receipt.execution_attempt_ref is None:
        raise ValueError("receipt carries no execution_attempt_ref")
    if receipt.execution_attempt_ref.execution_attempt_id != attempt.execution_attempt_id:
        raise ValueError("receipt.execution_attempt_ref does not name this execution_attempt")
    if receipt.execution_attempt_ref.object_hash != attempt.object_hash:
        raise ValueError(
            "receipt.execution_attempt_ref does not pin this exact execution_attempt revision"
        )
    if receipt.terminal_outcome is None:
        raise ValueError("receipt carries no terminal_outcome")
    if receipt.observed_at < attempt.started_at:
        raise ValueError("receipt.observed_at precedes attempt.started_at")


@dataclass(frozen=True)
class ResolvedOperationalReceipts:
    receipts: tuple[OperationalReceipt, ...]


@dataclass(frozen=True)
class QuarantinedOperationalReceipts:
    reason_codes: tuple[str, ...]
    receipts: tuple[OperationalReceipt, ...]


def resolve_operational_receipt_replay(
    receipts: Sequence[OperationalReceipt],
) -> ResolvedOperationalReceipts | QuarantinedOperationalReceipts:
    """ "Duplicate idempotency resolves to the same receipt," mirrored on
    ``revocation_receipt.resolve_revocation_replay``'s replay-identity
    grouping. Replay identity here is ``(receipt_type,
    execution_attempt_ref identity, idempotency_key)`` -- the attempt (when
    present) is what "one current result per attempt" scopes the dedup to;
    a queue-only receipt has no attempt, so its identity falls back to the
    family alone.
    """

    if not receipts:
        return QuarantinedOperationalReceipts(("missing_receipt",), ())

    grouped: dict[tuple[str, str, str], list[OperationalReceipt]] = {}
    for receipt in receipts:
        attempt_key = (
            receipt.execution_attempt_ref.execution_attempt_id.hex
            if receipt.execution_attempt_ref is not None
            else ""
        )
        replay_identity = (receipt.receipt_type, attempt_key, receipt.idempotency_key)
        grouped.setdefault(replay_identity, []).append(receipt)

    resolved: list[OperationalReceipt] = []
    for claims in grouped.values():
        canonical_receipt = claims[0]
        if any(claim != canonical_receipt for claim in claims[1:]):
            return QuarantinedOperationalReceipts(
                ("conflicting_idempotency_key",),
                tuple(receipts),
            )
        resolved.append(canonical_receipt)
    return ResolvedOperationalReceipts(tuple(resolved))
