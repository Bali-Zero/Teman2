"""Visit family -- what the visitor is quoted, pinned against the REAL price catalogue.

``test_seq11`` proves each visit code's ``pricing_key`` resolves to a catalogue row, and
``test_pack_chain_and_pricing`` only checks that a key exists. Nothing asserted the AMOUNT a
visitor is quoted for A1, B1, BRIDGING, C1, C2, C6, D1, D2 and D12 on the pack that is live, nor
that a row rewritten to prose ("Free", a range) fails closed instead of quoting a number. This
file closes that, on the HIGHEST SIGNED pack (so the day a newer pack is signed the pin follows
it and must still hold). The pack is VERIFIED -- Ed25519 signature, protected header and trust
chain through ``verify_rule_pack`` under the repository's production key -- never read by file
name; a tampered copy is refused (guilt twin below).

* each code prices from ONE named catalogue row and the quote is AVAILABLE at ONE all-inclusive
  IDR amount (A1 0, B1 750,000, C1 2,300,000, C2 3,600,000, C6 2,000,000, BRIDGING 3,500,000,
  D1 6,000,000, D2 6,500,000, D12 7,500,000). The amounts are typed below on purpose: the pin must
  not be derived from the very row it guards;
* A1 is a real ZERO: ``amount == 0`` is still an AVAILABLE quote that is built and signed, never
  collapsed into "no price";
* GUILT twins: an edited row amount moves the quote off the pin, a row rewritten to prose or to a
  range degrades to ``PRICING_ROW_NOT_EXACT_AMOUNT``, a missing row to ``PRICING_ROW_MISSING``, and
  a product RE-AIMED at a neighbouring row no longer satisfies the pin -- each of which the pin
  above turns red on.

What this file deliberately does NOT pin: stay lengths and validity. The pack models them and the
Imigrasi pages restate them; a duration assertion here would turn today's pack shape into a
client-facing CI contract. The pin is the PRICE the visitor is quoted.

The catalogue is read through the real ``PricingService`` (the same exact-key lookup the endpoint
uses), not a stand-in. A missing artifact FAILS (``_read_json``), it never skips.
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.gold_replay_driver import (
    _parse_utc,
    _repository_trust_store,
    select_highest_repository_pack,
)
from backend.services.pricing.pricing_service import get_pricing_service
from backend.services.visa_engine.bundle import verify_rule_pack
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import PricingKey, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import (
    ExactPricingCatalog,
    PricingResolution,
    build_price_quote,
    resolve_candidate_pricing,
)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_SIGNED_RE = re.compile(r"^rulepack-prod-(\d{3})\.signed\.json$")

_SINGLE = "single_entry_visas"
_MULTI = "multiple_entry_visas"
#: code -> (pricing key, the ONE all-inclusive IDR amount the visitor is quoted).
_PINS: dict[str, tuple[PricingKey, int]] = {
    "A1": (PricingKey(category=_SINGLE, item_key="A1 Visa-Free Tourism"), 0),
    "B1": (PricingKey(category=_SINGLE, item_key="B1 Visa on Arrival (VOA)"), 750_000),
    "C1": (PricingKey(category=_SINGLE, item_key="C1 Tourism"), 2_300_000),
    "C2": (PricingKey(category=_SINGLE, item_key="C2 Business"), 3_600_000),
    "C6": (PricingKey(category=_SINGLE, item_key="C6 Social Activity"), 2_000_000),
    "BRIDGING": (PricingKey(category=_SINGLE, item_key="Bridging Visa"), 3_500_000),
    "D1": (PricingKey(category=_MULTI, item_key="D1 Tourism (1 Year)"), 6_000_000),
    "D2": (PricingKey(category=_MULTI, item_key="D2 Business (1 Year)"), 6_500_000),
    "D12": (PricingKey(category=_MULTI, item_key="D12 Business Investigation (1 Year)"), 7_500_000),
}
_CODES = tuple(_PINS)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk -- a witness that never ran proves nothing"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _display_amount(raw: str) -> int:
    """The catalogue's own spelling ("2.300.000 IDR") as an int -- for the row-level pin."""

    return int(raw.split()[0].replace(".", ""))


