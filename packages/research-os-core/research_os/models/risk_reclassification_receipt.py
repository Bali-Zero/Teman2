"""Immutable RiskReclassificationReceipt contract from frozen CONTRACTS.md
section 18.

Purpose (verbatim): "justify a lower canonical risk class only after a
distinct successor has corrected or remediated the reason the predecessor
was riskier. It is not a privacy transformation, publication approval, or
permission to ignore unresolved evidence." This is the second of exactly
two instruments in ``research-os/v1.0.0`` that may ever lower a
classification dimension (section 1 rule 7) -- the other is
``SanitizationReceipt`` (section 17, ``sanitization_receipt.py``, which
carries the shared discussion of what a single-document validator can and
cannot enforce about that rule). Every guard below fails CLOSED.

Cross-object obligations this module does NOT enforce, and why (mirrors
``sanitization_receipt.py``'s discussion for the twin instrument):

- "The corrected successor, exact ObjectSuccessorEdge, and this receipt
  commit atomically with deferred cross-object constraints ... Any
  missing, mismatched, or invalid member rolls back the entire bundle;
  replay returns the same bundle." DECLARED LIMIT for the same reason as
  the sanitization side: no persistence/repository module exists anywhere
  under ``packages/research-os-core`` (confirmed by listing the package),
  and the one existing multi-object primitive
  (``research_os.graph.select_current_member``) is a pure in-memory
  selector over an already-fetched sequence, not a transactional writer.
  What IS expressible without a repository -- exact-hash, unexpired
  authorization of one specific output revision -- is
  ``risk_reclassification_authorizes_output`` below.
- "The new risk class must equal the deterministic policy result over the
  corrected output and exact current claim/evidence/verification inputs."
  This requires actually RUNNING the named policy over the referenced
  claims/evidence/verifications (an external, deterministic oracle this
  package does not contain -- ``policy`` here is only a
  ``{name, version}`` pointer, not an evaluable function). Not checkable
  from the wire document alone; DECLARED LIMIT.
- "The reviewer must be independent of the producer that performed the
  remediation when the policy gate requires independence." Checking actual
  independence needs the remediation's producer identity and the policy
  gate's independence requirement, neither of which is a field on this
  object (``reviewer.independence_class`` records the reviewer's own
  claimed class, not a comparison against anything). Cross-object,
  DECLARED LIMIT -- mirrors the identical gap the workflow-outcome lane
  already documented for ``VerificationReceipt.verifier.independence_class``
  ("no field on this wire object lets a single-object validator compare
  who verified against who produced").
- "The receipt is retrieved by exact output_object.object_hash; the output
  does not embed the receipt and cannot create a circular identity." Binds
  the OUTPUT object's own schema, not this one -- see
  ``sanitization_receipt.py``'s identical note (confirmed against
  ``ConductorHandoff``, the one already-shipped kind with the matching
  obligation in its own prose: no ``*_receipt_ref`` field embeds either
  receipt).
- "Expiry, source revocation, claim contradiction, or invalidated
  verification marks the successor stale ... it does not silently restore
  or invent a class." Staleness is a property of the referenced claims/
  evidence/verifications changing AFTER this receipt is issued -- not
  observable from this document at construction time. DECLARED LIMIT.

Judgment calls (spec silent or ambiguous, encoded conservatively, flagged
for ratification -- see the P04-D1 report):

- ``source_object``/``output_object`` are typed FLAT
  (``{object_kind, object_id, object_hash, risk_class, sensitivity}``),
  deliberately NOT reusing ``sanitization_receipt.ClassifiedObjectRef``
  (which nests classification under a ``classification`` key): section 18's
  own prose spells the flat shape, differing from section 17's nested one,
  and the two are kept as distinct types (``FlatClassifiedObjectRef`` here)
  rather than collapsed or cross-imported.
- ``source_object.object_hash != output_object.object_hash`` and
  ``.object_kind ==`` are enforced (verbatim: "distinct immutable
  successor"). CORRECTED (P04-D1 defect, see the P04-D1 report): an earlier
  draft of this module additionally forced
  ``source_object.object_id != output_object.object_id`` unconditionally,
  citing ``ObjectSuccessorEdge.validate_edge``'s
  ``predecessor_ref != successor_ref`` check as "the one-layer-up sibling of
  this same rule". That citation was false: ``validate_edge`` compares the
  full ``{object_kind, object_id, object_hash}`` triple for equality (see
  ``successor_edge.py``) -- it imposes no constraint that ``object_id``
  differ on its own, and is satisfied the instant the hash differs even
  when the id is unchanged. Section 1 rule 4 ("canonical objects are never
  overwritten ... append a successor object") does not require a new
  object_id either: ``ContentObject`` (CONTRACTS.md section 9) is the
  worked example -- ``content_object_id`` is STABLE across revisions
  (``revision`` is the field that increments; contrast section 6 ``Claim``,
  which mints a fresh ``claim_id`` per version because its own prose says
  "``claim_id`` identifies one immutable claim version"). Sections 9 and 10
  state, verbatim, "a distinct output revision may lower sensitivity only
  with a valid ``SanitizationReceipt``, lower risk only with a valid
  ``RiskReclassificationReceipt``" -- a *revision*, not a distinct object;
  the removed guard rejected exactly the workflow those sections authorize.
  The check now enforces what ``validate_edge`` actually enforces: the
  source and output must not be equal across their WHOLE identity
  (``object_kind`` AND ``object_id`` AND ``object_hash`` all matching,
  mirroring ``predecessor_ref == successor_ref``) -- reason code
  ``output_object_same_as_source``. It runs first in this validator (as
  ``validate_edge``'s equivalent check runs first in its own validator) so
  a fully-identical source/output pair reports that specific reason
  instead of the more generic ``output_same_as_source_hash``.
- "Sensitivity cannot decrease under this receipt" IS enforced --
  verbatim, unconditional (the one hard constraint this receipt carries on
  the dimension it does NOT own). Whether risk_class must actually DECREASE
  under every valid instance of this receipt (as opposed to staying equal)
  is deliberately NOT enforced: section 18 states the new class "must equal
  the deterministic policy result" (a DECLARED LIMIT above, not evaluable
  here) but never states unconditionally that a decrease must occur, unlike
  section 17's unconditional "cannot lower risk_class". Adding a strict
  "must decrease" check here would be exactly the over-constraining
  instinct another lane on this deliverable already got burned by (forcing
  an array non-empty against rule 9); left open.
- ``remediation.type`` is a local closed ``Literal`` (5 values verbatim
  from section 18's pipe-syntax), not added to the section 3 central
  registry -- no matching row exists there, consistent with how the
  workflow-outcome lane treated ``ConductorHandoff.considered_options[].disposition``
  under the identical circumstance (a closed pipe-syntax list with no
  section-3 registry entry).
- ``remediation.changed_field_paths`` carries no cardinality constraint,
  for the same reason as ``sanitization_receipt.ClassifiedObjectRef``'s
  ``source_objects``: no ``min_length`` is invented against a bare ``[]``.
- ``lineage.workflow_run_ref`` is mandatory here (no ``?`` in section 18's
  prose) -- same convention and same cross-lane precedent as
  ``sanitization_receipt.MandatoryWorkflowLineage``; the class is
  duplicated rather than imported across the two files (this contract
  family's established convention: keep structurally-identical shapes as
  separate named classes per owning module, e.g. ``ClaimRef``/``EvidenceRef``
  are never collapsed either).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import RiskClass, Sensitivity, max_sensitivity
from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
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

FieldPath = Annotated[str, Field(min_length=1)]


class FlatClassifiedObjectRef(FrozenCoreModel):
    """``{object_kind, object_id, object_hash, risk_class, sensitivity}``
    -- section 18's FLAT shape (contrast section 17's nested
    ``classification: {...}``; see module docstring).
    """

    object_kind: Identifier
    object_id: str = Field(min_length=1)
    object_hash: Sha256Hex
    risk_class: RiskClass
    sensitivity: Sensitivity


class SupersessionRef(FrozenCoreModel):
    object_successor_edge_id: UUID
    object_hash: Sha256Hex


class Remediation(FrozenCoreModel):
    type: Literal[
        "authoritative_source_added",
        "contradiction_resolved",
        "grounding_repaired",
        "prohibited_scope_removed",
        "classification_error_corrected",
    ]
    reason_codes: tuple[RegisteredName, ...]
    changed_field_paths: tuple[FieldPath, ...]


class ClaimRef(FrozenCoreModel):
    claim_id: UUID
    object_hash: Sha256Hex


class EvidenceRef(FrozenCoreModel):
    evidence_id: UUID
    object_hash: Sha256Hex


class VerificationReceiptRef(FrozenCoreModel):
    verification_receipt_id: UUID
    object_hash: Sha256Hex


class PolicyRef(FrozenCoreModel):
    name: Identifier
    version: str = Field(min_length=1)


class Reviewer(FrozenCoreModel):
    actor_ref: ActorRef
    independence_class: str = Field(min_length=1)


class ResidualRisk(FrozenCoreModel):
    risk_class: RiskClass
    findings: tuple[str, ...]


class PermittedUse(FrozenCoreModel):
    """``permitted_use: {purpose, destination, consumer, expires_at?}`` --
    unlike section 17's ``SanitizationReceipt``, ``expires_at`` carries a
    ``?`` and is optional here.
    """

    purpose: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    consumer: str = Field(min_length=1)
    expires_at: UtcDateTime | None = None


class MandatoryWorkflowLineage(FrozenCoreModel):
    """``lineage: {workflow_run_ref: {workflow_run_id, object_hash},
    input_hashes: []}`` with ``workflow_run_ref`` MANDATORY -- see the
    module docstring's judgment-call note.
    """

    workflow_run_ref: WorkflowRunRef
    input_hashes: tuple[Sha256Hex, ...]


class RiskReclassificationReceipt(FrozenCoreModel):
    risk_reclassification_receipt_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    source_object: FlatClassifiedObjectRef
    output_object: FlatClassifiedObjectRef
    supersession_ref: SupersessionRef
    remediation: Remediation
    claim_refs: tuple[ClaimRef, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    verification_receipt_refs: tuple[VerificationReceiptRef, ...]
    policy: PolicyRef
    reviewer: Reviewer
    residual_risk: ResidualRisk
    permitted_use: PermittedUse
    issued_at: UtcDateTime
    producer: Producer
    lineage: MandatoryWorkflowLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_risk_reclassification_receipt(self) -> RiskReclassificationReceipt:
        # Mirrors ObjectSuccessorEdge.validate_edge's
        # ``predecessor_ref == successor_ref`` check -- reject only when
        # source and output are equal across their WHOLE identity
        # (object_kind AND object_id AND object_hash). Runs first, exactly
        # as validate_edge's equivalent check runs first, so a
        # fully-identical pair reports this specific reason rather than the
        # more generic hash-only reason below. See module docstring --
        # object_id is deliberately NOT required to differ on its own: a
        # revision that keeps object_id stable and changes only
        # object_hash (CONTRACTS.md:453/:485 "a distinct output revision")
        # is a valid instance of this receipt, not a violation.
        if (
            self.source_object.object_kind == self.output_object.object_kind
            and self.source_object.object_id == self.output_object.object_id
            and self.source_object.object_hash == self.output_object.object_hash
        ):
            raise PydanticCustomError(
                "output_object_same_as_source",
                "output_object must differ from source_object on object_id or object_hash",
            )
        # "The output is a distinct immutable successor of the exact
        # source object; the receipt never rewrites or relabels the
        # predecessor." -- verbatim.
        if self.source_object.object_hash == self.output_object.object_hash:
            raise PydanticCustomError(
                "output_same_as_source_hash",
                "output_object.object_hash must differ from source_object.object_hash",
            )
        if self.source_object.object_kind != self.output_object.object_kind:
            raise PydanticCustomError(
                "output_object_kind_mismatch",
                "output_object.object_kind must equal source_object.object_kind",
            )
        # "Sensitivity cannot decrease under this receipt." -- verbatim,
        # unconditional. Checked as: output sensitivity is already the
        # greater of {output, source} -- i.e. not lower than the source.
        if (
            max_sensitivity(
                self.output_object.sensitivity, self.source_object.sensitivity
            )
            != self.output_object.sensitivity
        ):
            raise PydanticCustomError(
                "sensitivity_lowered",
                "output_object.sensitivity is lower than source_object.sensitivity",
            )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self


def risk_reclassification_authorizes_output(
    receipt: RiskReclassificationReceipt,
    *,
    output_kind: str,
    output_id: str,
    output_hash: str,
    at: datetime,
) -> None:
    """The risk-lowering gate's cross-object half: "is `receipt` a
    currently valid authorization for exactly this output revision, right
    now." Takes bare fields (not ``primitives.ExactObjectRef``) because
    this receipt's own refs are the FLAT shape (section 18), not the
    ``{object_kind, object_id, object_hash}`` primitive.

    Raises ``ValueError`` naming the exact mismatch; returns ``None`` only
    when ``receipt.output_object`` pins this exact output revision and,
    when ``permitted_use.expires_at`` is set, ``at`` is strictly before it
    -- ``expires_at`` is optional on this receipt (unlike
    ``SanitizationReceipt``), so an absent expiry never fails this check.
    ``at`` is caller-supplied, never the wall clock read internally, so
    replay and tests stay deterministic (mirrors
    ``approval_receipt.authorizes_action_intent`` on the sibling
    decision-chain lane and ``sanitization_receipt.sanitization_authorizes_output``).
    """

    if receipt.output_object.object_kind != output_kind:
        raise ValueError("receipt.output_object.object_kind does not name this output")
    if receipt.output_object.object_id != output_id:
        raise ValueError("receipt.output_object.object_id does not name this output")
    if receipt.output_object.object_hash != output_hash:
        raise ValueError(
            "receipt.output_object.object_hash does not pin this exact output revision"
        )
    if (
        receipt.permitted_use.expires_at is not None
        and at >= receipt.permitted_use.expires_at
    ):
        raise ValueError(
            "risk reclassification receipt is expired at the relied-on instant"
        )
