"""E31 family -- what the family member is quoted, pinned against the REAL price catalogue.

``test_duration_options`` proves the selector mechanics on a hand-built product and a
stand-in catalog; nothing asserted the AMOUNT a family member is shown for E31A..E31J on
the pack that is live, per stay length, through the real PricingService. This file closes
that, on the HIGHEST SIGNED pack in the repository (today seq-28, so the day a newer pack
is signed the pin follows it and must still hold). The pack is VERIFIED -- Ed25519
signature and protected header through ``verify_rule_pack`` under the repository's
production key, never read by file name; a tampered copy is refused (guilt twin). Signed
is not enough: the pack must also be ACTIVATABLE -- ``validate_activation`` is run against
its predecessor, so a pack whose ``previous_payload_sha256`` does not chain to the
predecessor can never become the reference. The sequence is pinned (>= 28) so a regressed
or reset packs directory cannot silently satisfy the pin.

* each of the nine codes offers exactly two duration options -- 365 and 730 days -- and the
  pricing keys are pinned per code, on the product AND on each option: E31A (the spouse)
  prices from the ``Spouse ... (Offshore)`` rows, E31B..E31J (the dependents) from the
  ``Dependent ... (Offshore)`` rows;
* the stay length picks the amount through the production path
  (``resolve_candidate_pricing(stay_days=...)`` / ``build_price_quote(stay_days=...)`` /
  ``_duration_display(..., stay_days=...)``): 1..365 days quote the 1-year row
  (11,000,000 IDR), 366..730 quote the 2-year row (15,000,000 IDR), and a wish beyond 730
  still quotes the 2-year row while ``extension_required`` flips to True -- False at every
  stay up to 730 and for an unknown stay (``None``);
* every quote carries exactly ONE all-inclusive IDR amount: no PNBP / government-fee /
  service-fee structured field and no split wording may appear in the catalogue rows
  (the guard and its guilt twins are lifted from the visit-family pin);
* the whole family resolves through the real ``PricingService`` -- all nine codes at both
  durations, not hand-copied digits;
* GUILT twins: '9.000.000 USD' and '11.000.000 USD' parse to no amount at all
  (``PRICING_ROW_NOT_EXACT_AMOUNT``, no quote), an edited row amount moves the quote off
  the pin, a 1-year row edit breaks the 365-day pin WITHOUT breaking the 730-day pin, a
  deleted row degrades to ``PRICING_ROW_MISSING``, and a product RE-AIMED at a neighbouring
  row (Extend, Altus/Onshore, the other family's row -- including neighbours that cost the
  same amount) no longer satisfies the pin: the row identity, not the number, is compared.

What this file deliberately does NOT pin: the E31 stay-policy or eligibility rules (those
are the rules' business and have their own gold coverage) and which pack production has
ACTIVATED (a database fact; the pin is the repository's highest activatable pack).

The catalogue is read through the real ``PricingService`` (the same exact-key lookup the
endpoint uses), not a stand-in. A missing artifact FAILS (``_read_json``), it never skips.
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
    _signed_production_sequence,
    select_highest_repository_pack,
)
from backend.services.pricing.pricing_service import get_pricing_service
from backend.services.visa_engine.bundle import (
    VerifiedRulePack,
    validate_activation,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.evaluate_path import _duration_display
from backend.services.visa_engine.models import PricingKey, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import (
    ExactPricingCatalog,
    PricingResolution,
    _parse_exact_idr_amount,
    build_price_quote,
    resolve_candidate_pricing,
    resolve_pricing_key,
)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_SIGNED_RE = re.compile(r"^rulepack-prod-(\d{3})\.signed\.json$")
_MIN_SEQUENCE = 28

_E31A = "E31A"
_CODES = (_E31A, "E31B", "E31C", "E31D", "E31E", "E31F", "E31G", "E31H", "E31J")


def _family_of(code: str) -> str:
    """E31A is the spouse; every other code is a dependent of the primary holder."""

    return "Spouse" if code == _E31A else "Dependent"


def _keys(family: str) -> tuple[PricingKey, PricingKey]:
    """(365-day key, 730-day key) of one family; the row names are typed, not read from the pack."""

    return (
        PricingKey(category="kitas_permits", item_key=f"{family} 1 Year (Offshore)"),
        PricingKey(category="kitas_permits", item_key=f"{family} 2 Years (Offshore)"),
    )


#: The ONE all-inclusive amount per duration, identical for both families today
#: (Spouse 1 Year (Offshore) and Dependent 1 Year (Offshore) are both 11,000,000 IDR).
#: Typed here on purpose.
_ONE_YEAR_AMOUNT = 11_000_000
_TWO_YEAR_AMOUNT = 15_000_000

#: (stay_days, expected amount, extension_required) -- None is an unknown stay.
_STAY_PINS: tuple[tuple[int | None, int, bool], ...] = (
    (None, _ONE_YEAR_AMOUNT, False),
    (1, _ONE_YEAR_AMOUNT, False),
    (30, _ONE_YEAR_AMOUNT, False),
    (364, _ONE_YEAR_AMOUNT, False),
    (365, _ONE_YEAR_AMOUNT, False),
    (366, _TWO_YEAR_AMOUNT, False),
    (400, _TWO_YEAR_AMOUNT, False),
    (729, _TWO_YEAR_AMOUNT, False),
    (730, _TWO_YEAR_AMOUNT, False),
    (731, _TWO_YEAR_AMOUNT, True),
    (1000, _TWO_YEAR_AMOUNT, True),
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk -- a witness that never ran proves nothing"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class _SignedPack:
    """The highest signed production pack, VERIFIED and ACTIVATABLE over its predecessor."""

    path: Path
    envelope: dict[str, Any]
    signed_at: datetime
    products: dict[str, VisaProductVersion]
    candidate: VerifiedRulePack
    predecessor: VerifiedRulePack


def _verified_predecessor(sequence: int) -> VerifiedRulePack:
    """The signed PRODUCTION pack at ``sequence - 1``, found by its sequence and verified."""

    found = []
    for path in sorted(_PACKS.glob("*.signed.json")):
        selected = _signed_production_sequence(path)
        if selected is not None and selected[0] == sequence - 1:
            found.append(selected[1])
    assert len(found) == 1, f"expected exactly one signed PRODUCTION pack at seq {sequence - 1}"
    return verify_rule_pack(
        found[0],
        trust_store=_repository_trust_store(),
        observed_at=_parse_utc(found[0]["protected"]["signed_at"]),
    )


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
    sequence = verified.pack.payload.sequence
    assert sequence == int(match.group(1))
    assert sequence >= _MIN_SEQUENCE, (
        f"the highest signed pack is seq {sequence} < {_MIN_SEQUENCE} -- re-read the pins "
        "against the pack that replaced it before relaxing this"
    )
    predecessor = _verified_predecessor(sequence)
    return _SignedPack(
        path=path,
        envelope=envelope,
        signed_at=signed_at,
        products={p.product_code: p for p in verified.pack.payload.products},
        candidate=verified,
        predecessor=predecessor,
    )


def _activate(candidate: VerifiedRulePack, over: VerifiedRulePack, *, over_sha: bytes) -> None:
    """The activation gate: sequence, ``previous_payload_sha256`` chain, environment and engine
    range. The engine side is the pack's own declared contract version."""

    validate_activation(
        candidate,
        current_sequence=over.pack.payload.sequence,
        current_payload_sha256=over_sha,
        environment="PRODUCTION",
        engine_version=candidate.pack.payload.engine_contract_version,
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
    product: VisaProductVersion,
    catalog: ExactPricingCatalog,
    at: datetime,
    *,
    stay_days: int | None = None,
) -> PricingResolution:
    return resolve_candidate_pricing(
        product, pricing_catalog=catalog, evaluated_at=at, stay_days=stay_days
    )


