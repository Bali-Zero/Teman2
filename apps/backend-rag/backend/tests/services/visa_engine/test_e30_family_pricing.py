"""E30 family -- what the visitor is quoted, pinned against the REAL price catalogue.

``test_pack_chain_and_pricing`` only checks that a ``pricing_key`` exists, so an edit to an E30A or
E30B catalogue row (or a rewired key) passed CI. This file pins, on the HIGHEST SIGNED pack (the
day a newer pack is signed the pin follows it and must still hold), the AMOUNT a student-visa
visitor is shown. The pack is VERIFIED -- Ed25519 signature, protected header and trust chain
through ``verify_rule_pack`` under the repository's production key -- never read by file name; a
tampered copy is refused (guilt twin below).

* E30A and E30B carry NO ``duration_options`` and one ``(1 Year)`` ``pricing_key`` each. For a stay
  of one year (365 days) the quote is AVAILABLE at IDR 9,000,000 -- one all-inclusive amount, read
  from the ``E30A Education Visa (1 Year)`` / ``E30B Higher Education (1 Year)`` rows of
  ``bali_zero_official_prices_2026.json``;
* E30, E30E and E30F carry NO ``pricing_key`` (the catalogue has no row for them) and resolve to
  CONTACT_REQUIRED / ``PRICING_KEY_NOT_CONFIGURED`` with no amount, so the page shows no price and
  offers a Bali Zero advisor ("Price on consultation. You can ask a Bali Zero advisor.") instead
  of inventing one;
* the same holds END TO END: ``run_evaluation`` over the real signed pack, the real pricing service
  and a real study walk names E30A, attaches the quote and renders the display;
* GUILT twins: an edited row amount moves the quote off the pin, a missing row degrades to
  ``PRICING_ROW_MISSING``, and a product RE-AIMED at a neighbouring row (the 2- and 4-year rows,
  or the sibling product's 1-year row) no longer satisfies the pin -- each turns red.

KNOWN GAP, pinned as a STRICT xfail (reason ``SEQ29-E30-02``). The catalogue holds the 2-year row
(IDR 11,500,000, E30A and E30B) and the 4-year row (IDR 15,000,000, E30B) and the official pages
offer 1/2 (E30A) and 1/2/4 (E30B) years, but no E30 product carries ``duration_options``, so a
730- or 1460-day stay is still quoted the 1-year price. The day a pack gives them options the
three xfail rows XPASS, ``strict=True`` turns that into a failure, and whoever signs that pack must
delete the xfail marker and let the rows become ordinary pins -- the gap cannot close unnoticed.
The xfail is narrowed to ``AssertionError`` (any other error is a red, never an XFAIL), and today's
behaviour is ALSO asserted outright (``TestTodaysLongerStayQuoteIsPinnedExplicitly``: the 1-year
row, same amount, same row hash), so the gap cannot drift in any direction without a review.

The catalogue is read through the real ``PricingService`` (the same exact-key lookup the endpoint
uses), not a stand-in. A missing artifact FAILS (``_read_json``), it never skips.
"""

from __future__ import annotations

import base64
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
    _REPOSITORY_PRODUCTION_SIGNING_KEYS,
    _parse_utc,
    _repository_trust_store,
    build_persona_request,
    select_highest_repository_pack,
)
from backend.services.pricing.pricing_service import get_pricing_service
from backend.services.visa_engine import evaluate_path, shadow
from backend.services.visa_engine.api_models import VisaOracleEvaluateResponse
from backend.services.visa_engine.bundle import verify_rule_pack
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import PricingKey, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import (
    ExactPricingCatalog,
    PricingResolution,
    _parse_exact_idr_amount,
    build_price_quote,
    resolve_candidate_pricing,
)
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_WALK_STUDY = _HERE / "gold_coverage/fixtures/walks/offshore_study_education_sponsor.json"

