"""Immutable ApprovalReceipt contract from frozen CONTRACTS.md section 13.3.

Section 3.2 (``RevocationReceipt``), which this chain's own invariant text
points back to: "Every downstream effect ... requires its own
``ActionItem``/``ActionIntent``, unexpired effect-specific
``ApprovalReceipt``, immutable started ``ExecutionAttempt``, typed terminal
``OperationalReceipt``, and ``OutcomeEvent``." This module is the "unexpired
effect-specific ``ApprovalReceipt``" link: it both validates one receipt in
isolation and, via ``authorizes_action_intent`` below, checks the exact
two-object relationship section 13's shared invariants describe: "No action
class executes without an unexpired ``approve`` receipt whose subject is the
exact ``ActionIntent`` hash and whose bindings match the exact
``arguments_hash`` and ``input_revision_hash``."
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import ApprovalDecision, ApprovalSubjectKind
from research_os.hashing import object_hash
from research_os.models.action_intent import ActionIntent
from research_os.models.action_item import ActionItemRef
from research_os.primitives import (
    ActorRef,
    Classification,
    Extensions,
    FrozenCoreModel,
    Identifier,
    Lineage,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    WorkflowRunRef,
    validate_extensions,
)

# Section 13.5, shared invariants: "Allowed subject/decision pairs are
# closed: `decision_packet` accepts `select`, `reject`, `request_changes`,
# `request_evidence`, or `defer`; `topic_lock`, `creative_lock`,
# `media_script_lock`, `media_shot_lock`, and `content_revision` accept
# `approve`, `reject`, or `request_changes`; `action_intent` accepts
# `approve`, `reject`, or `request_changes`. Every other pair fails
# validation." Transcribed verbatim as a closed table, not re-derived.
_ALLOWED_DECISIONS_BY_SUBJECT_KIND: dict[ApprovalSubjectKind, frozenset[ApprovalDecision]] = {
    ApprovalSubjectKind.DECISION_PACKET: frozenset(
        {
            ApprovalDecision.SELECT,
            ApprovalDecision.REJECT,
            ApprovalDecision.REQUEST_CHANGES,
            ApprovalDecision.REQUEST_EVIDENCE,
            ApprovalDecision.DEFER,
        }
    ),
    ApprovalSubjectKind.TOPIC_LOCK: frozenset(
        {ApprovalDecision.APPROVE, ApprovalDecision.REJECT, ApprovalDecision.REQUEST_CHANGES}
    ),
    ApprovalSubjectKind.CREATIVE_LOCK: frozenset(
        {ApprovalDecision.APPROVE, ApprovalDecision.REJECT, ApprovalDecision.REQUEST_CHANGES}
    ),
    ApprovalSubjectKind.MEDIA_SCRIPT_LOCK: frozenset(
        {ApprovalDecision.APPROVE, ApprovalDecision.REJECT, ApprovalDecision.REQUEST_CHANGES}
    ),
    ApprovalSubjectKind.MEDIA_SHOT_LOCK: frozenset(
        {ApprovalDecision.APPROVE, ApprovalDecision.REJECT, ApprovalDecision.REQUEST_CHANGES}
    ),
    ApprovalSubjectKind.CONTENT_REVISION: frozenset(
        {ApprovalDecision.APPROVE, ApprovalDecision.REJECT, ApprovalDecision.REQUEST_CHANGES}
    ),
    ApprovalSubjectKind.ACTION_INTENT: frozenset(
        {ApprovalDecision.APPROVE, ApprovalDecision.REJECT, ApprovalDecision.REQUEST_CHANGES}
    ),
}

# "Only this exact subject/decision pair may carry nonempty
# `authorized_effects` or authorize an `ExecutionAttempt`; every other valid
# pair requires `authorized_effects=[]` and creates no attempt."
_EFFECT_AUTHORIZING_PAIR = (ApprovalSubjectKind.ACTION_INTENT, ApprovalDecision.APPROVE)


class ApprovalSubject(FrozenCoreModel):
    kind: ApprovalSubjectKind
    object_id: str = Field(min_length=1)
    object_hash: Sha256Hex


class ApprovalContext(FrozenCoreModel):
    action_item_ref: ActionItemRef | None = None
    workflow_run_ref: WorkflowRunRef | None = None


class Authority(FrozenCoreModel):
    role: Identifier
    scope: str = Field(min_length=1)
    verified_at: UtcDateTime


class Bindings(FrozenCoreModel):
    input_revision_hash: Sha256Hex
    arguments_hash: Sha256Hex | None = None


class ApprovalReceipt(FrozenCoreModel):
    approval_receipt_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    subject: ApprovalSubject
    context: ApprovalContext
    decision: ApprovalDecision
    actor_ref: ActorRef
    authority: Authority
    bindings: Bindings
    before_hash: Sha256Hex | None = None
    after_hash: Sha256Hex | None = None
    authorized_effects: tuple[RegisteredName, ...]
    rationale_code: str = Field(min_length=1)
    classification: Classification
    issued_at: UtcDateTime
    expires_at: UtcDateTime
    idempotency_key: str = Field(min_length=1)
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_approval_receipt(self) -> ApprovalReceipt:
        allowed = _ALLOWED_DECISIONS_BY_SUBJECT_KIND[self.subject.kind]
        if self.decision not in allowed:
            raise PydanticCustomError(
                "subject_decision_pair_not_allowed",
                "this subject kind and decision pair is not in the closed registry",
            )
        pair = (self.subject.kind, self.decision)
        if pair != _EFFECT_AUTHORIZING_PAIR and self.authorized_effects:
            raise PydanticCustomError(
                "authorized_effects_not_permitted_for_pair",
                "only subject=action_intent decision=approve may carry nonempty authorized_effects",
            )
        # "An action approval requires exact context.action_item_ref,
        # bindings.arguments_hash, and classification matching the action
        # intent; lock and editorial approvals reject action-only fields
        # unless their specialization explicitly requires them." The
        # classification-matches-the-intent half is cross-object (see
        # authorizes_action_intent below); the field-presence half is
        # checkable here.
        if self.subject.kind == ApprovalSubjectKind.ACTION_INTENT:
            if self.context.action_item_ref is None:
                raise PydanticCustomError(
                    "action_approval_missing_action_item_ref",
                    "subject=action_intent requires context.action_item_ref",
                )
            if self.bindings.arguments_hash is None:
                raise PydanticCustomError(
                    "action_approval_missing_arguments_hash",
                    "subject=action_intent requires bindings.arguments_hash",
                )
        else:
            if self.context.action_item_ref is not None:
                raise PydanticCustomError(
                    "non_action_approval_carries_action_item_ref",
                    "lock/editorial approvals reject context.action_item_ref",
                )
            if self.bindings.arguments_hash is not None:
                raise PydanticCustomError(
                    "non_action_approval_carries_arguments_hash",
                    "lock/editorial approvals reject bindings.arguments_hash",
                )
        if self.expires_at <= self.issued_at:
            raise PydanticCustomError(
                "expires_at_not_after_issued_at",
                "expires_at must be strictly later than issued_at",
            )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self


def authorizes_action_intent(
    receipt: ApprovalReceipt, intent: ActionIntent, *, at: datetime
) -> None:
    """The chain's central gate: "an intent needs an unexpired approval."

    Raises ``ValueError`` naming the exact mismatch; returns ``None`` when
    ``receipt`` is a valid, currently-unexpired ``approve`` of exactly this
    ``intent`` revision. ``at`` is the instant authorization is being relied
    on (e.g. an ``ExecutionAttempt.started_at``) -- never the wall clock
    read internally, so replay and tests stay deterministic.
    """

    if receipt.subject.kind != ApprovalSubjectKind.ACTION_INTENT:
        raise ValueError("approval subject.kind is not action_intent")
    if receipt.decision != ApprovalDecision.APPROVE:
        raise ValueError("approval decision is not approve")
    if receipt.subject.object_id != str(intent.action_intent_id):
        raise ValueError("approval subject.object_id does not name this action_intent_id")
    if receipt.subject.object_hash != intent.object_hash:
        raise ValueError(
            "approval subject.object_hash does not pin this exact action_intent revision"
        )
    if receipt.bindings.arguments_hash != intent.arguments_hash:
        raise ValueError("approval bindings.arguments_hash diverges from the action_intent")
    if receipt.bindings.input_revision_hash != intent.input_revision_hash:
        raise ValueError("approval bindings.input_revision_hash diverges from the action_intent")
    if receipt.context.action_item_ref != intent.action_item_ref:
        raise ValueError("approval context.action_item_ref diverges from the action_intent")
    if receipt.classification.risk_class != intent.risk_class:
        raise ValueError("approval classification.risk_class diverges from the action_intent")
    if receipt.classification.sensitivity != intent.sensitivity:
        raise ValueError("approval classification.sensitivity diverges from the action_intent")
    if not (receipt.issued_at <= at < receipt.expires_at):
        raise ValueError("approval is not unexpired at the relied-on instant")