def _resolve_keyed(catalog: ExactPricingCatalog, key: PricingKey, at: datetime) -> str:
    """The row hash one pricing key resolves to, through the same lookup the product uses."""

    resolution = resolve_pricing_key(key, pricing_catalog=catalog, evaluated_at=at)
    assert resolution.status == "AVAILABLE", f"{key.item_key} must resolve to a priced row"
    assert resolution.row_sha256 is not None
    return resolution.row_sha256


def _edited_row(catalogue: dict[str, Any], key: PricingKey, price: str | None) -> dict[str, Any]:
    """A deep copy with ``key``'s row rewritten to ``price`` (``None`` deletes the row)."""

    out = copy.deepcopy(catalogue)
    if price is None:
        del out["services"][key.category][key.item_key]
    else:
        out["services"][key.category][key.item_key]["price"] = price
    return out


def _rewired(product: VisaProductVersion, keys: dict[int, PricingKey]) -> VisaProductVersion:
    """A product rebuilt through the validator with every pricing key re-aimed: the top-level
    key (which the model pins to the first option) and each option's own key."""

    raw = product.model_dump(mode="json", by_alias=True)
    assert raw["duration_options"], "the E31 products all carry duration options"
    raw["pricing_key"] = keys[raw["duration_options"][0]["days"]].model_dump(mode="json")
    for option in raw["duration_options"]:
        option["pricing_key"] = keys[option["days"]].model_dump(mode="json")
    return VisaProductVersion.model_validate(raw)


