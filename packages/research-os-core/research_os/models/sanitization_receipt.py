"""Immutable SanitizationReceipt contract from frozen CONTRACTS.md section 17.

Purpose (verbatim): "authorize one lower-sensitivity projection for a named
purpose and destination. It does not lower factual, legal, editorial, or
operational risk." This is one of exactly two instruments in
``research-os/v1.0.0`` that may ever lower a classification dimension
(section 1 rule 7) -- the other is ``RiskReclassificationReceipt``
(section 18). Getting either wrong is a data-protection failure, not a
schema nit; every guard below fails CLOSED.

Cross-object obligations this module does NOT enforce, and why:

- "Sanitization never changes the protected source." There is nothing IN
  this wire object to compare against -- ``source_objects`` records only
  the classification each source carried, never its content or a
  before/after diff. Enforcing immutability of the source is the same
  append-only-store guarantee section 1 rule 4 already places on every
  canonical object; it is a repository invariant, not a property of one
  receipt document.
- "The lower-sensitivity output and this receipt commit atomically with
  deferred cross-object constraints; if the output is a successor, its
  exact ObjectSuccessorEdge is in the same write-set ... Any missing,
  mismatched, or invalid member rolls back the entire bundle." DECLARED
  LIMIT, verified rather than assumed: the only existing multi-object
  primitive in this package, ``research_os.graph.select_current_member``,
  is a pure in-memory selector/quarantine function over an already-fetched
  ``Sequence`` of edges and members -- it has no notion of a write-set,
  atomicity, or rollback, and no persistence/repository module exists
  anywhere under ``packages/research-os-core`` to check against (confirmed
  by listing the package: ``primitives.py``, ``hashing.py``, ``enums.py``,
  ``graph.py``, ``models/``, ``schemas/``, ``cli.py`` -- no db/repository
  file). Expressing "commits atomically ... rolls back" here would mean
  inventing a persistence layer un-scoped to this deliverable (Work Packet
  04's canonical *validators*), not merely skipping an already-available
  primitive. What CAN be expressed without a repository -- "does this
  receipt authorize this exact output revision, right now" -- is provided
  below as ``sanitization_authorizes_output``, mirroring the sibling
  decision-chain lane's ``approval_receipt.authorizes_action_intent``.
- "A receipt is purpose- and destination-bound and cannot be reused for
  another audience." Reuse is a property of the whole system's receipt
  history, not of one document; this module requires ``permitted_use``'s
  fields to be present and non-empty (structural), which is everything a
  single-object validator can check.
- "The output object does not embed this receipt ID. The receipt is
  retrieved by its exact output_object.object_hash, avoiding a circular
  hash dependency." This obligation binds the OUTPUT object's OWN schema,
  not this one: this receipt only ever points AT an output via
  ``output_object.object_hash`` (one-directional), and never declares or
  requires a field on the output that would point back. Confirmed against
  the one already-shipped kind with the identical obligation in its own
  prose (section 15's ``ConductorHandoff``, "the handoff never embeds the
  receipt that binds it"): its model carries no
  ``sanitization_receipt_ref``/``risk_reclassification_receipt_ref`` field.
  Nothing in this module asks any output kind to embed a receipt id.

Judgment calls (spec silent or ambiguous, encoded conservatively, flagged
for ratification -- see the P04-D1 report):

- ``source_objects`` carries NO cardinality constraint in section 17's
  prose. A ``min_length=1`` was deliberately NOT added even though a
  sanitization receipt with zero sources reads as unusual: another lane on
  this same deliverable forced a bare ``[]`` field non-empty against
  section 1 rule 9 ("missing evidence is not negative evidence") and had
  to revert it three rounds later. Left open here for the same reason.
- ``residual_risk.rating`` is typed as an open non-empty string, NOT the
  closed ``RiskClass`` enum. Section 17 deliberately uses the word
  "rating" here while section 18's own ``residual_risk`` uses "risk_class"
  for what is presumably a related but not identical concept (a sanitizer
  reviewer's rating of RE-IDENTIFICATION/leakage risk, not the canonical
  three-value risk classification) -- no registered enum exists for it in
  section 3, so it is read as free text rather than an invented enum.
- ``residual_risk.findings`` is bare ``[]`` in the frozen prose with no
  item shape; read as a tuple of non-empty strings, matching the sibling
  ``VerificationReceipt.limits`` idiom (workflow-outcome lane) for the
  same kind of field.
- ``lineage.workflow_run_ref`` carries NO ``?`` in section 17's prose,
  unlike ``primitives.Lineage`` (whose ``workflow_run_ref`` is optional)
  and unlike most other sections that reuse the bare ``Lineage`` shape
  (sections 3.2, 14, 16 all write ``workflow_run_ref?``). This is read as
  MANDATORY here, per the contract's own established convention that a
  missing ``?`` means required (used consistently throughout CONTRACTS.md,
  e.g. ``expires_at?`` vs ``expires_at``) -- not a literal separate clause,
  but the same convention the operator-decisions lane independently
  reached for the structurally identical ``{workflow_run_ref: {...},
  input_hashes: []}`` shape in sections 8.1-8.3 and section 7
  (``decision_packet.py``'s ``RequiredWorkflowLineage``).
- ``policy: {name, version}`` is not reused from ``primitives.Producer``
  (an identical two-field shape) even though that would avoid a duplicate
  class: a policy and a producer are different concepts that happen to
  share a shape today, and the rest of this contract family already keeps
  structurally-identical ref shapes (e.g. ``ClaimRef``/``EvidenceRef``) as
  separate named classes rather than collapsing them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import Sensitivity, max_risk
from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
    Classification,
    ExactObjectRef,
    Extensions,
    FrozenCoreModel,
    Identifier,
    Producer,
    Retention,
    Sha256Hex,
    UtcDateTime,
    WorkflowRunRef,
    validate_extensions,
)


class ClassifiedObjectRef(FrozenCoreModel):
    """``{object_kind, object_id, object_hash, classification: {risk_class,
    sensitivity}}`` -- section 17's shape for both ``source_objects``
    entries and the singular ``output_object``. Note this NESTS
    classification under a ``classification`` key, unlike section 18's
    flat ``{..., risk_class, sensitivity}`` -- the two sections use
    different shapes and this module does not share a type with
    ``risk_reclassification_receipt.py``'s ``FlatClassifiedObjectRef``.
    """

    object_kind: Identifier
    object_id: str = Field(min_length=1)
    object_hash: Sha256Hex
    classification: Classification


class PolicyRef(FrozenCoreModel):
    name: Identifier
    version: str = Field(min_length=1)


class Transformation(FrozenCoreModel):
    field_path: str = Field(min_length=1)
    operation: Literal["remove", "generalize", "aggregate", "pseudonymize"]
    result_sensitivity: Sensitivity


class ResidualRiskRating(FrozenCoreModel):
    rating: str = Field(min_length=1)
    findings: tuple[str, ...]


class PermittedUse(FrozenCoreModel):
    """``permitted_use: {purpose, destination, consumer, expires_at}`` --
    unlike section 18's ``RiskReclassificationReceipt``, ``expires_at``
    carries no ``?`` here and is mandatory.
    """

    purpose: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    consumer: str = Field(min_length=1)
    expires_at: UtcDateTime


class PropagationScopeEntry(FrozenCoreModel):
    system: Identifier
    object_ref: ExactObjectRef


class MandatoryWorkflowLineage(FrozenCoreModel):
    """``lineage: {workflow_run_ref: {workflow_run_id, object_hash},
    input_hashes: []}`` with ``workflow_run_ref`` MANDATORY -- see the
    module docstring's judgment-call note.
    """

    workflow_run_ref: WorkflowRunRef
    input_hashes: tuple[Sha256Hex, ...]


class SanitizationReceipt(FrozenCoreModel):
    sanitization_receipt_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    source_objects: tuple[ClassifiedObjectRef, ...]
    output_object: ClassifiedObjectRef
    policy: PolicyRef
    transformations: tuple[Transformation, ...]
    residual_risk: ResidualRiskRating
    reviewer_ref: ActorRef
    permitted_use: PermittedUse
    issued_at: UtcDateTime
    propagation_scope: tuple[PropagationScopeEntry, ...]
    producer: Producer
    lineage: MandatoryWorkflowLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_sanitization_receipt(self) -> SanitizationReceipt:
        # "This receipt cannot lower risk_class" -- verbatim, unconditional
        # invariant (contrast section 18, where a risk DECREASE is exactly
        # the point). Checked as: the output's risk_class must already be
        # the greatest among {output, every source} -- i.e. not lower than
        # any source. Uses only the public `max_risk` ordering helper, not
        # the private `_RISK_ORDER` table in enums.py.
        if self.source_objects:
            candidates = (
                self.output_object.classification.risk_class,
                *(ref.classification.risk_class for ref in self.source_objects),
            )
            if max_risk(*candidates) != self.output_object.classification.risk_class:
                raise PydanticCustomError(
                    "risk_class_lowered",
                    "output_object.classification.risk_class is lower than a source's risk_class",
                )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self


def sanitization_authorizes_output(
    receipt: SanitizationReceipt, *, output_ref: ExactObjectRef, at: datetime
) -> None:
    """The lowering gate's cross-object half: "is `receipt` a currently
    valid authorization for exactly this output revision, right now."

    Raises ``ValueError`` naming the exact mismatch; returns ``None`` only
    when ``receipt.output_object`` pins this exact ``output_ref`` and
    ``at`` is strictly before ``permitted_use.expires_at``. ``at`` is
    supplied by the caller (e.g. the instant a downstream consumer relies
    on the lowered output) -- never read from the wall clock internally, so
    replay and tests stay deterministic (mirrors
    ``approval_receipt.authorizes_action_intent`` on the sibling
    decision-chain lane).
    """

    if receipt.output_object.object_kind != output_ref.object_kind:
        raise ValueError("receipt.output_object.object_kind does not name this output_ref")
    if receipt.output_object.object_id != output_ref.object_id:
        raise ValueError("receipt.output_object.object_id does not name this output_ref")
    if receipt.output_object.object_hash != output_ref.object_hash:
        raise ValueError(
            "receipt.output_object.object_hash does not pin this exact output revision"
        )
    if at >= receipt.permitted_use.expires_at:
        raise ValueError("sanitization receipt is expired at the relied-on instant")
