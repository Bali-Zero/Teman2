"""Immutable IntelEvent contract from frozen CONTRACTS.md section 4.

Purpose (verbatim): "immutable description of an observed or emitted event.
Intel Lake owns the canonical record."

Interpretation notes for fields the frozen wire shape names but does not
type (see the model docstrings below for the exact clause each shape
implements):

- ``producer.machine_class``, ``source.uri/native_id/canonical_url/
  jurisdiction``, ``identity.idempotency_key``, ``classification.rights``
  carry no pattern or enum in section 4, so they are modeled as
  non-empty strings rather than invented namespaced/enum shapes.
- ``event_type`` matches section 3's "registered namespaced string"
  phrasing used for ``reason_code`` elsewhere, so it reuses
  ``RegisteredName``. ``source.source_type``/``classification.domain``/
  ``classification.language`` are categorical single-or-namespaced
  tokens, so they reuse ``Identifier`` (whose pattern -- unlike
  ``RegisteredName`` -- accepts a bare unnamespaced token).
- ``payload_ref``'s two shapes ("durable reference" vs "validated inline
  public payload") are not given field-level detail in section 4; the
  concrete ``DurablePayloadReference``/``InlinePublicPayload`` layout
  below is this packet's canonical choice, discriminated on ``ref_type``.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import RiskClass, Sensitivity
from research_os.hashing import object_hash
from research_os.primitives import (
    Extensions,
    FrozenCoreModel,
    Identifier,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)

_PROTECTED_SENSITIVITIES = frozenset({Sensitivity.RESTRICTED_OSINT, Sensitivity.CLIENT_PII})


class EventRef(FrozenCoreModel):
    """Exact reference to one immutable ``IntelEvent`` revision.

    Reused verbatim (same two fields) wherever section 4/5/11 reference an
    ``IntelEvent`` by ``{event_id, object_hash}`` -- ``IntelEvent.lineage.
    input_event_refs``, ``Evidence.source_event_ref``, and ``StoryCluster.
    canonical_event_ref``/``members[].event_ref``.
    """

    event_id: UUID
    object_hash: Sha256Hex


class IntelEventProducer(FrozenCoreModel):
    """``producer: {name, version, machine_class}`` -- section 4."""

    name: Identifier
    version: str = Field(min_length=1)
    machine_class: str = Field(min_length=1)


class IntelEventSource(FrozenCoreModel):
    """``source: {uri, native_id?, canonical_url?, source_type, jurisdiction?}``."""

    uri: str = Field(min_length=1)
    native_id: str | None = Field(default=None, min_length=1)
    canonical_url: str | None = Field(default=None, min_length=1)
    source_type: Identifier
    jurisdiction: str | None = Field(default=None, min_length=1)


class IntelEventTimes(FrozenCoreModel):
    """``times: {published_at?, observed_at, ingested_at}``."""

    published_at: UtcDateTime | None = None
    observed_at: UtcDateTime
    ingested_at: UtcDateTime


class IntelEventIdentity(FrozenCoreModel):
    """``identity: {content_hash, normalized_hash?, idempotency_key}``."""

    content_hash: Sha256Hex
    normalized_hash: Sha256Hex | None = None
    idempotency_key: str = Field(min_length=1)


class IntelEventClassification(FrozenCoreModel):
    """``classification: {language?, domain?, risk_class, sensitivity, rights?}``."""

    language: Identifier | None = None
    domain: Identifier | None = None
    risk_class: RiskClass
    sensitivity: Sensitivity
    rights: str | None = Field(default=None, min_length=1)


class IntelEventLineage(FrozenCoreModel):
    """``lineage: {pipeline_run_id, input_event_refs, parser_version?, model_version?, prompt_version?}``."""

    pipeline_run_id: UUID
    input_event_refs: tuple[EventRef, ...]
    parser_version: str | None = Field(default=None, min_length=1)
    model_version: str | None = Field(default=None, min_length=1)
    prompt_version: str | None = Field(default=None, min_length=1)


class DurablePayloadReference(FrozenCoreModel):
    """The "durable reference" half of ``payload_ref`` -- an out-of-line pointer."""

    ref_type: Literal["reference"]
    uri: str = Field(min_length=1)
    content_hash: Sha256Hex


class InlinePublicPayload(FrozenCoreModel):
    """The "validated inline public payload" half of ``payload_ref``."""

    ref_type: Literal["inline_public"]
    payload: dict[str, Any]
    content_hash: Sha256Hex


class IntelEvent(FrozenCoreModel):
    event_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    event_type: RegisteredName
    producer: IntelEventProducer
    source: IntelEventSource
    times: IntelEventTimes
    identity: IntelEventIdentity
    classification: IntelEventClassification
    lineage: IntelEventLineage
    payload_ref: DurablePayloadReference | InlinePublicPayload = Field(discriminator="ref_type")
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_event(self) -> IntelEvent:
        validate_extensions(self.extensions)

        # Section 4 invariant: "restricted_osint or client_pii payloads are
        # references to protected Pro storage, never copied into general
        # event payloads."
        if self.classification.sensitivity in _PROTECTED_SENSITIVITIES and isinstance(
            self.payload_ref, InlinePublicPayload
        ):
            raise PydanticCustomError(
                "protected_payload_must_be_reference",
                "restricted_osint and client_pii payloads must use a durable "
                "reference, never an inline payload",
            )

        # NOTE: two section-4 invariants are repository-level, not checkable
        # on one standalone canonical object, and are therefore not enforced
        # here: "(producer.name, identity.idempotency_key) is unique" and
        # "replay creates delivery attempts, not duplicate canonical events."

        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
