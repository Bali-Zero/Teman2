"""E28 family -- what the visitor is quoted, pinned against the REAL price catalogue.

The seq-7/8/9/11 guards read old packs and ``test_pack_chain_and_pricing`` only checks that a
``pricing_key`` exists. Nothing asserted the AMOUNT a visitor is shown for E28A on the highest
signed pack in the repository, nor that E28B, E28C, E28D and E28F stay deliberately unpriced -- so
an edit to the catalogue row (or a rewired ``pricing_key``) passed CI. This file closes that, on
the HIGHEST SIGNED pack (so the day a newer pack is signed the pin follows it and must still
hold). The pack is VERIFIED -- Ed25519 signature and protected header through ``verify_rule_pack``
under the repository's production key, then ACTIVATABLE: ``validate_activation`` is run against
its predecessor, so a pack whose ``previous_payload_sha256`` does not chain to the predecessor
(signed, but not activatable) is refused and can never become the reference. The pack is never
read by file name; a tampered copy is refused (guilt twin).

What this proves, and what it cannot: the highest repository pack is signed, activatable and
priced as pinned. Which pack production has ACTIVATED is a database fact (the activation row);
this file does not read it, and its end-to-end walk stands the database binding in. "Live" here is
therefore never claimed -- the pin is the repository's highest activatable pack, and rollout of a
newer pack to production is checked by the deploy, not here. Likewise the wire is pinned up to the
backend JSON (name, status, reason, hash): how the portal renders ``CONTACT_REQUIRED`` is the
mouth adapter's contract and is covered by the mouth suite, not here.

* E28A prices from the ``Investor KITAS 2 Years (Offshore)`` row of
  ``bali_zero_official_prices_2026.json`` and the quote is AVAILABLE at IDR 17,000,000 -- one
  all-inclusive amount;
* E28B, E28C, E28D and E28F carry NO ``pricing_key`` AND the catalogue holds no row addressed to
  them (the set of Investor-family rows is pinned, so a new commercial row fails here until the
  pin is re-read), and resolve to CONTACT_REQUIRED / ``PRICING_KEY_NOT_CONFIGURED`` with no
  amount -- the wire status the portal turns into "an advisor confirms the price";
* the same holds END TO END on the backend: ``run_evaluation`` over the real signed pack, the real
  pricing service and a real full-capital PT PMA walk names E28A, attaches the quote and renders
  the display JSON (the database binding is stood in);
* GUILT twins: an edited row amount moves the quote off the pin, a missing row degrades to
  ``PRICING_ROW_MISSING``, and an E28A product RE-AIMED at a neighbouring row (Onshore, Extend, the
  Working KITAS) no longer satisfies the pin -- each of which the pin above turns red on.

What this file deliberately does NOT pin: the capital thresholds or the E28A stay. Those are the
rules' business and have their own gold coverage; the pin here is the PRICE the visitor is quoted,
whatever the pack's rule modelling becomes. The ``Investor KITAS 2 Years (Extend)`` row is a
neighbour only: E28A is quoted from the offshore row.

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
    _signed_production_sequence,
    build_persona_request,
    select_highest_repository_pack,
)
from backend.services.pricing.pricing_service import get_pricing_service
from backend.services.visa_engine import evaluate_path, shadow
from backend.services.visa_engine.api_models import VisaOracleEvaluateResponse
from backend.services.visa_engine.bundle import (
    VerifiedRulePack,
    validate_activation,
    verify_rule_pack,
)
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import PricingKey, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import (
    ExactPricingCatalog,
    PricingResolution,
    build_price_quote,
    resolve_candidate_pricing,
)
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_WALK_FULL_CAPITAL = _HERE / "gold_coverage/fixtures/walks/offshore_invest_pt_pma_full_capital.json"

_E28A_KEY = PricingKey(category="kitas_permits", item_key="Investor KITAS 2 Years (Offshore)")
#: The ONE all-inclusive E28A price. Typed here on purpose: the pin must not be derived from the
#: very row it guards.
_E28A_AMOUNT_IDR = 17_000_000
_UNPRICED = ("E28B", "E28C", "E28D", "E28F")
_SIGNED_RE = re.compile(r"^rulepack-prod-(\d{3})\.signed\.json$")
_NEIGHBOURS = (
    "Investor KITAS 2 Years (Altus/Onshore)",
    "Investor KITAS 2 Years (Extend)",
    "Working KITAS (Offshore)",
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
    assert verified.pack.payload.sequence == int(match.group(1))
    predecessor = _verified_predecessor(verified.pack.payload.sequence)
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
    range. The engine side is the pack's own declared contract version (1.0.0)."""

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


