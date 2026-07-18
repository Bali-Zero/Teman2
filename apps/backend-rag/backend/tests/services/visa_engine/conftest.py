"""Shared fixtures for the ``visa_engine`` PR1 test suite.

Every fixture builds real ``models.py`` objects (never raw dicts left
unvalidated) so a test that wants a "guilt" case constructs an otherwise
fully-valid pack and mutates exactly the one thing under test.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import pytest

from backend.services.visa_engine import models as M

GOLD_EFFECTIVE_AT = datetime(2026, 7, 17, 0, 0, 0, tzinfo=timezone.utc)

_OPEN_PERIOD = {"from": GOLD_EFFECTIVE_AT, "to": None}

#: Every ``HitPolicyDeclaration`` field is a JSON Schema ``const`` with no
#: Python default as of the PR1 hardening round (Codex finding 2) — every
#: builder that used to rely on ``hit_policy={}`` now spells this out.
_HIT_POLICY = {
    "hard_filter": "COLLECT_ALL",
    "eligibility": "COVER_ALL_DECLARED_PURPOSES",
    "human_review": "COLLECT_ALL",
    "ranking": "SUM_TRUE_INTEGER_WEIGHTS",
}


def make_source_record(
    *,
    source_record_id: uuid.UUID | None = None,
    source_key: str = "kepmen.2025.gr01",
) -> M.SourceRecord:
    return M.SourceRecord(
        source_record_id=source_record_id or uuid.uuid4(),
        source_key=source_key,
        version=1,
        authority_type="PRIMARY_LAW",
        status="VERIFIED",
        jurisdiction="ID",
        title="Kepmen M.IP-08.GR.01.01/2025",
        publisher="Kemenimipas",
        canonical_url="https://jdih.imipas.go.id/example",
        language="id",
        document_number=None,
        locators=[],
        content_sha256="a" * 64,
        legal_period=_OPEN_PERIOD,
        recorded_period=_OPEN_PERIOD,
        retrieved_at=GOLD_EFFECTIVE_AT,
        verified_at=GOLD_EFFECTIVE_AT,
        verified_by="analyst.a",
        supersedes_source_record_id=None,
    )


def make_product(
    *,
    product_version_id: uuid.UUID,
    source_refs: Sequence[uuid.UUID],
    product_code: str = "C1",
    covered_purposes: Sequence[str] = ("TOURISM",),
) -> M.VisaProductVersion:
    return M.VisaProductVersion(
        product_version_id=product_version_id,
        product_code=product_code,
        legacy_codes=[],
        legacy_slugs=[],
        names={"id": f"Visa {product_code}", "en": f"{product_code} product"},
        category="SHORT_STAY",
        status="ACTIVE",
        valid_period=_OPEN_PERIOD,
        covered_purposes=list(covered_purposes),
        prohibited_activities=[],
        sponsor_types=["NONE"],
        entry_policy={"entry_count": "SINGLE"},
        stay_policy={"kind": "FIXED_DAYS", "minimum_days": 30, "maximum_days": 30},
        extension_policy={"allowed": True, "maximum_extensions": 1, "days_per_extension": 30},
        clock_policy={"available": True, "anchor": "ENTRY_DATE", "checkpoints": []},
        pricing_key={"category": "visa", "item_key": f"{product_code.lower()}_tourism"},
        source_refs=list(source_refs),
        public_catalog=True,
    )


def make_support_rule(
    *,
    rule_id: str,
    product_version_ids: Sequence[uuid.UUID],
    source_refs: Sequence[uuid.UUID],
    covered_purposes: Sequence[str] = ("TOURISM",),
    when: dict | None = None,
    required_facts: Sequence[str] = ("intent.purposes",),
) -> M.Rule:
    return M.Rule(
        rule_id=rule_id,
        stage="ELIGIBILITY",
        scope="PRODUCTS",
        product_version_ids=list(product_version_ids),
        priority=100,
        valid_period=_OPEN_PERIOD,
        when=when
        or {"op": "intersects", "fact": "intent.purposes", "values": list(covered_purposes)},
        effect={
            "type": "SUPPORT",
            "reason_code": "PURPOSE_SUPPORTED",
            "covered_purposes": list(covered_purposes),
        },
        on_unknown="NEEDS_INPUT",
        required_facts=list(required_facts),
        source_refs=list(source_refs),
        explanation_key="explain.support",
        safety_critical=False,
    )


def make_rule_pack_payload(
    *,
    rules: Sequence[M.Rule],
    products: Sequence[M.VisaProductVersion],
    source_records: Sequence[M.SourceRecord],
    sequence: int = 1,
    environment: str = "TEST",
) -> M.RulePackPayload:
    return M.RulePackPayload(
        rule_pack_id=uuid.uuid4(),
        sequence=sequence,
        version="1.0.0",
        environment=environment,
        jurisdiction="ID",
        decision_domain="IMMIGRATION_VISA",
        engine_contract_version="1.0.0",
        engine_min_version="1.0.0",
        engine_max_version="1.0.0",
        valid_period=_OPEN_PERIOD,
        created_at=GOLD_EFFECTIVE_AT,
        created_by="pipeline.compiler",
        previous_payload_sha256=None if sequence == 1 else "d" * 64,
        rollback_of_payload_sha256=None,
        hit_policy=_HIT_POLICY,
        source_records=list(source_records),
        products=list(products),
        rules=list(rules),
    )


def make_rule_pack(payload: M.RulePackPayload, *, environment: str = "TEST") -> M.RulePack:
    return M.RulePack(
        canonicalization="RFC8785",
        protected={
            "domain": "balizero.visa-rulepack.v1",
            "alg": "Ed25519",
            "kid": "key-2026-07",
            "signed_at": GOLD_EFFECTIVE_AT,
            "schema_version": "1.0.0",
            "environment": environment,
        },
        payload=payload,
        payload_sha256="b" * 64,
        signature="c" * 86,
    )


def make_applicant_facts(*, assessment_id: uuid.UUID | None = None) -> M.ApplicantFacts:
    """Every one of the 35 fact paths as an ``UnknownFact`` (the simplest
    valid ``facts`` payload — proves the "all keys required, additionalProperties:
    false" shape without needing 35 different ``Known*`` builders).
    """
    unknown = {"status": "UNKNOWN", "reason": "NOT_ASKED"}
    facts = {
        "person.birth_date": unknown,
        "person.nationalities": unknown,
        "person.marital_status": unknown,
        "immigration.currently_in_indonesia": unknown,
        "immigration.current_status_code": unknown,
        "immigration.current_status_expiry": unknown,
        "immigration.last_entry_date": unknown,
        "immigration.overstay_days": unknown,
        "immigration.violation_history": unknown,
        "intent.purposes": unknown,
        "intent.stay_days": unknown,
        "intent.desired_entry_date": unknown,
        "intent.entry_pattern": unknown,
        "intent.requested_product_code": unknown,
        "work.employer_country_code": unknown,
        "work.employer_is_indonesian_entity": unknown,
        "work.serves_indonesian_clients": unknown,
        "work.indonesia_source_compensation": unknown,
        "work.indonesian_work_sponsor_confirmed": unknown,
        "investment.pt_pma_committed": unknown,
        "investment.investment_capital_idr": unknown,
        "investment.paid_up_capital_idr": unknown,
        "investment.proposed_role": unknown,
        "family.relation_to_sponsor": unknown,
        "family.sponsor_nationalities": unknown,
        "family.sponsor_status_code": unknown,
        "family.marriage_registered": unknown,
        "family.sponsor_confirmed": unknown,
        "study.level": unknown,
        "study.admission_confirmed": unknown,
        "study.sponsor_confirmed": unknown,
        "process.application_channel": unknown,
        "process.wants_onshore_conversion": unknown,
        "commercial.service_fee_budget_idr": unknown,
        "commercial.wants_quote": unknown,
    }
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=assessment_id or uuid.uuid4(),
        collected_at=GOLD_EFFECTIVE_AT,
        facts=facts,
    )


def make_fingerprint(*, digest: str = "f" * 64) -> M.Fingerprint:
    return M.Fingerprint(algorithm="HMAC-SHA256", key_id="fingerprint.key.1", digest=digest)


def make_rule_pack_ref(*, rule_pack_id: uuid.UUID | None = None) -> M.RulePackRef:
    return M.RulePackRef(
        rule_pack_id=rule_pack_id or uuid.uuid4(),
        sequence=1,
        version="1.0.0",
        payload_sha256="a" * 64,
    )


def make_reason(*, code: str = "SOME_REASON") -> M.Reason:
    return M.Reason(code=code, rule_ids=["rule.some"], source_refs=[uuid.uuid4()])


def make_price_quote(
    *,
    product_version_id: uuid.UUID,
    status: str = "AVAILABLE",
) -> M.PriceQuote:
    if status == "AVAILABLE":
        return M.PriceQuote(
            quote_id=uuid.uuid4(),
            product_version_id=product_version_id,
            product_code="C1",
            status=status,
            currency="IDR",
            amount=1_500_000,
            pricing_key={"category": "visa", "item_key": "c1_tourism"},
            catalog_version="2026.07",
            catalog_sha256="a" * 64,
            row_sha256="b" * 64,
            quoted_at=GOLD_EFFECTIVE_AT,
            valid_until=None,
            reason_code="PRICE_FOUND",
        )
    return M.PriceQuote(
        quote_id=uuid.uuid4(),
        product_version_id=product_version_id,
        product_code="C1",
        status=status,
        currency="IDR",
        amount=None,
        pricing_key={"category": "visa", "item_key": "c1_tourism"},
        catalog_version=None,
        catalog_sha256=None,
        row_sha256=None,
        quoted_at=GOLD_EFFECTIVE_AT,
        valid_until=None,
        reason_code="PRICE_UNAVAILABLE",
    )


def make_candidate(*, product_version_id: uuid.UUID) -> M.Candidate:
    return M.Candidate(
        rank=1,
        product_version_id=product_version_id,
        product_code="C1",
        score=10,
        covered_purposes=["TOURISM"],
        support_rule_ids=["rule.c1.tourism.support"],
        source_refs=[uuid.uuid4()],
        reason_codes=["PURPOSE_SUPPORTED"],
    )


def make_supported_candidates_decision(*, product_version_id: uuid.UUID) -> M.Decision:
    """A ``state=SUPPORTED_CANDIDATES`` Decision — every field the state's
    ``allOf`` conditional requires, populated.
    """
    return M.Decision(
        schema_version="1.0.0",
        decision_id=uuid.uuid4(),
        public_id="a" * 16,
        state="SUPPORTED_CANDIDATES",
        effective_at=GOLD_EFFECTIVE_AT,
        observed_at=GOLD_EFFECTIVE_AT,
        evaluated_at=GOLD_EFFECTIVE_AT,
        rule_pack=make_rule_pack_ref(),
        facts_fingerprint=make_fingerprint(),
        candidates=[make_candidate(product_version_id=product_version_id)],
        missing_facts=[],
        review_reasons=[],
        no_path_reasons=[],
        outage=None,
        quotes=[make_price_quote(product_version_id=product_version_id)],
        notices=[],
        trace_sha256="e" * 64,
        decision_integrity=make_fingerprint(digest="d" * 64),
    )


@pytest.fixture
def source_record() -> M.SourceRecord:
    return make_source_record()


@pytest.fixture
def minimal_valid_pack(source_record: M.SourceRecord) -> M.RulePack:
    """One product (C1, TOURISM), one ELIGIBILITY SUPPORT rule, zero defects."""
    product_id = uuid.uuid4()
    product = make_product(
        product_version_id=product_id, source_refs=[source_record.source_record_id]
    )
    rule = make_support_rule(
        rule_id="rule.c1.tourism.support",
        product_version_ids=[product_id],
        source_refs=[source_record.source_record_id],
    )
    payload = make_rule_pack_payload(
        rules=[rule], products=[product], source_records=[source_record]
    )
    return make_rule_pack(payload)
