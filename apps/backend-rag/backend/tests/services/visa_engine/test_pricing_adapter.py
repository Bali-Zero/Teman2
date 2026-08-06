"""Deterministic PricingTool adapter tests: exact lookup, no amount leakage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from backend.services.visa_engine.models import PricingKey, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import resolve_candidate_pricing
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader

_NOW = datetime(2026, 8, 4, 1, 0, tzinfo=timezone.utc)


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
            "metadata": {"last_updated": "2026-05-06", "currency": "IDR"},
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


def test_exact_row_with_no_freshness_policy_still_requires_contact() -> None:
    catalog = _Catalog(
        loaded=True,
        row={
            "key": "C1 exact",
            "category": "single_entry_visas",
            "price": "test-only-redacted-value",
        },
    )
    result = resolve_candidate_pricing(
        _product(PricingKey(category="single_entry_visas", item_key="C1 exact")),
        pricing_catalog=catalog,
        evaluated_at=_NOW,
    )
    assert result.status == "CONTACT_REQUIRED"
    assert result.reason_code == "PRICING_FRESHNESS_UNKNOWN"
    assert result.catalog_last_updated is not None
    assert result.catalog_sha256 is not None
    assert result.row_sha256 is not None
    _assert_no_amount(result.as_json())