def _resolve(
    product: VisaProductVersion, catalog: ExactPricingCatalog, at: datetime
) -> PricingResolution:
    return resolve_candidate_pricing(product, pricing_catalog=catalog, evaluated_at=at)


def _with_key(product: VisaProductVersion, item_key: str) -> VisaProductVersion:
    """A product rebuilt through the validator with ONE thing changed: its ``pricing_key``."""

    raw = product.model_dump(mode="json", by_alias=True)
    raw["pricing_key"] = {"category": "kitas_permits", "item_key": item_key}
    return VisaProductVersion.model_validate(raw)


class TestThePackUnderTestIsVerifiedNotNamed:
    def test_the_highest_signed_pack_verifies_under_the_production_key(
        self, signed: _SignedPack
    ) -> None:
        assert {"E28A", *_UNPRICED} <= set(signed.products)

    def test_the_highest_signed_pack_is_activatable_over_its_predecessor(
        self, signed: _SignedPack
    ) -> None:
        """Signed is not enough: a pack that does not chain to the one before it could never be
        activated, so the pack production serves would still be the previous one."""

        payload = signed.candidate.pack.payload
        assert payload.previous_payload_sha256 == signed.predecessor.payload_sha256.hex()
        assert payload.sequence == signed.predecessor.pack.payload.sequence + 1
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
        victim = next(p for p in tampered["payload"]["products"] if p["product_code"] == "E28B")
        victim["pricing_key"] = _E28A_KEY.model_dump(mode="json")
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                tampered, trust_store=_repository_trust_store(), observed_at=signed.signed_at
            )


class TestE28AIsQuotedFromItsCatalogueRow:
    def test_the_key_is_the_offshore_working_kitas_row(self, signed: _SignedPack) -> None:
        assert signed.products["E28A"].pricing_key == _E28A_KEY

    def test_the_real_catalogue_row_exists_with_the_pinned_amount(
        self, catalogue: dict[str, Any]
    ) -> None:
        row = catalogue["services"][_E28A_KEY.category][_E28A_KEY.item_key]
        assert row["price"].split()[0].replace(".", "") == str(_E28A_AMOUNT_IDR)

    def test_the_quote_is_available_at_the_pinned_amount_through_the_real_service(
        self, signed: _SignedPack
    ) -> None:
        resolution = _resolve(signed.products["E28A"], get_pricing_service(), signed.signed_at)
        assert (resolution.status, resolution.reason_code) == ("AVAILABLE", "PRICE_AVAILABLE")
        assert resolution.amount == _E28A_AMOUNT_IDR
        assert resolution.row_sha256 is not None
        assert resolution.catalog_version is not None

    def test_the_signed_quote_carries_the_amount_and_the_key(self, signed: _SignedPack) -> None:
        product = signed.products["E28A"]
        resolution = _resolve(product, get_pricing_service(), signed.signed_at)
        quote = build_price_quote(product, resolution, decision_id=uuid.UUID(int=28))
        assert quote is not None
        assert (quote.product_code, quote.status, quote.currency) == ("E28A", "AVAILABLE", "IDR")
        assert quote.amount == _E28A_AMOUNT_IDR
        assert quote.pricing_key == _E28A_KEY


#: Every catalogue row whose key names the investor / golden-visa family, today. E28B, E28C, E28D
#: and E28F have NO row of their own; the day one is added this set changes and the pin is re-read.
_INVESTOR_ROWS = {
    ("multiple_entry_visas", "D12 Business Investigation (1 Year)"),
    ("multiple_entry_visas", "D12 Business Investigation (2 Years)"),
    ("kitas_permits", "Investor KITAS 2 Years (Altus/Onshore)"),
    ("kitas_permits", "Investor KITAS 2 Years (Offshore)"),
    ("kitas_permits", "Investor KITAS 2 Years (Extend)"),
    ("kitap_permits", "Investor KITAP + MERP"),
}
_FAMILY_RE = re.compile(r"investor|investigation|golden|\bE28[A-F]?\b|\bIKN\b|nusantara", re.I)


