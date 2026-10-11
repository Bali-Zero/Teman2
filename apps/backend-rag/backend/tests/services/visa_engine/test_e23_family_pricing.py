"""E23 family -- what the visitor is quoted, pinned against the REAL price catalogue.

The seq-7/8/9/11 guards read old packs and ``test_pack_chain_and_pricing`` only checks that a
``pricing_key`` exists. Nothing asserted the AMOUNT a visitor is shown for E23 on the pack that is
live, nor that E23U and E23V stay deliberately unpriced -- so an edit to the catalogue row (or a
rewired ``pricing_key``) passed CI. This file closes that, on the HIGHEST SIGNED pack (so the day a
newer pack is signed the pin follows it and must still hold):

* E23 prices from the ``Working KITAS (Offshore)`` row of ``bali_zero_official_prices_2026.json``
  and the quote is AVAILABLE at IDR 34,500,000 -- one amount, no duration alternatives;
* E23U and E23V carry NO ``pricing_key`` (the catalogue has no row for a diplomatic-household or
  trade-office worker) and resolve to CONTACT_REQUIRED / ``PRICING_KEY_NOT_CONFIGURED`` with no
  amount, so the page says an advisor confirms the price instead of inventing one;
* GUILT twins: an edited row amount moves the quote off the pin, a missing row degrades to
  ``PRICING_ROW_MISSING``, and a ``pricing_key`` aimed at a neighbouring row (Onshore, Extend,
  Freelance) is not the E23 key -- each of which the pin above turns red on.

The catalogue is read through the real ``PricingService`` (the same exact-key lookup the endpoint
uses), not a stand-in. A missing artifact FAILS (``_read_json``), it never skips.
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.services.pricing.pricing_service import get_pricing_service
from backend.services.visa_engine.models import PricingKey, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import (
    ExactPricingCatalog,
    build_price_quote,
    resolve_candidate_pricing,
)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)

_E23_KEY = PricingKey(category="kitas_permits", item_key="Working KITAS (Offshore)")
#: The ONE all-inclusive E23 price. Typed here on purpose: the pin must not be derived from the
#: very row it guards.
_E23_AMOUNT_IDR = 34_500_000
_UNPRICED = ("E23U", "E23V")
_SIGNED_RE = re.compile(r"^rulepack-prod-(\d{3})\.signed\.json$")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk -- a witness that never ran proves nothing"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _highest_signed() -> Path:
    signed = sorted(
        (int(m.group(1)), p)
        for p in _PACKS.iterdir()
        if (m := _SIGNED_RE.match(p.name)) is not None
    )
    assert signed, "no signed production pack on disk"
    return signed[-1][1]


@pytest.fixture(scope="module")
def pack() -> dict[str, Any]:
    path = _highest_signed()
    payload = _read_json(path)["payload"]
    assert payload["sequence"] == int(_SIGNED_RE.match(path.name).group(1))  # type: ignore[union-attr]
    return payload


@pytest.fixture(scope="module")
def catalogue() -> dict[str, Any]:
    return _read_json(_CATALOGUE)


def _product(pack: dict[str, Any], code: str) -> VisaProductVersion:
    return VisaProductVersion.model_validate(
        next(p for p in pack["products"] if p["product_code"] == code)
    )


class _EditedCatalog:
    """The real catalogue JSON behind the ``ExactPricingCatalog`` surface, optionally edited."""

    loaded = True

    def __init__(self, catalogue: dict[str, Any]) -> None:
        self._catalogue = catalogue
        self._rows = catalogue["services"]["kitas_permits"]

    def get_service_by_key(self, key: str) -> dict[str, Any] | None:
        row = self._rows.get(key)
        return None if row is None else {**row, "category": "kitas_permits"}

    def get_all_prices(self) -> dict[str, Any]:
        return {
            "version": self._catalogue["version"],
            "metadata": self._catalogue["metadata"],
            "services": self._rows,
        }


def _resolve(product: VisaProductVersion, catalog: ExactPricingCatalog) -> Any:
    return resolve_candidate_pricing(product, pricing_catalog=catalog, evaluated_at=_NOW)


class TestE23IsQuotedFromItsCatalogueRow:
    def test_the_key_is_the_offshore_working_kitas_row(self, pack: dict[str, Any]) -> None:
        product = _product(pack, "E23")
        assert product.pricing_key == _E23_KEY
        assert not product.duration_options, "E23 is a single 365-day option: one price, no choice"

    def test_the_real_catalogue_row_exists_with_the_pinned_amount(
        self, catalogue: dict[str, Any]
    ) -> None:
        row = catalogue["services"][_E23_KEY.category][_E23_KEY.item_key]
        assert row["price"].split()[0].replace(".", "") == str(_E23_AMOUNT_IDR)

    def test_the_quote_is_available_at_the_pinned_amount_through_the_real_service(
        self, pack: dict[str, Any]
    ) -> None:
        product = _product(pack, "E23")
        resolution = _resolve(product, get_pricing_service())
        assert (resolution.status, resolution.reason_code) == ("AVAILABLE", "PRICE_AVAILABLE")
        assert resolution.amount == _E23_AMOUNT_IDR
        assert resolution.row_sha256 is not None
        assert resolution.catalog_version is not None

    def test_the_signed_quote_carries_the_amount_and_the_key(self, pack: dict[str, Any]) -> None:
        product = _product(pack, "E23")
        resolution = _resolve(product, get_pricing_service())
        quote = build_price_quote(product, resolution, decision_id=uuid.UUID(int=23))
        assert quote is not None
        assert (quote.product_code, quote.status, quote.currency) == ("E23", "AVAILABLE", "IDR")
        assert quote.amount == _E23_AMOUNT_IDR
        assert quote.pricing_key == _E23_KEY


class TestTheDiplomaticAndTradeOfficeVisasStayUnpriced:
    @pytest.mark.parametrize("code", _UNPRICED)
    def test_no_pricing_key_and_no_options(self, code: str, pack: dict[str, Any]) -> None:
        product = _product(pack, code)
        assert product.pricing_key is None
        assert not product.duration_options

    @pytest.mark.parametrize("code", _UNPRICED)
    def test_contact_required_with_no_amount(self, code: str, pack: dict[str, Any]) -> None:
        product = _product(pack, code)
        resolution = _resolve(product, get_pricing_service())
        assert resolution.status == "CONTACT_REQUIRED"
        assert resolution.reason_code == "PRICING_KEY_NOT_CONFIGURED"
        assert resolution.amount is None
        assert build_price_quote(product, resolution, decision_id=uuid.uuid4()) is None


class TestTheGuardHasTeeth:
    """Guilt twins: the same resolution on a catalogue that drifted is NOT the pinned quote."""

    def test_an_edited_row_amount_moves_the_quote_off_the_pin(
        self, pack: dict[str, Any], catalogue: dict[str, Any]
    ) -> None:
        edited = copy.deepcopy(catalogue)
        edited["services"]["kitas_permits"]["Working KITAS (Offshore)"]["price"] = "35.000.000 IDR"
        resolution = _resolve(_product(pack, "E23"), _EditedCatalog(edited))
        assert resolution.status == "AVAILABLE"
        assert resolution.amount == 35_000_000
        assert resolution.amount != _E23_AMOUNT_IDR

    def test_a_deleted_row_degrades_to_contact_required(
        self, pack: dict[str, Any], catalogue: dict[str, Any]
    ) -> None:
        gone = copy.deepcopy(catalogue)
        del gone["services"]["kitas_permits"]["Working KITAS (Offshore)"]
        resolution = _resolve(_product(pack, "E23"), _EditedCatalog(gone))
        assert (resolution.status, resolution.reason_code) == (
            "CONTACT_REQUIRED",
            "PRICING_ROW_MISSING",
        )
        assert resolution.amount is None

    @pytest.mark.parametrize(
        "neighbour",
        [
            "Working KITAS (Altus/Onshore)",
            "Working KITAS (Extend)",
            "Freelance E23 (Altus/Onshore)",
            "Freelance E23 (Offshore)",
        ],
    )
    def test_a_neighbouring_row_is_a_different_price(
        self, neighbour: str, catalogue: dict[str, Any]
    ) -> None:
        rows = catalogue["services"]["kitas_permits"]
        assert neighbour in rows, f"{neighbour} left the catalogue -- re-read this twin"
        amount = int(rows[neighbour]["price"].split()[0].replace(".", ""))
        assert neighbour != _E23_KEY.item_key
        assert amount != _E23_AMOUNT_IDR
