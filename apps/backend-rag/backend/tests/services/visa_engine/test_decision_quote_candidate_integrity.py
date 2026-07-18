"""F6: every PriceQuote in a Decision must reference a product_version_id
present among the decision's own candidates, with a matching product_code —
a quote for a product the decision never actually offered (or a
mismatched product_code for the same id) is a data-integrity bug, not a
legitimate state.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.models import (
    CandidateDecision,
    Decision,
    Fingerprint,
    PriceQuote,
)

CANDIDATE_PRODUCT_ID = uuid.uuid4()
OTHER_PRODUCT_ID = uuid.uuid4()


def _candidate(**overrides: object) -> dict:
    base = {
        "rank": 1,
        "product_version_id": str(CANDIDATE_PRODUCT_ID),
        "product_code": "C1",
        "score": 10,
        "covered_purposes": ["TOURISM"],
        "support_rule_ids": ["el-tourism"],
        "source_refs": [str(uuid.uuid4())],
        "reason_codes": ["TOURISM_SUPPORTED"],
    }
    base.update(overrides)
    return base


def _quote(**overrides: object) -> dict:
    base = {
        "quote_id": str(uuid.uuid4()),
        "product_version_id": str(CANDIDATE_PRODUCT_ID),
        "product_code": "C1",
        "status": "UNAVAILABLE",
        "currency": "IDR",
        "amount": None,
        "pricing_key": {"category": "single_entry_visas", "item_key": "c1_tourist"},
        "catalog_version": None,
        "catalog_sha256": None,
        "row_sha256": None,
        "quoted_at": "2026-07-18T00:00:00Z",
        "valid_until": None,
        "reason_code": "NO_QUOTE",
    }
    base.update(overrides)
    return base


def _decision(*, candidates: list[dict], quotes: list[dict]) -> dict:
    return {
        "schema_version": "1.0.0",
        "decision_id": str(uuid.uuid4()),
        "public_id": "a" * 16,
        "state": DecisionState.SUPPORTED_CANDIDATES.value,
        "effective_at": "2026-07-18T00:00:00Z",
        "observed_at": "2026-07-18T00:00:00Z",
        "evaluated_at": "2026-07-18T00:00:00Z",
        "rule_pack": {
            "rule_pack_id": str(uuid.uuid4()),
            "sequence": 1,
            "version": "1.0.0",
            "payload_sha256": "a" * 64,
        },
        "facts_fingerprint": {
            "algorithm": "HMAC-SHA256",
            "key_id": "test-key",
            "digest": "b" * 64,
        },
        "candidates": candidates,
        "missing_facts": [],
        "review_reasons": [],
        "no_path_reasons": [],
        "outage": None,
        "quotes": quotes,
        "notices": [],
        "trace_sha256": None,
        "decision_integrity": None,
    }


def test_quote_referencing_unknown_product_version_id_is_rejected() -> None:
    payload = _decision(
        candidates=[_candidate()],
        quotes=[_quote(product_version_id=str(OTHER_PRODUCT_ID))],
    )
    with pytest.raises(ValidationError):
        Decision(**payload)


def test_quote_with_mismatched_product_code_for_same_id_is_rejected() -> None:
    payload = _decision(
        candidates=[_candidate()],
        quotes=[_quote(product_code="C9")],
    )
    with pytest.raises(ValidationError):
        Decision(**payload)


def test_quote_matching_a_real_candidate_is_accepted() -> None:
    payload = _decision(candidates=[_candidate()], quotes=[_quote()])
    decision = Decision(**payload)
    assert len(decision.quotes) == 1


def test_empty_quotes_is_always_fine() -> None:
    payload = _decision(candidates=[_candidate()], quotes=[])
    decision = Decision(**payload)
    assert decision.quotes == ()


def test_sanity_models_import() -> None:
    assert CandidateDecision is not None
    assert PriceQuote is not None
    assert Fingerprint is not None
