"""BrainRequest / BrainCandidate — the provider-independent client-bot contract.

Frozen per docs/plans/2026-08-25-due-bot-live/MANDATE.md F1/F3 and
research/operations/2026-08-25-due-bot-7-lens-research.md §1.5.

``BrainCandidate`` is the ONLY thing a ``ClientBrainProvider`` (Gemini,
Codex broker, a future metered leg) may return. It is deliberately a much
narrower surface than ``BrainRequest``: providers receive a frozen
evidence/pricing package and must answer inside its shape — they cannot
enqueue a message, invoke a surface sender, or ship anything the
``FinalPolicyGate`` (out of scope for this unit — see ``policy/types.py``)
has not yet cleared.

``schemas/client_brain_candidate_v1.json`` is generated FROM
``BrainCandidate.model_json_schema()`` (see
``scripts/... test_contracts_freeze.py::test_pydantic_json_schema_matches_committed_file``)
so the two can never drift silently.

Author: Claude Opus 5 (lane B1a — client-bot contract freeze)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.channels.models import CanonicalMessage
from backend.channels.profiles import FROZEN_PROFILES, SurfaceProfile

__all__ = [
    "BrainCandidate",
    "BrainRequest",
    "Claim",
    "EvidenceItem",
    "GroundingBundle",
    "HistoryRole",
    "HistoryTurn",
    "PricingSnapshot",
]

# sha256 hex digest shape, reused for package/snapshot integrity hashes.
_SHA256_HEX = r"^[0-9a-f]{64}$"

# A "simple identifier format" (research capture §1.5, last paragraph) for
# evidence/source/claim ids — lowercase, digits, underscore/hyphen, no
# whitespace or path-like separators. Chosen deliberately narrow: these ids
# round-trip through provider structured output (Gemini/Codex), so the
# format must reject anything that could smuggle a path, URL, or control
# character through a claims/citations field.
_SIMPLE_ID = r"^[a-z0-9][a-z0-9_-]{0,63}$"


class EvidenceItem(BaseModel):
    """One retrieved grounding fact, frozen into the package before generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: Annotated[str, Field(pattern=_SIMPLE_ID)]
    source_id: Annotated[str, Field(pattern=_SIMPLE_ID)]
    source_title: Annotated[str, Field(min_length=1, max_length=500)]
    source_uri: Annotated[str, Field(max_length=2_048)] | None
    source_kind: Literal["regulation", "kb", "pricing", "procedure"]
    text: Annotated[str, Field(min_length=1, max_length=4_000)]
    retrieval_score: Annotated[float, Field(ge=0.0, le=1.0)]
    effective_at: datetime | None
    retrieved_at: datetime


class PricingSnapshot(BaseModel):
    """A frozen PricingTool result. Providers may only quote from this — never recompute."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: UUID
    pricing_tool_version: Annotated[str, Field(min_length=1, max_length=64)]
    generated_at: datetime
    # PricingTool's typed result, frozen at the API boundary; the concrete
    # per-item pydantic model belongs to PricingTool itself (out of scope
    # here — CLAUDE.md §8 rule 11: "PricingTool Only. All prices from
    # PricingTool"). This is the transport shape the client-bot layer
    # freezes it into, not a re-definition of PricingTool's own schema.
    items: tuple[dict[str, object], ...] = Field(default=(), max_length=100)
    snapshot_sha256: Annotated[str, Field(pattern=_SHA256_HEX)]


class HistoryRole(StrEnum):
    """Closed role set for a history turn — never an arbitrary key."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class HistoryTurn(BaseModel):
    """One sanitized, bounded conversation turn (research capture §1.5: 'sanitized
    and bounded'). This is the field that carries prior conversation content to a
    CLOUD provider — the surface SYMBIOSIS Law 2 governs — so it is a real typed
    model with ``extra="forbid"``, not a free-form ``dict[str, str]`` whose keys
    and values a docstring merely asserted were sanitized. A dict shape cannot
    enforce that; this model does.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: HistoryRole
    content: Annotated[str, Field(max_length=4_000)]


class GroundingBundle(BaseModel):
    """The single frozen evidence/pricing/history package every provider sees identically."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bundle_id: UUID
    query: Annotated[str, Field(min_length=1, max_length=4_000)]
    domain: Annotated[str, Field(min_length=1, max_length=64)]
    evidence: tuple[EvidenceItem, ...] = Field(default=(), max_length=50)
    pricing: PricingSnapshot | None = None
    history: tuple[HistoryTurn, ...] = Field(default=(), max_length=50)
    persona_digest: Annotated[str, Field(min_length=1, max_length=200)]
    package_sha256: Annotated[str, Field(pattern=_SHA256_HEX)]