_CATEGORY = "kitas_permits"
_E30A_1Y = PricingKey(category=_CATEGORY, item_key="E30A Education Visa (1 Year)")
_E30B_1Y = PricingKey(category=_CATEGORY, item_key="E30B Higher Education (1 Year)")
#: The ONE all-inclusive 1-year price of both products. Typed here on purpose: the pin must not be
#: derived from the very rows it guards.
_ONE_YEAR_IDR = 9_000_000
_TWO_YEAR_IDR = 11_500_000
_FOUR_YEAR_IDR = 15_000_000
_ONE_YEAR_STAY_DAYS = 365
_PRICED = {"E30A": _E30A_1Y, "E30B": _E30B_1Y}
#: Every catalogue row of the family: (item_key, typed amount). Pinned so a row edit is red even
#: for the rows no pack key reaches yet (the 2- and 4-year ones the seq-29 options will use).
_FAMILY_ROWS = (
    ("E30A Education Visa (1 Year)", _ONE_YEAR_IDR),
    ("E30A Education Visa (2 Years)", _TWO_YEAR_IDR),
    ("E30B Higher Education (1 Year)", _ONE_YEAR_IDR),
    ("E30B Higher Education (2 Years)", _TWO_YEAR_IDR),
    ("E30B Higher Education (4 Years)", _FOUR_YEAR_IDR),
)
_UNPRICED = ("E30", "E30E", "E30F")
_SIGNED_RE = re.compile(r"^rulepack-prod-(\d{3})\.signed\.json$")
#: For each priced product, the rows a drifted key would land on: its own other durations and the
#: sibling product's rows.
_NEIGHBOURS = (
    ("E30A", "E30A Education Visa (2 Years)"),
    ("E30A", "E30B Higher Education (1 Year)"),
    ("E30A", "E30B Higher Education (2 Years)"),
    ("E30B", "E30B Higher Education (2 Years)"),
    ("E30B", "E30B Higher Education (4 Years)"),
    ("E30B", "E30A Education Visa (1 Year)"),
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk -- a witness that never ran proves nothing"
        )
    return json.loads(path.read_text(encoding="utf-8"))


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
        self._rows = catalogue["services"][_CATEGORY]

    def get_service_by_key(self, key: str) -> dict[str, Any] | None:
        row = self._rows.get(key)
        return None if row is None else {**row, "category": _CATEGORY}

    def get_all_prices(self) -> dict[str, Any]:
        return {
            "version": self._catalogue["version"],
            "metadata": self._catalogue["metadata"],
            "services": self._rows,
        }


def _resolve(
    product: VisaProductVersion,
    catalog: ExactPricingCatalog,
    at: datetime,
    stay_days: int | None = _ONE_YEAR_STAY_DAYS,
) -> PricingResolution:
    return resolve_candidate_pricing(
        product, pricing_catalog=catalog, evaluated_at=at, stay_days=stay_days
    )


def _with_key(product: VisaProductVersion, item_key: str) -> VisaProductVersion:
    """A product rebuilt through the validator with ONE thing changed: its ``pricing_key``."""

    raw = product.model_dump(mode="json", by_alias=True)
    raw["pricing_key"] = {"category": _CATEGORY, "item_key": item_key}
    raw.pop("duration_options", None)
    return VisaProductVersion.model_validate(raw)


class TestThePackUnderTestIsVerifiedNotNamed:
    def test_the_highest_signed_pack_verifies_under_the_production_key(
        self, signed: _SignedPack
    ) -> None:
        assert {*_PRICED, *_UNPRICED} <= set(signed.products)

    def test_guilt_a_pack_edited_after_signing_is_refused(self, signed: _SignedPack) -> None:
        tampered = copy.deepcopy(signed.envelope)
        victim = next(p for p in tampered["payload"]["products"] if p["product_code"] == "E30E")
        victim["pricing_key"] = _E30B_1Y.model_dump(mode="json")
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                tampered, trust_store=_repository_trust_store(), observed_at=signed.signed_at
            )


