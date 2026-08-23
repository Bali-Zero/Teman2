"""Immutable ActionIntent contract from frozen CONTRACTS.md section 13.2.

Section 13, shared invariants: "When an ``ActionIntent`` is materialized
from a ``RequestedActionSpec``, both the initial ``ActionItem`` and the
``ActionIntent`` retain the exact spec reference. The complete
authorization-bearing fields -- action type, target, arguments reference and
hash, input revision hash, risk, sensitivity, authority, and expected
outcomes -- transfer losslessly into the ``ActionIntent``; the ``ActionItem``
carries only queue semantics, exact source references, risk, sensitivity,
ownership, priority, and SLA." That transfer is a two-object invariant
(section 13.1's ``ActionItem`` is not importable here without a cycle risk,
so it lives on ``ActionItem`` itself via ``requested_action_spec_ref`` and is
checked by ``verify_action_intent_matches_action_item`` below, called by a
repository/orchestration layer that holds both objects at once -- exactly
the split ``successor_edge.py`` documents for its own cross-member checks it
cannot make wire-locally).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import RiskClass, Sensitivity
from research_os.hashing import object_hash
from research_os.models.action_item import ActionItem, ActionItemRef, RequestedActionSpecRef
from research_os.primitives import (
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


class Target(FrozenCoreModel):
    # `object_ref` reuses the generic exact_object_ref shape (section 2): a
    # family ID alone is never exact identity, and the action's target is
    # named the same way every other exact reference in this contract
    # family is.
    system: Identifier
    object_ref: ExactObjectRef
    surface: Identifier | None = None


class AuthorityRequired(FrozenCoreModel):
    role: Identifier
    scope: str = Field(min_length=1)
    expires_after_seconds: int = Field(gt=0)


class ActionIntent(FrozenCoreModel):
    action_intent_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    action_item_ref: ActionItemRef
    requested_action_spec_ref: RequestedActionSpecRef
    action_type: RegisteredName
    target: Target
    arguments_ref: str = Field(min_length=1)
    arguments_hash: Sha256Hex
    input_revision_hash: Sha256Hex
    risk_class: RiskClass
    sensitivity: Sensitivity
    authority_required: AuthorityRequired
    idempotency_key: str = Field(min_length=1)
    expected_outcome_types: tuple[RegisteredName, ...]
    created_at: UtcDateTime
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_action_intent(self) -> ActionIntent:
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self


def verify_action_intent_matches_action_item(item: ActionItem, intent: ActionIntent) -> None:
    """Enforce the lossless-transfer cross-object invariant quoted above.

    Raises ``ValueError`` naming the exact field that diverged; returns
    ``None`` on a matching pair. This is the "an intent needs its item's
    exact facts, not just its own say-so" half of the chain -- the
    authorization half (an intent needs an *unexpired approval*) is
    ``approval_receipt.authorizes_action_intent``.
    """

    if intent.action_item_ref.action_item_id != item.action_item_id:
        raise ValueError("action_intent.action_item_ref does not name this action_item")
    if intent.action_item_ref.object_hash != item.object_hash:
        raise ValueError(
            "action_intent.action_item_ref does not pin this exact action_item revision"
        )
    if intent.requested_action_spec_ref != item.requested_action_spec_ref:
        raise ValueError(
            "action_intent.requested_action_spec_ref diverges from action_item.requested_action_spec_ref"
        )
    if intent.risk_class != item.risk_class:
        raise ValueError("action_intent.risk_class diverges from action_item.risk_class")
    if intent.sensitivity != item.sensitivity:
        raise ValueError("action_intent.sensitivity diverges from action_item.sensitivity")
