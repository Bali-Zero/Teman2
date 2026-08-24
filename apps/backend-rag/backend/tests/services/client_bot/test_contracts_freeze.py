"""Contract-freeze tests for BOT A (lane B1a).

Covers, per the lane B1a mandate:
- round-trip serialization (model_dump -> model_validate) on every new model
- unknown-field REJECTION on every model (extra="forbid")
- schema_version pinning (CanonicalMessage + BrainCandidate)
- pydantic <-> JSON-Schema agreement: BrainCandidate.model_json_schema()
  must match the committed schemas/client_brain_candidate_v1.json verbatim,
  so the two can never drift silently
- the F2 profile invariants: length/format/citation/history/deadlines/
  handoff-queue present, NEVER a provider name; KBLI domain-restricted;
  portal requires auth
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.channels.models import (
    AttachmentKind,
    CanonicalActor,
    CanonicalAttachment,
    CanonicalMessage,
    ClientSurface,
    MessageKind,
    SurfaceContext,
)
from backend.channels.profiles import (
    CLIENT_IG_V1,
    CLIENT_KBLI_V1,
    CLIENT_PORTAL_V1,
    CLIENT_WA_V1,
    FROZEN_PROFILES,
    PROFILES_BY_ID,
    PROFILES_BY_SURFACE,
    CitationPolicy,
    SurfaceProfile,
    get_profile,
)
from backend.services.client_bot.contracts import (
    BrainCandidate,
    BrainRequest,
    Claim,
    EvidenceItem,
    GroundingBundle,
    PricingSnapshot,
)
from backend.services.client_bot.policy.types import FinalDecision, GateReason, GateVerdict

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "schemas" / "client_brain_candidate_v1.json"
)

_SHA = "a" * 64
_HEX_TOKEN = "b" * 64


def _sha256(prefix: str) -> str:
    """A syntactically-valid 64-hex-char digest, distinguishable per prefix."""
    return (prefix * 64)[:64]


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def make_actor(**overrides: object) -> CanonicalActor:
    defaults: dict[str, object] = {
        "subject_token": _sha256("1"),
        "canonical_user_id": uuid4(),
        "authenticated": False,
        "locale": "id-ID",
        "customer_tier": None,
    }
    defaults.update(overrides)
    return CanonicalActor(**defaults)


def make_surface_context(**overrides: object) -> SurfaceContext:
    defaults: dict[str, object] = {
        "account_ref": "waba:123456",
        "route": None,
        "product": "client_bot",
        "portal_case_id": None,
        "kbli_code": None,
        "page_context_ref": None,
        "authenticated_session_id": None,
    }
    defaults.update(overrides)
    return SurfaceContext(**defaults)


def make_canonical_message(**overrides: object) -> CanonicalMessage:
    now = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
    defaults: dict[str, object] = {
        "event_id": uuid4(),
        "trace_id": uuid4(),
        "surface": ClientSurface.WHATSAPP,
        "external_message_id": "wamid.abc123",
        "idempotency_key": _sha256("2"),
        "conversation_id": uuid4(),
        "session_id": uuid4(),
        "reply_to_external_message_id": None,
        "kind": MessageKind.TEXT,
        "text": "Berapa biaya KITAS investor?",
        "attachments": (),
        "actor": make_actor(),
        "surface_context": make_surface_context(),
        "occurred_at": now,
        "received_at": now,
        "delivery_deadline_at": None,
        "locale_hint": "id",
        "raw_payload_sha256": _sha256("3"),
    }
    defaults.update(overrides)
    return CanonicalMessage(**defaults)


def make_evidence_item(**overrides: object) -> EvidenceItem:
    now = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
    defaults: dict[str, object] = {
        "evidence_id": "ev-001",
        "source_id": "src-001",
        "source_title": "Permenkumham 22/2023",
        "source_uri": "https://example.com/reg/22-2023",
        "source_kind": "regulation",
        "text": "KITAS investor requires a minimum paid-up capital of IDR 10 billion.",
        "retrieval_score": 0.92,
        "effective_at": now,
        "retrieved_at": now,
    }
    defaults.update(overrides)
    return EvidenceItem(**defaults)


def make_pricing_snapshot(**overrides: object) -> PricingSnapshot:
    now = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
    defaults: dict[str, object] = {
        "snapshot_id": uuid4(),
        "pricing_tool_version": "2026.08.1",
        "generated_at": now,
        "items": ({"service": "kitas_investor", "amount_idr": 15_000_000},),
        "snapshot_sha256": _sha256("4"),
    }
    defaults.update(overrides)
    return PricingSnapshot(**defaults)


def make_grounding_bundle(**overrides: object) -> GroundingBundle:
    defaults: dict[str, object] = {
        "bundle_id": uuid4(),
        "query": "Berapa biaya KITAS investor?",
        "domain": "immigration",
        "evidence": (make_evidence_item(),),
        "pricing": make_pricing_snapshot(),
        "history": (),
        "persona_digest": _sha256("5")[:40],
        "package_sha256": _sha256("6"),
    }
    defaults.update(overrides)
    return GroundingBundle(**defaults)


def make_brain_request(**overrides: object) -> BrainRequest:
    now = datetime(2026, 8, 25, 12, 0, 5, tzinfo=timezone.utc)
    defaults: dict[str, object] = {
        "request_id": uuid4(),
        "message": make_canonical_message(),
        "profile": CLIENT_WA_V1,
        "grounding": make_grounding_bundle(),
        "deadline_at": now,
    }
    defaults.update(overrides)
    return BrainRequest(**defaults)


def make_claim(**overrides: object) -> Claim:
    defaults: dict[str, object] = {
        "claim_id": "claim-001",
        "text": "Minimum paid-up capital is IDR 10 billion.",
        "kind": "regulatory",
        "evidence_ids": ("ev-001",),
    }
    defaults.update(overrides)
    return Claim(**defaults)


def make_brain_candidate(**overrides: object) -> BrainCandidate:
    defaults: dict[str, object] = {
        "schema_version": "1.0",
        "disposition": "answer",
        "answer": "KITAS investor requires IDR 10 billion paid-up capital [1].",
        "claims": (make_claim(),),
        "cited_evidence_ids": ("ev-001",),
        "handoff_reason_code": None,
        "provider_name": "gemini",
        "model_name": "gemini-3.1-pro",
        "package_sha256": _sha256("6"),
    }
    defaults.update(overrides)
    return BrainCandidate(**defaults)


def make_final_decision(**overrides: object) -> FinalDecision:
    defaults: dict[str, object] = {
        "decision_id": uuid4(),
        "request_id": uuid4(),
        "verdict": GateVerdict.ALLOW,
        "reason": GateReason.PASSED_ALL_CHECKS,
        "reason_detail": None,
        "rendered_text": "KITAS investor requires IDR 10 billion paid-up capital [1].",
        "evaluated_at": datetime(2026, 8, 25, 12, 0, 6, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return FinalDecision(**defaults)


# ---------------------------------------------------------------------------
# Round-trip serialization — every new model
# ---------------------------------------------------------------------------

ALL_MODEL_BUILDERS = [
    ("CanonicalActor", make_actor),
    ("SurfaceContext", make_surface_context),
    ("CanonicalMessage", make_canonical_message),
    ("SurfaceProfile", lambda: CLIENT_WA_V1),
    ("EvidenceItem", make_evidence_item),
    ("PricingSnapshot", make_pricing_snapshot),
    ("GroundingBundle", make_grounding_bundle),
    ("BrainRequest", make_brain_request),
    ("Claim", make_claim),
    ("BrainCandidate", make_brain_candidate),
    ("FinalDecision", make_final_decision),
]


@pytest.mark.parametrize("name,builder", ALL_MODEL_BUILDERS, ids=[n for n, _ in ALL_MODEL_BUILDERS])
def test_round_trip_serialization(name: str, builder) -> None:
    instance = builder()
    model_cls = type(instance)
    dumped = instance.model_dump(mode="json")
    rehydrated = model_cls.model_validate(dumped)
    assert rehydrated == instance, f"{name} round-trip mismatch"
    # And through raw JSON text, not just python dict.
    as_json = instance.model_dump_json()
    rehydrated_from_text = model_cls.model_validate(json.loads(as_json))
    assert rehydrated_from_text == instance, f"{name} JSON-text round-trip mismatch"


def test_canonical_attachment_round_trip() -> None:
    attachment = CanonicalAttachment(
        attachment_id=uuid4(),
        kind=AttachmentKind.IMAGE,
        mime_type="image/jpeg",
        media_ref="media-store:abc123",
        filename="ktp.jpg",
        size_bytes=204_800,
        sha256=_sha256("7"),
        extracted_text_ref=None,
    )
    dumped = attachment.model_dump(mode="json")
    assert CanonicalAttachment.model_validate(dumped) == attachment


# ---------------------------------------------------------------------------
# Unknown-field rejection — every new model (extra="forbid")
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,builder", ALL_MODEL_BUILDERS, ids=[n for n, _ in ALL_MODEL_BUILDERS])
def test_unknown_field_rejected(name: str, builder) -> None:
    instance = builder()
    dumped = instance.model_dump(mode="json")
    dumped["totally_unexpected_field"] = "should never be accepted"
    with pytest.raises(ValidationError):
        type(instance).model_validate(dumped)


def test_canonical_attachment_rejects_unknown_field() -> None:
    dumped = {
        "attachment_id": str(uuid4()),
        "kind": "image",
        "mime_type": "image/jpeg",
        "media_ref": "media-store:abc123",
        "unexpected": "nope",
    }
    with pytest.raises(ValidationError):
        CanonicalAttachment.model_validate(dumped)


# ---------------------------------------------------------------------------
# schema_version pinning
# ---------------------------------------------------------------------------


def test_canonical_message_schema_version_defaults_to_1_0() -> None:
    msg = make_canonical_message()
    assert msg.schema_version == "1.0"


def test_canonical_message_rejects_other_schema_version() -> None:
    dumped = make_canonical_message().model_dump(mode="json")
    dumped["schema_version"] = "2.0"
    with pytest.raises(ValidationError):
        CanonicalMessage.model_validate(dumped)


def test_brain_candidate_requires_schema_version_1_0() -> None:
    candidate = make_brain_candidate()
    assert candidate.schema_version == "1.0"
    dumped = candidate.model_dump(mode="json")
    dumped["schema_version"] = "0.9"
    with pytest.raises(ValidationError):
        BrainCandidate.model_validate(dumped)


def test_brain_candidate_schema_version_is_required_no_default() -> None:
    dumped = make_brain_candidate().model_dump(mode="json")
    del dumped["schema_version"]
    with pytest.raises(ValidationError):
        BrainCandidate.model_validate(dumped)


# ---------------------------------------------------------------------------
# pydantic <-> JSON-Schema agreement (the drift-prevention test)
# ---------------------------------------------------------------------------


def test_pydantic_json_schema_matches_committed_file() -> None:
    generated = BrainCandidate.model_json_schema()
    assert SCHEMA_PATH.exists(), f"committed schema missing at {SCHEMA_PATH}"
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert generated == committed, (
        "schemas/client_brain_candidate_v1.json has drifted from "
        "BrainCandidate.model_json_schema() — regenerate the file from the model."
    )


def test_committed_schema_forbids_additional_properties_everywhere() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema.get("additionalProperties") is False
    for def_name, definition in schema.get("$defs", {}).items():
        assert definition.get("additionalProperties") is False, (
            f"$defs.{def_name} does not forbid additional properties"
        )


def test_committed_schema_is_draft_2020_12_and_strict_shape() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    required = set(schema["required"])
    assert required == {
        "schema_version",
        "disposition",
        "answer",
        "provider_name",
        "model_name",
        "package_sha256",
    }


# ---------------------------------------------------------------------------
# F2 profile invariants
# ---------------------------------------------------------------------------


def test_four_frozen_profiles_exist_with_exact_ids() -> None:
    assert {p.profile_id for p in FROZEN_PROFILES} == {
        "client-wa-v1",
        "client-ig-v1",
        "client-portal-v1",
        "client-kbli-v1",
    }
    assert len(FROZEN_PROFILES) == 4
    for profile_id in ("client-wa-v1", "client-ig-v1", "client-portal-v1", "client-kbli-v1"):
        assert get_profile(profile_id).profile_id == profile_id
        assert PROFILES_BY_ID[profile_id].profile_id == profile_id


def test_profiles_by_surface_covers_all_four_surfaces() -> None:
    assert set(PROFILES_BY_SURFACE.keys()) == set(ClientSurface)


@pytest.mark.parametrize(
    "profile", FROZEN_PROFILES, ids=[p.profile_id for p in FROZEN_PROFILES]
)
def test_no_profile_mentions_any_provider_name(profile: SurfaceProfile) -> None:
    """F2: a profile carries length/format/citation/history/deadlines/handoff-queue,
    NEVER a provider name. SurfaceProfile has no field that could hold one, but
    this test also guards against a provider name leaking into a *string value*
    (e.g. someone hand-editing renderer_name/handoff_queue/copy keys later).
    """
    blob = json.dumps(profile.model_dump(mode="json")).lower()
    forbidden_provider_names = (
        "gemini",
        "codex",
        "openai",
        "gpt-",
        "anthropic",
        "claude",
        "future_metered",
    )
    for needle in forbidden_provider_names:
        assert needle not in blob, f"{profile.profile_id} leaks provider name substring {needle!r}"


def test_surface_profile_has_no_provider_field_at_all() -> None:
    """Structural guarantee, not just a string scan: no field name on
    SurfaceProfile could hold a provider identifier, so
    CLIENT_BOT_PRIMARY_PROVIDER literally cannot alter transport behavior.

    ``provider_deadline_ms`` is intentionally NOT flagged: it is a timing
    budget (research capture §1.4 gives it verbatim), not a provider
    identity — it says how long any provider gets, never which one.
    """
    field_names = set(SurfaceProfile.model_fields.keys())
    banned_exact = {"provider", "provider_name", "brain_provider", "llm_provider", "model_name"}
    assert not (field_names & banned_exact), (
        f"SurfaceProfile has a provider-identity field: {field_names & banned_exact}"
    )
    for needle in ("brain", "llm", "gemini", "codex"):
        assert not any(needle in f for f in field_names), (
            f"SurfaceProfile has a field name containing {needle!r}: {field_names}"
        )


def test_kbli_widget_is_domain_restricted_to_kbli_only() -> None:
    assert CLIENT_KBLI_V1.allowed_domains == frozenset({"kbli"})
    assert CLIENT_KBLI_V1.citation_policy == CitationPolicy.ALL_FACTUAL


def test_other_three_profiles_include_kbli_plus_regulated_domains() -> None:
    expected = frozenset({"immigration", "company", "tax", "property", "kbli"})
    for profile in (CLIENT_WA_V1, CLIENT_IG_V1, CLIENT_PORTAL_V1):
        assert profile.allowed_domains == expected


def test_portal_profile_requires_authentication() -> None:
    assert CLIENT_PORTAL_V1.authentication_required is True


def test_non_portal_profiles_do_not_require_authentication() -> None:
    for profile in (CLIENT_WA_V1, CLIENT_IG_V1, CLIENT_KBLI_V1):
        assert profile.authentication_required is False


def test_all_profiles_are_final_content_atomic() -> None:
    for profile in FROZEN_PROFILES:
        assert profile.final_content_atomic is True


# ---------------------------------------------------------------------------
# CanonicalMessage F1/F2 invariants
# ---------------------------------------------------------------------------


def test_canonical_message_requires_text_or_attachment() -> None:
    with pytest.raises(ValidationError):
        make_canonical_message(text="", attachments=())


def test_canonical_message_allows_attachment_only() -> None:
    attachment = CanonicalAttachment(
        attachment_id=uuid4(),
        kind=AttachmentKind.IMAGE,
        mime_type="image/jpeg",
        media_ref="media-store:abc123",
    )
    msg = make_canonical_message(text="", attachments=(attachment,), kind=MessageKind.IMAGE)
    assert msg.text == ""
    assert len(msg.attachments) == 1


def test_portal_case_id_rejected_off_portal_surface() -> None:
    with pytest.raises(ValidationError):
        make_canonical_message(
            surface=ClientSurface.WHATSAPP,
            surface_context=make_surface_context(portal_case_id=uuid4()),
        )


def test_portal_case_id_allowed_on_portal_surface() -> None:
    msg = make_canonical_message(
        surface=ClientSurface.PORTAL,
        surface_context=make_surface_context(
            portal_case_id=uuid4(), authenticated_session_id=uuid4()
        ),
        actor=make_actor(authenticated=True),
    )
    assert msg.surface_context.portal_case_id is not None


def test_kbli_code_rejected_off_kbli_surface() -> None:
    with pytest.raises(ValidationError):
        make_canonical_message(
            surface=ClientSurface.WHATSAPP,
            surface_context=make_surface_context(kbli_code="47710"),
        )


def test_kbli_code_allowed_on_kbli_widget_surface() -> None:
    msg = make_canonical_message(
        surface=ClientSurface.KBLI_WIDGET,
        surface_context=make_surface_context(kbli_code="47710"),
    )
    assert msg.surface_context.kbli_code == "47710"


def test_portal_surface_requires_authenticated_actor() -> None:
    with pytest.raises(ValidationError):
        make_canonical_message(
            surface=ClientSurface.PORTAL,
            actor=make_actor(authenticated=False),
            surface_context=make_surface_context(authenticated_session_id=uuid4()),
        )


def test_portal_surface_requires_authenticated_session_id() -> None:
    with pytest.raises(ValidationError):
        make_canonical_message(
            surface=ClientSurface.PORTAL,
            actor=make_actor(authenticated=True),
            surface_context=make_surface_context(authenticated_session_id=None),
        )


def test_subject_token_must_be_hmac_shaped_not_a_raw_phone_number() -> None:
    """F1 hard invariant encoded in the type: a raw phone number cannot
    satisfy the 64-hex-char pattern subject_token requires."""
    with pytest.raises(ValidationError):
        make_actor(subject_token="+6281234567890")


def test_media_ref_rejects_url_shaped_values() -> None:
    """F1 hard invariant: never a signed media URL, only an opaque reference."""
    with pytest.raises(ValidationError):
        CanonicalAttachment(
            attachment_id=uuid4(),
            kind=AttachmentKind.IMAGE,
            mime_type="image/jpeg",
            media_ref="https://cdn.example.com/signed/abc?token=xyz",
        )


def test_media_ref_accepts_opaque_reference() -> None:
    attachment = CanonicalAttachment(
        attachment_id=uuid4(),
        kind=AttachmentKind.IMAGE,
        mime_type="image/jpeg",
        media_ref="media-store:abc123",
    )
    assert attachment.media_ref == "media-store:abc123"


# ---------------------------------------------------------------------------
# GateVerdict / GateReason / FinalDecision
# ---------------------------------------------------------------------------


def test_gate_verdict_has_exactly_six_frozen_members() -> None:
    assert {v.value for v in GateVerdict} == {
        "allow",
        "abstain",
        "handoff",
        "text_defect",
        "policy_blocked",
        "drop",
    }
    assert len(GateVerdict) == 6


def test_final_decision_allow_requires_rendered_text() -> None:
    with pytest.raises(ValidationError):
        make_final_decision(verdict=GateVerdict.ALLOW, rendered_text=None)


def test_final_decision_non_allow_forbids_rendered_text() -> None:
    with pytest.raises(ValidationError):
        make_final_decision(
            verdict=GateVerdict.ABSTAIN,
            reason=GateReason.EVIDENCE_SEMANTIC_SUPPORT_BELOW_THRESHOLD,
            rendered_text="should not be here",
        )


def test_final_decision_abstain_without_rendered_text_is_valid() -> None:
    decision = make_final_decision(
        verdict=GateVerdict.ABSTAIN,
        reason=GateReason.EVIDENCE_SEMANTIC_SUPPORT_BELOW_THRESHOLD,
        rendered_text=None,
    )
    assert decision.rendered_text is None
    assert decision.is_retryable is False


def test_only_text_defect_is_retryable() -> None:
    for verdict in GateVerdict:
        reason = (
            GateReason.PASSED_ALL_CHECKS
            if verdict == GateVerdict.ALLOW
            else GateReason.LENGTH_EXCEEDS_HARD_LIMIT
        )
        decision = make_final_decision(
            verdict=verdict,
            reason=reason,
            rendered_text="x" if verdict == GateVerdict.ALLOW else None,
        )
        assert decision.is_retryable == (verdict == GateVerdict.TEXT_DEFECT)


# ---------------------------------------------------------------------------
# BrainCandidate strictness (F3 machine-readable contract)
# ---------------------------------------------------------------------------


def test_brain_candidate_rejects_bad_provider_name() -> None:
    with pytest.raises(ValidationError):
        make_brain_candidate(provider_name="gemini; DROP TABLE clients;")


def test_brain_candidate_rejects_bad_package_sha256() -> None:
    with pytest.raises(ValidationError):
        make_brain_candidate(package_sha256="not-a-sha")


def test_claim_evidence_ids_must_be_simple_identifiers() -> None:
    with pytest.raises(ValidationError):
        make_claim(evidence_ids=("../../etc/passwd",))
