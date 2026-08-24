"""Deterministic PricingTool adapter tests: exact lookup and strict amounts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.services.visa_engine.models import PricingKey, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import (
    build_price_quote,
    resolve_candidate_pricing,
)
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader

_NOW = datetime(2026, 8, 4, 1, 0, tzinfo=timezone.utc)

# Arbitrary, deliberately NOT the real pricing catalog's date (see
# backend/data/bali_zero_official_prices_2026.json::metadata.last_updated
# and backend/tests/services/pricing/test_pricing_data_freshness.py, which
# is what actually guards that file's freshness). This mock only needs SOME
# value to prove the adapter reads ``metadata.last_updated`` at all.
_MOCK_CATALOG_LAST_UPDATED = "2020-01-01"


def _product(pricing_key: PricingKey | None) -> VisaProductVersion:
    product = gold_loader.load_and_compile_rule_pack().source_pack.payload.products[0]
    return product.model_copy(update={"pricing_key": pricing_key})


class _Catalog:
    def __init__(
        self,
        *,
        loaded: bool,
        row: dict[str, Any] | None = None,
    ) -> None:
        self.loaded = loaded
        self._row = row
        self.lookups: list[str] = []

    def get_service_by_key(self, key: str) -> dict[str, Any] | None:
        self.lookups.append(key)
        return self._row

    def get_all_prices(self) -> dict[str, Any]:
        return {
            "version": "test-2026.1",
            "metadata": {"last_updated": _MOCK_CATALOG_LAST_UPDATED, "currency": "IDR"},
            "services": {"single_entry_visas": {}},
        }


def _assert_no_amount(payload: dict[str, object]) -> None:
    assert "amount" not in payload
    assert "price" not in payload


def test_missing_product_pricing_key_requires_contact_without_lookup() -> None:
    catalog = _Catalog(loaded=True)
    result = resolve_candidate_pricing(
        _product(None),
        pricing_catalog=catalog,
        evaluated_at=_NOW,
    )
    assert result.status == "CONTACT_REQUIRED"
    assert result.reason_code == "PRICING_KEY_NOT_CONFIGURED"
    assert catalog.lookups == []
    _assert_no_amount(result.as_json())


def test_unloaded_catalog_is_unknown_without_lookup() -> None:
    catalog = _Catalog(loaded=False)
    result = resolve_candidate_pricing(
        _product(PricingKey(category="single_entry_visas", item_key="C1 exact")),
        pricing_catalog=catalog,
        evaluated_at=_NOW,
    )
    assert result.status == "UNKNOWN"
    assert result.reason_code == "PRICING_CATALOG_UNAVAILABLE"
    assert catalog.lookups == []
    _assert_no_amount(result.as_json())


def test_catalog_read_failure_is_unknown_without_lookup() -> None:
    class _BrokenCatalog(_Catalog):
        def get_all_prices(self) -> dict[str, Any]:
            return {"error": "test-only outage"}

    catalog = _BrokenCatalog(loaded=True)
    result = resolve_candidate_pricing(
        _product(PricingKey(category="single_entry_visas", item_key="C1 exact")),
        pricing_catalog=catalog,
        evaluated_at=_NOW,
    )
    assert result.status == "UNKNOWN"
    assert result.reason_code == "PRICING_CATALOG_UNAVAILABLE"
    assert catalog.lookups == []
    _assert_no_amount(result.as_json())


@pytest.mark.parametrize(
    "row",
    [None, {"key": "C1 exact", "category": "wrong_category", "price": "test-only"}],
)
def test_missing_exact_item_or_category_requires_contact(row: dict[str, Any] | None) -> None:
    catalog = _Catalog(loaded=True, row=row)
    result = resolve_candidate_pricing(
        _product(PricingKey(category="single_entry_visas", item_key="C1 exact")),
        pricing_catalog=catalog,
        evaluated_at=_NOW,
    )
    assert result.status == "CONTACT_REQUIRED"
    assert result.reason_code == "PRICING_ROW_MISSING"
    assert catalog.lookups == ["C1 exact"]
    assert result.catalog_sha256 is not None
    assert result.row_sha256 is None
    _assert_no_amount(result.as_json())


def test_exact_row_emits_approved_all_inclusive_amount() -> None:
    catalog = _Catalog(
        loaded=True,
        row={
            "key": "C1 exact",
            "category": "single_entry_visas",
            "price": "2.300.000 IDR",
        },
    )
    result = resolve_candidate_pricing(
        _product(PricingKey(category="single_entry_visas", item_key="C1 exact")),
        pricing_catalog=catalog,
        evaluated_at=_NOW,
    )
    assert result.status == "AVAILABLE"
    assert result.reason_code == "PRICE_AVAILABLE"
    assert result.amount == 2_300_000
    assert result.catalog_version == "test-2026.1"
    assert result.catalog_last_updated is not None
    assert result.catalog_sha256 is not None
    assert result.row_sha256 is not None
    _assert_no_amount(result.as_json())
    product = _product(PricingKey(category="single_entry_visas", item_key="C1 exact"))
    decision_id = uuid.UUID("00000000-0000-4000-8000-000000000001")
    quote = build_price_quote(product, result, decision_id=decision_id)
    assert quote is not None
    assert quote.amount == 2_300_000
    assert quote.catalog_version == "test-2026.1"
    quote_again = build_price_quote(
        product,
        result,
        decision_id=decision_id,
    )
    assert quote_again is not None
    assert quote.quote_id == quote_again.quote_id


@pytest.mark.parametrize(
    "raw_price",
    [
        "Contact",
        "1.800.000 – 2.000.000 IDR",
        "USD 100",
        "2.3 million IDR",
        "IDR 2.300.000 IDR",
        "2.300,000 IDR",
        "-2.300.000 IDR",
        "9,007,199,254,740,992 IDR",
        None,
    ],
)
def test_non_exact_or_non_idr_price_requires_contact(raw_price: object) -> None:
    catalog = _Catalog(
        loaded=True,
        row={
            "key": "C1 exact",
            "category": "single_entry_visas",
            "price": raw_price,
        },
    )
    result = resolve_candidate_pricing(
        _product(PricingKey(category="single_entry_visas", item_key="C1 exact")),
        pricing_catalog=catalog,
        evaluated_at=_NOW,
    )
    assert result.status == "CONTACT_REQUIRED"
    assert result.reason_code == "PRICING_ROW_NOT_EXACT_AMOUNT"
    assert result.amount is None
    assert result.row_sha256 is not None
