"""Seq-30 fold gates: E28 family close-out (SEQ29-A2, SEQ29-D1, SEQ29-S1, SEQ29-N1) plus S02 and SEQ29-E30-02.

Chained on verified signed ``seq-29`` (``rulepack-prod-029.signed.json``, payload SHA-256
``3f3b45ed1aaeadc72ec9dd2a5e33519ded3a0ec1da8408fade150a0ae39b9295``).
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import fold_pack_seq28 as seq28_mod
from backend.scripts.visa_engine import fold_pack_seq30 as fold_mod
from backend.scripts.visa_engine.fold_pack_seq25 import load_ledger
from backend.scripts.visa_engine.ledger_paths import read_receipt_text
from backend.scripts.visa_engine.review_hold_inventory import (
    pack_review_rules,
    pack_unknown_escalations,
)
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload, VisaProductVersion
from backend.services.visa_engine.pricing_adapter import resolve_candidate_pricing
from backend.tests.services.visa_engine import test_interview_walk_census as census
from backend.tests.services.visa_engine.test_seq28_pack import (
    PROD_TRUST_STORE_JSON,
    _Catalog,
    _decide,
    _known,
    _portals,
    _products,
    _read_json,
    _rules,
)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_RESEARCH = _REPO_ROOT / "research/visa"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_PERSONAS = Path(__file__).resolve().parent / "gold_coverage" / "personas"
_SEQ29_SOURCE = _PACKS / "rulepack-prod-029.source.json"
_SEQ29_SIGNED = _PACKS / "rulepack-prod-029.signed.json"
_SEQ30_SOURCE = _PACKS / "rulepack-prod-030.source.json"
_SEQ30_SIGNED = _PACKS / "rulepack-prod-030.signed.json"
_SEQ29_LEDGER = _RESEARCH / "2026-10-13-organ-reattest-seq29"
_E28_PAGES_DIR = _RESEARCH / "2026-10-15-e28-pages"
_PORTAL_MAX_AGE = timedelta(seconds=2_764_800)
_UNKNOWN = {"status": "UNKNOWN", "reason": "NOT_ASKED"}


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
    return _read_json(_SEQ29_SOURCE)


@pytest.fixture(scope="module")
def anchor_signed() -> dict[str, Any]:
    return _read_json(_SEQ29_SIGNED)


@pytest.fixture(scope="module")
def seq30() -> dict[str, Any]:
    return _read_json(_SEQ30_SOURCE)


@pytest.fixture(scope="module")
def folded(
    anchor: dict[str, Any], anchor_signed: dict[str, Any], seq30: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    return fold_mod.fold_from_signed_seq29(
        anchor,
        anchor_signed,
        _read_json(_CATALOGUE),
        trust_store=StaticTrustStore.from_env(),
        created_at=str(seq30["created_at"]),
        created_by=str(seq30["created_by"]),
    )


@pytest.fixture(scope="module")
def restamped(folded: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    return folded[0]


@pytest.fixture(scope="module")
def pack(seq30: dict[str, Any], tmp_path_factory: pytest.TempPathFactory) -> census.PackUnderTest:
    path = tmp_path_factory.mktemp("seq30-candidate") / "rulepack-prod-030.source.json"
    path.write_text(json.dumps(seq30, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return census._pack_from_source(path)


@pytest.fixture(scope="module")
def old_pack() -> census.PackUnderTest:
    return census._pack_from_source(_SEQ29_SOURCE)


class TestCommittedSourceMatchesFold:
    def test_committed_seq30_source_is_byte_for_byte_the_fold_output(
        self, folded: tuple[dict[str, Any], dict[str, Any]], seq30: dict[str, Any]
    ) -> None:
        _, out = folded
        assert canonicalize_json(out) == canonicalize_json(seq30), (
            "the committed seq-30 source is not what fold_pack_seq30 produces; "
            "rerun the fold, never edit it by hand"
        )

    def test_cli_check_passes_on_the_committed_source(self) -> None:
        assert fold_mod.main(["--check"]) == 0


class TestPackIntegrity:
    def test_chain_sequence_and_uuid5(self, seq30: dict[str, Any], anchor: dict[str, Any]) -> None:
        assert seq30["sequence"] == 30
        assert anchor["sequence"] == 29
        assert seq30["version"] == fold_mod.FOLD_VERSION
        assert seq30["previous_payload_sha256"] == fold_mod.SEQ29_PAYLOAD_SHA256
        assert (
            hashlib.sha256(canonicalize_json(anchor)).hexdigest()
            == fold_mod.SEQ29_PAYLOAD_SHA256
        )
        assert seq30["rollback_of_payload_sha256"] is None
        assert seq30["rule_pack_id"] == str(seq28_mod._rule_pack_id(30))

    def test_only_expected_paths_move(
        self, restamped: dict[str, Any], seq30: dict[str, Any], anchor: dict[str, Any]
    ) -> None:
        fold_mod.assert_only_expected_changes(restamped, seq30)
        fold_mod.assert_anchor_relative_changes(anchor, seq30)

    def test_all_source_records_are_byte_identical_to_seq29(
        self, anchor: dict[str, Any], seq30: dict[str, Any]
    ) -> None:
        assert canonicalize_json(anchor["source_records"]) == canonicalize_json(
            seq30["source_records"]
        )
        assert len(_portals(seq30)) == 18
        assert len(seq30["source_records"]) == 28

    def test_product_count_order_and_scheduled_edits(
        self, anchor: dict[str, Any], seq30: dict[str, Any]
    ) -> None:
        before_ids = [p["product_version_id"] for p in anchor["products"]]
        after_ids = [p["product_version_id"] for p in seq30["products"]]
        assert before_ids == after_ids
        assert len(seq30["products"]) == 38

    def test_rule_counts_and_order(self, anchor: dict[str, Any], seq30: dict[str, Any]) -> None:
        before = [r["rule_id"] for r in anchor["rules"]]
        after = [r["rule_id"] for r in seq30["rules"]]
        assert len(before) == 117
        assert len(after) == 118
        assert after == [*before, *fold_mod.INSERTED_RULE_IDS_IN_ORDER]

    def test_model_validates(self, seq30: dict[str, Any]) -> None:
        payload = RulePackPayload.model_validate(seq30)
        assert payload.sequence == 30

    def test_every_changed_rule_required_facts_equal_its_when_facts(
        self, seq30: dict[str, Any]
    ) -> None:
        rules = _rules(seq30)
        for rule_id in (*sorted(fold_mod.MODIFIED_RULE_IDS), *fold_mod.INSERTED_RULE_IDS_IN_ORDER):
            assert rules[rule_id]["required_facts"] == seq28_mod._fact_paths(
                rules[rule_id]["when"]
            )

    def test_review_hold_inventory_is_unchanged_from_seq29(
        self, seq30: dict[str, Any]
    ) -> None:
        payload = RulePackPayload.model_validate(seq30)
        assert sorted(r.rule_id for r in pack_review_rules(payload)) == [
            "review.e31j-marital-status-other",
            "review.e33.below-threshold-studio",
        ]
        assert pack_unknown_escalations(payload) == ()

    def test_every_rule_source_ref_and_product_id_resolves(
        self, seq30: dict[str, Any]
    ) -> None:
        source_ids = {r["source_record_id"] for r in seq30["source_records"]}
        product_ids = {p["product_version_id"] for p in seq30["products"]}
        for rule_id, rule in _rules(seq30).items():
            assert set(rule["source_refs"]) <= source_ids, rule_id
            if rule["product_version_ids"] is not None:
                assert set(rule["product_version_ids"]) <= product_ids, rule_id


class TestSavedE28OfficialPages:
    def test_all_six_saved_e28_pages_and_receipts_verify(self) -> None:
        assert fold_mod.verify_saved_e28_pages(_E28_PAGES_DIR) is None
        assert len(fold_mod.SAVED_E28_PAGE_SPECS) == 6

    def test_guilt_a_tampered_e28_receipt_digest_is_refused(self, tmp_path: Path) -> None:
        copied = tmp_path / "e28-pages"
        shutil.copytree(_E28_PAGES_DIR, copied)
        receipts_path = copied / "e28-pages.receipts.jsonl"
        lines = receipts_path.read_text(encoding="utf-8").splitlines()
        row0 = json.loads(lines[0])
        row0["visible_text_sha256"] = "0" * 64
        lines[0] = json.dumps(row0)
        receipts_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with pytest.raises(SystemExit):
            fold_mod.verify_saved_e28_pages(copied)

    def test_guilt_a_missing_role_sentence_in_saved_e28d_text_is_refused(
        self, tmp_path: Path
    ) -> None:
        copied = tmp_path / "e28-pages"
        shutil.copytree(_E28_PAGES_DIR, copied)
        text_path = copied / fold_mod.SAVED_E28_PAGE_SPECS["E28D"]["file"]
        mutated = text_path.read_text(encoding="utf-8").replace(
            fold_mod.SAVED_E28_PAGE_SPECS["E28D"]["role_line"],
            "kalimat dihapus",
        )
        text_path.write_text(mutated, encoding="utf-8")
        # Update receipt sha256 so the failure specifically hits the phrase check.
        new_sha = fold_mod.fingerprint(mutated.rstrip("\n"))
        receipts_path = copied / "e28-pages.receipts.jsonl"
        new_lines = []
        for line in receipts_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["canonical_url"].endswith("/E28D"):
                row["visible_text_sha256"] = new_sha
            new_lines.append(json.dumps(row))
        receipts_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        with pytest.raises(SystemExit):
            fold_mod.verify_saved_e28_pages(copied)


class TestSeq29A2E28APassiveShareholder:
    _BASE_E28A = _read_json(_PERSONAS / "E28A.json")["overrides"]

    def test_e28a_investment_rule_drops_proposed_role(self, seq30: dict[str, Any]) -> None:
        rule = _rules(seq30)[fold_mod.E28A_RULE_ID]
        assert rule["required_facts"] == [
            "intent.purposes",
            "investment.investment_capital_idr",
            "investment.paid_up_capital_idr",
            "investment.pt_pma_committed",
        ]
        assert "investment.proposed_role" not in json.dumps(rule["when"])

    def test_sibling_e28a_capital_hard_filters_stay_intact(
        self, anchor: dict[str, Any], seq30: dict[str, Any]
    ) -> None:
        for rule_id in ("hf.e28a.paid-capital-below-min", "hf.e28a.total-investment-below-min"):
            assert canonicalize_json(_rules(anchor)[rule_id]) == canonicalize_json(
                _rules(seq30)[rule_id]
            )

    @pytest.mark.parametrize("role", ["NO_OPERATIONAL_ROLE", "EMPLOYEE"])
    def test_guilt_a_passive_shareholder_with_10b_gains_e28a(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest, role: str
    ) -> None:
        facts = {
            **self._BASE_E28A,
            "investment.proposed_role": _known(role),
            "investment.paid_up_capital_idr": _known(2_500_000_000),
            "investment.investment_capital_idr": _known(10_000_000_000),
        }
        assert "E28A" not in _decide(old_pack, facts)["candidates"]
        assert "E28A" in _decide(pack, facts)["candidates"]

    def test_innocence_under_10b_passive_shareholder_is_still_excluded_from_e28a(
        self, pack: census.PackUnderTest
    ) -> None:
        facts = {
            **self._BASE_E28A,
            "investment.proposed_role": _known("NO_OPERATIONAL_ROLE"),
            "investment.paid_up_capital_idr": _known(2_500_000_000),
            "investment.investment_capital_idr": _known(5_000_000_000),
        }
        assert "E28A" not in _decide(pack, facts)["candidates"]

    def test_guilt_builder_refuses_an_already_updated_e28a_rule(
        self, seq30: dict[str, Any]
    ) -> None:
        with pytest.raises(SystemExit):
            fold_mod.build_e28a_rule(_rules(seq30)[fold_mod.E28A_RULE_ID])


class TestSeq29D1E28DAndE28FRoleGate:
    _E28D_FACTS = _read_json(_PERSONAS / "E28D.json")["overrides"]
    _E28F_FACTS = _read_json(_PERSONAS / "E28F.json")["overrides"]

    def test_e28d_and_e28f_rules_require_director_or_commissioner_role(
        self, seq30: dict[str, Any]
    ) -> None:
        e28d = _rules(seq30)[fold_mod.E28D_RULE_ID]
        e28f = _rules(seq30)[fold_mod.E28F_RULE_ID]
        assert e28d["on_unknown"] == "NEEDS_INPUT"
        assert e28f["on_unknown"] == "NEEDS_INPUT"
        assert e28d["required_facts"] == [
            "intent.purposes",
            "investment.foreign_branch_or_subsidiary",
            "investment.meets_published_threshold",
            "investment.proposed_role",
        ]
        assert e28f["required_facts"] == [
            "intent.purposes",
            "investment.foreign_branch_or_subsidiary",
            "investment.ikn_subsidiary",
            "investment.meets_published_threshold",
            "investment.proposed_role",
        ]

    @pytest.mark.parametrize("role", ["NO_OPERATIONAL_ROLE", "EMPLOYEE"])
    def test_guilt_branch_or_ikn_subsidiary_without_board_role_loses_e28d_and_e28f(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest, role: str
    ) -> None:
        d_facts = {**self._E28D_FACTS, "investment.proposed_role": _known(role)}
        assert "E28D" in _decide(old_pack, d_facts)["candidates"]
        assert "E28D" not in _decide(pack, d_facts)["candidates"]

        f_facts = {**self._E28F_FACTS, "investment.proposed_role": _known(role)}
        assert "E28F" in _decide(old_pack, f_facts)["candidates"]
        assert "E28F" not in _decide(pack, f_facts)["candidates"]

    def test_guilt_unknown_proposed_role_withholds_e28d_and_e28f_and_asks_for_it(
        self, pack: census.PackUnderTest
    ) -> None:
        d_facts = {
            **self._E28D_FACTS,
            "intent.stay_days": _known(1825),
            "investment.pt_pma_committed": _known(False),
            "investment.proposed_role": _UNKNOWN,
        }
        d_res = _decide(pack, d_facts)
        assert "E28D" not in d_res["candidates"]
        assert "investment.proposed_role" in d_res["missing_facts"]

        f_facts = {
            **self._E28F_FACTS,
            "intent.stay_days": _known(1825),
            "investment.pt_pma_committed": _known(False),
            "investment.proposed_role": _UNKNOWN,
        }
        f_res = _decide(pack, f_facts)
        assert "E28F" not in f_res["candidates"]
        assert "investment.proposed_role" in f_res["missing_facts"]

    @pytest.mark.parametrize("role", ["SHAREHOLDER_DIRECTOR", "SHAREHOLDER_COMMISSIONER"])
    def test_innocence_director_and_commissioner_keep_e28d_and_e28f(
        self, pack: census.PackUnderTest, role: str
    ) -> None:
        d_facts = {**self._E28D_FACTS, "investment.proposed_role": _known(role)}
        assert "E28D" in _decide(pack, d_facts)["candidates"]

        f_facts = {**self._E28F_FACTS, "investment.proposed_role": _known(role)}
        assert "E28F" in _decide(pack, f_facts)["candidates"]

    def test_guilt_builders_refuse_already_updated_e28d_and_e28f_rules(
        self, seq30: dict[str, Any]
    ) -> None:
        with pytest.raises(SystemExit):
            fold_mod.build_e28d_rule(_rules(seq30)[fold_mod.E28D_RULE_ID])
        with pytest.raises(SystemExit):
            fold_mod.build_e28f_rule(_rules(seq30)[fold_mod.E28F_RULE_ID])


class TestS02A1NotConvertible:
    _A1 = _read_json(_PERSONAS / "A1.json")["overrides"]

    def test_the_saved_official_page_says_a_visa_exempt_stay_cannot_be_converted(self) -> None:
        ledger = load_ledger(_SEQ29_LEDGER)
        receipt = next(
            r for r in ledger.receipts if r["source_record_id"] == fold_mod.SRC_ALIH_STATUS_PORTAL
        )
        text = read_receipt_text(ledger.text_dir, receipt)
        assert "Bebas Visa Kunjungan" in text
        assert "tidak dapat dialihstatuskan menjadi Izin Tinggal lain" in text

    def test_guilt_a_visitor_who_will_convert_on_shore_loses_a1(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> None:
        facts = {**self._A1, "process.wants_onshore_conversion": _known(True)}
        assert "A1" in _decide(old_pack, facts)["candidates"]
        assert "A1" not in _decide(pack, facts)["candidates"]

    def test_the_a1_exclusion_rule_shape(self, seq30: dict[str, Any]) -> None:
        rule = _rules(seq30)[fold_mod.A1_RULE_ID]
        assert rule["effect"] == {"type": "EXCLUDE", "reason_code": "A1_NOT_CONVERTIBLE"}
        assert rule["on_unknown"] == "NO_EFFECT"
        assert rule["product_version_ids"] == [fold_mod.A1_PRODUCT_VERSION_ID]

    @pytest.mark.parametrize("answer", [_known(False), _UNKNOWN])
    def test_innocence_no_or_unasked_conversion_keeps_a1(
        self, pack: census.PackUnderTest, answer: dict[str, Any]
    ) -> None:
        facts = {**self._A1, "process.wants_onshore_conversion": answer}
        actual = _decide(pack, facts)
        assert "A1" in actual["candidates"]
        assert actual["missing_facts"] == []


class TestSeq29E3002MultiYearOptions:
    _NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)

    def _quote(self, payload: dict[str, Any], code: str, stay_days: int) -> int | None:
        product = VisaProductVersion.model_validate(_products(payload)[code])
        resolution = resolve_candidate_pricing(
            product,
            pricing_catalog=_Catalog(_read_json(_CATALOGUE)),
            evaluated_at=self._NOW,
            stay_days=stay_days,
        )
        assert resolution.status == "AVAILABLE"
        return resolution.amount

    @pytest.mark.parametrize(
        ("code", "stay_days", "amount"),
        [
            ("E30A", 365, 9_000_000),
            ("E30A", 730, 11_500_000),
            ("E30B", 365, 9_000_000),
            ("E30B", 730, 11_500_000),
            ("E30B", 1000, 15_000_000),
            ("E30B", 1460, 15_000_000),
        ],
    )
    def test_guilt_a_multi_year_student_is_quoted_the_row_of_their_stay(
        self, seq30: dict[str, Any], code: str, stay_days: int, amount: int
    ) -> None:
        assert self._quote(seq30, code, stay_days) == amount

    def test_seq29_quoted_every_stay_at_the_one_year_row(
        self, anchor: dict[str, Any]
    ) -> None:
        for code in ("E30A", "E30B"):
            assert not _products(anchor)[code].get("duration_options")
            assert self._quote(anchor, code, 730) == 9_000_000

    def test_innocence_the_one_year_row_and_the_stay_policy_do_not_move(
        self, anchor: dict[str, Any], seq30: dict[str, Any]
    ) -> None:
        for code in ("E30A", "E30B"):
            before, after = _products(anchor)[code], _products(seq30)[code]
            assert after["pricing_key"] == before["pricing_key"]
            assert after["stay_policy"] == before["stay_policy"]
            assert after["duration_options"][0]["pricing_key"] == before["pricing_key"]
            assert after["duration_options"][-1]["days"] == after["stay_policy"]["maximum_days"]

    def test_guilt_an_option_with_no_catalogue_row_is_refused(self) -> None:
        catalogue = copy.deepcopy(_read_json(_CATALOGUE))
        del catalogue["services"]["kitas_permits"]["E30B Higher Education (4 Years)"]
        with pytest.raises(SystemExit):
            fold_mod.assert_catalogue_preconditions(catalogue)

    def test_guilt_the_builder_refuses_a_product_that_already_has_options(
        self, seq30: dict[str, Any]
    ) -> None:
        with pytest.raises(SystemExit):
            fold_mod.build_e30_product(_products(seq30)["E30A"])


class TestSeq29S1AndN1E28Products:
    def test_e28b_e28d_e28f_sponsor_types_are_none_while_e28a_remains_investment(
        self, anchor: dict[str, Any], seq30: dict[str, Any]
    ) -> None:
        before = _products(anchor)
        after = _products(seq30)
        for code in ("E28B", "E28D", "E28F"):
            assert before[code]["sponsor_types"] == ["INVESTMENT"]
            assert after[code]["sponsor_types"] == ["NONE"]
        assert after["E28A"]["sponsor_types"] == ["INVESTMENT"]
        assert after["E28C"]["sponsor_types"] == ["NONE"]

    def test_e28c_e28d_e28f_names_match_saved_official_headings(
        self, anchor: dict[str, Any], seq30: dict[str, Any]
    ) -> None:
        before = _products(anchor)
        after = _products(seq30)
        for code, pid in (
            ("E28C", fold_mod.E28C_PRODUCT_VERSION_ID),
            ("E28D", fold_mod.E28D_PRODUCT_VERSION_ID),
            ("E28F", fold_mod.E28F_PRODUCT_VERSION_ID),
        ):
            assert before[code]["names"] == fold_mod.E28_NAME_UPDATES[pid]["before"]
            assert after[code]["names"] == fold_mod.E28_NAME_UPDATES[pid]["after"]

    def test_e28a_extension_policy_stays_verified_for_36_month_renewal_walks(
        self, seq30: dict[str, Any]
    ) -> None:
        assert _products(seq30)["E28A"]["extension_policy"] == {
            "status": "VERIFIED",
            "allowed": True,
            "reason_code": None,
            "days_per_extension": 365,
            "maximum_extensions": 100,
        }

    def test_guilt_builder_refuses_an_already_updated_e28_product(
        self, seq30: dict[str, Any]
    ) -> None:
        for code in ("E28B", "E28C", "E28D", "E28F"):
            with pytest.raises(SystemExit):
                fold_mod.build_e28_product(_products(seq30)[code])


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


class TestSignedBundleTiesToSource:
    def test_jcs_payload_equals_source(self, seq30: dict[str, Any]) -> None:
        signed = _read_json(_SEQ30_SIGNED)
        assert canonicalize_json(signed["payload"]) == canonicalize_json(seq30)

    def test_verifies_under_the_pinned_prod_key(self) -> None:
        signed = _read_json(_SEQ30_SIGNED)
        verified = verify_rule_pack(
            signed,
            trust_store=StaticTrustStore.from_env(),
            observed_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert verified.pack.protected.kid == "prod-2026-07-1"
        assert verified.pack.payload.sequence == 30

    def test_anchor_is_the_seq29_digest(self) -> None:
        signed = _read_json(_SEQ30_SIGNED)
        assert signed["payload"]["previous_payload_sha256"] == fold_mod.SEQ29_PAYLOAD_SHA256

    def test_guilt_one_flipped_byte_breaks_signature(self) -> None:
        signed = copy.deepcopy(_read_json(_SEQ30_SIGNED))
        signed["payload"]["created_by"] += "x"
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                signed,
                trust_store=StaticTrustStore.from_env(),
                observed_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
