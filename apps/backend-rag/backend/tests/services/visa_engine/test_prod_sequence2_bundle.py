"""Golden gates for the forward-only production RulePack sequence 2."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.services.visa_engine import evaluate_path
from backend.services.visa_engine.ast import (
    FactSnapshot,
    KnownFact,
    evaluate_condition,
)
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    validate_activation,
    verify_rule_pack,
)
from backend.services.visa_engine.compiler import build_compiled_pack, compile_rule_pack
from backend.services.visa_engine.enums import DecisionState, FactPath, TruthValue
from backend.services.visa_engine.evaluator import build_decision_identity, evaluate
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader

PACK_PATH = (
    Path(__file__).resolve().parents[3]
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
    / "rulepack-prod-002.signed.json"
)
SOURCE_PATH = PACK_PATH.with_name("rulepack-prod-002.source.json")
SEQUENCE_1_PAYLOAD_SHA256 = "47a97c32045c1f58798c8661473c265decbab5d8427e0e606406a29402db5fda"
SEQUENCE_2_PAYLOAD_SHA256 = "d51ba2b18230720fbc62e79b8944df46515fb732c962c73c503899edddd9cb31"
PROD_TRUST_STORE_JSON = json.dumps(
    [
        {
            "kid": "prod-2026-07-1",
            "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",  # pragma: allowlist secret - pinned Ed25519 public verification key, not a credential
            "environment": "PRODUCTION",
            "valid_from": "2026-07-19T00:00:00Z",
            "valid_to": None,
            "revoked_at": None,
        }
    ]
)


@pytest.fixture
def verified_pack(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)
    raw = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    return verify_rule_pack(
        raw,
        trust_store=StaticTrustStore.from_env(),
        observed_at=datetime(2026, 8, 6, 8, 0, tzinfo=timezone.utc),
    )


def test_sequence_two_signature_compile_and_hash_chain(verified_pack) -> None:
    payload = verified_pack.pack.payload
    raw_signed = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    raw_source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))

    assert verified_pack.payload_sha256.hex() == SEQUENCE_2_PAYLOAD_SHA256
    assert canonicalize_json(raw_signed["payload"]) == canonicalize_json(raw_source)
    assert payload.sequence == 2
    assert payload.previous_payload_sha256 == SEQUENCE_1_PAYLOAD_SHA256
    assert verified_pack.pack.protected.kid == "prod-2026-07-1"
    assert compile_rule_pack(verified_pack.pack).ok

    validate_activation(
        verified_pack,
        current_sequence=1,
        current_payload_sha256=bytes.fromhex(SEQUENCE_1_PAYLOAD_SHA256),
        environment="PRODUCTION",
        engine_version="1.0.0",
    )


def test_sequence_two_has_no_unsigned_freshness_fallback(verified_pack) -> None:
    source_records = verified_pack.pack.payload.source_records

    assert len(source_records) == 28
    assert all(record.freshness_policy is not None for record in source_records)
    assert {
        record.freshness_policy.max_age_seconds
        for record in source_records
        if record.freshness_policy is not None
    } == {604_800, 31_536_000}


def test_sequence_two_extension_unknowns_are_explicit_and_neutral(verified_pack) -> None:
    expected_unknown = {
        "E23U",
        "E23V",
        "E28B",
        "E28C",
        "E28D",
        "E28F",
        "E30",
        "E30A",
        "E30B",
        "E30E",
        "E30F",
        "E33",
        "E33A",
        "E33B",
        "E33C",
        "E33E",
    }
    unknown = {
        product.product_code
        for product in verified_pack.pack.payload.products
        if product.extension_policy.status == "UNKNOWN"
    }

    assert unknown == expected_unknown
    for product in verified_pack.pack.payload.products:
        policy = product.extension_policy
        assert policy.status in {"VERIFIED", "UNKNOWN"}
        if policy.status == "UNKNOWN":
            assert policy.reason_code == "EXTENSION_POLICY_NOT_VERIFIED"
            assert policy.allowed is False
            assert policy.maximum_extensions == 0
            assert policy.days_per_extension is None


def test_sequence_two_current_sources_preserve_conclusive_supported_persona(
    verified_pack,
) -> None:
    """A signed/current pack must not globally abstain a supported persona."""

    observed_at = datetime(2026, 8, 6, 8, 0, tzinfo=timezone.utc)
    compiled = build_compiled_pack(verified_pack.pack)
    persona = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "07_retiree.json")

    raw = evaluate(
        persona.facts,
        compiled,
        effective_at=observed_at,
        observed_at=observed_at,
        identity_provider=lambda facts, rule_pack_ref, effective_at, _environment: (
            build_decision_identity(
                facts,
                rule_pack_ref,
                effective_at,
                fingerprint_key=b"sequence-2-golden-vector-key-32b",
                fingerprint_key_id="sequence-2-golden-vector",
            )
        ),
    )
    decisive_held = evaluate_path._apply_decisive_source_authority_hold(raw, compiled)
    final = evaluate_path._apply_safety_critical_source_hold(decisive_held, compiled)

    assert raw.state is DecisionState.SUPPORTED_CANDIDATES
    assert final.state is DecisionState.SUPPORTED_CANDIDATES
    assert not any("SOURCE_STALE" in reason.code for reason in final.review_reasons)


@pytest.mark.parametrize(
    ("nationality", "expected_truth"),
    [
        ("AF", TruthValue.TRUE),
        ("IL", TruthValue.TRUE),
        ("KP", TruthValue.TRUE),
        ("LR", TruthValue.TRUE),
        ("NG", TruthValue.TRUE),
        ("SO", TruthValue.TRUE),
        ("GN", TruthValue.FALSE),
        ("CM", TruthValue.FALSE),
        ("NE", TruthValue.FALSE),
    ],
)
def test_sequence_two_calling_visa_country_golden_vectors(
    verified_pack,
    nationality: str,
    expected_truth: TruthValue,
) -> None:
    compiled = build_compiled_pack(verified_pack.pack)
    rule = next(rule for rule in compiled.rules if rule.rule_id == "review.calling-visa")
    facts = FactSnapshot(
        values={FactPath.PERSON_NATIONALITIES: KnownFact(frozenset({nationality}))}
    )

    assert evaluate_condition(rule.when, facts).truth is expected_truth