class TestThePackUnderTestIsVerifiedNotNamed:
    def test_the_highest_signed_pack_carries_every_e31_code(self, signed: _SignedPack) -> None:
        assert set(_CODES) <= set(signed.products)

    def test_the_highest_signed_pack_is_activatable_over_its_predecessor(
        self, signed: _SignedPack
    ) -> None:
        """Signed is not enough: a pack that does not chain to the one before it could never
        be activated, so the pack production serves would still be the previous one."""

        payload = signed.candidate.pack.payload
        assert payload.previous_payload_sha256 == signed.predecessor.payload_sha256.hex()
        assert payload.sequence == signed.predecessor.pack.payload.sequence + 1
        assert payload.sequence >= _MIN_SEQUENCE
        _activate(signed.candidate, signed.predecessor, over_sha=signed.predecessor.payload_sha256)

    def test_guilt_a_pack_that_does_not_chain_to_its_predecessor_is_refused(
        self, signed: _SignedPack
    ) -> None:
        with pytest.raises(RulePackVerificationError):
            _activate(signed.candidate, signed.predecessor, over_sha=b"\x00" * 32)

    def test_guilt_a_pack_not_above_the_current_sequence_is_refused(
        self, signed: _SignedPack
    ) -> None:
        with pytest.raises(RulePackVerificationError):
            _activate(
                signed.predecessor, signed.candidate, over_sha=signed.candidate.payload_sha256
            )

    def test_guilt_a_pack_edited_after_signing_is_refused(self, signed: _SignedPack) -> None:
        tampered = copy.deepcopy(signed.envelope)
        victim = next(p for p in tampered["payload"]["products"] if p["product_code"] == "E31B")
        assert victim["pricing_key"] == _keys("Dependent")[0].model_dump(mode="json")
        victim["pricing_key"] = _keys("Spouse")[0].model_dump(mode="json")
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                tampered, trust_store=_repository_trust_store(), observed_at=signed.signed_at
            )