class BrainRequest(BaseModel):
    """What ``ClientBotEngine`` (out of scope) hands to a ``ClientBrainProvider``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    message: CanonicalMessage
    profile: SurfaceProfile
    grounding: GroundingBundle
    deadline_at: datetime


class Claim(BaseModel):
    """One factual/regulatory/numeric assertion inside a candidate answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: Annotated[str, Field(pattern=_SIMPLE_ID)]
    text: Annotated[str, Field(min_length=1, max_length=2_000)]
    kind: Literal["regulatory", "eligibility", "deadline", "price", "procedural", "other"]
    evidence_ids: tuple[Annotated[str, Field(pattern=_SIMPLE_ID)], ...] = Field(
        default=(), max_length=20
    )


# The brain contract serves all four surfaces through ONE schema, so its bound
# must be the ENVELOPE across every frozen profile's hard cap — never a number
# picked independently of them. Derived, not hardcoded, so a future profile
# edit cannot silently reopen the gap the B1a review round-1 found (BrainCandidate
# permitted 8000 chars while three of four surfaces cap lower, and Portal's own
# 12000-char budget was unreachable by construction). See
# test_brain_candidate_answer_envelope_covers_every_profile_hard_cap.
_ANSWER_MAX_LENGTH = max(profile.hard_max_chars for profile in FROZEN_PROFILES)


class BrainCandidate(BaseModel):
    """The ONLY type a ClientBrainProvider may return (research capture §1.5/§1.6).

    Strict by construction: ``extra="forbid"`` is what makes
    ``model_json_schema()`` emit ``additionalProperties: false`` — required
    for both ``codex exec --output-schema`` (F3) and Gemini structured
    output, and re-validated server-side even when a provider claims schema
    compliance (research capture §1.5, closing paragraph).

    For B2: provider-side structured-output enforcement (OpenAI/Gemini
    ``response_schema``) typically grammar-enforces only a SUBSET of this
    JSON Schema — required/enum/type, not ``pattern``/``minLength``/
    ``maxLength``/``maxItems``. This schema constrains STRUCTURE; every
    bound here MUST be re-validated server-side via
    ``BrainCandidate.model_validate()`` regardless of what the provider
    claims to have enforced.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://balizero.com/schemas/client_brain_candidate_v1.json",
        },
    )

    schema_version: Literal["1.0"]
    disposition: Literal["answer", "abstain", "handoff"]
    # No default: research capture §1.5 requires the shared schema to "require
    # all fields" — a default would drop `answer` out of the generated
    # schema's `required` list. Callers must pass answer="" explicitly for
    # abstain/handoff (enforced by the validator below).
    answer: Annotated[str, Field(max_length=_ANSWER_MAX_LENGTH)]
    claims: tuple[Claim, ...] = Field(default=(), max_length=50)
    cited_evidence_ids: tuple[Annotated[str, Field(pattern=_SIMPLE_ID)], ...] = Field(
        default=(), max_length=50
    )
    handoff_reason_code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,63}$")] | None = None
    provider_name: Annotated[str, Field(pattern=r"^[a-zA-Z0-9._-]{1,128}$")]
    model_name: Annotated[str, Field(pattern=r"^[a-zA-Z0-9._:/-]{1,128}$")]
    package_sha256: Annotated[str, Field(pattern=_SHA256_HEX)]

    @model_validator(mode="after")
    def _disposition_constrains_payload(self) -> BrainCandidate:
        """B1a review round-1, finding 5: ``disposition`` constrained nothing
        about the rest of the payload — a ``handoff`` with no reason code, an
        ``answer`` with an empty ``answer``, and an ``abstain`` carrying an
        8000-char answer plus 50 claims were all schema-valid. Couple them:

        - ``handoff_reason_code`` is set if and only if ``disposition == "handoff"``.
        - ``answer`` is non-empty if and only if ``disposition == "answer"``.
        - ``claims``/``cited_evidence_ids`` are empty unless ``disposition == "answer"``.

        This conditional coupling is NOT representable in the committed JSON
        Schema without hand-authored ``if``/``then`` keywords (pydantic does
        not export model_validators to JSON Schema) — it is enforced here,
        server-side, on every candidate regardless of provider.
        """
        is_answer = self.disposition == "answer"
        is_handoff = self.disposition == "handoff"

        if is_handoff and self.handoff_reason_code is None:
            raise ValueError("handoff_reason_code is required when disposition is handoff")
        if not is_handoff and self.handoff_reason_code is not None:
            raise ValueError("handoff_reason_code must be unset unless disposition is handoff")

        if is_answer and not self.answer:
            raise ValueError("answer must be non-empty when disposition is answer")
        if not is_answer and self.answer:
            raise ValueError("answer must be empty unless disposition is answer")

        if not is_answer and (self.claims or self.cited_evidence_ids):
            raise ValueError("claims/cited_evidence_ids must be empty unless disposition is answer")

        return self