class TestTheCatalogueRowsAreWhatTheVisitorIsQuoted:
    @pytest.mark.parametrize(("item_key", "amount"), _FAMILY_ROWS)
    def test_the_real_catalogue_row_exists_with_the_pinned_amount(
        self, item_key: str, amount: int, catalogue: dict[str, Any]
    ) -> None:
        row = catalogue["services"][_CATEGORY][item_key]
        # The PRODUCTION parser reads the price string, currency included: "11.500.000 USD" is
        # refused there (None), so it is refused here -- the pin cannot pass on a digit-only match.
        assert _parse_exact_idr_amount(row["price"]) == amount
        # One all-inclusive amount: the row carries no fee split.
        assert row["notes"] == "All-inclusive price."

    @pytest.mark.parametrize(("item_key", "amount"), _FAMILY_ROWS)
    def test_every_family_row_resolves_available_through_the_real_service(
        self, item_key: str, amount: int, signed: _SignedPack
    ) -> None:
        """Every E30 catalogue row is resolved by the real ``PricingService`` in IDR."""

        product = _with_key(signed.products["E30B"], item_key)
        resolution = _resolve(product, get_pricing_service(), signed.signed_at)
        assert (resolution.status, resolution.reason_code) == ("AVAILABLE", "PRICE_AVAILABLE")
        assert resolution.amount == amount
        quote = build_price_quote(
            product, resolution, decision_id=uuid.UUID(int=31), stay_days=_ONE_YEAR_STAY_DAYS
        )
        assert quote is not None
        assert (quote.status, quote.currency, quote.amount) == ("AVAILABLE", "IDR", amount)


class TestE30AAndE30BAreQuotedTheirOneYearRow:
    @pytest.mark.parametrize("code", sorted(_PRICED))
    def test_the_key_is_the_one_year_row_and_duration_options_match_the_catalogue(
        self, code: str, signed: _SignedPack
    ) -> None:
        assert signed.products[code].pricing_key == _PRICED[code]
        expected_days = (365, 730) if code == "E30A" else (365, 730, 1460)
        assert tuple(o.days for o in signed.products[code].duration_options) == expected_days
        assert signed.products[code].duration_options[0].pricing_key == _PRICED[code]

    @pytest.mark.parametrize("code", sorted(_PRICED))
    def test_a_one_year_stay_is_available_at_the_pinned_amount_through_the_real_service(
        self, code: str, signed: _SignedPack
    ) -> None:
        resolution = _resolve(signed.products[code], get_pricing_service(), signed.signed_at)
        assert (resolution.status, resolution.reason_code) == ("AVAILABLE", "PRICE_AVAILABLE")
        assert resolution.amount == _ONE_YEAR_IDR
        assert resolution.row_sha256 is not None
        assert resolution.catalog_version is not None

    @pytest.mark.parametrize("code", sorted(_PRICED))
    def test_the_signed_quote_carries_the_amount_and_the_key(
        self, code: str, signed: _SignedPack
    ) -> None:
        product = signed.products[code]
        resolution = _resolve(product, get_pricing_service(), signed.signed_at)
        quote = build_price_quote(
            product,
            resolution,
            decision_id=uuid.UUID(int=30),
            stay_days=_ONE_YEAR_STAY_DAYS,
        )
        assert quote is not None
        assert (quote.product_code, quote.status, quote.currency) == (code, "AVAILABLE", "IDR")
        assert quote.amount == _ONE_YEAR_IDR
        assert quote.pricing_key == _PRICED[code]

    @pytest.mark.parametrize("code", sorted(_PRICED))
    def test_a_short_or_unstated_stay_is_quoted_the_same_one_year_row(
        self, code: str, signed: _SignedPack
    ) -> None:
        """At or below a year the 1-year row IS the right row, so these may never move."""

        for stay_days in (None, 1, 121, _ONE_YEAR_STAY_DAYS):
            resolution = _resolve(
                signed.products[code], get_pricing_service(), signed.signed_at, stay_days
            )
            assert resolution.amount == _ONE_YEAR_IDR, stay_days