class TestEveryCodeIsAimedAtItsFamilyRows:
    @pytest.mark.parametrize("code", _CODES)
    def test_the_product_key_is_the_family_offshore_row(
        self, code: str, signed: _SignedPack
    ) -> None:
        one, _ = _keys(_family_of(code))
        assert signed.products[code].pricing_key == one

    @pytest.mark.parametrize("code", _CODES)
    def test_every_duration_option_aims_at_the_family_offshore_row(
        self, code: str, signed: _SignedPack
    ) -> None:
        one, two = _keys(_family_of(code))
        options = signed.products[code].duration_options
        assert options is not None, "the E31 products all carry duration options"
        assert [(o.days, o.pricing_key) for o in options] == [(365, one), (730, two)]

    @pytest.mark.parametrize("code", _CODES)
    def test_the_real_catalogue_rows_exist_with_the_pinned_amounts(
        self, code: str, catalogue: dict[str, Any]
    ) -> None:
        one, two = _keys(_family_of(code))
        for key, amount in ((one, _ONE_YEAR_AMOUNT), (two, _TWO_YEAR_AMOUNT)):
            row = catalogue["services"][key.category][key.item_key]
            assert _parse_exact_idr_amount(row["price"]) == amount, (
                f"{key.item_key} no longer parses to the typed pin {amount}"
            )
            assert _split_findings(row) == [], "the row must be ONE all-inclusive IDR amount"


#: Every key a family-row may carry. A NEW key -- above all a fee component such as ``pnbp`` /
#: ``government_fee`` / ``service_fee`` -- is a structural split of the one all-inclusive price
#: and must fail until a human decides it should not.
_ROW_KEYS = frozenset(
    {
        "name",
        "price",
        "tier_range",
        "duration",
        "validity",
        "notes",
        "description_en",
        "icon_id",
    }
)
#: Client-visible free-text fields of a row (the price is checked on its own).
_TEXT_FIELDS = ("name", "duration", "validity", "notes", "description_en")
_AMOUNT_IN_TEXT = re.compile(
    r"(?:\bIDR\s*\d|\bRp\.?\s*\d|\d[\d.,]*\s*(?:IDR|rupiah)\b)", re.IGNORECASE
)
_SPLIT_WORDING = re.compile(r"\bPNBP\b|\bpajak\b.*\bjasa\b|\bplus\b.*\bfee\b", re.IGNORECASE)


def _split_findings(row: dict[str, Any]) -> list[str]:
    """Why ``row`` is NOT one all-inclusive price (empty list: it is).

    Three independent shapes: an unknown (fee-component) key, a ``price`` that is not exactly
    one amount in IDR, and client-visible text that carries a second figure or names a
    PNBP/fee split. Wording that merely STATES inclusion is not a split and stays innocent.
    """

    findings = [f"unknown key {key!r}" for key in sorted(set(row) - _ROW_KEYS)]
    price = row.get("price")
    if not isinstance(price, str) or re.fullmatch(r"\d{1,3}(?:\.\d{3})* IDR|0 IDR", price) is None:
        findings.append("price is not one grouped IDR amount")
    for field in _TEXT_FIELDS:
        text = row.get(field)
        if not isinstance(text, str):
            continue
        if _AMOUNT_IN_TEXT.search(text):
            findings.append(f"{field} carries a second figure")
        if _SPLIT_WORDING.search(text):
            findings.append(f"{field} names a fee split")
    return findings


#: The display entries _duration_display emits per option: exactly ONE amount each, no split.
_DISPLAY_OPTION_KEYS = {"days", "pricing_key", "selected", "status", "reason_code", "amount_idr"}


