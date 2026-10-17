"""Seq-31 fold gates: the E28A own-shareholding re-key (owner ruling 1 of 2026-10-15, SEQ29-A1).

Chained on verified signed ``seq-30`` (``rulepack-prod-030.signed.json``, payload SHA-256
``972f339283e6a66962f3dd8f4dbb1c4a5014c5b16352234e425abfed988df413``).

The tests in ``TestSignedBundleTiesToSource`` need ``rulepack-prod-031.signed.json``; until the
owner signs the candidate they skip, and they run unchanged once the bundle exists.  Every other
test grades the unsigned source.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import fold_pack_seq28 as seq28_mod
from backend.scripts.visa_engine import fold_pack_seq31 as fold_mod
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload
from backend.tests.services.visa_engine import test_interview_walk_census as census
from backend.tests.services.visa_engine.test_seq28_pack import (
    PROD_TRUST_STORE_JSON,
    _decide,
    _known,
    _portals,
    _read_json,
    _rules,
)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_PERSONAS = Path(__file__).resolve().parent / "gold_coverage" / "personas"
_SEQ30_SOURCE = _PACKS / "rulepack-prod-030.source.json"
_SEQ30_SIGNED = _PACKS / "rulepack-prod-030.signed.json"
_SEQ31_SOURCE = _PACKS / "rulepack-prod-031.source.json"
_SEQ31_SIGNED = _PACKS / "rulepack-prod-031.signed.json"
_UNKNOWN = {"status": "UNKNOWN", "reason": "NOT_ASKED"}
_OWN = "investment.own_shareholding_idr"
_CAPITAL = "investment.investment_capital_idr"
_PAID_UP = "investment.paid_up_capital_idr"
_REASON = "E28A_OWN_SHAREHOLDING_BELOW_MIN"
_OLD_REASON = "E28A_TOTAL_INVESTMENT_BELOW_MIN"

requires_signed = pytest.mark.skipif(
    not _SEQ31_SIGNED.is_file(),
    reason="rulepack-prod-031.signed.json is signed by the owner after the gates",
)


@pytest.fixture(scope="module", autouse=True)
def prod_trust_store_env() -> None:
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
    return _read_json(_SEQ30_SOURCE)


@pytest.fixture(scope="module")
def anchor_signed() -> dict[str, Any]:
    return _read_json(_SEQ30_SIGNED)


@pytest.fixture(scope="module")
def seq31() -> dict[str, Any]:
    return _read_json(_SEQ31_SOURCE)


@pytest.fixture(scope="module")
def folded(
    anchor: dict[str, Any], anchor_signed: dict[str, Any], seq31: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    return fold_mod.fold_from_signed_seq30(
        anchor,
        anchor_signed,
        trust_store=StaticTrustStore.from_env(),
        created_at=str(seq31["created_at"]),
        created_by=str(seq31["created_by"]),
    )


@pytest.fixture(scope="module")
def restamped(folded: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    return folded[0]


@pytest.fixture(scope="module")
def pack(seq31: dict[str, Any], tmp_path_factory: pytest.TempPathFactory) -> census.PackUnderTest:
    path = tmp_path_factory.mktemp("seq31-candidate") / "rulepack-prod-031.source.json"
    path.write_text(json.dumps(seq31, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return census._pack_from_source(path)


@pytest.fixture(scope="module")
def old_pack() -> census.PackUnderTest:
    return census._pack_from_source(_SEQ30_SOURCE)


class TestCommittedSourceMatchesFold:
    def test_committed_seq31_source_is_byte_for_byte_the_fold_output(
        self, folded: tuple[dict[str, Any], dict[str, Any]], seq31: dict[str, Any]
    ) -> None:
        _, out = folded
        assert canonicalize_json(out) == canonicalize_json(seq31), (
            "the committed seq-31 source is not what fold_pack_seq31 produces; "
            "rerun the fold, never edit it by hand"
        )

    def test_cli_check_passes_on_the_committed_source(self) -> None:
        assert fold_mod.main(["--check"]) == 0


class TestPackIntegrity:
    def test_chain_sequence_and_uuid5(self, seq31: dict[str, Any], anchor: dict[str, Any]) -> None:
        assert seq31["sequence"] == 31
        assert anchor["sequence"] == 30
        assert seq31["version"] == fold_mod.FOLD_VERSION
        assert seq31["previous_payload_sha256"] == fold_mod.SEQ30_PAYLOAD_SHA256
        assert (
            hashlib.sha256(canonicalize_json(anchor)).hexdigest() == fold_mod.SEQ30_PAYLOAD_SHA256
        )
        assert seq31["rollback_of_payload_sha256"] is None
        assert seq31["rule_pack_id"] == str(seq28_mod._rule_pack_id(31))

    def test_created_at_is_a_past_instant_so_the_signer_chronology_check_holds(
        self, seq31: dict[str, Any], anchor: dict[str, Any]
    ) -> None:
        created = datetime.fromisoformat(seq31["created_at"].replace("Z", "+00:00"))
        assert created <= datetime.now(timezone.utc)
        assert created > datetime.fromisoformat(anchor["created_at"].replace("Z", "+00:00"))
        assert seq31["created_at"] == fold_mod.FOLD_CREATED_AT

    def test_only_expected_paths_move(
        self, restamped: dict[str, Any], seq31: dict[str, Any], anchor: dict[str, Any]
    ) -> None:
        fold_mod.assert_only_expected_changes(restamped, seq31)
        fold_mod.assert_anchor_relative_changes(anchor, seq31)

    def test_all_source_records_are_byte_identical_to_seq30(
        self, anchor: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        assert canonicalize_json(anchor["source_records"]) == canonicalize_json(
            seq31["source_records"]
        )
        assert len(_portals(seq31)) == 18
        assert len(seq31["source_records"]) == 28

    def test_every_non_rule_key_other_than_identity_is_identical(
        self, anchor: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        moved = {
            key for key in anchor if canonicalize_json(anchor[key]) != canonicalize_json(seq31[key])
        }
        assert moved == {
            "version",
            "sequence",
            "created_at",
            "created_by",
            "rule_pack_id",
            "previous_payload_sha256",
            "rules",
        }
        assert canonicalize_json(anchor["products"]) == canonicalize_json(seq31["products"])
        assert len(seq31["products"]) == 38

    def test_model_validates(self, seq31: dict[str, Any]) -> None:
        assert RulePackPayload.model_validate(seq31).sequence == 31

    def test_every_rule_source_ref_and_product_id_resolves(self, seq31: dict[str, Any]) -> None:
        source_ids = {r["source_record_id"] for r in seq31["source_records"]}
        product_ids = {p["product_version_id"] for p in seq31["products"]}
        for rule_id, rule in _rules(seq31).items():
            assert set(rule["source_refs"]) <= source_ids, rule_id
            if rule["product_version_ids"] is not None:
                assert set(rule["product_version_ids"]) <= product_ids, rule_id


class TestExactRuleDiff:
    def test_one_modified_one_retired_one_inserted_and_nothing_else(
        self, anchor: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        before, after = _rules(anchor), _rules(seq31)
        assert set(before) - set(after) == {"hf.e28a.total-investment-below-min"}
        assert set(after) - set(before) == {"hf.e28a.own-shareholding-below-min"}
        changed = {rid for rid in set(before) & set(after) if before[rid] != after[rid]}
        assert changed == {"el.e28a.investment"}
        assert len(before) == len(after) == 118

    def test_rule_order_retires_in_place_and_appends_the_new_rule(
        self, anchor: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        before = [r["rule_id"] for r in anchor["rules"]]
        after = [r["rule_id"] for r in seq31["rules"]]
        assert after == [
            *(rid for rid in before if rid != "hf.e28a.total-investment-below-min"),
            "hf.e28a.own-shareholding-below-min",
        ]

    def test_eligibility_rule_is_rekeyed_to_own_shareholding_and_nothing_else(
        self, anchor: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        before = _rules(anchor)["el.e28a.investment"]
        after = _rules(seq31)["el.e28a.investment"]
        assert after["when"] == {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["INVESTMENT"]},
                {"op": "eq", "fact": "investment.pt_pma_committed", "value": True},
                {"op": "gte", "fact": _PAID_UP, "value": 2_500_000_000},
                {"op": "gte", "fact": _OWN, "value": 10_000_000_000},
            ],
        }
        assert after["required_facts"] == [
            "intent.purposes",
            _OWN,
            _PAID_UP,
            "investment.pt_pma_committed",
        ]
        assert after["required_facts"] == seq28_mod._fact_paths(after["when"])
        assert after["on_unknown"] == before["on_unknown"] == "NEEDS_INPUT"
        # The sentence the code carries changes meaning (company capital -> own shares), so the
        # SUPPORT code is renamed; a replayed seq-20..30 decision keeps the old one.
        assert before["effect"]["reason_code"] == "E28A_INVESTMENT_ELIGIBLE"
        assert after["effect"] == {
            **before["effect"],
            "reason_code": "E28A_OWN_SHAREHOLDING_ELIGIBLE",
        }
        for key in set(before) - {"when", "required_facts", "effect"}:
            assert after[key] == before[key], key

    def test_no_rule_emits_the_retired_support_code_any_more(self, seq31: dict[str, Any]) -> None:
        assert "E28A_INVESTMENT_ELIGIBLE" not in json.dumps(seq31["rules"])

    def test_new_hard_filter_shape_mirrors_the_retired_one_with_the_new_fact(
        self, anchor: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        old = _rules(anchor)["hf.e28a.total-investment-below-min"]
        new = _rules(seq31)["hf.e28a.own-shareholding-below-min"]
        assert old["when"] == {"op": "lt", "fact": _CAPITAL, "value": 10_000_000_000}
        assert new["when"] == {"op": "lt", "fact": _OWN, "value": 10_000_000_000}
        assert new["effect"] == {"type": "EXCLUDE", "reason_code": _REASON}
        assert new["required_facts"] == [_OWN]
        assert new["explanation_key"] == "explain.hf.e28a.own-shareholding-below-min"
        for key in (
            "stage",
            "scope",
            "product_version_ids",
            "on_unknown",
            "priority",
            "source_refs",
            "safety_critical",
        ):
            assert new[key] == old[key], key
        assert new["on_unknown"] == "NEEDS_INPUT"

    def test_the_paid_up_company_prerequisite_is_untouched(
        self, anchor: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        assert canonicalize_json(_rules(anchor)["hf.e28a.paid-capital-below-min"]) == (
            canonicalize_json(_rules(seq31)["hf.e28a.paid-capital-below-min"])
        )

    def test_no_rule_reads_company_investment_capital_any_more(self, seq31: dict[str, Any]) -> None:
        offenders = [rid for rid, rule in _rules(seq31).items() if _CAPITAL in json.dumps(rule)]
        assert offenders == []
        assert _OLD_REASON not in json.dumps(seq31["rules"])

    def test_no_unverified_regulation_pinpoint_enters_the_changed_rules(
        self, seq31: dict[str, Any]
    ) -> None:
        for rule_id in ("el.e28a.investment", "hf.e28a.own-shareholding-below-min"):
            text = json.dumps(_rules(seq31)[rule_id])
            for forbidden in ("Permenkumham", "22/2023", "11/2024", "Pasal 38"):
                assert forbidden not in text, (rule_id, forbidden)

    def test_the_changed_rules_cite_the_e28a_catalogue_record_the_pack_already_has(
        self, seq31: dict[str, Any]
    ) -> None:
        record = next(
            r
            for r in seq31["source_records"]
            if r["source_record_id"] == fold_mod.SRC_E28A_CATALOGUE
        )
        assert {"kind": "PAGE", "value": "/wna/daftar-visa-indonesia/E28A"} in record["locators"]
        for rule_id in ("el.e28a.investment", "hf.e28a.own-shareholding-below-min"):
            assert _rules(seq31)[rule_id]["source_refs"] == [fold_mod.SRC_E28A_CATALOGUE]


class TestE28ABoundaryWitnesses:
    _BASE = {
        **_read_json(_PERSONAS / "E28A.json")["overrides"],
        "sponsor.type": _known("INVESTMENT"),
    }

    def _facts(self, own: Any, **extra: Any) -> dict[str, Any]:
        value = _UNKNOWN if own is None else _known(own)
        return {**self._BASE, _OWN: value, **extra}

    def test_guilt_one_rupiah_under_the_floor_is_excluded_with_the_renamed_reason(
        self, pack: census.PackUnderTest
    ) -> None:
        result = _decide(pack, self._facts(9_999_999_999))
        assert "E28A" not in result["candidates"]
        assert _REASON in result["no_path_reason_codes"]
        assert _OLD_REASON not in result["no_path_reason_codes"]

    def test_innocence_exactly_the_floor_with_paid_up_and_pt_pma_is_supported(
        self, pack: census.PackUnderTest
    ) -> None:
        facts = self._facts(10_000_000_000, **{_PAID_UP: _known(2_500_000_000)})
        result = _decide(pack, facts)
        assert result["state"] == "SUPPORTED_CANDIDATES"
        assert "E28A" in result["candidates"]
        assert result["no_path_reason_codes"] == []

    def test_unknown_own_shareholding_asks_for_it_and_withholds_e28a(
        self, pack: census.PackUnderTest
    ) -> None:
        result = _decide(pack, self._facts(None))
        assert result["state"] == "NEEDS_INPUT"
        assert "E28A" not in result["candidates"]
        assert _OWN in result["missing_facts"]

    @pytest.mark.parametrize("role", ["NO_OPERATIONAL_ROLE", "EMPLOYEE"])
    def test_a_passive_shareholder_at_the_floor_is_still_admitted(
        self, pack: census.PackUnderTest, role: str
    ) -> None:
        facts = self._facts(10_000_000_000, **{"investment.proposed_role": _known(role)})
        assert "E28A" in _decide(pack, facts)["candidates"]

    def test_company_investment_capital_no_longer_decides_e28a(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> None:
        # Own shares at the floor, company capital far under it: seq-30 refused, seq-31 admits.
        small_company = self._facts(10_000_000_000, **{_CAPITAL: _known(1_000_000_000)})
        assert "E28A" not in _decide(old_pack, small_company)["candidates"]
        assert "E28A" in _decide(pack, small_company)["candidates"]
        # Company capital at the floor, own shares one rupiah under: seq-30 admitted, seq-31 refuses.
        big_company = self._facts(9_999_999_999, **{_CAPITAL: _known(10_000_000_000)})
        assert "E28A" in _decide(old_pack, big_company)["candidates"]
        assert "E28A" not in _decide(pack, big_company)["candidates"]
        # The company-capital fact may be wholly unknown without moving E28A.
        no_capital = self._facts(10_000_000_000, **{_CAPITAL: _UNKNOWN})
        assert "E28A" in _decide(pack, no_capital)["candidates"]

    def test_the_paid_up_company_bound_still_excludes_independently_of_own_shares(
        self, pack: census.PackUnderTest
    ) -> None:
        facts = self._facts(50_000_000_000, **{_PAID_UP: _known(2_499_999_999)})
        result = _decide(pack, facts)
        assert "E28A" not in result["candidates"]
        assert "E28A_PAID_CAPITAL_BELOW_MIN" in result["no_path_reason_codes"]
        assert _REASON not in result["no_path_reason_codes"]

    def test_the_old_pack_ignored_the_new_fact(self, old_pack: census.PackUnderTest) -> None:
        assert "E28A" in _decide(old_pack, self._facts(1))["candidates"]


class TestCorpusOnTheCandidate:
    """Census-level witnesses on the 182-walk corpus: only the boundary witness moves."""

    @pytest.fixture(scope="class")
    def replays(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        walks = census._load_walks()
        return walks, census._outcomes_on(walks, old_pack), census._outcomes_on(walks, pack)

    def test_only_the_9999999999_witness_changes_and_only_by_losing_e28a(
        self, replays: tuple[Any, dict[str, Any], dict[str, Any]]
    ) -> None:
        _walks, before, after = replays
        moved = {label for label in before if before[label] != after[label]}
        assert moved == {"offshore/invest/pt_pma/own_shareholding_9999999999"}
        label = next(iter(moved))
        assert before[label]["state"] == after[label]["state"] == "SUPPORTED_CANDIDATES"
        assert set(before[label]["candidates"]) - set(after[label]["candidates"]) == {"E28A"}
        assert "E28A" in after["offshore/invest/pt_pma/own_shareholding_10000000000"]["candidates"]
        assert "E28A" in after["offshore/invest/pt_pma/full_capital"]["candidates"]

    def test_walks_that_never_ask_own_shareholding_do_not_become_needs_input(
        self, replays: tuple[Any, dict[str, Any], dict[str, Any]]
    ) -> None:
        walks, before, after = replays
        unasked = [
            label
            for label, spec in walks.items()
            if spec["overrides"].get(_OWN, {}).get("status") != "KNOWN"
        ]
        assert len(unasked) > 100
        for label in unasked:
            assert after[label] == before[label], label
        assert [label for label, out in after.items() if _OWN in out["missing_facts"]] == []


class TestBuilderGuards:
    def test_guilt_builder_refuses_an_already_rekeyed_e28a_rule(
        self, seq31: dict[str, Any]
    ) -> None:
        with pytest.raises(SystemExit):
            fold_mod.build_e28a_rule(_rules(seq31)["el.e28a.investment"])

    def test_guilt_a_threshold_drift_in_the_inserted_rule_is_refused(
        self, restamped: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq31)
        _rules(tampered)["hf.e28a.own-shareholding-below-min"]["when"]["value"] = 5_000_000_000
        with pytest.raises(SystemExit):
            fold_mod.assert_only_expected_changes(restamped, tampered)

    def test_guilt_keeping_the_retired_rule_is_refused(
        self, restamped: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq31)
        tampered["rules"].append(
            copy.deepcopy(_rules(restamped)["hf.e28a.total-investment-below-min"])
        )
        with pytest.raises(SystemExit):
            fold_mod.assert_only_expected_changes(restamped, tampered)

    def test_guilt_a_source_record_change_is_refused(
        self, restamped: dict[str, Any], seq31: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq31)
        tampered["source_records"][0]["title"] += "x"
        with pytest.raises(SystemExit):
            fold_mod.assert_only_expected_changes(restamped, tampered)

    def test_guilt_a_wrong_anchor_digest_is_refused(
        self, anchor: dict[str, Any], anchor_signed: dict[str, Any]
    ) -> None:
        drifted = copy.deepcopy(anchor)
        drifted["created_by"] += "x"
        with pytest.raises(SystemExit):
            fold_mod.fold_from_signed_seq30(
                drifted, anchor_signed, trust_store=StaticTrustStore.from_env()
            )


class TestGoldPersonasOnTheCandidate:
    def test_every_gold_persona_still_replays_to_its_expectation(
        self, pack: census.PackUnderTest
    ) -> None:
        checked = 0
        for path in sorted(_PERSONAS.glob("*.json")):
            persona = _read_json(path)
            actual = _decide(pack, persona["overrides"])
            assert actual["state"] == persona["expected_state"], path.name
            assert set(persona["expected_candidates"]) <= set(actual["candidates"]), path.name
            checked += 1
        assert checked == len(list(_PERSONAS.glob("*.json"))) >= 28

    def test_the_updated_e28a_persona_replays_identically_on_seq30_and_seq31(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> None:
        moved: list[str] = []
        for path in sorted(_PERSONAS.glob("*.json")):
            persona = _read_json(path)
            if _decide(pack, persona["overrides"]) != _decide(old_pack, persona["overrides"]):
                moved.append(path.name)
        assert moved == []  # the E28A persona now answers the new question on BOTH packs
        assert _read_json(_PERSONAS / "E28A.json")["overrides"][_OWN] == _known(10_000_000_000)


@requires_signed
class TestSignedBundleTiesToSource:
    def test_jcs_payload_equals_source(self, seq31: dict[str, Any]) -> None:
        signed = _read_json(_SEQ31_SIGNED)
        assert canonicalize_json(signed["payload"]) == canonicalize_json(seq31)

    def test_verifies_under_the_pinned_prod_key(self) -> None:
        signed = _read_json(_SEQ31_SIGNED)
        verified = verify_rule_pack(
            signed,
            trust_store=StaticTrustStore.from_env(),
            observed_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert verified.pack.protected.kid == "prod-2026-07-1"
        assert verified.pack.payload.sequence == 31

    def test_anchor_is_the_seq30_digest(self) -> None:
        signed = _read_json(_SEQ31_SIGNED)
        assert signed["payload"]["previous_payload_sha256"] == fold_mod.SEQ30_PAYLOAD_SHA256

    def test_guilt_one_flipped_byte_breaks_signature(self) -> None:
        signed = copy.deepcopy(_read_json(_SEQ31_SIGNED))
        signed["payload"]["created_by"] += "x"
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                signed,
                trust_store=StaticTrustStore.from_env(),
                observed_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