@dataclass(frozen=True)
class _SignedPack:
    """The highest signed production pack, VERIFIED -- signature, header and trust chain."""

    path: Path
    envelope: dict[str, Any]
    signed_at: datetime
    products: dict[str, VisaProductVersion]


@pytest.fixture(scope="module")
def signed() -> _SignedPack:
    path, envelope = select_highest_repository_pack(_PACKS)
    match = _SIGNED_RE.match(path.name)
    assert match is not None, f"{path.name} is not a rulepack-prod-NNN.signed.json"
    signed_at = _parse_utc(envelope["protected"]["signed_at"])
    verified = verify_rule_pack(
        envelope, trust_store=_repository_trust_store(), observed_at=signed_at
    )
    assert verified.unsigned_dev is False
    assert verified.pack.payload.sequence == int(match.group(1))
    return _SignedPack(
        path=path,
        envelope=envelope,
        signed_at=signed_at,
        products={p.product_code: p for p in verified.pack.payload.products},
    )


@pytest.fixture(scope="module")
def catalogue() -> dict[str, Any]:
    return _read_json(_CATALOGUE)


class _EditedCatalog:
    """The real catalogue JSON behind the ``ExactPricingCatalog`` surface, optionally edited."""

    loaded = True

    def __init__(self, catalogue: dict[str, Any]) -> None:
        self._catalogue = catalogue
        self._services = catalogue["services"]

    def get_service_by_key(self, key: str) -> dict[str, Any] | None:
        for category, rows in self._services.items():
            if key in rows:
                return {**rows[key], "category": category}
        return None

    def get_all_prices(self) -> dict[str, Any]:
        return {
            "version": self._catalogue["version"],
            "metadata": self._catalogue["metadata"],
            "services": self._services,
        }


def _resolve(
    product: VisaProductVersion, catalog: ExactPricingCatalog, at: datetime
) -> PricingResolution:
    return resolve_candidate_pricing(product, pricing_catalog=catalog, evaluated_at=at)


def _with_key(product: VisaProductVersion, key: PricingKey) -> VisaProductVersion:
    """A product rebuilt through the validator with ONE thing changed: its ``pricing_key``."""

    raw = product.model_dump(mode="json", by_alias=True)
    raw["pricing_key"] = key.model_dump(mode="json")
    return VisaProductVersion.model_validate(raw)


def _edited(catalogue: dict[str, Any], code: str, price: str | None) -> dict[str, Any]:
    """A deep copy with the row of ``code`` rewritten to ``price`` (``None`` deletes the row)."""

    key = _PINS[code][0]
    out = copy.deepcopy(catalogue)
    if price is None:
        del out["services"][key.category][key.item_key]
    else:
        out["services"][key.category][key.item_key]["price"] = price
    return out


class TestThePackUnderTestIsVerifiedNotNamed:
    def test_the_highest_signed_pack_carries_every_visit_code(self, signed: _SignedPack) -> None:
        assert set(_CODES) <= set(signed.products)

    def test_guilt_a_pack_edited_after_signing_is_refused(self, signed: _SignedPack) -> None:
        tampered = copy.deepcopy(signed.envelope)
        victim = next(p for p in tampered["payload"]["products"] if p["product_code"] == "C1")
        victim["pricing_key"] = _PINS["D1"][0].model_dump(mode="json")
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                tampered, trust_store=_repository_trust_store(), observed_at=signed.signed_at
            )