class TestEveryStayLengthQuotesThePinnedAmount:
    @pytest.mark.parametrize("code", _CODES)
    @pytest.mark.parametrize(("stay_days", "amount", "extension"), _STAY_PINS)
    def test_the_quote_is_pinned_at_this_stay(
        self,
        code: str,
        stay_days: int | None,
        amount: int,
        extension: bool,
        signed: _SignedPack,
    ) -> None:
        product = signed.products[code]
        one, two = _keys(_family_of(code))
        expected_key = one if amount == _ONE_YEAR_AMOUNT else two
        catalog = get_pricing_service()

        resolution = _resolve(product, catalog, signed.signed_at, stay_days=stay_days)
        assert (resolution.status, resolution.reason_code) == ("AVAILABLE", "PRICE_AVAILABLE")
        assert resolution.amount == amount
        assert resolution.row_sha256 is not None
        assert resolution.catalog_version is not None

        quote = build_price_quote(
            product, resolution, decision_id=uuid.UUID(int=31), stay_days=stay_days
        )
        assert quote is not None
        assert (quote.product_code, quote.status, quote.currency) == (code, "AVAILABLE", "IDR")
        assert quote.amount == amount
        assert quote.pricing_key == expected_key
        assert not [f for f in quote.model_dump() if re.search(r"pnbp|fee", f, re.I)], (
            "a quote carries ONE all-inclusive amount -- a PNBP/fee component field is a split"
        )

        shown = _duration_display(
            product,
            stay_days=stay_days,
            pricing_catalog=catalog,
            evaluated_at=signed.signed_at,
        )
        assert shown["extension_required"] is extension
        expected_selected = 365 if amount == _ONE_YEAR_AMOUNT else 730
        assert shown["selected_duration_days"] == expected_selected
        options = shown["duration_options"]
        assert [(o["days"], o["selected"], o["amount_idr"]) for o in options] == [
            (365, expected_selected == 365, _ONE_YEAR_AMOUNT),
            (730, expected_selected == 730, _TWO_YEAR_AMOUNT),
        ]
        for option in options:
            assert set(option) == _DISPLAY_OPTION_KEYS, (
                "a duration entry must carry exactly one all-inclusive amount_idr -- "
                "a fee-split field here is a PNBP leak into the client-visible display"
            )

    def test_every_family_row_resolves_through_the_real_service(self, signed: _SignedPack) -> None:
        """All 9 codes x 2 durations = 18 resolutions through the real PricingService, not
        hand-copied digits: if a row drifts, at least one of these turns red."""

        catalog = get_pricing_service()
        for code in _CODES:
            one, two = _keys(_family_of(code))
            at_365 = _resolve(signed.products[code], catalog, signed.signed_at, stay_days=365)
            at_730 = _resolve(signed.products[code], catalog, signed.signed_at, stay_days=730)
            assert at_365.amount == _ONE_YEAR_AMOUNT
            assert at_365.row_sha256 is not None
            assert at_730.amount == _TWO_YEAR_AMOUNT
            assert at_730.row_sha256 is not None
            assert at_365.row_sha256 != at_730.row_sha256
            # Each duration prices from its own family row, addressed explicitly per code.
            one_row = _resolve_keyed(catalog, one, signed.signed_at)
            two_row = _resolve_keyed(catalog, two, signed.signed_at)
            assert at_365.row_sha256 == one_row
            assert at_730.row_sha256 == two_row


def _neighbours(code: str) -> dict[int, tuple[str, ...]]:
    """The neighbouring rows a twin may be re-aimed at, per option.

    Includes rows that cost the SAME as the pinned one (``... (Extend)`` at 730 days:
    Spouse/Dependent 2 Years (Extend) is 15.000.000 IDR, exactly the offshore pin) --
    the pin compares row identity, not the number, so a same-priced neighbour must not
    hold the pin either."""

    family = _family_of(code)
    other = "Dependent" if family == "Spouse" else "Spouse"
    return {
        365: (
            f"{family} 1 Year (Extend)",
            f"{family} 1 Year (Altus/Onshore)",
            f"{other} 1 Year (Offshore)",
        ),
        730: (
            f"{family} 2 Years (Extend)",
            f"{family} 2 Years (Altus/Onshore)",
            f"{other} 2 Years (Offshore)",
        ),
    }


