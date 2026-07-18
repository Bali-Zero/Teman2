"""Shared plain-dict builders for visa_engine tests.

Not collected as tests (no ``test_`` prefix / no test functions). Every
builder returns a plain JSON-safe ``dict`` — the same shape a signer/author
would hand the engine on the wire — so both the Pydantic models
(``backend.services.visa_engine.models``) and the packaged JSON Schema
files can validate the *same* object in coherence tests.
"""

from __future__ import annotations

import uuid
from typing import Any

from backend.services.visa_engine.fact_registry import ApplicantFactPath

UTC_NOW = "2026-07-18T00:00:00Z"

ALL_APPLICANT_FACT_PATHS: tuple[str, ...] = tuple(path.value for path in ApplicantFactPath)


def new_uuid() -> str:
    return str(uuid.uuid4())


def sha256_hex(seed: str = "a") -> str:
    return (seed * 64)[:64]


def time_range(*, start: str = UTC_NOW, end: str | None = None) -> dict[str, Any]:
    return {"from": start, "to": end}


def source_record(*, source_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "source_record_id": source_id or new_uuid(),
        "source_key": "test-source",
        "version": 1,
        "authority_type": "PRIMARY_LAW",
        "status": "VERIFIED",
        "jurisdiction": "ID",
        "title": "Test Source",
        "publisher": "Test Publisher",
        "canonical_url": "https://example.com/source",
        "language": "en",
        "document_number": None,
        "locators": [],
        "content_sha256": sha256_hex("a"),
        "legal_period": time_range(),
        "recorded_period": time_range(),
        "retrieved_at": UTC_NOW,
        "verified_at": UTC_NOW,
        "verified_by": "test-verifier",
        "supersedes_source_record_id": None,
    }
    record.update(overrides)
    return record


def product(*, source_id: str, product_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    prod: dict[str, Any] = {
        "product_version_id": product_id or new_uuid(),
        "product_code": "C1",
        "legacy_codes": [],
        "legacy_slugs": [],
        "names": {"id": "Visa Turis", "en": "Tourist Visa"},
        "category": "SHORT_STAY",
        "status": "ACTIVE",
        "valid_period": time_range(),
        "covered_purposes": ["TOURISM"],
        "prohibited_activities": [],
        "sponsor_types": ["NONE"],
        "entry_policy": {"entry_count": "SINGLE"},
        "stay_policy": {"kind": "FIXED_DAYS", "minimum_days": 1, "maximum_days": 30},
        "extension_policy": {"allowed": True, "maximum_extensions": 1, "days_per_extension": 30},
        "clock_policy": {"available": False, "anchor": "NOT_APPLICABLE", "checkpoints": []},
        "pricing_key": {"category": "single_entry_visas", "item_key": "c1_tourist"},
        "source_refs": [source_id],
        "public_catalog": True,
    }
    prod.update(overrides)
    return prod


def rule(
    *,
    rule_id: str,
    stage: str,
    scope: str,
    when: dict[str, Any],
    effect: dict[str, Any],
    source_id: str,
    required_facts: list[str] | None = None,
    priority: int = 100,
    on_unknown: str = "NEEDS_INPUT",
    product_version_ids: list[str] | None = None,
    safety_critical: bool = False,
    **overrides: Any,
) -> dict[str, Any]:
    r: dict[str, Any] = {
        "rule_id": rule_id,
        "stage": stage,
        "scope": scope,
        "priority": priority,
        "valid_period": time_range(),
        "when": when,
        "effect": effect,
        "on_unknown": on_unknown,
        "required_facts": required_facts or [],
        "source_refs": [source_id],
        "explanation_key": f"{rule_id}-explanation",
        "safety_critical": safety_critical,
    }
    if scope == "PRODUCTS":
        r["product_version_ids"] = product_version_ids or []
    r.update(overrides)
    return r


def rule_pack_payload(
    *,
    rules: list[dict[str, Any]],
    products: list[dict[str, Any]],
    source_records: list[dict[str, Any]],
    sequence: int = 1,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_pack_id": new_uuid(),
        "sequence": sequence,
        "version": "1.0.0",
        "environment": "TEST",
        "jurisdiction": "ID",
        "decision_domain": "IMMIGRATION_VISA",
        "engine_contract_version": "1.0.0",
        "engine_min_version": "1.0.0",
        "engine_max_version": "1.0.0",
        "valid_period": time_range(),
        "created_at": UTC_NOW,
        "created_by": "test-author",
        "previous_payload_sha256": None if sequence == 1 else sha256_hex("d"),
        "rollback_of_payload_sha256": None,
        "hit_policy": {
            "hard_filter": "COLLECT_ALL",
            "eligibility": "COVER_ALL_DECLARED_PURPOSES",
            "human_review": "COLLECT_ALL",
            "ranking": "SUM_TRUE_INTEGER_WEIGHTS",
        },
        "source_records": source_records,
        "products": products,
        "rules": rules,
    }
    payload.update(overrides)
    return payload


def rule_pack_envelope(payload: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "canonicalization": "RFC8785",
        "protected": {
            "domain": "balizero.visa-rulepack.v1",
            "alg": "Ed25519",
            "kid": "test-key-1",
            "signed_at": UTC_NOW,
            "schema_version": "1.0.0",
            "environment": payload["environment"],
        },
        "payload": payload,
        "payload_sha256": sha256_hex("b"),
        "signature": "c" * 86,
    }
    envelope.update(overrides)
    return envelope


def minimal_valid_envelope() -> dict[str, Any]:
    """One GLOBAL hard-filter rule, one PRODUCTS eligibility rule, one GLOBAL
    ranking rule, one product, one source record — small but exercises every
    stage/effect pairing."""

    source_id = new_uuid()
    product_id = new_uuid()
    src = source_record(source_id=source_id)
    prod = product(product_id=product_id, source_id=source_id)

    hard_filter = rule(
        rule_id="hf-overstay",
        stage="HARD_FILTER",
        scope="GLOBAL",
        when={"op": "gt", "fact": "immigration.overstay_days", "value": 60},
        effect={"type": "EXCLUDE", "reason_code": "OVERSTAY_TOO_LONG"},
        source_id=source_id,
        required_facts=["immigration.overstay_days"],
        safety_critical=True,
    )
    eligibility = rule(
        rule_id="el-tourism",
        stage="ELIGIBILITY",
        scope="PRODUCTS",
        product_version_ids=[product_id],
        when={
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
                {"op": "lte", "fact": "intent.stay_days", "value": 30},
            ],
        },
        effect={
            "type": "SUPPORT",
            "reason_code": "TOURISM_SUPPORTED",
            "covered_purposes": ["TOURISM"],
        },
        source_id=source_id,
        required_facts=["intent.purposes", "intent.stay_days"],
    )
    ranking = rule(
        rule_id="rank-budget",
        stage="RANKING",
        scope="GLOBAL",
        when={"op": "known", "fact": "commercial.wants_quote"},
        effect={"type": "ADD_SCORE", "reason_code": "WANTS_QUOTE_BOOST", "points": 5},
        source_id=source_id,
        required_facts=["commercial.wants_quote"],
        on_unknown="NO_EFFECT",
    )

    payload = rule_pack_payload(
        rules=[hard_filter, eligibility, ranking], products=[prod], source_records=[src]
    )
    return rule_pack_envelope(payload)


