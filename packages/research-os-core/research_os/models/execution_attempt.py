"""Immutable ExecutionAttempt contract from frozen CONTRACTS.md section 13.4.

Section 13, shared invariants: "``ExecutionAttempt`` is created only when
invocation actually starts and is immutable in ``started`` state. Planning
belongs to the intent; terminal truth belongs to a separate
``OperationalReceipt``." Two structural facts fall directly out of that
sentence and need no extra validator: the model carries no terminal/outcome
field at all (that lives on ``OperationalReceipt``, section 13.5), and
``FrozenCoreModel``'s ``model_config = ConfigDict(frozen=True)`` makes every
instance immutable the moment it is constructed -- there is no setter to
close by omission.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import ExecutionAttemptState
from research_os.hashing import object_hash
from research_os.models.action_intent import ActionIntent
from research_os.models.action_item import ActionIntentRef
from research_os.models.approval_receipt import ApprovalReceipt, authorizes_action_intent
from research_os.primitives import (
    ActorRef,
    Extensions,
    FrozenCoreModel,
    Identifier,
    Lineage,
    Producer,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)


class ApprovalReceiptRef(FrozenCoreModel):
    """``{approval_receipt_id, object_hash}``, co-located here (not in
    ``approval_receipt.py``) because ``ExecutionAttempt`` is its only
    consumer in this kind group -- mirrors why ``ActionIntentRef`` lives in
    ``action_item.py`` rather than ``action_intent.py``.
    """

    approval_receipt_id: UUID
    object_hash: Sha256Hex


class Executor(FrozenCoreModel):
    name: Identifier
    version: str = Field(min_length=1)
    actor_ref: ActorRef | None = None


class ExecutionAttempt(FrozenCoreModel):
    execution_attempt_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    action_intent_ref: ActionIntentRef
    approval_receipt_ref: ApprovalReceiptRef
    attempt_number: int = Field(ge=1)
    state: ExecutionAttemptState
    idempotency_key: str = Field(min_length=1)
    executor: Executor
    started_at: UtcDateTime
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_execution_attempt(self) -> ExecutionAttempt:
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self


def validate_execution_attempt_authorization(
    attempt: ExecutionAttempt, intent: ActionIntent, receipt: ApprovalReceipt
) -> None:
    """ "An attempt must be immutable once started" (structural, above) --
    this is its twin, "and it must never have started without an unexpired
    approval of exactly this intent." Raises ``ValueError`` naming the exact
    mismatch; returns ``None`` when ``attempt`` legitimately started under
    ``receipt``'s authorization of ``intent``.
    """

    if attempt.action_intent_ref.action_intent_id != intent.action_intent_id:
        raise ValueError("execution_attempt.action_intent_ref does not name this action_intent")
    if attempt.action_intent_ref.object_hash != intent.object_hash:
        raise ValueError(
            "execution_attempt.action_intent_ref does not pin this exact action_intent revision"
        )
    if attempt.approval_receipt_ref.approval_receipt_id != receipt.approval_receipt_id:
        raise ValueError(
            "execution_attempt.approval_receipt_ref does not name this approval_receipt"
        )
    if attempt.approval_receipt_ref.object_hash != receipt.object_hash:
        raise ValueError(
            "execution_attempt.approval_receipt_ref does not pin this exact approval_receipt revision"
        )
    authorizes_action_intent(receipt, intent, at=attempt.started_at)
