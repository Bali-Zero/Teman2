"""Visit family -- what the visitor is quoted, pinned against the REAL price catalogue.

``test_seq11`` proves each visit code's ``pricing_key`` resolves to a catalogue row, and
``test_pack_chain_and_pricing`` only checks that a key exists. Nothing asserted the AMOUNT a
visitor is quoted for A1, B1, BRIDGING, C1, C2, C6, D1, D2 and D12 on the pack that is live, nor
that a row rewritten to prose ("Free", a range) fails closed instead of quoting a number. This
file closes that, on the HIGHEST SIGNED pack file in the repository (so the day a newer pack is
signed the pin follows it and must still hold). That envelope is VERIFIED through
``verify_rule_pack`` under the repository's production key -- Ed25519 signature, protected header
and payload hash of THAT ONE envelope -- never read by file name; a tampered copy is refused
(guilt twin below). What this does NOT claim: the previous-payload chain back to the production
pack (``validate_activation`` owns that) and which pack the database has ACTIVE (the file chosen
is the highest on disk, not the database binding).

* each code prices from ONE named catalogue row and the quote is AVAILABLE at ONE all-inclusive
  IDR amount (A1 0, B1 750,000, C1 2,300,000, C2 3,600,000, C6 2,000,000, BRIDGING 3,500,000,
  D1 6,000,000, D2 6,500,000, D12 7,500,000). The amounts are typed below on purpose: the pin must
  not be derived from the very row it guards;
* A1 is a real ZERO: ``amount == 0`` is still an AVAILABLE quote that is built and carried in the
  decision, never collapsed into "no price";
* the same nine amounts are pinned END TO END: a real interview walk goes through the real
  ``run_evaluation`` (verify, compile, evaluate, price, seal, persist, project) and the quote must
  be in the SEALED decision, in the persisted decision and in the public response, with the
  display's row hash agreeing; a product that became unreachable, or a quote that dropped out,
  turns it red;
* the catalogue rows carry ONE all-inclusive IDR amount: structured fee fields (``pnbp``,
  ``government_fee``, ``service_fee``...) and split wording in client-visible fields are refused
  by a guard that has its own guilt twins;
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
    build_price_quote,
    resolve_candidate_pricing,
)
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_WALKS = Path(__file__).resolve().parent / "gold_coverage" / "fixtures" / "walks"
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


#: Every key a visit-family catalogue row may carry. A NEW key -- above all a fee component such as
#: ``pnbp`` / ``government_fee`` / ``service_fee`` -- is a structural split of the one all-inclusive
#: price and must fail until a human decides it should not.
_ROW_KEYS = frozenset(
    {
        "name",
        "price",
        "tier_range",
        "duration",
        "validity",
        "notes",
        "verified_on",
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

    Three independent shapes: an unknown (fee-component) key, a ``price`` that is not exactly one
    amount in IDR, and client-visible text that carries a second figure or names a PNBP/fee split.
    Wording that merely STATES inclusion ("the government fee is included", "No Bali Zero service
    fee") is not a split and stays innocent -- the existing A1 and B1 rows say exactly that.
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


#: code -> (real interview walk, by label, whose ENGINE decision names it). The walks are the
#: corpus the interview census replays, so the personas are the funnel's own, not invented here.
#: BRIDGING is the one product no public walk reaches (owner ruling D4: the funnel never asks
#: which permit is wanted); its witness is the census's own recipe -- an onshore OTHER-purpose
#: walk, current permit outside the visit class, requested product supplied at engine level.
_WALK_FOR: dict[str, str] = {
    "A1": "offshore/tourism/visa_free_30d",
    "B1": "offshore/tourism/voa_60d",
    "C1": "offshore/tourism/multiple_entry",
    "C2": "offshore/business/exploring",
    "C6": "offshore/other/no_paid_activity/medical",
    "BRIDGING": "onshore/other",
    "D1": "offshore/tourism/multiple_entry",
    "D2": "offshore/business/no_local_compensation",
    "D12": "offshore/invest/pt_pma/full_capital",
}
assert set(_WALK_FOR) == set(_PINS)


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
        assert _split_findings(row) == [], "the row must be ONE all-inclusive IDR amount"

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
    def test_the_quote_built_from_the_signed_product_carries_the_amount_and_the_key(
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
        """A1 costs IDR 0: still an AVAILABLE quote built from the signed product -- ``0`` is not ``None``."""

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


class TestNoFeeSplitGuard:
    """The all-inclusive rule is enforced by ``_split_findings``; the resolver does not enforce it.

    A row that grew ``pnbp`` / ``service_fee`` fields beside the unchanged price still resolves
    AVAILABLE at the same amount -- that is the counterexample, kept below as a witness, which is
    why the guard exists at all."""

    @pytest.mark.parametrize("code", _CODES)
    def test_innocence_every_real_visit_row_is_one_all_inclusive_amount(
        self, code: str, catalogue: dict[str, Any]
    ) -> None:
        key = _PINS[code][0]
        assert _split_findings(catalogue["services"][key.category][key.item_key]) == []

    @pytest.mark.parametrize("code", _CODES)
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
        key = _PINS[code][0]
        row = {**catalogue["services"][key.category][key.item_key], **extra}
        findings = _split_findings(row)
        assert findings and all("unknown key" in f for f in findings)

    @pytest.mark.parametrize("code", _CODES)
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
        key = _PINS[code][0]
        row = {**catalogue["services"][key.category][key.item_key], field: text}
        assert _split_findings(row), f"{field}={text!r} must be refused"

    @pytest.mark.parametrize(
        "price", ["1.000.000 + 1.300.000 IDR", "1.000.000 IDR + 1.300.000 IDR"]
    )
    def test_guilt_a_split_price_is_refused(self, price: str, catalogue: dict[str, Any]) -> None:
        key = _PINS["C1"][0]
        row = {**catalogue["services"][key.category][key.item_key], "price": price}
        assert "price is not one grouped IDR amount" in _split_findings(row)

    def test_witness_the_resolver_alone_does_not_see_a_split(
        self, signed: _SignedPack, catalogue: dict[str, Any]
    ) -> None:
        """The red-team counterexample, pinned: split fields beside the unchanged C1 price still
        quote AVAILABLE 2.300.000 -- only the guard above turns red on it."""

        key = _PINS["C1"][0]
        split = copy.deepcopy(catalogue)
        split["services"][key.category][key.item_key].update(pnbp=1_000_000, service_fee=1_300_000)
        resolution = _resolve(signed.products["C1"], _EditedCatalog(split), signed.signed_at)
        assert (resolution.status, resolution.amount) == ("AVAILABLE", 2_300_000)
        assert _split_findings(split["services"][key.category][key.item_key])


def _walk_facts(code: str) -> Any:
    """The applicant facts of the real walk that reaches ``code`` (BRIDGING: see ``_WALK_FOR``)."""

    label = _WALK_FOR[code]
    spec = _read_json(_WALKS / f"{label.replace('/', '_')}.json")
    assert spec["label"] == label
    overrides = copy.deepcopy(spec["overrides"])
    if code == "BRIDGING":
        overrides["immigration.current_status_code"] = {"status": "KNOWN", "value": "KITAS"}
        overrides["intent.purposes"] = {"status": "KNOWN", "value": ["OTHER"]}
        overrides["intent.requested_product_code"] = {"status": "KNOWN", "value": "C6"}
    persona = Persona(
        id=0, label=label, overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    return build_persona_request(persona).applicant_facts()


class _Persisted:
    def __init__(self) -> None:
        self.decisions: list[Any] = []


@pytest.fixture
def real_evaluate_path(monkeypatch: pytest.MonkeyPatch, signed: _SignedPack) -> _Persisted:
    """The real ``run_evaluation`` over the real signed pack and the real price catalogue.

    Only the three database touch-points are replaced (retention gate, active-pack binding,
    decision writer); the trust store is the repository's production key, the pack is verified
    and compiled by the real code, the decision is evaluated, priced, sealed and projected by it.
    """

    persisted = _Persisted()

    async def _binding(
        pool: object, *, environment: str, effective_at: datetime, observed_at: datetime
    ) -> shadow._PackBinding:
        return shadow._PackBinding(
            rule_pack_id=uuid.UUID(int=11),
            ruleset_activation_id=uuid.UUID(int=12),
            environment="PRODUCTION",
            raw_envelope=signed.envelope,
        )

    async def _save(pool: object, **kwargs: Any) -> None:
        persisted.decisions.append(kwargs["decision"])

    async def _retention(*args: object, **kwargs: object) -> bool:
        return True

    class _Trust:
        @staticmethod
        def from_env() -> Any:
            return _repository_trust_store()

    secret = base64.urlsafe_b64encode(b"\x01" * 32).rstrip(b"=").decode("ascii")
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "PRODUCTION")
    monkeypatch.setenv(
        "VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON",
        json.dumps(
            [
                {
                    "kid": "test-visit-pricing",
                    "secret": secret,
                    "environment": "PRODUCTION",
                    "valid_from": "2020-01-01T00:00:00+00:00",
                }
            ]
        ),
    )
    monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _binding)
    monkeypatch.setattr(evaluate_path, "_save_evaluate_decision", _save)
    monkeypatch.setattr(evaluate_path, "active_retention_policy_available", _retention)
    monkeypatch.setattr(evaluate_path, "StaticTrustStore", _Trust)
    return persisted


async def _evaluate(code: str, signed: _SignedPack) -> tuple[VisaOracleEvaluateResponse, Any]:
    body = await evaluate_path.run_evaluation(
        object(),
        facts=_walk_facts(code),
        traffic_source="real",
        request_category_hint=None,
        request_trace=f"visit-pricing-{code}",
        evaluation_time=signed.signed_at,
    )
    return VisaOracleEvaluateResponse.model_validate(body), body


class TestTheQuoteSurvivesTheWholeEvaluatePath:
    """A real interview walk -> ``run_evaluation`` -> sealed decision -> persisted row -> response."""

    @pytest.mark.parametrize("code", _CODES)
    async def test_the_walk_is_offered_the_product_at_the_pinned_amount(
        self, code: str, signed: _SignedPack, real_evaluate_path: _Persisted
    ) -> None:
        response, body = await _evaluate(code, signed)
        decision = response.decision
        assert decision.state is DecisionState.SUPPORTED_CANDIDATES
        assert decision.decision_integrity is not None, "the decision must be sealed"
        candidate = next((c for c in decision.candidates if c.product_code == code), None)
        assert candidate is not None, f"{code} is not offered by its own walk"
        quote = next((q for q in decision.quotes if q.product_code == code), None)
        assert quote is not None, f"{code} was offered but its quote is not in the response"
        assert (quote.status, quote.currency, quote.amount) == ("AVAILABLE", "IDR", _PINS[code][1])
        assert quote.pricing_key == _PINS[code][0]
        assert quote.product_version_id == candidate.product_version_id

        # persistence: the row written is the one quoted
        assert len(real_evaluate_path.decisions) == 1
        saved = next(q for q in real_evaluate_path.decisions[0].quotes if q.product_code == code)
        assert (saved.amount, saved.row_sha256) == (quote.amount, quote.row_sha256)

        # display: the candidate entry prices from the same catalogue row the quote carries
        entry = next(c for c in body["display"]["candidates"] if c["product_code"] == code)
        assert entry["pricing"]["status"] == "AVAILABLE"
        assert entry["pricing"]["row_sha256"] == quote.row_sha256

    @pytest.mark.parametrize("code", ["A1", "C1", "D12"])
    async def test_guilt_an_edited_row_moves_the_quote_the_response_carries(
        self,
        code: str,
        signed: _SignedPack,
        real_evaluate_path: _Persisted,
        catalogue: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bumped = _edited(catalogue, code, f"{_PINS[code][1] + 100_000:,} IDR".replace(",", "."))
        monkeypatch.setattr(evaluate_path, "get_pricing_service", lambda: _EditedCatalog(bumped))
        response, _ = await _evaluate(code, signed)
        quote = next(q for q in response.decision.quotes if q.product_code == code)
        assert quote.amount == _PINS[code][1] + 100_000
        assert quote.amount != _PINS[code][1]

    @pytest.mark.parametrize("code", ["A1", "C1", "D12"])
    async def test_guilt_a_row_rewritten_to_prose_drops_the_quote_from_the_response(
        self,
        code: str,
        signed: _SignedPack,
        real_evaluate_path: _Persisted,
        catalogue: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        prose = _edited(catalogue, code, "price on consultation")
        monkeypatch.setattr(evaluate_path, "get_pricing_service", lambda: _EditedCatalog(prose))
        response, body = await _evaluate(code, signed)
        assert all(q.product_code != code for q in response.decision.quotes)
        entry = next(c for c in body["display"]["candidates"] if c["product_code"] == code)
        assert entry["pricing"]["status"] == "CONTACT_REQUIRED"
