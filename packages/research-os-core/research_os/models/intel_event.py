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

Adversarial-review corrections (2026, post-merge refuter pass on PR #4610):

- ``DurablePayloadReference.uri`` was originally an unconstrained string.
  A "reference" whose locator is a ``data:`` URI is not a reference at
  all -- it is the payload, copied inline, wearing a reference's label.
  ``_DURABLE_REFERENCE_URI_PATTERN`` now requires an ``https://`` or
  ``s3://`` locator with a non-empty host, so ``data:``/``blob:``/
  ``javascript:`` URIs (and any scheme-less or host-less string) fail
  field-level validation before the model is even constructed. ``https``
  covers a stable web/API reference (including an S3-compatible
  endpoint's HTTPS form); ``s3`` covers this repo's actual object-storage
  backend (Tigris, S3-compatible -- see the ``tigris`` skill). This is a
  single ``Field(pattern=...)``, not a duplicate Python-only check, so
  the constraint is visible in the checked-in JSON Schema too (a
  non-Python consumer gets the same guard). The scheme match is
  case-INsensitive (RFC 3986 section 3.1: the scheme component is
  case-insensitive, so ``HTTPS://``/``Https://`` are valid ``https``
  URIs, not a different, forbidden scheme) -- corrected 2026, third pass
  on PR #4610, after review found the original lowercase-only pattern
  rejected legitimate case variants with no such rule declared anywhere.
- The inline/reference gate used to read "protected sensitivities must
  use a reference" (i.e. everything except ``client_pii``/
  ``restricted_osint`` could inline). Section 4's own wire text says
  "validated inline **public** payload" -- the inline arm is for
  ``sensitivity: public`` only, not merely "not the two named protected
  ones". ``internal``/``confidential`` payloads must also use a
  reference. This narrows previously-accepted behaviour; see
  ``invalid_internal_payload_inline`` fixture.
- A second-pass draft of this fix (PR #4610) added a Python check
  forbidding ``extensions`` outright whenever ``classification.
  sensitivity`` is ``client_pii``/``restricted_osint``. That check has
  been REMOVED (third pass, same PR): CONTRACTS.md section 2 grants
  every core object namespaced ``extensions`` unconditionally, and no
  clause in section 2 or section 4 conditions that grant on
  ``classification.sensitivity`` -- the check was an implementer-chosen
  narrowing of a frozen contract, not a spec-derived one, and it was
  invisible to non-Python consumers (no matching JSON Schema
  constraint). Per section 21, a rule not in the freeze belongs in a
  versioned freeze-change proposal for the Conductor to rule on, not in
  a silent validator addition. The gap this would have closed is real
  and stays a DECLARED LIMIT instead of a guard: nothing on this object
  detects free-form PII/OSINT content hidden inside an arbitrary,
  producer-defined ``extensions`` payload whose ``classification.
  sensitivity`` is (correctly or incorrectly) something other than
  ``client_pii``/``restricted_osint`` -- no field in section 2's
  extension envelope declares what "PII-shaped" means, and a single
  immutable object cannot discharge that judgment about its own opaque
  payload. That responsibility belongs to whichever component assigns
  ``classification.sensitivity`` in the first place (the producer
  pipeline) or to a content-classification gate upstream of ingestion,
  not to this structural validator.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import RiskClass, Sensitivity
from research_os.hashing import canonicalize, object_hash
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

# A durable reference must be an https:// or s3:// locator with a
# non-empty host -- see the "Adversarial-review corrections" docstring
# note above. The scheme is matched case-insensitively (spelled-out
# per-letter character classes, not an inline flag -- ECMA-262/Draft
# 2020-12 ``pattern`` has no inline-flag syntax) because RFC 3986
# section 3.1 makes the scheme component case-insensitive: ``HTTPS://``
# is the same scheme as ``https://``, not a different, forbidden one.
# No possessive quantifiers/atomic groups (ECMA-262 safe); linear in
# input length (single alternation, one non-overlapping character-class
# run, one optional trailing greedy group).
_DURABLE_REFERENCE_URI_PATTERN = r"^([hH][tT][tT][pP][sS]|[sS]3)://[^/]+(/.*)?$"


def _intel_event_json_schema_extra(schema: dict[str, Any], _model: type[Any]) -> None:
    """Express the inline-requires-public invariant for non-Python consumers.

    ``validate_event`` below enforces this in Python; Draft 2020-12's
    ``if``/``then`` lets the same constraint reach the checked-in schema
    artifact, so a Go/TypeScript validator rejects the same documents.
    """

    schema["if"] = {
        "required": ["payload_ref"],
        "properties": {
            "payload_ref": {
                "required": ["ref_type"],
                "properties": {"ref_type": {"const": "inline_public"}},
            }
        },
    }
    schema["then"] = {
        "required": ["classification"],
        "properties": {
            "classification": {
                "required": ["sensitivity"],
                "properties": {"sensitivity": {"const": "public"}},
            }
        },
    }


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
    """The "durable reference" half of ``payload_ref`` -- an out-of-line pointer.

    ``uri`` must denote an actual durable external storage location (an
    ``https://`` or ``s3://`` locator with a host) -- see the module
    docstring's "Adversarial-review corrections" note. This rejects
    ``data:``/``blob:``/``javascript:`` URIs, which are not references
    to anything durable: a ``data:`` URI IS the payload, inline.
    """

    ref_type: Literal["reference"]
    uri: str = Field(min_length=1, pattern=_DURABLE_REFERENCE_URI_PATTERN)
    content_hash: Sha256Hex


class InlinePublicPayload(FrozenCoreModel):
    """The "validated inline public payload" half of ``payload_ref``.

    ``content_hash`` is verified against the actual ``payload`` bytes
    (RFC 8785 canonical JSON + sha256, the same rule section 2 uses for
    ``object_hash``) so the field cannot be a decorative, unchecked
    label -- see the module docstring's "Adversarial-review corrections"
    note.
    """

    ref_type: Literal["inline_public"]
    payload: dict[str, Any]
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_inline_content_hash(self) -> InlinePublicPayload:
        expected = sha256(canonicalize(self.payload)).hexdigest()
        if self.content_hash != expected:
            raise PydanticCustomError(
                "inline_payload_content_hash_mismatch",
                "content_hash must equal sha256(RFC 8785 canonical payload)",
            )
        return self


class IntelEvent(FrozenCoreModel):
    model_config = ConfigDict(json_schema_extra=_intel_event_json_schema_extra)

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
    payload_ref: DurablePayloadReference | InlinePublicPayload = Field(
        discriminator="ref_type"
    )
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_event(self) -> IntelEvent:
        validate_extensions(self.extensions)

        # Section 4 invariant, narrowed to what the wire text actually
        # says ("validated inline PUBLIC payload"): inline is valid only
        # for sensitivity=public. Every other sensitivity -- including
        # internal/confidential, not just the two protected ones -- must
        # use a durable reference. See the "Adversarial-review
        # corrections" module docstring note.
        if (
            isinstance(self.payload_ref, InlinePublicPayload)
            and self.classification.sensitivity != Sensitivity.PUBLIC
        ):
            raise PydanticCustomError(
                "inline_payload_requires_public_sensitivity",
                "payload_ref may only be inline_public when "
                "classification.sensitivity is public; every other "
                "sensitivity must use a durable reference",
            )

        # NOTE: two section-4 invariants are repository-level, not checkable
        # on one standalone canonical object, and are therefore not enforced
        # here: "(producer.name, identity.idempotency_key) is unique" and
        # "replay creates delivery attempts, not duplicate canonical events."
        #
        # NOTE: this validator does NOT gate ``extensions`` on
        # ``classification.sensitivity`` -- see the module docstring's
        # "Adversarial-review corrections" note (last bullet) for why that
        # was tried and reverted, and what the resulting declared limit is.

        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