class TestTheGuardHasTeeth:
    """Guilt twins: the same resolution on a catalogue or key that drifted is NOT the pin."""

    @pytest.mark.parametrize("code", [_E31A, "E31B"])
    @pytest.mark.parametrize("price", ["9.000.000 USD", "11.000.000 USD"])
    def test_a_row_in_usd_quotes_no_amount(
        self,
        code: str,
        price: str,
        signed: _SignedPack,
        catalogue: dict[str, Any],
    ) -> None:
        """'9.000.000 USD' and '11.000.000 USD' must NOT parse as a quote: the parser refuses
        a non-IDR currency, the resolution degrades to PRICING_ROW_NOT_EXACT_AMOUNT and no
        PriceQuote is built."""

        assert _parse_exact_idr_amount(price) is None
        one, _ = _keys(_family_of(code))
        usd = _edited_row(catalogue, one, price)
        resolution = _resolve(
            signed.products[code], _EditedCatalog(usd), signed.signed_at, stay_days=365
        )
        assert (resolution.status, resolution.reason_code) == (
            "CONTACT_REQUIRED",
            "PRICING_ROW_NOT_EXACT_AMOUNT",
        )
        assert resolution.amount is None
        assert (
            build_price_quote(
                signed.products[code], resolution, decision_id=uuid.uuid4(), stay_days=365
            )
            is None
        )

    @pytest.mark.parametrize("code", [_E31A, "E31B"])
    def test_an_edited_row_amount_moves_the_quote_off_the_pin(
        self, code: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        one, _ = _keys(_family_of(code))
        bumped = _edited_row(catalogue, one, "12.000.000 IDR")
        resolution = _resolve(
            signed.products[code], _EditedCatalog(bumped), signed.signed_at, stay_days=365
        )
        assert resolution.status == "AVAILABLE"
        assert resolution.amount == 12_000_000
        assert resolution.amount != _ONE_YEAR_AMOUNT

    @pytest.mark.parametrize("code", [_E31A, "E31B"])
    def test_an_edited_1_year_row_breaks_the_365_pin_not_the_730_pin(
        self, code: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        """The durations price from DIFFERENT rows: editing the 1-year row moves the 365-day
        quote while the 730-day quote still holds -- a twin that a single-row pin would miss."""

        one, _ = _keys(_family_of(code))
        bumped = _edited_row(catalogue, one, "12.000.000 IDR")
        edited = _EditedCatalog(bumped)
        at_365 = _resolve(signed.products[code], edited, signed.signed_at, stay_days=365)
        at_730 = _resolve(signed.products[code], edited, signed.signed_at, stay_days=730)
        assert at_365.amount == 12_000_000 != _ONE_YEAR_AMOUNT
        assert at_730.amount == _TWO_YEAR_AMOUNT

    @pytest.mark.parametrize("code", [_E31A, "E31B"])
    @pytest.mark.parametrize("days", [365, 730])
    def test_a_deleted_row_degrades_to_contact_required(
        self, code: str, days: int, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        one, two = _keys(_family_of(code))
        key = one if days == 365 else two
        gone = _edited_row(catalogue, key, None)
        resolution = _resolve(
            signed.products[code], _EditedCatalog(gone), signed.signed_at, stay_days=days
        )
        assert (resolution.status, resolution.reason_code) == (
            "CONTACT_REQUIRED",
            "PRICING_ROW_MISSING",
        )
        assert resolution.amount is None
        assert (
            build_price_quote(
                signed.products[code], resolution, decision_id=uuid.uuid4(), stay_days=days
            )
            is None
        )

    @pytest.mark.parametrize("code", [_E31A, "E31B"])
    @pytest.mark.parametrize("days", [365, 730])
    @pytest.mark.parametrize("neighbour_index", [0, 1, 2])
    def test_a_product_rewired_to_a_neighbouring_row_does_not_hold_the_pin(
        self,
        code: str,
        days: int,
        neighbour_index: int,
        signed: _SignedPack,
        catalogue: dict[str, Any],
    ) -> None:
        """The twin REROUTES every key at one neighbouring row and resolves that product.
        It is red on the row it is re-aimed at, not on the neighbour's price -- so a neighbour
        that costs the same amount (the (Extend) rows) is still not this code's row."""

        neighbours = _neighbours(code)
        neighbour = neighbours[days][neighbour_index]
        assert neighbour in catalogue["services"]["kitas_permits"], (
            f"{neighbour} left the catalogue -- re-read this twin"
        )
        family = _family_of(code)
        pinned = {d: _keys(family)[i] for i, d in enumerate((365, 730))}
        assert all(key.item_key != neighbour for key in pinned.values())

        catalog = get_pricing_service()
        real = _resolve(signed.products[code], catalog, signed.signed_at, stay_days=days)
        assert real.row_sha256 is not None

        keys = dict(pinned)
        keys[days] = PricingKey(category="kitas_permits", item_key=neighbour)
        rewired_product = _rewired(signed.products[code], keys)
        rewired = _resolve(rewired_product, catalog, signed.signed_at, stay_days=days)
        assert rewired.status == "AVAILABLE", "the twin must hit a real, priced neighbouring row"
        assert rewired.row_sha256 != real.row_sha256


class TestNoFeeSplitGuard:
    """The all-inclusive rule is enforced by ``_split_findings``; the resolver alone does not
    see a split -- split fields beside the unchanged price still quote the same amount."""

    @pytest.mark.parametrize("code", [_E31A, "E31B"])
    def test_innocence_every_real_family_row_is_one_all_inclusive_amount(
        self, code: str, catalogue: dict[str, Any]
    ) -> None:
        for key in _keys(_family_of(code)):
            assert _split_findings(catalogue["services"][key.category][key.item_key]) == []

    @pytest.mark.parametrize("code", [_E31A, "E31B"])
    @pytest.mark.parametrize(
        "extra",
        [
            {"pnbp": 1_000_000},
            {"government_fee": "1.000.000 IDR"},
            {"service_fee": 1_300_000},
            {"pnbp": 1_000_000, "service_fee": 1_300_000},
        ],
    )
    def test_guilt_a_structured_fee_component_is_refused(
        self, code: str, extra: dict[str, Any], catalogue: dict[str, Any]
    ) -> None:
        for key in _keys(_family_of(code)):
            row = {**catalogue["services"][key.category][key.item_key], **extra}
            findings = _split_findings(row)
            assert findings and all("unknown key" in f for f in findings)

    @pytest.mark.parametrize("code", [_E31A, "E31B"])
    @pytest.mark.parametrize(
        ("field", "text"),
        [
            ("notes", "Government fee (PNBP) 1.000.000 IDR plus service 1.300.000 IDR."),
            ("notes", "Includes PNBP."),
            ("description_en", "Visa fee IDR 1.000.000 plus Bali Zero service fee."),
            ("validity", "Biaya 1.000.000 rupiah"),
        ],
    )
    def test_guilt_split_wording_in_a_client_visible_field_is_refused(
        self, code: str, field: str, text: str, catalogue: dict[str, Any]
    ) -> None:
        for key in _keys(_family_of(code)):
            row = {**catalogue["services"][key.category][key.item_key], field: text}
            assert _split_findings(row), f"{field}={text!r} must be refused"

    @pytest.mark.parametrize(
        "price", ["1.000.000 + 1.300.000 IDR", "1.000.000 IDR + 1.300.000 IDR"]
    )
    def test_guilt_a_split_price_is_refused(self, price: str, catalogue: dict[str, Any]) -> None:
        key = _keys("Dependent")[0]
        row = {**catalogue["services"][key.category][key.item_key], "price": price}
        assert "price is not one grouped IDR amount" in _split_findings(row)

    def test_witness_the_resolver_alone_does_not_see_a_split(
        self, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        """The red-team counterexample, pinned: split fields beside the unchanged Dependent
        1-year price still quote AVAILABLE 11.000.000 -- only the guard above turns red on it,
        and the quote/display still carry exactly one amount."""

        key = _keys("Dependent")[0]
        split = copy.deepcopy(catalogue)
        split["services"][key.category][key.item_key].update(pnbp=1_000_000, service_fee=1_300_000)
        catalog = _EditedCatalog(split)
        resolution = _resolve(signed.products["E31B"], catalog, signed.signed_at, stay_days=365)
        assert (resolution.status, resolution.amount) == ("AVAILABLE", _ONE_YEAR_AMOUNT)
        assert _split_findings(split["services"][key.category][key.item_key])
        quote = build_price_quote(
            signed.products["E31B"], resolution, decision_id=uuid.uuid4(), stay_days=365
        )
        assert quote is not None and quote.amount == _ONE_YEAR_AMOUNT
