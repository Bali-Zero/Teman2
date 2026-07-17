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
        engine_min_version="1.0.0",
        engine_max_version="1.0.0",
        valid_period=_OPEN_PERIOD,
        created_at=GOLD_EFFECTIVE_AT,
        created_by="pipeline.compiler",
        previous_payload_sha256=None if sequence == 1 else "d" * 64,
        rollback_of_payload_sha256=None,
        hit_policy={},
        source_records=list(source_records),
        products=list(products),
        rules=list(rules),
    )


def make_rule_pack(payload: M.RulePackPayload, *, environment: str = "TEST") -> M.RulePack:
    return M.RulePack(
        protected={
            "kid": "key-2026-07",
            "signed_at": GOLD_EFFECTIVE_AT,
            "environment": environment,
        },
        payload=payload,
        payload_sha256="b" * 64,
        signature="c" * 86,
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