class TestTheLongerStaysAreQuotedTheirOwnDurationRow:
    """SEQ29-E30-02 closed in seq-30: 2- and 4-year stays resolve to their own duration_options row."""

    @pytest.mark.parametrize(
        ("code", "stay_days", "amount"),
        [
            ("E30A", 730, _TWO_YEAR_IDR),
            ("E30B", 730, _TWO_YEAR_IDR),
            ("E30B", 1460, _FOUR_YEAR_IDR),
        ],
    )
    def test_a_longer_stay_is_quoted_its_own_duration_row(
        self, code: str, stay_days: int, amount: int, signed: _SignedPack
    ) -> None:
        resolution = _resolve(
            signed.products[code], get_pricing_service(), signed.signed_at, stay_days
        )
        assert (resolution.status, resolution.amount) == ("AVAILABLE", amount)


class TestTheOtherE30VisasStayUnpriced:
    @pytest.mark.parametrize("code", _UNPRICED)
    def test_no_pricing_key_and_no_duration_options(self, code: str, signed: _SignedPack) -> None:
        assert signed.products[code].pricing_key is None
        assert not signed.products[code].duration_options

    @pytest.mark.parametrize("code", _UNPRICED)
    def test_contact_required_with_no_amount_at_every_stay(
        self, code: str, signed: _SignedPack
    ) -> None:
        product = signed.products[code]
        for stay_days in (None, _ONE_YEAR_STAY_DAYS, 730, 1460):
            resolution = _resolve(product, get_pricing_service(), signed.signed_at, stay_days)
            assert resolution.status == "CONTACT_REQUIRED", stay_days
            assert resolution.reason_code == "PRICING_KEY_NOT_CONFIGURED", stay_days
            assert resolution.amount is None
            assert (
                build_price_quote(
                    product, resolution, decision_id=uuid.uuid4(), stay_days=stay_days
                )
                is None
            )