def _family_rows(catalogue: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (category, key)
        for category, rows in catalogue["services"].items()
        for key in rows
        if _FAMILY_RE.search(key)
    }


class TestTheOtherInvestorVisasStayUnpriced:
    def test_the_catalogue_has_no_row_for_them(self, catalogue: dict[str, Any]) -> None:
        """No row is addressed to E28B/C/D/F by code, golden-visa or IKN name, and the set of
        Investor-family rows is exactly the known one -- a new commercial row for any of them
        turns this red even while the pack is still unwired."""

        assert _family_rows(catalogue) == _INVESTOR_ROWS

    def test_guilt_a_new_investor_family_row_is_seen(self, catalogue: dict[str, Any]) -> None:
        added = copy.deepcopy(catalogue)
        added["services"]["kitas_permits"]["Investor Golden Visa (E28B)"] = {"price": "1 IDR"}
        assert _family_rows(added) != _INVESTOR_ROWS

    @pytest.mark.parametrize("code", _UNPRICED)
    def test_no_pricing_key(self, code: str, signed: _SignedPack) -> None:
        assert signed.products[code].pricing_key is None

    @pytest.mark.parametrize("code", _UNPRICED)
    def test_contact_required_with_no_amount(self, code: str, signed: _SignedPack) -> None:
        product = signed.products[code]
        resolution = _resolve(product, get_pricing_service(), signed.signed_at)
        assert resolution.status == "CONTACT_REQUIRED"
        assert resolution.reason_code == "PRICING_KEY_NOT_CONFIGURED"
        assert resolution.amount is None
        assert build_price_quote(product, resolution, decision_id=uuid.uuid4()) is None


