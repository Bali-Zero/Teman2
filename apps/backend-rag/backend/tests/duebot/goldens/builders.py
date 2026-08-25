"""Deterministic builders for the frozen BOT A client-bot contracts.

Every UUID/sha256-shaped field these contracts require (``CanonicalMessage``
alone has seven) is derived from ``det_uuid``/``det_sha256`` — NEVER
``uuid.uuid4()`` — so two runs of the same fixture code produce byte-
identical instances. That is what makes a golden fixture a GOLDEN fixture:
a reviewer diffing this file sees the actual field values change when a
fixture's intent changes, never noise from a fresh random id on every
import.

These builders intentionally do not try to be "the" production adapter
construction path (that code — turning a raw WhatsApp/Instagram webhook
into a ``CanonicalMessage`` — is out of scope for this contract-freeze
lane, per ``backend.channels.models``'s own module docstring). They exist
only to make a VALID instance of each frozen type cheap and readable to
construct in a fixture file, respecting every ``pattern``/``model_validator``
constraint the real types enforce.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from backend.channels.models import (
    AttachmentKind,
    CanonicalActor,
    CanonicalAttachment,
    CanonicalMessage,
    ClientSurface,
    MessageKind,
    SurfaceContext,
)
from backend.channels.profiles import SurfaceProfile
from backend.services.client_bot.contracts import (
    BrainCandidate,
    BrainRequest,
    Claim,
    EvidenceItem,
    GroundingBundle,
    HistoryRole,
    HistoryTurn,
    PricingSnapshot,
)
from backend.services.client_bot.policy.types import FinalDecision, GateReason, GateVerdict

# Arbitrary fixed namespace (a hand-picked valid hex UUID, frozen here) —
# uuid.uuid5 with a FIXED namespace + a fixture-specific string is what
# makes det_uuid deterministic across runs/machines. Never regenerate this
# value; doing so would silently change every fixture's ids.
_UUID_NAMESPACE = uuid.UUID("c1a55ec0-b6b0-4000-8000-000000000001")

# Frozen wall-clock for every fixture — goldens must never depend on
# datetime.now() (a fixture diff should never show a timestamp-only change).
FIXED_NOW = datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc)


def det_uuid(*parts: str) -> uuid.UUID:
    """A UUID5 derived from ``parts`` — the same parts always produce the
    same UUID, so fixtures are reviewable and stay stable across runs.
    """
    return uuid.uuid5(_UUID_NAMESPACE, ":".join(parts))


def det_sha256(*parts: str) -> str:
    """A 64-hex-char sha256 hex digest derived from ``parts`` — stands in
    for the many HMAC/sha256-shaped fields these contracts require
    (``subject_token``, ``idempotency_key``, ``package_sha256``, ...).
    NOT a real HMAC of anything real — fixture data only. It satisfies the
    field's SHAPE, which is explicitly all ``CanonicalActor.subject_token``
    proves per its own docstring ("a SHAPE guarantee, not a cryptographic
    one") — this builder does not misrepresent that boundary.
    """
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# CanonicalMessage and its nested types (backend.channels.models)
# ---------------------------------------------------------------------------


def make_actor(
    case_id: str,
    *,
    authenticated: bool = False,
    locale: str | None = "id-ID",
    customer_tier: str | None = None,
) -> CanonicalActor:
    return CanonicalActor(
        subject_token=det_sha256(case_id, "subject"),
        canonical_user_id=det_uuid(case_id, "user"),
        authenticated=authenticated,
        locale=locale,
        customer_tier=customer_tier,
    )


def make_surface_context(
    case_id: str,
    *,
    surface: ClientSurface,
    portal_case_id: uuid.UUID | None = None,
    kbli_code: str | None = None,
    authenticated_session_id: uuid.UUID | None = None,
) -> SurfaceContext:
    product = "client_bot"
    if surface == ClientSurface.PORTAL:
        product = "portal"
    elif surface == ClientSurface.KBLI_WIDGET:
        product = "kbli_navigator"
    return SurfaceContext(
        account_ref=f"acct-{case_id}",
        route=None,
        product=product,
        portal_case_id=portal_case_id,
        kbli_code=kbli_code,
        page_context_ref=None,
        authenticated_session_id=authenticated_session_id,
    )


def make_attachment(
    case_id: str,
    *,
    suffix: str = "att1",
    kind: AttachmentKind = AttachmentKind.IMAGE,
    mime_type: str = "image/jpeg",
    filename: str | None = None,
    size_bytes: int | None = 245_760,
) -> CanonicalAttachment:
    return CanonicalAttachment(
        attachment_id=det_uuid(case_id, suffix),
        kind=kind,
        mime_type=mime_type,
        media_ref=f"media-store:{case_id}-{suffix}",
        filename=filename,
        size_bytes=size_bytes,
        sha256=det_sha256(case_id, suffix, "content"),
        extracted_text_ref=None,
    )


def make_canonical_message(
    case_id: str,
    *,
    surface: ClientSurface = ClientSurface.WHATSAPP,
    text: str = "Halo, saya mau tanya soal KITAS.",
    kind: MessageKind = MessageKind.TEXT,
    attachments: tuple[CanonicalAttachment, ...] = (),
    authenticated: bool = False,
    portal_case_id: uuid.UUID | None = None,
    kbli_code: str | None = None,
    authenticated_session_id: uuid.UUID | None = None,
    locale_hint: str | None = "id-ID",
    reply_to_external_message_id: str | None = None,
) -> CanonicalMessage:
    actor = make_actor(case_id, authenticated=authenticated, locale=locale_hint)
    surface_context = make_surface_context(
        case_id,
        surface=surface,
        portal_case_id=portal_case_id,
        kbli_code=kbli_code,
        authenticated_session_id=authenticated_session_id,
    )
    return CanonicalMessage(
        event_id=det_uuid(case_id, "event"),
        trace_id=det_uuid(case_id, "trace"),
        surface=surface,
        external_message_id=f"ext-{case_id}",
        idempotency_key=det_sha256(case_id, "idem"),
        conversation_id=det_uuid(case_id, "conversation"),
        session_id=det_uuid(case_id, "session"),
        reply_to_external_message_id=reply_to_external_message_id,
        kind=kind,
        text=text,
        attachments=attachments,
        actor=actor,
        surface_context=surface_context,
        occurred_at=FIXED_NOW,
        received_at=FIXED_NOW,
        delivery_deadline_at=None,
        locale_hint=locale_hint,
        raw_payload_sha256=det_sha256(case_id, "raw_payload"),
    )


def make_portal_message(
    case_id: str,
    *,
    text: str = "Mohon info status kasus saya.",
    portal_case_id_suffix: str = "case1",
) -> CanonicalMessage:
    """Convenience wrapper: PORTAL surface requires ``actor.authenticated``
    AND ``surface_context.authenticated_session_id`` (F2 —
    ``CanonicalMessage._portal_surface_requires_authentication``). Getting
    both right by hand at every call site is exactly the kind of thing a
    golden-fixture author forgets; this wrapper cannot forget it.
    """
    return make_canonical_message(
        case_id,
        surface=ClientSurface.PORTAL,
        text=text,
        authenticated=True,
        portal_case_id=det_uuid(case_id, portal_case_id_suffix),
        authenticated_session_id=det_uuid(case_id, "session-auth"),
    )


# ---------------------------------------------------------------------------
# GroundingBundle and its nested types (backend.services.client_bot.contracts)
# ---------------------------------------------------------------------------


def make_evidence_item(
    case_id: str,
    *,
    suffix: str = "ev1",
    source_kind: str = "regulation",
    source_title: str = "Regulation X",
    text: str = "Grounding text supporting the claim.",
    retrieval_score: float = 0.9,
    source_uri: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"ev-{suffix}",
        source_id=f"src-{suffix}",
        source_title=source_title,
        source_uri=source_uri,
        source_kind=source_kind,
        text=text,
        retrieval_score=retrieval_score,
        effective_at=FIXED_NOW,
        retrieved_at=FIXED_NOW,
    )


def make_pricing_snapshot(
    case_id: str,
    *,
    items: tuple[dict[str, object], ...] = (),
) -> PricingSnapshot:
    return PricingSnapshot(
        snapshot_id=det_uuid(case_id, "pricing"),
        pricing_tool_version="pricing-tool-v1",
        generated_at=FIXED_NOW,
        items=items,
        snapshot_sha256=det_sha256(case_id, "pricing", "snapshot"),
    )


def make_history_turn(role: HistoryRole, content: str) -> HistoryTurn:
    return HistoryTurn(role=role, content=content)


def make_grounding_bundle(
    case_id: str,
    *,
    query: str = "query text",
    domain: str = "immigration",
    evidence: tuple[EvidenceItem, ...] = (),
    pricing: PricingSnapshot | None = None,
    history: tuple[HistoryTurn, ...] = (),
) -> GroundingBundle:
    return GroundingBundle(
        bundle_id=det_uuid(case_id, "bundle"),
        query=query,
        domain=domain,
        evidence=evidence,
        pricing=pricing,
        history=history,
        persona_digest="zantara-persona-v1",
        package_sha256=det_sha256(case_id, "bundle", "package"),
    )


def make_brain_request(
    case_id: str,
    *,
    message: CanonicalMessage,
    profile: SurfaceProfile,
    grounding: GroundingBundle,
    deadline_at: datetime = FIXED_NOW,
) -> BrainRequest:
    return BrainRequest(
        request_id=det_uuid(case_id, "request"),
        message=message,
        profile=profile,
        grounding=grounding,
        deadline_at=deadline_at,
    )


# ---------------------------------------------------------------------------
# BrainCandidate and Claim
# ---------------------------------------------------------------------------


def make_claim(
    *,
    suffix: str = "c1",
    text: str = "claim text",
    kind: str = "regulatory",
    evidence_ids: tuple[str, ...] = (),
    price_service_key: str | None = None,
) -> Claim:
    return Claim(
        claim_id=f"claim-{suffix}",
        text=text,
        kind=kind,
        evidence_ids=evidence_ids,
        price_service_key=price_service_key,
    )


def make_answer_candidate(
    case_id: str,
    *,
    answer: str = "Jawaban singkat dan berbasis regulasi.",
    claims: tuple[Claim, ...] = (),
    cited_evidence_ids: tuple[str, ...] = (),
    provider_name: str = "gemini",
    model_name: str = "gemini-2.5-pro",
) -> BrainCandidate:
    return BrainCandidate(
        schema_version="1.0",
        disposition="answer",
        answer=answer,
        claims=claims,
        cited_evidence_ids=cited_evidence_ids,
        handoff_reason_code=None,
        provider_name=provider_name,
        model_name=model_name,
        package_sha256=det_sha256(case_id, "candidate"),
    )


def make_abstain_candidate(
    case_id: str,
    *,
    provider_name: str = "gemini",
    model_name: str = "gemini-2.5-pro",
) -> BrainCandidate:
    return BrainCandidate(
        schema_version="1.0",
        disposition="abstain",
        answer="",
        claims=(),
        cited_evidence_ids=(),
        handoff_reason_code=None,
        provider_name=provider_name,
        model_name=model_name,
        package_sha256=det_sha256(case_id, "candidate"),
    )


def make_handoff_candidate(
    case_id: str,
    *,
    handoff_reason_code: str = "OUT_OF_SCOPE_REGULATED_REQUEST",
    provider_name: str = "gemini",
    model_name: str = "gemini-2.5-pro",
) -> BrainCandidate:
    return BrainCandidate(
        schema_version="1.0",
        disposition="handoff",
        answer="",
        claims=(),
        cited_evidence_ids=(),
        handoff_reason_code=handoff_reason_code,
        provider_name=provider_name,
        model_name=model_name,
        package_sha256=det_sha256(case_id, "candidate"),
    )


# ---------------------------------------------------------------------------
# FinalDecision (backend.services.client_bot.policy.types)
# ---------------------------------------------------------------------------


def make_final_decision(
    case_id: str,
    *,
    verdict: GateVerdict,
    reason: GateReason,
    reason_detail: str | None = None,
    rendered_text: str | None = None,
) -> FinalDecision:
    return FinalDecision(
        decision_id=det_uuid(case_id, "decision"),
        request_id=det_uuid(case_id, "request"),
        verdict=verdict,
        reason=reason,
        reason_detail=reason_detail,
        rendered_text=rendered_text,
        evaluated_at=FIXED_NOW,
    )
