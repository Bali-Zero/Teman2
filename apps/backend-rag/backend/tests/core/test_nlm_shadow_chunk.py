"""Tests for NLMShadowChunk Pydantic model (Sprint 2 Shadow Graphing)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.core.nlm_shadow_chunk import NLMShadowChunk


def test_minimal_construction():
    c = NLMShadowChunk(
        chunk_id="nlm_shadow_NB-3_20260425_001",
        claim_text="PT PMA minimum capital is IDR 10 billion under PP 28/2025.",
        nb_id="933509f9-1561-403d-bd44-4a7a67a36df2",
        nb_label="company",
        extraction_run_id="run-001",
    )
    assert c.source == "nlm_shadow"
    assert c.ttl_hours == 72
    assert c.deepseek_validated is False
    assert c.deepseek_confidence == 0.0


def test_to_qdrant_payload_flat():
    c = NLMShadowChunk(
        chunk_id="x",
        claim_text="A claim with enough length.",
        nb_id="nb-uuid",
        nb_label="tax",
        extraction_run_id="r1",
        deepseek_validated=True,
        deepseek_confidence=0.85,
        deepseek_notes="ok",
    )
    payload = c.to_qdrant_payload()
    # Flat — no nested dicts
    for v in payload.values():
        assert not isinstance(v, dict)
    assert payload["source"] == "nlm_shadow"
    assert isinstance(payload["extracted_at"], str)
    assert payload["deepseek_confidence"] == 0.85


def test_round_trip_qdrant_payload():
    original = NLMShadowChunk(
        chunk_id="rt",
        claim_text="A round-trip test claim.",
        nb_id="nb-rt",
        nb_label="immigration",
        extraction_run_id="r-rt",
        nlm_source_id="src-rt",
        deepseek_validated=True,
        deepseek_confidence=0.7,
    )
    payload = original.to_qdrant_payload()
    rehydrated = NLMShadowChunk.from_qdrant_payload(payload)
    assert rehydrated.chunk_id == original.chunk_id
    assert rehydrated.claim_text == original.claim_text
    assert rehydrated.nlm_source_id == "src-rt"
    assert rehydrated.deepseek_validated is True


def test_empty_claim_text_rejected():
    with pytest.raises(ValidationError):
        NLMShadowChunk(
            chunk_id="x",
            claim_text="   ",  # blank after strip
            nb_id="nb",
            nb_label="tax",
            extraction_run_id="r",
        )


def test_short_claim_text_rejected():
    with pytest.raises(ValidationError):
        NLMShadowChunk(
            chunk_id="x",
            claim_text="short",  # < 10 chars
            nb_id="nb",
            nb_label="tax",
            extraction_run_id="r",
        )


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        NLMShadowChunk(
            chunk_id="x",
            claim_text="A valid claim text.",
            nb_id="nb",
            nb_label="tax",
            extraction_run_id="r",
            deepseek_confidence=1.5,  # > 1.0
        )


def test_empty_string_optionals_become_none_on_rehydrate():
    payload = {
        "chunk_id": "x",
        "claim_text": "Round-trip empty optionals test.",
        "nb_id": "nb",
        "nb_label": "tax",
        "extraction_run_id": "r",
        "extracted_at": datetime.now(tz=timezone.utc).isoformat(),
        "deepseek_validated": False,
        "deepseek_confidence": 0.0,
        "deepseek_notes": "",          # empty string in storage
        "nlm_source_id": "",           # empty string in storage
        "source": "nlm_shadow",
        "ttl_hours": 72,
    }
    rehydrated = NLMShadowChunk.from_qdrant_payload(payload)
    assert rehydrated.deepseek_notes is None
    assert rehydrated.nlm_source_id is None
