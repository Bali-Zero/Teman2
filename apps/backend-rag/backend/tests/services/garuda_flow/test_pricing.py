"""Exact-key pricing boundary tests for the GARUDA preview/archive."""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_flow.pricing import price_for_case


class _PricingStub:
    def __init__(self, row: object) -> None:
        self.row = row
        self.keys: list[str] = []

    def get_service_by_key(self, key: str) -> Any:
        self.keys.append(key)
        return self.row

    def search_service(self, query: str) -> None:
        raise AssertionError(f"fuzzy search must never run: {query}")


@pytest.mark.parametrize(
    ("case_type", "key", "price", "expected"),
    [
        (CaseType.ISSUANCE, "B1 Visa on Arrival (VOA)", "790.000 IDR", 790_000),
        (
            CaseType.EXTENSION,
            "B1 Visa on Arrival Extension",
            "850.000 IDR",
            850_000,
        ),
    ],
)
def test_price_for_case_uses_only_the_exact_official_key(
    case_type: CaseType,
    key: str,
    price: str,
    expected: int,
) -> None:
    pricing = _PricingStub({"key": key, "price": price})

    assert price_for_case(case_type, pricing=pricing) == (expected, key)  # type: ignore[arg-type]
    assert pricing.keys == [key]


@pytest.mark.parametrize(
    "row",
    [
        None,
        {},
        {"key": "B1 Visa on Arrival Extension", "price": "850.000 IDR"},
        {"key": "B1 Visa on Arrival (VOA)"},
        {"key": "B1 Visa on Arrival (VOA)", "price": "Contact"},
        {"key": "B1 Visa on Arrival (VOA)", "price": "790000"},
        {"key": "B1 Visa on Arrival (VOA)", "price": 0},
        {"key": "B1 Visa on Arrival (VOA)", "price": -1},
        {"key": "B1 Visa on Arrival (VOA)", "price": True},
        {"key": "B1 Visa on Arrival (VOA)", "price": 790_000.0},
        {"key": "B1 Visa on Arrival (VOA)", "price": 1},
        {"key": "B1 Visa on Arrival (VOA)", "price": 999_999_999_999},
    ],
)
def test_price_for_case_fails_closed_on_missing_drifted_or_malformed_rows(
    row: object,
) -> None:
    pricing = _PricingStub(row)

    assert price_for_case(CaseType.ISSUANCE, pricing=pricing) == (None, None)  # type: ignore[arg-type]