_DEFAULT_STAGE_EFFECTS: dict[str, dict[str, Any]] = {
    "HARD_FILTER": {"type": "EXCLUDE", "reason_code": "TEST_EXCLUDE"},
    "ELIGIBILITY": {
        "type": "SUPPORT",
        "reason_code": "TEST_SUPPORT",
        "covered_purposes": ["TOURISM"],
    },
    "HUMAN_REVIEW": {"type": "REQUIRE_REVIEW", "reason_code": "TEST_REVIEW"},
    "RANKING": {"type": "ADD_SCORE", "reason_code": "TEST_SCORE", "points": 1},
}


def single_rule_envelope(
    *,
    when: dict[str, Any],
    stage: str = "HARD_FILTER",
    effect: dict[str, Any] | None = None,
    required_facts: list[str] | None = None,
    scope: str = "GLOBAL",
    product_version_ids: list[str] | None = None,
    rule_overrides: dict[str, Any] | None = None,
    environment: str = "TEST",
    protected_environment: str | None = None,
    extra_products: list[dict[str, Any]] | None = None,
    extra_source_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A minimal one-rule envelope for compiler unit tests that need full
    control over a single rule's ``when``/``stage``/``effect``/
    ``required_facts`` without the other stage-pairing constraints
    ``minimal_valid_envelope()``'s 3-rule scaffold carries.

    ``required_facts`` defaults to ``None`` -> ``[]`` (via the ``rule()``
    builder) — callers testing anything other than F8 (required_facts ==
    collect_fact_paths(when)) MUST pass the correct set explicitly, or the
    F8 check will reject the pack for an unrelated reason.
    """

    source_id = new_uuid()
    product_id = new_uuid()
    src = source_record(source_id=source_id)
    prod = product(product_id=product_id, source_id=source_id)

    r = rule(
        rule_id="r-under-test",
        stage=stage,
        scope=scope,
        when=when,
        effect=effect or _DEFAULT_STAGE_EFFECTS[stage],
        source_id=source_id,
        required_facts=required_facts,
        product_version_ids=product_version_ids if scope == "PRODUCTS" else None,
        **(rule_overrides or {}),
    )

    payload = rule_pack_payload(
        rules=[r],
        products=[prod, *(extra_products or [])],
        source_records=[src, *(extra_source_records or [])],
        environment=environment,
    )
    envelope = rule_pack_envelope(payload)
    if protected_environment is not None:
        envelope["protected"]["environment"] = protected_environment
    return envelope


_UNKNOWN_FACT: dict[str, Any] = {"status": "UNKNOWN", "reason": "NOT_ASKED"}


def applicant_facts_dict(**known_overrides: Any) -> dict[str, Any]:
    """All 35 fact paths set to ``UNKNOWN{NOT_ASKED}``, except ``known_overrides``
    (keys are dotted fact paths, values are already-shaped ``{"status": "KNOWN", ...}``
    dicts)."""

    facts: dict[str, Any] = {path: dict(_UNKNOWN_FACT) for path in ALL_APPLICANT_FACT_PATHS}
    facts.update(known_overrides)
    return facts


def applicant_facts_envelope(**known_overrides: Any) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "assessment_id": new_uuid(),
        "collected_at": UTC_NOW,
        "facts": applicant_facts_dict(**known_overrides),
    }
