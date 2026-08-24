"""Exact-key pricing boundary tests for the GARUDA preview/archive."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_flow.pricing import catalogue_last_updated_stamp, price_for_case

# A fixed, fresh-relative pair used by every test below that isn't
# specifically exercising the freshness gate itself (that's
# `TestPriceCatalogueFreshnessGate`) — chosen well inside the 90-day
# `price_catalogue` window so those tests stay about key-matching, not dates.
_FRESH_LAST_UPDATED = "2026-01-01"
_TODAY_WITHIN_WINDOW = date(2026, 1, 15)


class _PricingStub:
    def __init__(self, row: object, *, last_updated: str | None = _FRESH_LAST_UPDATED) -> None:
        self.row = row
        self.keys: list[str] = []
        self.prices: dict[str, Any] = (
            {"metadata": {"last_updated": last_updated}} if last_updated is not None else {}
        )

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

    assert price_for_case(case_type, pricing=pricing, today=_TODAY_WITHIN_WINDOW) == (  # type: ignore[arg-type]
        expected,
        key,
    )
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

    assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=_TODAY_WITHIN_WINDOW) == (  # type: ignore[arg-type]
        None,
        None,
    )


class TestCatalogueLastUpdatedStamp:
    def test_reads_the_metadata_last_updated_field(self) -> None:
        pricing = _PricingStub({"key": "x"}, last_updated="2026-05-06")
        assert catalogue_last_updated_stamp(pricing) == "2026-05-06"  # type: ignore[arg-type]

    def test_missing_prices_attribute_reads_as_no_stamp(self) -> None:
        class _NoPricesAttr:
            pass

        assert catalogue_last_updated_stamp(_NoPricesAttr()) is None  # type: ignore[arg-type]

    def test_prices_without_metadata_reads_as_no_stamp(self) -> None:
        class _NoMetadata:
            prices: dict[str, Any] = {"services": {}}

        assert catalogue_last_updated_stamp(_NoMetadata()) is None  # type: ignore[arg-type]

    def test_metadata_without_last_updated_reads_as_no_stamp(self) -> None:
        pricing = _PricingStub({"key": "x"}, last_updated=None)
        assert catalogue_last_updated_stamp(pricing) is None  # type: ignore[arg-type]


class TestPriceCatalogueFreshnessGate:
    """Proven to bite both ways: a fresh catalogue prices the case, a stale
    one declines to quote via the EXISTING `(None, None)` shape — never a
    new one — exactly like a missing/malformed row already does.

    `conftest.py`'s autouse fixture pins `pricing.price_catalogue_freshness`
    to a canned FRESH report for every OTHER test in this package (so real
    dates/the real catalogue can't flip an unrelated assertion) — these
    tests exist specifically to test THAT function, so each starts with
    `monkeypatch.undo()` to reach the real, unpatched wiring.
    """

    _KEY = "B1 Visa on Arrival (VOA)"
    _ROW = {"key": _KEY, "price": "790.000 IDR"}

    def test_catalogue_exactly_at_the_90_day_window_still_prices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        pricing = _PricingStub(self._ROW, last_updated="2026-01-01")
        today = date(2026, 4, 1)  # exactly 90 days after 2026-01-01
        assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=today) == (  # type: ignore[arg-type]
            790_000,
            self._KEY,
        )

    def test_catalogue_one_day_past_the_window_declines_to_quote(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        pricing = _PricingStub(self._ROW, last_updated="2026-01-01")
        today = date(2026, 4, 2)  # 91 days after 2026-01-01
        assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=today) == (  # type: ignore[arg-type]
            None,
            None,
        )
        # the row is never even looked up once the catalogue is stale —
        # staleness is checked before key-matching.
        assert pricing.keys == []

    def test_catalogue_with_no_stamp_at_all_declines_to_quote(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        pricing = _PricingStub(self._ROW, last_updated=None)
        assert price_for_case(  # type: ignore[arg-type]
            CaseType.ISSUANCE, pricing=pricing, today=_TODAY_WITHIN_WINDOW
        ) == (None, None)

    def test_catalogue_with_a_malformed_stamp_declines_to_quote(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        pricing = _PricingStub(self._ROW, last_updated="not-a-date")
        assert price_for_case(  # type: ignore[arg-type]
            CaseType.ISSUANCE, pricing=pricing, today=_TODAY_WITHIN_WINDOW
        ) == (None, None)