class TestTheEvaluatePathQuotesE28AOnTheRealPack:
    """``run_evaluation`` end to end: real signature check, real compile, real evaluator, real
    ``PricingService`` -- only the database (pack binding, persistence) is stood in for."""

    async def test_a_full_capital_pt_pma_walk_is_offered_e28a_at_the_pinned_price(
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
                        "kid": "e28a-price-pin-throwaway",
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

        walk = _read_json(_WALK_FULL_CAPITAL)
        persona = Persona(
            id=0,
            label=walk["label"],
            overrides=walk["overrides"],
            expected_state=DecisionState.NEEDS_INPUT,
        )
        body = await evaluate_path.run_evaluation(
            object(),
            facts=build_persona_request(persona).applicant_facts(),
            traffic_source="real",
            request_category_hint=None,
            request_trace="trace-e28a-price-pin",
            evaluation_time=signed.signed_at,
        )
        response = VisaOracleEvaluateResponse.model_validate(body)  # the wire contract holds

        assert response.mode.value == "ENGINE"
        assert response.decision.state is DecisionState.SUPPORTED_CANDIDATES
        assert "E28A" in [str(c.product_code) for c in response.decision.candidates]

        e28a_quotes = [q for q in response.decision.quotes if q.product_code == "E28A"]
        assert len(e28a_quotes) == 1
        quote = e28a_quotes[0]
        assert (quote.status, quote.currency, quote.reason_code) == (
            "AVAILABLE",
            "IDR",
            "PRICE_AVAILABLE",
        )
        assert quote.amount == _E28A_AMOUNT_IDR
        assert quote.pricing_key == _E28A_KEY

        shown = [c for c in body["display"]["candidates"] if c["product_code"] == "E28A"]
        assert len(shown) == 1
        assert shown[0]["pricing"]["status"] == "AVAILABLE"
        assert shown[0]["pricing"]["reason_code"] == "PRICE_AVAILABLE"
        assert shown[0]["pricing"]["row_sha256"] == quote.row_sha256
        # The bilingual name the visitor reads beside the price comes from the signed pack.
        assert shown[0]["name"] == {
            "id": signed.products["E28A"].names.id,
            "en": signed.products["E28A"].names.en,
        }
        assert shown[0]["name"]["id"] and shown[0]["name"]["en"]

        # The siblings the walk names (E28B, E28D, E28F) are shown WITHOUT an amount: the page
        # says an advisor confirms the price, never an invented figure -- and no quote is persisted.
        siblings = [c for c in body["display"]["candidates"] if c["product_code"] in _UNPRICED]
        assert {c["product_code"] for c in siblings} >= {"E28B", "E28D", "E28F"}
        for sibling in siblings:
            assert sibling["pricing"]["status"] == "CONTACT_REQUIRED"
            assert sibling["pricing"]["reason_code"] == "PRICING_KEY_NOT_CONFIGURED"
            assert sibling["pricing"]["row_sha256"] is None
        assert not [q for q in response.decision.quotes if q.product_code in _UNPRICED]

        # The quote that is shown is the quote that is persisted.
        assert len(saved) == 1
        assert [
            (q.product_code, q.amount)
            for q in saved[0]["decision"].quotes
            if q.product_code == "E28A"
        ] == [("E28A", _E28A_AMOUNT_IDR)]


def _holds_the_pin(resolution: PricingResolution, e28a_row_sha256: str) -> bool:
    """The pin, as a predicate: E28A's quote is THE E28A row's, at the typed amount."""

    return resolution.amount == _E28A_AMOUNT_IDR and resolution.row_sha256 == e28a_row_sha256


class TestTheGuardHasTeeth:
    """Guilt twins: the same resolution on a catalogue or key that drifted is NOT the pinned quote."""

    def test_innocence_the_real_e28a_product_holds_the_pin(self, signed: _SignedPack) -> None:
        catalog = get_pricing_service()
        e28a_row = _resolve(signed.products["E28A"], catalog, signed.signed_at)
        assert e28a_row.row_sha256 is not None
        assert _holds_the_pin(e28a_row, e28a_row.row_sha256)

    def test_an_edited_row_amount_moves_the_quote_off_the_pin(
        self, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        edited = copy.deepcopy(catalogue)
        edited["services"]["kitas_permits"][_E28A_KEY.item_key]["price"] = "18.000.000 IDR"
        resolution = _resolve(signed.products["E28A"], _EditedCatalog(edited), signed.signed_at)
        assert resolution.status == "AVAILABLE"
        assert resolution.amount == 18_000_000
        assert resolution.amount != _E28A_AMOUNT_IDR

    def test_a_deleted_row_degrades_to_contact_required(
        self, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        gone = copy.deepcopy(catalogue)
        del gone["services"]["kitas_permits"][_E28A_KEY.item_key]
        resolution = _resolve(signed.products["E28A"], _EditedCatalog(gone), signed.signed_at)
        assert (resolution.status, resolution.reason_code) == (
            "CONTACT_REQUIRED",
            "PRICING_ROW_MISSING",
        )
        assert resolution.amount is None

    @pytest.mark.parametrize("neighbour", _NEIGHBOURS)
    def test_an_e28a_product_rewired_to_a_neighbouring_row_does_not_hold_the_pin(
        self, neighbour: str, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        """The twin REROUTES the key and resolves that product. It is red on the row it is
        re-aimed at, not on the neighbour's price -- so a neighbour that one day costs the same
        amount is still not E28A's row (the row identity, not the number, is compared)."""

        assert neighbour in catalogue["services"]["kitas_permits"], (
            f"{neighbour} left the catalogue -- re-read this twin"
        )
        assert neighbour != _E28A_KEY.item_key
        catalog = get_pricing_service()
        real = _resolve(signed.products["E28A"], catalog, signed.signed_at)
        assert real.row_sha256 is not None
        rewired_product = _with_key(signed.products["E28A"], neighbour)
        assert rewired_product.pricing_key != _E28A_KEY
        rewired = _resolve(rewired_product, catalog, signed.signed_at)
        assert rewired.status == "AVAILABLE", "the twin must hit a real, priced neighbouring row"
        assert not _holds_the_pin(rewired, real.row_sha256)