class TestTheEvaluatePathQuotesE30OnTheRealPack:
    """``run_evaluation`` end to end: real signature check, real compile, real evaluator, real
    ``PricingService`` -- only the database (pack binding, persistence) is stood in for."""

    async def test_a_one_year_education_walk_is_offered_e30a_at_the_pinned_price(
        self, signed: _SignedPack, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        saved: list[dict[str, Any]] = []

        async def _binding(
            pool: object, *, environment: str, effective_at: datetime, observed_at: datetime
        ) -> shadow._PackBinding:
            return shadow._PackBinding(
                rule_pack_id=uuid.uuid5(uuid.NAMESPACE_URL, signed.path.name),
                ruleset_activation_id=uuid.uuid4(),
                environment="PRODUCTION",
                raw_envelope=signed.envelope,
            )

        async def _save(pool: object, **kwargs: Any) -> None:
            saved.append(kwargs)

        async def _retention(*args: object, **kwargs: object) -> bool:
            return True

        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
        monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "PRODUCTION")
        monkeypatch.setenv(
            "VISA_ENGINE_TRUST_STORE_KEYS_JSON",
            json.dumps(list(_REPOSITORY_PRODUCTION_SIGNING_KEYS)),
        )
        # PRODUCTION fails closed without a facts-fingerprint key; a throwaway, test-only HMAC key
        # (not a credential) lets the real sealing path run on the real pack.
        monkeypatch.setenv(
            "VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON",
            json.dumps(
                [
                    {
                        "kid": "e30-price-pin-throwaway",
                        "secret": base64.urlsafe_b64encode(b"\x07" * 32).rstrip(b"=").decode(),
                        "environment": "PRODUCTION",
                        "valid_from": "2020-01-01T00:00:00+00:00",
                    }
                ]
            ),
        )
        monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _binding)
        monkeypatch.setattr(evaluate_path, "_save_evaluate_decision", _save)
        monkeypatch.setattr(evaluate_path, "active_retention_policy_available", _retention)

        walk = _read_json(_WALK_STUDY)
        overrides = copy.deepcopy(walk["overrides"])
        overrides["intent.stay_days"] = {"status": "KNOWN", "value": _ONE_YEAR_STAY_DAYS}
        persona = Persona(
            id=0,
            label=walk["label"],
            overrides=overrides,
            expected_state=DecisionState.NEEDS_INPUT,
        )
        body = await evaluate_path.run_evaluation(
            object(),
            facts=build_persona_request(persona).applicant_facts(),
            traffic_source="real",
            request_category_hint=None,
            request_trace="trace-e30-price-pin",
            evaluation_time=signed.signed_at,
        )
        response = VisaOracleEvaluateResponse.model_validate(body)  # the wire contract holds

        assert response.mode.value == "ENGINE"
        assert response.decision.state is DecisionState.SUPPORTED_CANDIDATES
        candidates = [str(c.product_code) for c in response.decision.candidates]
        assert "E30A" in candidates

        e30a_quotes = [q for q in response.decision.quotes if q.product_code == "E30A"]
        assert len(e30a_quotes) == 1
        quote = e30a_quotes[0]
        assert (quote.status, quote.currency, quote.reason_code) == (
            "AVAILABLE",
            "IDR",
            "PRICE_AVAILABLE",
        )
        assert quote.amount == _ONE_YEAR_IDR
        assert quote.pricing_key == _E30A_1Y

        # The siblings the same walk lists carry NO quote: their price is on consultation.
        quoted = {q.product_code for q in response.decision.quotes}
        assert quoted <= set(_PRICED)
        assert not quoted & set(_UNPRICED)

        # ... and they are still OFFERED: each sibling is a candidate of the walk, displayed with
        # CONTACT_REQUIRED / PRICING_KEY_NOT_CONFIGURED and no row. That status is what the mouth
        # adapter turns into the advisor offer ("Price on consultation. You can ask a Bali Zero
        # advisor." / "Harga melalui konsultasi. Anda dapat bertanya kepada konsultan Bali Zero.");
        # both lines are pinned in the mouth suite (engine-adapter.test.ts), not here.
        for code in _UNPRICED:
            assert code in candidates, f"{code} left the walk's candidates"
            sibling = [c for c in body["display"]["candidates"] if c["product_code"] == code]
            assert len(sibling) == 1, code
            assert sibling[0]["pricing"]["status"] == "CONTACT_REQUIRED", code
            assert sibling[0]["pricing"]["reason_code"] == "PRICING_KEY_NOT_CONFIGURED", code
            assert sibling[0]["pricing"]["row_sha256"] is None, code
            assert "amount" not in sibling[0]["pricing"], code

        shown = [c for c in body["display"]["candidates"] if c["product_code"] == "E30A"]
        assert len(shown) == 1
        assert shown[0]["pricing"]["status"] == "AVAILABLE"
        assert shown[0]["pricing"]["reason_code"] == "PRICE_AVAILABLE"
        assert shown[0]["pricing"]["row_sha256"] == quote.row_sha256
        # The bilingual name the visitor reads beside the price comes from the signed pack.
        assert shown[0]["name"] == {
            "id": signed.products["E30A"].names.id,
            "en": signed.products["E30A"].names.en,
        }
        assert shown[0]["name"]["id"] and shown[0]["name"]["en"]

        # The quote that is shown is the quote that is persisted, and no unpriced sibling has one.
        assert len(saved) == 1
        assert not {q.product_code for q in saved[0]["decision"].quotes} & set(_UNPRICED)
        assert [
            (q.product_code, q.amount)
            for q in saved[0]["decision"].quotes
            if q.product_code == "E30A"
        ] == [("E30A", _ONE_YEAR_IDR)]


