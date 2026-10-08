"""Duration options: a product may offer several stay lengths, each priced by its own row."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from backend.services.visa_engine.evaluate_path import _duration_display
from backend.services.visa_engine.models import VisaProductVersion
from backend.services.visa_engine.pricing_adapter import (
    build_price_quote,
    effective_pricing_key,
    resolve_candidate_pricing,
    select_duration_option,
)

_PACK = (
    Path(__file__).resolve().parents[3]
    / "services/visa_engine/contracts/packs/rulepack-prod-025.source.json"
)
_NOW = datetime(2026, 10, 8, 1, 0, tzinfo=timezone.utc)
_ONE = {"category": "kitas_permits", "item_key": "Dependent 1 Year (Offshore)"}
_TWO = {"category": "kitas_permits", "item_key": "Dependent 2 Years (Offshore)"}
_ROWS = {
    _ONE["item_key"]: "11.000.000 IDR",
    _TWO["item_key"]: "15.000.000 IDR",
}


def _base() -> dict[str, Any]:
    pack = json.loads(_PACK.read_text(encoding="utf-8"))
    return next(p for p in pack["products"] if p["product_code"] == "E31B")


def _product(options: list[dict[str, Any]] | None, **stay: Any) -> VisaProductVersion:
    raw = _base()
    raw["stay_policy"] = {
        "kind": "FIXED_DAYS",
        "minimum_days": 365,
        "maximum_days": 730,
        **stay,
    }
    raw["pricing_key"] = _ONE
    if options is not None:
        raw["duration_options"] = options
    return VisaProductVersion.model_validate(raw)


def _two_year_product() -> VisaProductVersion:
    return _product([{"days": 365, "pricing_key": _ONE}, {"days": 730, "pricing_key": _TWO}])


class _Catalog:
    loaded = True

    def get_service_by_key(self, key: str) -> dict[str, Any] | None:
        if key not in _ROWS:
            return None
        return {"category": "kitas_permits", "name": key, "price": _ROWS[key]}

    def get_all_prices(self) -> dict[str, Any]:
        return {
            "version": "test-2026.1",
            "metadata": {"last_updated": "2026-05-06", "currency": "IDR"},
            "services": {"kitas_permits": {}},
        }


class TestModelValidation:
    def test_product_without_options_is_valid_and_serialises_without_the_key(self) -> None:
        product = _product(None)
        assert product.duration_options is None
        assert "duration_options" not in product.model_dump(mode="json")

    def test_ordered_options_within_stay_bounds_are_valid(self) -> None:
        assert [o.days for o in _two_year_product().duration_options or ()] == [365, 730]

    @pytest.mark.parametrize("days", [[730, 365], [365, 365]])
    def test_days_must_be_strictly_increasing(self, days: list[int]) -> None:
        options = [{"days": d, "pricing_key": _ONE} for d in days]
        with pytest.raises(ValidationError, match="strictly increasing"):
            _product(options)

    def test_option_above_stay_maximum_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="above stay_policy.maximum_days"):
            _product([{"days": 365, "pricing_key": _ONE}, {"days": 1095, "pricing_key": _TWO}])

    def test_option_below_stay_minimum_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="below stay_policy.minimum_days"):
            _product([{"days": 180, "pricing_key": _ONE}])

    def test_top_level_pricing_key_must_equal_the_first_option(self) -> None:
        raw = _base()
        raw["stay_policy"] = {"kind": "FIXED_DAYS", "minimum_days": 365, "maximum_days": 730}
        raw["pricing_key"] = _TWO
        raw["duration_options"] = [
            {"days": 365, "pricing_key": _ONE},
            {"days": 730, "pricing_key": _TWO},
        ]
        with pytest.raises(ValidationError, match="first duration option"):
            VisaProductVersion.model_validate(raw)

    def test_options_on_a_non_fixed_days_policy_are_refused(self) -> None:
        raw = _base()
        raw["stay_policy"] = {
            "kind": "VARIABLE_BY_GRANT",
            "minimum_days": None,
            "maximum_days": None,
        }
        raw["pricing_key"] = _ONE
        raw["duration_options"] = [{"days": 365, "pricing_key": _ONE}]
        with pytest.raises(ValidationError, match="FIXED_DAYS"):
            VisaProductVersion.model_validate(raw)

    def test_empty_options_are_refused(self) -> None:
        with pytest.raises(ValidationError):
            _product([])


class TestSelector:
    @pytest.mark.parametrize(
        ("requested", "expected"),
        [(None, 365), (0, 365), (365, 365), (366, 730), (730, 730), (1095, 730)],
    )
    def test_smallest_covering_option_else_the_last(
        self, requested: int | None, expected: int
    ) -> None:
        option = select_duration_option(_two_year_product(), requested)
        assert option is not None
        assert option.days == expected

    def test_a_product_without_options_selects_nothing(self) -> None:
        product = _product(None)
        assert select_duration_option(product, 730) is None
        assert effective_pricing_key(product, 730) == product.pricing_key


class TestPricing:
    def _amount(self, product: VisaProductVersion, stay_days: int | None) -> int | None:
        return resolve_candidate_pricing(
            product, pricing_catalog=_Catalog(), evaluated_at=_NOW, stay_days=stay_days
        ).amount

    def test_each_option_resolves_its_own_catalogue_row(self) -> None:
        product = _two_year_product()
        assert self._amount(product, 365) == 11_000_000
        assert self._amount(product, 730) == 15_000_000
        assert self._amount(product, 1095) == 15_000_000

    def test_a_730_selection_never_carries_the_1_year_price(self) -> None:
        product = _two_year_product()
        assert self._amount(product, 730) != self._amount(product, 365)

    def test_product_without_options_ignores_the_requested_stay(self) -> None:
        product = _product(None)
        assert self._amount(product, 730) == 11_000_000

    def test_quote_names_the_selected_option_key_and_differs_per_option(self) -> None:
        import uuid

        product = _two_year_product()
        decision_id = uuid.uuid4()
        quotes = []
        for stay_days in (365, 730):
            resolution = resolve_candidate_pricing(
                product, pricing_catalog=_Catalog(), evaluated_at=_NOW, stay_days=stay_days
            )
            quote = build_price_quote(
                product, resolution, decision_id=decision_id, stay_days=stay_days
            )
            assert quote is not None
            quotes.append(quote)
        assert [q.pricing_key.item_key for q in quotes] == [_ONE["item_key"], _TWO["item_key"]]
        assert quotes[0].quote_id != quotes[1].quote_id
        assert [q.amount for q in quotes] == [11_000_000, 15_000_000]


class TestDisplay:
    def test_fields_present_only_when_options_exist(self) -> None:
        kwargs = {"pricing_catalog": _Catalog(), "evaluated_at": _NOW}
        assert _duration_display(_product(None), stay_days=730, **kwargs) == {}
        shown = _duration_display(_two_year_product(), stay_days=730, **kwargs)
        assert shown["selected_duration_days"] == 730
        options = shown["duration_options"]
        assert isinstance(options, list)
        assert [(o["days"], o["selected"], o["amount_idr"]) for o in options] == [
            (365, False, 11_000_000),
            (730, True, 15_000_000),
        ]

    @pytest.mark.parametrize(
        ("stay_days", "selected", "extension"),
        [
            (1095, 730, True),
            (731, 730, True),
            (540, 730, False),
            (730, 730, False),
            (None, 365, False),
        ],
    )
    def test_extension_required_only_when_the_wish_exceeds_the_last_option(
        self, stay_days: int | None, selected: int, extension: bool
    ) -> None:
        shown = _duration_display(
            _two_year_product(), stay_days=stay_days, pricing_catalog=_Catalog(), evaluated_at=_NOW
        )
        assert shown["selected_duration_days"] == selected
        assert shown["extension_required"] is extension
