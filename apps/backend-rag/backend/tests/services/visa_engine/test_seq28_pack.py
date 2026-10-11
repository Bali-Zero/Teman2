"""Seq-28 fold gates: newest organ restamp plus the ruled E33 corrections.

Before the Sunday organ run, this suite builds a scratch candidate from the
newest ledger only after proving that ledger produced signed seq-27 from
signed seq-26.  Once a newer ledger is committed, the same fixture folds it
from seq-27 and compares the result with the committed seq-28 source.  Signed
bundle checks become active when the human ceremony adds the signed artifact.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import fold_pack_seq28 as fold_mod
from backend.scripts.visa_engine.fold_pack_generic import fold as generic_fold
from backend.scripts.visa_engine.fold_pack_seq25 import PORTAL_AUTHORITY, load_ledger
from backend.scripts.visa_engine.gold_replay_driver import (
    _offline_identity_provider,
    build_persona_request,
)
from backend.scripts.visa_engine.ledger_paths import read_receipt_text
from backend.scripts.visa_engine.review_hold_inventory import (
    pack_review_rules,
    pack_unknown_escalations,
)
from backend.services.visa_engine import evaluate_path, evaluator
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import DecisionState, RulePackPayload, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import resolve_candidate_pricing
from backend.tests.services.visa_engine import test_interview_walk_census as census
from backend.tests.services.visa_engine.gold_replay import _decision_actual
from backend.tests.services.visa_engine.test_evaluator_gold import (
    PERSONAS,
    Persona,
    production_replay_expectations_for_sequence,
)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_RESEARCH = _REPO_ROOT / "research/visa"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_SEQ26_SOURCE = _PACKS / "rulepack-prod-026.source.json"
_SEQ26_SIGNED = _PACKS / "rulepack-prod-026.signed.json"
_SEQ27_SOURCE = _PACKS / "rulepack-prod-027.source.json"
_SEQ27_SIGNED = _PACKS / "rulepack-prod-027.signed.json"
_SEQ28_SOURCE = _PACKS / "rulepack-prod-028.source.json"
_SEQ28_SIGNED = _PACKS / "rulepack-prod-028.signed.json"
_PORTAL_MAX_AGE = timedelta(seconds=2_764_800)
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
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _portals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in payload["source_records"] if r["authority_type"] == PORTAL_AUTHORITY]


def _rules(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rule["rule_id"]: rule for rule in payload["rules"]}


def _products(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {product["product_code"]: product for product in payload["products"]}


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


_UNKNOWN = {"status": "UNKNOWN", "reason": "NOT_ASKED"}


@pytest.fixture(scope="module", autouse=True)
def prod_trust_store_env() -> None:
    # pytest's process-local environment is restored by the runner after the
    # module; no private key is involved (this is the pinned public key).
    import os

    old = os.environ.get("VISA_ENGINE_TRUST_STORE_KEYS_JSON")
    os.environ["VISA_ENGINE_TRUST_STORE_KEYS_JSON"] = PROD_TRUST_STORE_JSON
    yield
    if old is None:
        os.environ.pop("VISA_ENGINE_TRUST_STORE_KEYS_JSON", None)
    else:
        os.environ["VISA_ENGINE_TRUST_STORE_KEYS_JSON"] = old


@pytest.fixture(scope="module")
def anchor() -> dict[str, Any]:
    return _read_json(_SEQ27_SOURCE)


@pytest.fixture(scope="module")
def anchor_signed() -> dict[str, Any]:
    return _read_json(_SEQ27_SIGNED)


@pytest.fixture(scope="module")
def newest_ledger() -> Path:
    return fold_mod.discover_newest_ledger(_RESEARCH)


@pytest.fixture(scope="module")
def folded(
    anchor: dict[str, Any],
    anchor_signed: dict[str, Any],
    newest_ledger: Path,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    catalogue = _read_json(_CATALOGUE)
    trust_store = StaticTrustStore.from_env()
    fetched = [
        datetime.fromisoformat(str(row["fetched_at"]).replace("Z", "+00:00"))
        for row in load_ledger(newest_ledger).receipts
    ]
    earliest, latest = min(fetched), max(fetched)
    observed_at = max(
        datetime.now(timezone.utc),
        latest + timedelta(days=1),
        datetime.fromisoformat(fold_mod.FOLD_CREATED_AT.replace("Z", "+00:00")) + timedelta(days=1),
    )

    if earliest > max(
        datetime.fromisoformat(r["verified_at"].replace("Z", "+00:00")) for r in _portals(anchor)
    ):
        expected = _read_json(_SEQ28_SOURCE)
        restamped = generic_fold(
            anchor,
            anchor_signed,
            load_ledger(newest_ledger),
            trust_store=trust_store,
            version=fold_mod.FOLD_VERSION,
            created_at=fold_mod.FOLD_CREATED_AT,
            created_by=fold_mod.FOLD_CREATED_BY,
            verified_by=fold_mod._portal_verified_by(expected),
            observed_at=observed_at,
            baseline_root=_RESEARCH,
            ledger_dir=newest_ledger,
        )
        candidate = fold_mod.apply_content_edits(restamped, catalogue)
        assert canonicalize_json(candidate) == canonicalize_json(expected)
        return restamped, candidate, "real"

    restamped, candidate = fold_mod.dry_run_from_anchor_ledger(
        anchor,
        anchor_signed,
        newest_ledger,
        catalogue,
        trust_store=trust_store,
        baseline_root=_RESEARCH,
        previous_source=_read_json(_SEQ26_SOURCE),
        previous_signed=_read_json(_SEQ26_SIGNED),
        observed_at=observed_at,
    )
    assert not _SEQ28_SOURCE.exists(), (
        "a committed seq-28 source exists but the newest ledger does not postdate seq-27"
    )
    return restamped, candidate, "dry-run"


@pytest.fixture(scope="module")
def restamped(folded: tuple[dict[str, Any], dict[str, Any], str]) -> dict[str, Any]:
    return folded[0]


@pytest.fixture(scope="module")
def seq28(folded: tuple[dict[str, Any], dict[str, Any], str]) -> dict[str, Any]:
    return folded[1]


@pytest.fixture(scope="module")
def candidate_path(tmp_path_factory: pytest.TempPathFactory, seq28: dict[str, Any]) -> Path:
    path = tmp_path_factory.mktemp("seq28-candidate") / "rulepack-prod-028.source.json"
    path.write_text(json.dumps(seq28, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def pack(candidate_path: Path) -> census.PackUnderTest:
    return census._pack_from_source(candidate_path)


def _decide(pack: census.PackUnderTest, overrides: dict[str, Any]) -> dict[str, Any]:
    request = build_persona_request(
        Persona(
            id=0,
            label="seq28-content-witness",
            overrides=overrides,
            expected_state=DecisionState.NEEDS_INPUT,
        )
    )
    facts = request.applicant_facts()
    decision = evaluator.evaluate(
        facts,
        pack.compiled,
        effective_at=pack.as_of,
        observed_at=pack.as_of,
        identity_provider=_offline_identity_provider,
    )
    decision = evaluate_path.apply_public_policy_adapters(
        decision,
        facts,
        pack.compiled,
        disclosed_review_flags=request.effective_review_flags(),
    )
    return _decision_actual(decision)


class _Catalog:
    loaded = True

    def __init__(self, catalogue: dict[str, Any]) -> None:
        self.catalogue = catalogue
        self.rows = catalogue["services"]["kitas_permits"]

    def get_service_by_key(self, key: str) -> dict[str, Any] | None:
        row = self.rows.get(key)
        return None if row is None else {**row, "category": "kitas_permits"}

    def get_all_prices(self) -> dict[str, Any]:
        return self.catalogue


class TestIntegrity:
    def test_chain_sequence_and_uuid5(self, seq28: dict[str, Any]) -> None:
        assert seq28["sequence"] == 28
        assert seq28["previous_payload_sha256"] == fold_mod.SEQ27_PAYLOAD_SHA256
        assert seq28["rollback_of_payload_sha256"] is None
        assert seq28["rule_pack_id"] == str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/28",
            )
        )
        assert (seq28["version"], seq28["created_at"], seq28["created_by"]) == (
            fold_mod.FOLD_VERSION,
            fold_mod.FOLD_CREATED_AT,
            fold_mod.FOLD_CREATED_BY,
        )

    def test_only_the_expected_paths_move(
        self, restamped: dict[str, Any], seq28: dict[str, Any], anchor: dict[str, Any]
    ) -> None:
        fold_mod.assert_only_expected_changes(restamped, seq28)
        fold_mod.assert_anchor_relative_changes(anchor, seq28)

    def test_non_portal_records_are_byte_identical(
        self, anchor: dict[str, Any], seq28: dict[str, Any]
    ) -> None:
        before = [r for r in anchor["source_records"] if r["authority_type"] != PORTAL_AUTHORITY]
        after = [r for r in seq28["source_records"] if r["authority_type"] != PORTAL_AUTHORITY]
        assert len(after) == 10
        assert canonicalize_json(before) == canonicalize_json(after)

    def test_portals_move_only_their_stamp(
        self, anchor: dict[str, Any], seq28: dict[str, Any], folded: tuple[Any, Any, str]
    ) -> None:
        before = {r["source_record_id"]: r for r in _portals(anchor)}
        after = {r["source_record_id"]: r for r in _portals(seq28)}
        assert set(before) == set(after) and len(after) == 18
        for record_id, record in after.items():
            moved = {key for key in record if record[key] != before[record_id][key]}
            if folded[2] == "real":
                assert moved == {"verified_at", "verified_by"}
            else:
                assert moved == set()

    def test_e31_duration_options_are_unchanged(
        self, anchor: dict[str, Any], seq28: dict[str, Any]
    ) -> None:
        before, after = _products(anchor), _products(seq28)
        for code in _E31:
            assert after[code]["duration_options"]
            assert after[code] == before[code]

    def test_boundary_is_stamp_plus_2764800_seconds(self, seq28: dict[str, Any]) -> None:
        stamps = {
            datetime.fromisoformat(record["verified_at"].replace("Z", "+00:00"))
            for record in _portals(seq28)
        }
        assert len(stamps) == 1
        stamp = next(iter(stamps))
        assert stamp + _PORTAL_MAX_AGE > stamp
        assert _PORTAL_MAX_AGE.total_seconds() == 2_764_800

    def test_model_validates(self, seq28: dict[str, Any]) -> None:
        payload = RulePackPayload.model_validate(seq28)
        assert payload.sequence == 28
        assert len(payload.rules) == 114


class TestLedger:
    def test_one_clean_receipt_and_one_judgement_per_portal(
        self, newest_ledger: Path, anchor: dict[str, Any]
    ) -> None:
        ledger = load_ledger(newest_ledger)
        portal_ids = {r["source_record_id"] for r in _portals(anchor)}
        assert Counter(row["source_record_id"] for row in ledger.receipts) == Counter(portal_ids)
        assert Counter(row["source_record_id"] for row in ledger.judgements) == Counter(portal_ids)
        by_id = {row["source_record_id"]: row for row in ledger.receipts}
        for judgement in ledger.judgements:
            receipt = by_id[judgement["source_record_id"]]
            assert receipt["http_status"] == 200
            assert receipt["key_phrase_found"] is True
            assert receipt["canonical_url"] == receipt["final_url"]
            assert judgement["judged_at"] >= receipt["fetched_at"]
            # A fingerprint row is marked ``judge: fingerprint``; a page whose visible
            # text moved against the baseline carries no marker and is a model verdict
            # (the 2026-10-11 ledger has exactly one: the Bridging page).
            assert judgement.get("judge", "model") in {"fingerprint", "model"}
            if "judge" not in judgement:
                assert judgement["semantic_change"] == "none"

    def test_stamp_is_the_earliest_successful_read(
        self, newest_ledger: Path, seq28: dict[str, Any]
    ) -> None:
        ledger = load_ledger(newest_ledger)
        stamp = min(row["fetched_at"] for row in ledger.receipts)
        if min(row["fetched_at"] for row in ledger.receipts) > max(
            r["verified_at"] for r in _portals(_read_json(_SEQ27_SOURCE))
        ):
            assert {r["verified_at"] for r in _portals(seq28)} == {stamp}
        else:
            assert {r["verified_at"] for r in _portals(seq28)} == {
                r["verified_at"] for r in _portals(_read_json(_SEQ27_SOURCE))
            }

    def test_saved_texts_carry_their_receipt_fingerprints(self, newest_ledger: Path) -> None:
        ledger = load_ledger(newest_ledger)
        assert ledger.text_dir is not None
        for receipt in ledger.receipts:
            text = read_receipt_text(ledger.text_dir, receipt)
            body = text[:-1] if text.endswith("\n") else text
            assert (
                hashlib.sha256(body.encode("utf-8")).hexdigest() == receipt["visible_text_sha256"]
            )

    def test_fold_reproduces_the_candidate(
        self, restamped: dict[str, Any], seq28: dict[str, Any]
    ) -> None:
        rebuilt = fold_mod.apply_content_edits(restamped, _read_json(_CATALOGUE))
        assert canonicalize_json(rebuilt) == canonicalize_json(seq28)

    def test_guilt_missing_receipt_is_refused(
        self,
        newest_ledger: Path,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        seq28: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        copy_dir = tmp_path / "ledger"
        shutil.copytree(newest_ledger, copy_dir)
        receipts_path = next(copy_dir.glob("*-receipts.jsonl"))
        lines = receipts_path.read_text(encoding="utf-8").splitlines()
        receipts_path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
        with pytest.raises(SystemExit):
            generic_fold(
                anchor,
                anchor_signed,
                load_ledger(copy_dir),
                trust_store=StaticTrustStore.from_env(),
                version=fold_mod.FOLD_VERSION,
                created_at=fold_mod.FOLD_CREATED_AT,
                created_by=fold_mod.FOLD_CREATED_BY,
                verified_by=fold_mod._portal_verified_by(seq28),
                observed_at=datetime.now(timezone.utc) + timedelta(days=2),
                baseline_root=_RESEARCH,
                ledger_dir=copy_dir,
            )


class TestContent:
    def test_e33e_resolves_to_45m_and_sibling_keys_stay_put(
        self, anchor: dict[str, Any], seq28: dict[str, Any]
    ) -> None:
        catalogue = _read_json(_CATALOGUE)
        before, after = _products(anchor), _products(seq28)
        product = VisaProductVersion.model_validate(after["E33E"])
        resolution = resolve_candidate_pricing(
            product,
            pricing_catalog=_Catalog(catalogue),
            evaluated_at=datetime(2026, 10, 12, tzinfo=timezone.utc),
        )
        assert resolution.amount == 45_000_000
        assert after["E33E"]["pricing_key"] == {
            "category": "kitas_permits",
            "item_key": fold_mod.E33E_PRICE_ITEM_KEY,
        }
        assert "duration_options" not in after["E33E"]
        assert "Retirement (Offshore)" in catalogue["services"]["kitas_permits"]
        for code in ("E33", "E33F", "E33G"):
            assert after[code]["pricing_key"] == before[code]["pricing_key"]

    @pytest.mark.parametrize(
        "overrides",
        [
            {
                "intent.purposes": _known(["BUSINESS_MEETINGS"]),
                "person.birth_date": _known("1990-01-01"),
            },
            PERSONAS[0].overrides,
        ],
    )
    def test_age_below_55_does_not_leak_outside_retirement(
        self, pack: census.PackUnderTest, overrides: dict[str, Any]
    ) -> None:
        assert "AGE_BELOW_55" not in _decide(pack, overrides)["no_path_reason_codes"]

    @pytest.mark.parametrize("persona_id", [1, 3, 4])
    def test_gold_personas_1_3_4_match_the_seq28_rederivation(
        self, pack: census.PackUnderTest, persona_id: int
    ) -> None:
        persona = PERSONAS[persona_id - 1]
        actual = _decide(pack, persona.overrides)
        expected = production_replay_expectations_for_sequence(28)[persona_id]
        assert actual["state"] == expected.state.value
        assert tuple(actual["no_path_reason_codes"]) == expected.no_path_codes

    def test_retirement_age_54_is_excluded(self, pack: census.PackUnderTest) -> None:
        actual = _decide(
            pack,
            {
                "intent.purposes": _known(["RETIREMENT"]),
                "person.birth_date": _known("1972-01-01"),
                "secondhome.bank_deposit_usd": _known(60_000),
                "secondhome.bank_deposit_at_state_bank": _known(True),
                "secondhome.bank_deposit_in_own_name": _known(True),
                "secondhome.passive_monthly_income_usd": _known(3_500),
            },
        )
        assert "AGE_BELOW_55" in actual["no_path_reason_codes"]

    @pytest.mark.parametrize("birth_date", ["1971-01-01", "1966-01-01"])
    def test_retirement_55_and_60_return_e33e_and_e33f(
        self, pack: census.PackUnderTest, birth_date: str
    ) -> None:
        actual = _decide(
            pack,
            {
                "intent.purposes": _known(["RETIREMENT"]),
                "person.birth_date": _known(birth_date),
                "secondhome.bank_deposit_usd": _known(60_000),
                "secondhome.bank_deposit_at_state_bank": _known(True),
                "secondhome.bank_deposit_in_own_name": _known(True),
                "secondhome.passive_monthly_income_usd": _known(3_500),
            },
        )
        assert actual["state"] == "SUPPORTED_CANDIDATES"
        assert actual["candidates"] == ["E33E", "E33F"]

    def test_second_home_age_62_does_not_open_retirement_products(
        self, pack: census.PackUnderTest
    ) -> None:
        actual = _decide(
            pack,
            {
                "intent.purposes": _known(["SECOND_HOME"]),
                "person.birth_date": _known("1964-01-01"),
                "secondhome.bank_deposit_usd": _known(60_000),
                "secondhome.bank_deposit_at_state_bank": _known(True),
                "secondhome.bank_deposit_in_own_name": _known(True),
            },
        )
        assert not {"E33E", "E33F"}.intersection(actual["candidates"])

    @pytest.mark.parametrize(
        ("income", "state", "candidates", "reason", "missing"),
        [
            (60_000, "SUPPORTED_CANDIDATES", ["E33G"], None, []),
            (59_999, "NO_SUPPORTED_PATH", [], "E33G_INCOME_BELOW_THRESHOLD", []),
            (None, "NEEDS_INPUT", [], None, [fold_mod.E33G_ANNUAL_INCOME_FACT]),
        ],
    )
    def test_e33g_income_boundary(
        self,
        pack: census.PackUnderTest,
        income: int | None,
        state: str,
        candidates: list[str],
        reason: str | None,
        missing: list[str],
    ) -> None:
        overrides = {
            "intent.purposes": _known(["REMOTE_WORK"]),
            "work.employer_is_indonesian_entity": _known(False),
            "work.serves_indonesian_clients": _known(False),
            "work.indonesia_source_compensation": _known(False),
            fold_mod.E33G_ANNUAL_INCOME_FACT: _UNKNOWN if income is None else _known(income),
        }
        actual = _decide(pack, overrides)
        assert actual["state"] == state
        assert actual["candidates"] == candidates
        assert actual["missing_facts"] == missing
        if reason is not None:
            assert reason in actual["no_path_reason_codes"]

    def test_tourism_income_zero_is_unchanged_from_seq27(
        self, pack: census.PackUnderTest, tmp_path: Path
    ) -> None:
        old_pack = census._pack_from_source(_SEQ27_SOURCE)
        overrides = {
            "intent.purposes": _known(["TOURISM"]),
            fold_mod.E33G_ANNUAL_INCOME_FACT: _known(0),
        }
        assert _decide(pack, overrides) == _decide(old_pack, overrides)

    def test_hard_filter_lt_equals_eligibility_gte(self, seq28: dict[str, Any]) -> None:
        rules = _rules(seq28)
        eligibility = rules[fold_mod.E33G_ELIGIBILITY_RULE_ID]
        hard_filter = rules[fold_mod.E33G_INCOME_FILTER_RULE_ID]
        gte = next(
            node["value"]
            for node in eligibility["when"]["args"]
            if node.get("op") == "gte" and node.get("fact") == fold_mod.E33G_ANNUAL_INCOME_FACT
        )
        lt = next(
            node["value"]
            for node in hard_filter["when"]["args"]
            if node.get("op") == "lt" and node.get("fact") == fold_mod.E33G_ANNUAL_INCOME_FACT
        )
        assert lt == gte == 60_000

    def test_review_inventory_is_studio_only(self, seq28: dict[str, Any]) -> None:
        payload = RulePackPayload.model_validate(seq28)
        assert [row.rule_id for row in pack_review_rules(payload)] == [
            "review.e33.below-threshold-studio"
        ]
        assert pack_unknown_escalations(payload) == ()


class TestSignedBundleTiesToSource:
    def _signed_or_skip(self) -> dict[str, Any]:
        if not _SEQ28_SIGNED.exists():
            pytest.skip("seq-28 is intentionally unsigned until the separate human ceremony")
        return _read_json(_SEQ28_SIGNED)

    def test_jcs_payload_equals_source(self, seq28: dict[str, Any]) -> None:
        signed = self._signed_or_skip()
        assert canonicalize_json(signed["payload"]) == canonicalize_json(seq28)

    def test_verifies_under_the_pinned_prod_key(self) -> None:
        signed = self._signed_or_skip()
        verified = verify_rule_pack(
            signed,
            trust_store=StaticTrustStore.from_env(),
            observed_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert verified.pack.protected.kid == "prod-2026-07-1"
        assert verified.pack.payload.sequence == 28

    def test_anchor_is_seq27_digest(self) -> None:
        signed = self._signed_or_skip()
        assert signed["payload"]["previous_payload_sha256"] == fold_mod.SEQ27_PAYLOAD_SHA256

    def test_guilt_one_flipped_byte_breaks_signature(self) -> None:
        signed = copy.deepcopy(self._signed_or_skip())
        signed["payload"]["created_by"] += "x"
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                signed,
                trust_store=StaticTrustStore.from_env(),
                observed_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
