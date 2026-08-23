"""Immutable ActionItem contract from frozen CONTRACTS.md section 13.1.

``ActionItem`` is the Action Inbox queue record: "It records attention and
ownership, not approval or execution truth." Each object is an immutable
queue snapshot; a change appends the next revision in the same
``action_item_family_id`` and binds ``supersedes_action_item_ref`` (section
13, shared invariants: "``ActionItem`` versions are immutable queue
snapshots. Assignment, decision readiness, intent linkage, closure, or SLA
change appends a new revision in the same ``action_item_family_id``, binds
``supersedes_action_item_ref``, and atomically commits its
``ObjectSuccessorEdge``.").
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import QueueState, RiskClass, Sensitivity
from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
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

ClosingReason = Literal["completed", "rejected", "duplicate", "obsolete", "invalid"]
Priority = Literal["p0", "p1", "p2", "p3"]


class ActionItemRef(FrozenCoreModel):
    """``{action_item_id, object_hash}`` -- the typed pointer used everywhere
    the chain names one exact ``ActionItem`` revision (never a bare family
    ID, per primitive ``exact_object_ref``'s rule generalized to this kind).
    """

    action_item_id: UUID
    object_hash: Sha256Hex


class ActionIntentRef(FrozenCoreModel):
    """``{action_intent_id, object_hash}``, defined here (not in
    ``action_intent.py``) so ``ActionItem.current_intent_ref`` and
    ``ActionIntent.action_item_ref`` (section 13.2) can reference each
    other's exact identity without an import cycle between the two modules.
    """

    action_intent_id: UUID
    object_hash: Sha256Hex


class DecisionPacketRef(FrozenCoreModel):
    decision_packet_id: UUID
    object_hash: Sha256Hex


class RequestedActionSpecRef(FrozenCoreModel):
    requested_action_spec_id: UUID
    object_hash: Sha256Hex


class Sla(FrozenCoreModel):
    """``sla: {opened_at, due_at, paused_at?, breached_at?}``.

    INTERPRETATION: section 13.1 does not spell out an ordering invariant
    for this sub-object the way primitive ``valid_time`` does for its
    half-open interval, but an SLA whose due date precedes its own open
    date, or whose pause/breach instant precedes it opened, describes a
    clock that ran backwards. Mirrored on ``primitives.ValidTime``'s
    strictly-later pattern rather than inventing a new idiom.
    """

    opened_at: UtcDateTime
    due_at: UtcDateTime
    paused_at: UtcDateTime | None = None
    breached_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def validate_sla_clock(self) -> Sla:
        if self.due_at <= self.opened_at:
            raise PydanticCustomError(
                "sla_due_at_not_after_opened_at",
                "due_at must be strictly later than opened_at",
            )
        if self.paused_at is not None and self.paused_at < self.opened_at:
            raise PydanticCustomError(
                "sla_paused_at_before_opened_at",
                "paused_at cannot precede opened_at",
            )
        if self.breached_at is not None and self.breached_at < self.opened_at:
            raise PydanticCustomError(
                "sla_breached_at_before_opened_at",
                "breached_at cannot precede opened_at",
            )
        return self


class ActionItem(FrozenCoreModel):
    action_item_id: UUID
    action_item_family_id: RegisteredName
    revision: int = Field(ge=1)
    supersedes_action_item_ref: ActionItemRef | None = None
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    decision_packet_ref: DecisionPacketRef
    requested_action_spec_ref: RequestedActionSpecRef
    queue_state: QueueState
    owner_ref: ActorRef | None = None
    risk_class: RiskClass
    sensitivity: Sensitivity
    priority: Priority
    sla: Sla
    current_intent_ref: ActionIntentRef | None = None
    close_reason: ClosingReason | None = None
    created_at: UtcDateTime
    recorded_at: UtcDateTime
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_action_item(self) -> ActionItem:
        # "ActionItem versions are immutable queue snapshots ... appends a
        # new revision ... binds supersedes_action_item_ref": the first
        # revision of a family has nothing to supersede, and every later
        # revision must name its exact predecessor -- this is the one part
        # of that succession invariant checkable without the family's other
        # members (the rest -- later recorded_at, unique current member,
        # same family_id on both sides -- is graph.select_current_member's
        # job, exactly as successor_edge.py defers cross-member checks
        # there).
        if self.revision == 1 and self.supersedes_action_item_ref is not None:
            raise PydanticCustomError(
                "initial_revision_cannot_supersede",
                "revision 1 of a family cannot carry supersedes_action_item_ref",
            )
        if self.revision > 1 and self.supersedes_action_item_ref is None:
            raise PydanticCustomError(
                "revision_missing_supersedes_ref",
                "revision > 1 must bind supersedes_action_item_ref to its exact predecessor",
            )
        if (
            self.supersedes_action_item_ref is not None
            and self.supersedes_action_item_ref.action_item_id == self.action_item_id
        ):
            raise PydanticCustomError(
                "supersedes_ref_is_self",
                "supersedes_action_item_ref cannot name this same action_item_id",
            )
        # INTERPRETATION: not a transcribed clause -- close_reason is the
        # terminal disposition of a closed queue_state and only makes
        # sense there; a non-closed row asserting a close reason is
        # asserting a fact its own queue_state contradicts (mirrored on
        # `OperationalReceipt`'s `execution.result` biconditional pairing).
        if self.queue_state == QueueState.CLOSED and self.close_reason is None:
            raise PydanticCustomError(
                "closed_without_close_reason",
                "queue_state=closed requires close_reason",
            )
        if self.queue_state != QueueState.CLOSED and self.close_reason is not None:
            raise PydanticCustomError(
                "close_reason_without_closed_state",
                "close_reason requires queue_state=closed",
            )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
