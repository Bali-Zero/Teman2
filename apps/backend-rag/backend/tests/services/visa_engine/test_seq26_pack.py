"""seq-26 — the E31 family ITAS is a 1- OR 2-year duration option of the same product.

Proves, each with a guilt twin where one exists:

* seq-26 chains to the SIGNED seq-25 and moves only the E31 products' duration modelling;
* every option comes from a saved portal page that says "1 tahun atau 2 tahun" and from a
  catalogue row that exists, with the same Onshore/Offshore variant as the 1-year key;
* the evaluator picks 365, 730 and 730 (extension required) for 365, 730 and 1095 days,
  and prices each pick from its own catalogue row;
* the committed source is what the derivation script produces.

A missing artifact FAILS (``_read_json``), it never skips.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import derive_seq26_e31_options as derive_mod
from backend.scripts.visa_engine.derive_seq26_e31_options import (
    FOLD_CREATED_BY,
    FOLD_VERSION,
    SEQ25_PAYLOAD_SHA256,
    derive,
    portal_text_for,
    rule_pack_id,
)
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.evaluate_path import _duration_display
from backend.services.visa_engine.models import RulePackPayload, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import (
    effective_pricing_key,
    resolve_candidate_pricing,
    select_duration_option,
)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_SEQ25_SOURCE = _PACKS / "rulepack-prod-025.source.json"
_SEQ25_SIGNED = _PACKS / "rulepack-prod-025.signed.json"
_SEQ26_SOURCE = _PACKS / "rulepack-prod-026.source.json"
_LEDGER = _REPO_ROOT / "research/visa/2026-10-07-freshness-restamp-seq25"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_STAMP = "2026-10-07T13:32:18Z"
_NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
_E31 = ["E31A", "E31B", "E31C", "E31D", "E31E", "E31F", "E31G", "E31H", "E31J"]
PROD_TRUST_STORE_JSON = json.dumps(
    [
        {
            "kid": "prod-2026-07-1",
            "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",
            "environment": "PRODUCTION",
            "valid_from": "2026-07-19T00:00:00Z",
            "valid_to": None,
            "revoked_at": None,
        }
    ]
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk — a witness that never ran proves nothing"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq25() -> dict[str, Any]:
    return _read_json(_SEQ25_SOURCE)


@pytest.fixture(scope="module")
def seq26() -> dict[str, Any]:
    return _read_json(_SEQ26_SOURCE)


@pytest.fixture(scope="module")
def catalogue() -> dict[str, Any]:
    return _read_json(_CATALOGUE)


def _products(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["product_code"]: p for p in pack["products"]}


def _idr(catalogue: dict[str, Any], item_key: str) -> int:
    return int(
        catalogue["services"]["kitas_permits"][item_key]["price"].split()[0].replace(".", "")
    )


class _Catalog:
    loaded = True

    def __init__(self, catalogue: dict[str, Any]) -> None:
        self._rows = catalogue["services"]["kitas_permits"]
        self._catalogue = catalogue

    def get_service_by_key(self, key: str) -> dict[str, Any] | None:
        row = self._rows.get(key)
        return None if row is None else {**row, "category": "kitas_permits"}

    def get_all_prices(self) -> dict[str, Any]:
        return {
            "version": self._catalogue["version"],
            "metadata": self._catalogue["metadata"],
            "services": self._rows,
        }


class TestIntegrity:
    def test_chain_and_identity(self, seq25: dict[str, Any], seq26: dict[str, Any]) -> None:
        assert hashlib.sha256(canonicalize_json(seq25)).hexdigest() == SEQ25_PAYLOAD_SHA256
        assert seq26["sequence"] == 26
        assert seq26["previous_payload_sha256"] == SEQ25_PAYLOAD_SHA256
        assert seq26["rollback_of_payload_sha256"] is None
        assert seq26["rule_pack_id"] == str(rule_pack_id(26))
        assert rule_pack_id(26) == uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/26",
        )
        assert (seq26["version"], seq26["created_by"]) == (FOLD_VERSION, FOLD_CREATED_BY)
        assert datetime.strptime(seq26["created_at"], "%Y-%m-%dT%H:%M:%SZ") > datetime.strptime(
            seq25["created_at"], "%Y-%m-%dT%H:%M:%SZ"
        )

    def test_the_anchor_is_the_signed_seq25(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)
        verified = verify_rule_pack(
            _read_json(_SEQ25_SIGNED),
            trust_store=StaticTrustStore.from_env(),
            observed_at=_NOW,
        )
        assert verified.payload_sha256.hex() == SEQ25_PAYLOAD_SHA256
        assert verified.pack.payload.sequence == 25

    def test_rules_and_every_source_record_are_untouched(
        self, seq25: dict[str, Any], seq26: dict[str, Any]
    ) -> None:
        assert canonicalize_json({"r": seq26["rules"]}) == canonicalize_json({"r": seq25["rules"]})
        assert canonicalize_json({"s": seq26["source_records"]}) == canonicalize_json(
            {"s": seq25["source_records"]}
        )
        portal_stamps = {
            r["verified_at"]
            for r in seq26["source_records"]
            if r["authority_type"] == "OFFICIAL_PORTAL"
        }
        assert portal_stamps == {_STAMP}

    def test_only_the_identity_fields_and_the_products_move(
        self, seq25: dict[str, Any], seq26: dict[str, Any]
    ) -> None:
        moved = {k for k in seq25 if seq25[k] != seq26[k]}
        assert moved == {
            "version",
            "products",
            "sequence",
            "created_at",
            "created_by",
            "rule_pack_id",
            "previous_payload_sha256",
        }

    def test_only_the_e31_products_move_and_only_in_their_duration_fields(
        self, seq25: dict[str, Any], seq26: dict[str, Any]
    ) -> None:
        before, after = _products(seq25), _products(seq26)
        assert set(before) == set(after)
        for code, old in before.items():
            new = copy.deepcopy(after[code])
            if code in _E31:
                new.pop("duration_options")
                new["stay_policy"]["maximum_days"] = old["stay_policy"]["maximum_days"]
            assert canonicalize_json(new) == canonicalize_json(old), code
        moved = {c for c in before if before[c] != after[c]}
        assert moved == set(_E31)

    def test_the_payload_validates_and_loads_as_a_pack(self, seq26: dict[str, Any]) -> None:
        payload = RulePackPayload.model_validate(seq26)
        assert sum(1 for p in payload.products if p.duration_options) == len(_E31)

    def test_no_pnbp_figure_or_word_in_client_facing_names(self, seq26: dict[str, Any]) -> None:
        for code in _E31:
            names = json.dumps(_products(seq26)[code]["names"]).lower()
            assert "pnbp" not in names

    def test_the_committed_source_is_what_the_derivation_produces(
        self, seq25: dict[str, Any], seq26: dict[str, Any], catalogue: dict[str, Any]
    ) -> None:
        derived = derive(seq25, catalogue, _LEDGER)
        assert canonicalize_json(derived) == canonicalize_json(seq26)


class TestPerProduct:
    @pytest.mark.parametrize("code", _E31)
    def test_options_pages_and_catalogue_agree(
        self, code: str, seq26: dict[str, Any], catalogue: dict[str, Any]
    ) -> None:
        product = _products(seq26)[code]
        assert portal_text_for(product, _LEDGER) is not None, (
            f"{code}: no saved page says 1 or 2 years"
        )
        options = product["duration_options"]
        assert [o["days"] for o in options] == [365, 730]
        assert options[0]["pricing_key"] == product["pricing_key"]
        one, two = options[0]["pricing_key"]["item_key"], options[1]["pricing_key"]["item_key"]
        assert two == one.replace("1 Year", "2 Years")
        assert ("Offshore" in one) == ("Offshore" in two)
        rows = catalogue["services"]["kitas_permits"]
        assert one in rows and two in rows
        assert _idr(catalogue, two) > _idr(catalogue, one)
        assert product["stay_policy"] == {
            "kind": "FIXED_DAYS",
            "minimum_days": 365,
            "maximum_days": 730,
        }

    @pytest.mark.parametrize("code", _E31)
    @pytest.mark.parametrize(
        ("stay_days", "selected", "extension"),
        [
            (365, 365, False),
            (366, 730, False),
            (730, 730, False),
            (1095, 730, True),
            (None, 365, False),
        ],
    )
    def test_selection_price_and_extension(
        self,
        code: str,
        stay_days: int | None,
        selected: int,
        extension: bool,
        seq26: dict[str, Any],
        catalogue: dict[str, Any],
    ) -> None:
        product = VisaProductVersion.model_validate(_products(seq26)[code])
        option = select_duration_option(product, stay_days)
        assert option is not None and option.days == selected
        resolution = resolve_candidate_pricing(
            product, pricing_catalog=_Catalog(catalogue), evaluated_at=_NOW, stay_days=stay_days
        )
        assert resolution.amount == _idr(catalogue, option.pricing_key.item_key)
        assert effective_pricing_key(product, stay_days) == option.pricing_key
        shown = _duration_display(
            product, stay_days=stay_days, pricing_catalog=_Catalog(catalogue), evaluated_at=_NOW
        )
        assert shown["selected_duration_days"] == selected
        assert shown["extension_required"] is extension

    def test_the_two_year_price_is_never_the_one_year_price(
        self, seq26: dict[str, Any], catalogue: dict[str, Any]
    ) -> None:
        for code in _E31:
            product = VisaProductVersion.model_validate(_products(seq26)[code])
            cat = _Catalog(catalogue)
            one = resolve_candidate_pricing(
                product, pricing_catalog=cat, evaluated_at=_NOW, stay_days=365
            )
            two = resolve_candidate_pricing(
                product, pricing_catalog=cat, evaluated_at=_NOW, stay_days=730
            )
            assert (one.amount, two.amount) == (11_000_000, 15_000_000), code

    def test_e31a_ambiguity_is_cured(self, seq25: dict[str, Any], seq26: dict[str, Any]) -> None:
        old = _products(seq25)["E31A"]
        assert old["stay_policy"]["maximum_days"] == 730 and "duration_options" not in old
        new = _products(seq26)["E31A"]
        assert new["duration_options"][1]["pricing_key"]["item_key"] == "Spouse 2 Years (Offshore)"


class TestDerivationRefuses:
    def test_a_product_whose_page_does_not_say_two_years_gets_no_option(
        self, seq25: dict[str, Any], catalogue: dict[str, Any], tmp_path: Path
    ) -> None:
        ledger = tmp_path / "ledger"
        shutil.copytree(_LEDGER, ledger)
        product = _products(seq25)["E31B"]
        for source_id in product["source_refs"]:
            text = ledger / "text" / f"{source_id[:8]}.txt"
            if text.exists():
                text.write_text("Visa keluarga selama 1 tahun.", encoding="utf-8")
        derived = derive(seq25, catalogue, ledger)
        assert "duration_options" not in _products(derived)["E31B"]
        assert "duration_options" in _products(derived)["E31C"]

    def test_a_missing_two_year_sibling_aborts(
        self, seq25: dict[str, Any], catalogue: dict[str, Any]
    ) -> None:
        broken = copy.deepcopy(catalogue)
        del broken["services"]["kitas_permits"]["Dependent 2 Years (Offshore)"]
        with pytest.raises(SystemExit, match="sibling .* is missing"):
            derive(seq25, broken, _LEDGER)

    def test_an_anchor_that_is_not_the_signed_seq25_aborts(
        self, seq25: dict[str, Any], catalogue: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq25)
        tampered["version"] = "2026.10.7-x"
        with pytest.raises(SystemExit, match="not the signed artifact"):
            derive(tampered, catalogue, _LEDGER)

    def test_a_created_at_in_the_future_aborts(
        self, seq25: dict[str, Any], catalogue: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(derive_mod, "FOLD_CREATED_AT", "2999-01-01T00:00:00Z")
        with pytest.raises(SystemExit, match="in the future"):
            derive(seq25, catalogue, _LEDGER)


class TestGoldFamilyPersonasAskForTwoYears:
    """Gold personas 6 (minor child) and 7 (spouse) are the canonical E31 walks. They are run
    through the real evaluator on the unsigned seq-26 candidate, with a stay of 12, 24 and 36
    months added, because the 20-persona corpus is pinned by spec and replays the highest
    SIGNED pack, which seq-26 is not yet."""

    @staticmethod
    def _candidate_prices(
        overrides: dict[str, Any], stay_days: int, label: str, catalogue: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        from backend.tests.services.visa_engine import _gold_fixtures as gf
        from backend.tests.services.visa_engine import test_interview_walk_census as census

        pack = census._candidate_pack()
        assert pack is not None, "seq-26 is the unsigned candidate above the highest signed pack"
        decision, compiled, _ = census._decide(
            {**overrides, "intent.stay_days": gf.known(stay_days)}, label, pack=pack
        )
        products = {p.product_version_id: p for p in compiled.source_pack.payload.products}
        shown: dict[str, dict[str, Any]] = {}
        for candidate in decision.candidates:
            product = products[candidate.product_version_id]
            if not product.duration_options:
                continue
            row = _duration_display(
                product, stay_days=stay_days, pricing_catalog=_Catalog(catalogue), evaluated_at=_NOW
            )
            shown[str(candidate.product_code)] = row
        return shown

    @pytest.mark.parametrize("persona_index", [5, 6])
    @pytest.mark.parametrize(
        ("stay_days", "selected", "amount", "extension"),
        [
            (365, 365, 11_000_000, False),
            (730, 730, 15_000_000, False),
            (1095, 730, 15_000_000, True),
        ],
    )
    def test_an_e31_candidate_carries_the_requested_duration_and_its_own_price(
        self,
        persona_index: int,
        stay_days: int,
        selected: int,
        amount: int,
        extension: bool,
        catalogue: dict[str, Any],
    ) -> None:
        from backend.tests.services.visa_engine import test_evaluator_gold as gold

        persona = gold.PERSONAS[persona_index]
        shown = self._candidate_prices(
            persona.overrides, stay_days, f"gold-{persona.id}", catalogue
        )
        assert shown, (
            f"persona {persona.id} lost its E31 candidate when a {stay_days}-day stay was asked"
        )
        for code, row in shown.items():
            assert code.startswith("E31")
            assert row["selected_duration_days"] == selected
            assert row["extension_required"] is extension
            picked = next(o for o in row["duration_options"] if o["selected"])
            assert picked["amount_idr"] == amount