def _holds_the_pin(resolution: PricingResolution, own_row_sha256: str) -> bool:
    """The pin, as a predicate: the quote is THE product's own row, at the typed amount."""

    return resolution.amount == _ONE_YEAR_IDR and resolution.row_sha256 == own_row_sha256


class TestTheGuardHasTeeth:
    """Guilt twins: the same resolution on a catalogue or key that drifted is NOT the pinned quote."""

    @pytest.mark.parametrize("code", sorted(_PRICED))
    def test_innocence_the_real_product_holds_the_pin(self, code: str, signed: _SignedPack) -> None:
        own = _resolve(signed.products[code], get_pricing_service(), signed.signed_at)
        assert own.row_sha256 is not None
        assert _holds_the_pin(own, own.row_sha256)

    @pytest.mark.parametrize("code", sorted(_PRICED))
    def test_an_edited_row_amount_moves_the_quote_off_the_pin(
        self, code: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        edited = copy.deepcopy(catalogue)
        edited["services"][_CATEGORY][_PRICED[code].item_key]["price"] = "9.500.000 IDR"
        resolution = _resolve(signed.products[code], _EditedCatalog(edited), signed.signed_at)
        assert resolution.status == "AVAILABLE"
        assert resolution.amount == 9_500_000
        assert resolution.amount != _ONE_YEAR_IDR

    @pytest.mark.parametrize("code", sorted(_PRICED))
    @pytest.mark.parametrize("price", ["9.000.000 USD", "9.000.000", "Rp 9.000.000"])
    def test_a_corrupted_currency_is_not_a_quote(
        self, code: str, price: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        """The amount digits are right, the currency is not: the production parser refuses it."""

        edited = copy.deepcopy(catalogue)
        edited["services"][_CATEGORY][_PRICED[code].item_key]["price"] = price
        assert _parse_exact_idr_amount(price) is None
        resolution = _resolve(signed.products[code], _EditedCatalog(edited), signed.signed_at)
        assert resolution.status != "AVAILABLE"
        assert resolution.amount is None

    @pytest.mark.parametrize("price", ["IDR 9.000.000", "9.000.000 IDR"])
    def test_innocence_both_valid_idr_notations_parse_to_the_pinned_amount(
        self, price: str
    ) -> None:
        assert _parse_exact_idr_amount(price) == _ONE_YEAR_IDR

    @pytest.mark.parametrize("code", sorted(_PRICED))
    def test_a_deleted_row_degrades_to_contact_required(
        self, code: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        gone = copy.deepcopy(catalogue)
        del gone["services"][_CATEGORY][_PRICED[code].item_key]
        resolution = _resolve(signed.products[code], _EditedCatalog(gone), signed.signed_at)
        assert (resolution.status, resolution.reason_code) == (
            "CONTACT_REQUIRED",
            "PRICING_ROW_MISSING",
        )
        assert resolution.amount is None

    @pytest.mark.parametrize(("code", "neighbour"), _NEIGHBOURS)
    def test_a_product_rewired_to_a_neighbouring_row_does_not_hold_the_pin(
        self, code: str, neighbour: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        """The twin REROUTES the key and resolves that product. It is red on the row it is
        re-aimed at, not on the neighbour's price -- E30A and E30B 1-year rows cost the same today,
        yet a key swapped between them is still not the product's own row (the row identity, not
        the number, is compared)."""

        assert neighbour in catalogue["services"][_CATEGORY], (
            f"{neighbour} left the catalogue -- re-read this twin"
        )
        assert neighbour != _PRICED[code].item_key
        catalog = get_pricing_service()
        real = _resolve(signed.products[code], catalog, signed.signed_at)
        assert real.row_sha256 is not None
        rewired_product = _with_key(signed.products[code], neighbour)
        assert rewired_product.pricing_key != _PRICED[code]
        rewired = _resolve(rewired_product, catalog, signed.signed_at)
        assert rewired.status == "AVAILABLE", "the twin must hit a real, priced neighbouring row"
        assert not _holds_the_pin(rewired, real.row_sha256)
