"""Public candidate display projections backed by the signed seq-29 pack."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from backend.services.visa_engine.api_models import CandidateDisplayDTO, VisaOracleEvaluateResponse
from backend.services.visa_engine.bundle import StaticTrustStore, verify_rule_pack
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.documentation_catalog import catalogue_codes
from backend.services.visa_engine.evaluate_path import _build_display, _build_sources_dto
from backend.services.visa_engine.pricing_adapter import UnavailablePricingCatalog
from backend.tests.services.visa_engine import test_interview_walk_census as census
from backend.tests.services.visa_engine.test_seq28_pack import PROD_TRUST_STORE_JSON

_REPO_ROOT = Path(__file__).resolve().parents[6]
_SIGNED_PACK = (
    _REPO_ROOT
    / "apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-029.signed.json"
)
_CONTRACT = (
    _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/contract.schema.json"
)


@pytest.fixture(scope="module")
def signed_seq29_pack() -> census.PackUnderTest:
    signed = json.loads(_SIGNED_PACK.read_text(encoding="utf-8"))
    signed_at = datetime.fromisoformat(signed["protected"]["signed_at"].replace("Z", "+00:00"))
    observed_at = signed_at + timedelta(hours=1)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)
        verified = verify_rule_pack(
            signed,
            trust_store=StaticTrustStore.from_env(),
            observed_at=observed_at,
        )
    assert verified.pack.payload.sequence == 29
    return census.PackUnderTest(
        compiled=build_compiled_pack(verified.pack),
        as_of=observed_at,
    )


@pytest.fixture(scope="module")
def candidate_displays(
    signed_seq29_pack: census.PackUnderTest,
) -> list[tuple[Any, Any, dict[str, Any]]]:
    cases: list[tuple[Any, Any, dict[str, Any]]] = []
    for label, spec in census._load_walks().items():
        decision, compiled, _request = census._decide(spec["overrides"], label, signed_seq29_pack)
        if not decision.candidates:
            continue
        display = _build_display(
            decision,
            compiled,
            request_trace="test",
            pricing_catalog=UnavailablePricingCatalog(),
        )
        cases.append((decision, compiled, display))
    assert cases
    return cases


def test_e33_candidate_carries_sale_prohibition(
    candidate_displays: list[tuple[Any, Any, dict[str, Any]]],
) -> None:
    e33 = next(
        shown
        for _decision, _compiled, display in candidate_displays
        for shown in display["candidates"]
        if shown["product_code"] == "E33"
    )
    assert "sale_of_goods_or_services" in e33["prohibited_activities"]


def test_every_candidate_matches_pack_prohibited_activities_in_pack_order(
    candidate_displays: list[tuple[Any, Any, dict[str, Any]]],
) -> None:
    for decision, compiled, display in candidate_displays:
        products = {
            product.product_version_id: product for product in compiled.source_pack.payload.products
        }
        for candidate, shown in zip(decision.candidates, display["candidates"], strict=True):
            expected = [
                str(activity)
                for activity in products[candidate.product_version_id].prohibited_activities
            ]
            assert shown["prohibited_activities"] == expected


def test_empty_prohibited_activities_are_emitted_as_empty_lists(
    candidate_displays: list[tuple[Any, Any, dict[str, Any]]],
) -> None:
    empty_candidates = [
        shown
        for _decision, compiled, display in candidate_displays
        for shown in display["candidates"]
        if not next(
            product
            for product in compiled.source_pack.payload.products
            if str(product.product_version_id) == shown["product_version_id"]
        ).prohibited_activities
    ]
    assert empty_candidates
    assert all(shown["prohibited_activities"] == [] for shown in empty_candidates)


def test_response_validates_against_dto_and_committed_contract_schema(
    candidate_displays: list[tuple[Any, Any, dict[str, Any]]],
) -> None:
    decision, compiled, display = next(
        case
        for case in candidate_displays
        if any(not shown["prohibited_activities"] for shown in case[2]["candidates"])
    )
    response = VisaOracleEvaluateResponse.model_validate(
        {
            "mode": "ENGINE",
            "decision": decision.model_dump(mode="json"),
            "sources": _build_sources_dto(decision, compiled, request_trace="test"),
            "display": display,
        }
    )
    payload = response.model_dump(mode="json")
    empty_candidate = next(
        shown for shown in payload["display"]["candidates"] if shown["prohibited_activities"] == []
    )
    legacy_candidate = dict(empty_candidate)
    legacy_candidate.pop("prohibited_activities")
    assert (
        CandidateDisplayDTO.model_validate(legacy_candidate).model_dump(mode="json")[
            "prohibited_activities"
        ]
        == []
    )
    contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    validator = Draft202012Validator(
        {"$defs": contract["$defs"], "$ref": "#/$defs/VisaOracleEvaluateResponse"}
    )
    assert list(validator.iter_errors(payload)) == []


def test_documentation_is_available_only_for_catalogue_products(
    candidate_displays: list[tuple[Any, Any, dict[str, Any]]],
) -> None:
    shown_codes: set[str] = set()
    for _decision, _compiled, display in candidate_displays:
        for shown in display["candidates"]:
            documentation = shown["documentation"]
            shown_codes.add(shown["product_code"])
            if shown["product_code"] in catalogue_codes():
                assert documentation["status"] == "AVAILABLE"
                assert documentation["requirements"]
            else:
                assert documentation["status"] == "UNKNOWN"
                assert documentation["reason_code"] == "DOCUMENTATION_CATALOG_NOT_VERIFIED"
                assert documentation["requirements"] == []
                assert documentation["checklist"] == []
    assert shown_codes & catalogue_codes()
    assert shown_codes - catalogue_codes()