class TestEveryVisitCodeIsQuotedFromItsCatalogueRow:
    @pytest.mark.parametrize("code", _CODES)
    def test_the_key_is_the_pinned_row(self, code: str, signed: _SignedPack) -> None:
        assert signed.products[code].pricing_key == _PINS[code][0]

    @pytest.mark.parametrize("code", _CODES)
    def test_the_real_catalogue_row_exists_with_the_pinned_amount(
        self, code: str, catalogue: dict[str, Any]
    ) -> None:
        key, amount = _PINS[code]
        row = catalogue["services"][key.category][key.item_key]
        assert _display_amount(row["price"]) == amount
        assert row["price"].endswith(" IDR")  # one amount in one currency, no fee split

    @pytest.mark.parametrize("code", _CODES)
    def test_the_quote_is_available_at_the_pinned_amount_through_the_real_service(
        self, code: str, signed: _SignedPack
    ) -> None:
        resolution = _resolve(signed.products[code], get_pricing_service(), signed.signed_at)
        assert (resolution.status, resolution.reason_code) == ("AVAILABLE", "PRICE_AVAILABLE")
        assert resolution.amount == _PINS[code][1]
        assert resolution.row_sha256 is not None
        assert resolution.catalog_version is not None

    @pytest.mark.parametrize("code", _CODES)
    def test_the_signed_quote_carries_the_amount_and_the_key(
        self, code: str, signed: _SignedPack
    ) -> None:
        product = signed.products[code]
        resolution = _resolve(product, get_pricing_service(), signed.signed_at)
        quote = build_price_quote(product, resolution, decision_id=uuid.UUID(int=7))
        assert quote is not None
        assert (quote.product_code, quote.status, quote.currency) == (code, "AVAILABLE", "IDR")
        assert quote.amount == _PINS[code][1]
        assert quote.pricing_key == _PINS[code][0]

    def test_the_visa_free_entry_is_a_real_zero_not_a_missing_price(
        self, signed: _SignedPack
    ) -> None:
        """A1 costs IDR 0: still an AVAILABLE, signed quote -- ``0`` is not ``None``."""

        product = signed.products["A1"]
        resolution = _resolve(product, get_pricing_service(), signed.signed_at)
        quote = build_price_quote(product, resolution, decision_id=uuid.UUID(int=1))
        assert resolution.amount == 0
        assert quote is not None
        assert quote.amount == 0
        assert quote.amount is not None


class TestTheGuardHasTeeth:
    """Guilt twins: the same resolution on a catalogue or key that drifted is NOT the pin."""

    @pytest.mark.parametrize("code", _CODES)
    def test_an_edited_row_amount_moves_the_quote_off_the_pin(
        self, code: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        bumped = _edited(catalogue, code, f"{_PINS[code][1] + 100_000:,} IDR".replace(",", "."))
        resolution = _resolve(signed.products[code], _EditedCatalog(bumped), signed.signed_at)
        assert resolution.status == "AVAILABLE"
        assert resolution.amount == _PINS[code][1] + 100_000
        assert resolution.amount != _PINS[code][1]

    @pytest.mark.parametrize("code", _CODES)
    @pytest.mark.parametrize(
        "prose", ["Free", "1.000.000 - 2.000.000 IDR", "price on consultation"]
    )
    def test_a_row_rewritten_to_prose_or_a_range_quotes_no_amount(
        self, code: str, prose: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        resolution = _resolve(
            signed.products[code], _EditedCatalog(_edited(catalogue, code, prose)), signed.signed_at
        )
        assert (resolution.status, resolution.reason_code) == (
            "CONTACT_REQUIRED",
            "PRICING_ROW_NOT_EXACT_AMOUNT",
        )
        assert resolution.amount is None
        assert (
            build_price_quote(signed.products[code], resolution, decision_id=uuid.uuid4()) is None
        )

    @pytest.mark.parametrize("code", _CODES)
    def test_a_deleted_row_degrades_to_contact_required(
        self, code: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        resolution = _resolve(
            signed.products[code], _EditedCatalog(_edited(catalogue, code, None)), signed.signed_at
        )
        assert (resolution.status, resolution.reason_code) == (
            "CONTACT_REQUIRED",
            "PRICING_ROW_MISSING",
        )
        assert resolution.amount is None

    @pytest.mark.parametrize("code", _CODES)
    def test_a_product_rewired_to_a_neighbouring_row_does_not_hold_the_pin(
        self, code: str, signed: _SignedPack
    ) -> None:
        """The twin REROUTES the key and resolves that product. The row identity (its hash), not
        just the number, is compared -- so a neighbour that one day costs the same amount is still
        not this code's row."""

        neighbour = next(k for c, (k, _) in _PINS.items() if c != code)
        catalog = get_pricing_service()
        real = _resolve(signed.products[code], catalog, signed.signed_at)
        assert real.row_sha256 is not None
        rewired = _resolve(_with_key(signed.products[code], neighbour), catalog, signed.signed_at)
        assert rewired.status == "AVAILABLE", "the twin must hit a real, priced neighbouring row"
        assert rewired.row_sha256 != real.row_sha256
