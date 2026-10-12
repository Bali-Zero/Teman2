"""Seq-29 fold gates: the organ re-stamp of signed seq-28 plus four decision-free corrections.

Until the organ run that follows seq-28 exists the committed source is the dry-run output: the
2026-10-11 ledger is first re-proved (it must reproduce signed seq-28 from signed seq-27) and
its stamps are kept.  Once a newer ledger is committed the same fixture folds it from seq-28
and compares the result with the committed seq-29 source.  Signed-bundle checks wake up when
the ceremony adds the signed artifact.
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

from backend.scripts.visa_engine import fold_pack_seq28 as seq28_mod
from backend.scripts.visa_engine import fold_pack_seq29 as fold_mod
from backend.scripts.visa_engine.fold_pack_generic import fold as generic_fold
from backend.scripts.visa_engine.fold_pack_seq25 import PORTAL_AUTHORITY, load_ledger
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
from backend.services.visa_engine.models import RulePackPayload
from backend.tests.services.visa_engine import test_interview_walk_census as census
from backend.tests.services.visa_engine.test_seq28_pack import (
    PROD_TRUST_STORE_JSON,
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
_SEQ27_SOURCE = _PACKS / "rulepack-prod-027.source.json"
_SEQ27_SIGNED = _PACKS / "rulepack-prod-027.signed.json"
_SEQ28_SOURCE = _PACKS / "rulepack-prod-028.source.json"
_SEQ28_SIGNED = _PACKS / "rulepack-prod-028.signed.json"
_SEQ29_SOURCE = _PACKS / "rulepack-prod-029.source.json"
_SEQ29_SIGNED = _PACKS / "rulepack-prod-029.signed.json"
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
    return _read_json(_SEQ28_SOURCE)


@pytest.fixture(scope="module")
def anchor_signed() -> dict[str, Any]:
    return _read_json(_SEQ28_SIGNED)


@pytest.fixture(scope="module")
def newest_ledger() -> Path:
    return seq28_mod.discover_newest_ledger(_RESEARCH)


@pytest.fixture(scope="module")
def committed() -> dict[str, Any]:
    return _read_json(_SEQ29_SOURCE)


@pytest.fixture(scope="module")
def folded(
    anchor: dict[str, Any],
    anchor_signed: dict[str, Any],
    newest_ledger: Path,
    committed: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    catalogue = _read_json(_CATALOGUE)
    trust_store = StaticTrustStore.from_env()
    fetched = [
        datetime.fromisoformat(str(row["fetched_at"]).replace("Z", "+00:00"))
        for row in load_ledger(newest_ledger).receipts
    ]
    created_at = str(committed["created_at"])
    observed_at = max(
        datetime.now(timezone.utc),
        max(fetched) + timedelta(days=1),
        datetime.fromisoformat(created_at.replace("Z", "+00:00")) + timedelta(days=1),
    )
    anchor_stamp = max(
        datetime.fromisoformat(r["verified_at"].replace("Z", "+00:00")) for r in _portals(anchor)
    )
    if min(fetched) > anchor_stamp:
        restamped = generic_fold(
            anchor,
            anchor_signed,
            load_ledger(newest_ledger),
            trust_store=trust_store,
            version=fold_mod.FOLD_VERSION,
            created_at=created_at,
            created_by=str(committed["created_by"]),
            verified_by=seq28_mod._portal_verified_by(committed),
            observed_at=observed_at,
            baseline_root=_RESEARCH,
            ledger_dir=newest_ledger,
        )
        candidate = fold_mod.apply_content_edits(restamped, created_at=created_at)
        mode = "real"
    else:
        restamped, candidate = fold_mod.dry_run_from_anchor_ledger(
            anchor,
            newest_ledger,
            catalogue,
            trust_store=trust_store,
            baseline_root=_RESEARCH,
            previous_source=_read_json(_SEQ27_SOURCE),
            previous_signed=_read_json(_SEQ27_SIGNED),
            observed_at=observed_at,
            created_at=created_at,
            created_by=str(committed["created_by"]),
        )
        mode = "dry-run"
    assert canonicalize_json(candidate) == canonicalize_json(committed), (
        "the committed seq-29 source is not what the fold produces; rerun the fold, never edit it"
    )
    return restamped, candidate, mode


@pytest.fixture(scope="module")
def restamped(folded: tuple[dict[str, Any], dict[str, Any], str]) -> dict[str, Any]:
    return folded[0]


@pytest.fixture(scope="module")
def seq29(folded: tuple[dict[str, Any], dict[str, Any], str]) -> dict[str, Any]:
    return folded[1]


@pytest.fixture(scope="module")
def pack(seq29: dict[str, Any], tmp_path_factory: pytest.TempPathFactory) -> census.PackUnderTest:
    path = tmp_path_factory.mktemp("seq29-candidate") / "rulepack-prod-029.source.json"
    path.write_text(json.dumps(seq29, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return census._pack_from_source(path)


@pytest.fixture(scope="module")
def old_pack() -> census.PackUnderTest:
    return census._pack_from_source(_SEQ28_SOURCE)


def _family(relation: str, **overrides: Any) -> dict[str, Any]:
    """A FAMILY walk on a 365-day stay: C1 (180 days) cannot mask the E31 outcome."""

    facts: dict[str, Any] = {
        "intent.purposes": _known(["FAMILY"]),
        "intent.stay_days": _known(365),
        "intent.entry_pattern": _known("MULTIPLE"),
        "family.relation_to_sponsor": _known(relation),
        "family.sponsor_confirmed": _known(True),
        "family.sponsor_status_code": _known("E23"),
        "family.sponsor_nationalities": _known(["IT"]),
        "person.nationalities": _known(["NL"]),
        "person.birth_date": _known("2012-01-01"),
        "person.marital_status": _known("SINGLE"),
        "person.guardian_consent": _known(True),
        "sponsor.type": _known("INDIVIDUAL"),
    }
    facts.update(overrides)
    return facts


_ADULT = "2000-01-01"


class TestIntegrity:
    def test_chain_sequence_and_uuid5(self, seq29: dict[str, Any], anchor: dict[str, Any]) -> None:
        assert seq29["sequence"] == 29
        assert (
            fold_mod.SEQ28_PAYLOAD_SHA256 == hashlib.sha256(canonicalize_json(anchor)).hexdigest()
        )
        assert seq29["previous_payload_sha256"] == fold_mod.SEQ28_PAYLOAD_SHA256
        assert seq29["rollback_of_payload_sha256"] is None
        assert seq29["rule_pack_id"] == str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/29",
            )
        )

    def test_the_pinned_anchor_is_the_signed_seq28_payload(
        self, anchor_signed: dict[str, Any]
    ) -> None:
        digest = hashlib.sha256(canonicalize_json(anchor_signed["payload"])).hexdigest()
        assert digest == fold_mod.SEQ28_PAYLOAD_SHA256

    def test_only_the_expected_paths_move(
        self, restamped: dict[str, Any], seq29: dict[str, Any], anchor: dict[str, Any]
    ) -> None:
        fold_mod.assert_only_expected_changes(restamped, seq29)
        fold_mod.assert_anchor_relative_changes(anchor, seq29)

    def test_non_portal_records_are_byte_identical(
        self, anchor: dict[str, Any], seq29: dict[str, Any]
    ) -> None:
        before = [r for r in anchor["source_records"] if r["authority_type"] != PORTAL_AUTHORITY]
        after = [r for r in seq29["source_records"] if r["authority_type"] != PORTAL_AUTHORITY]
        assert len(after) == 10
        assert canonicalize_json(before) == canonicalize_json(after)

    def test_portals_move_only_their_stamp(
        self, anchor: dict[str, Any], seq29: dict[str, Any], folded: tuple[Any, Any, str]
    ) -> None:
        before = {r["source_record_id"]: r for r in _portals(anchor)}
        after = {r["source_record_id"]: r for r in _portals(seq29)}
        assert set(before) == set(after) and len(after) == 18
        for record_id, record in after.items():
            moved = {key for key in record if record[key] != before[record_id][key]}
            assert moved == ({"verified_at", "verified_by"} if folded[2] == "real" else set())

    def test_no_product_changes(self, anchor: dict[str, Any], seq29: dict[str, Any]) -> None:
        assert canonicalize_json(anchor["products"]) == canonicalize_json(seq29["products"])
        assert len(seq29["products"]) == 38

    def test_rule_counts_and_order(self, anchor: dict[str, Any], seq29: dict[str, Any]) -> None:
        before = [r["rule_id"] for r in anchor["rules"]]
        after = [r["rule_id"] for r in seq29["rules"]]
        assert len(before) == 114 and len(after) == 116
        assert set(before) - set(after) == {"el.e31j-dependency-age"}
        assert after[-3:] == list(fold_mod.INSERTED_RULE_IDS_IN_ORDER)
        assert after[:-3] == [r for r in before if r != "el.e31j-dependency-age"]

    def test_boundary_is_stamp_plus_2764800_seconds(self, seq29: dict[str, Any]) -> None:
        stamps = {r["verified_at"] for r in _portals(seq29)}
        assert len(stamps) == 1
        assert {r["freshness_policy"]["max_age_seconds"] for r in _portals(seq29)} == {
            int(_PORTAL_MAX_AGE.total_seconds())
        }

    def test_model_validates(self, seq29: dict[str, Any]) -> None:
        payload = RulePackPayload.model_validate(seq29)
        assert payload.sequence == 29
        assert len(payload.rules) == 116

    def test_every_new_or_changed_rule_reads_exactly_the_facts_it_requires(
        self, seq29: dict[str, Any]
    ) -> None:
        rules = _rules(seq29)
        for rule_id in (*sorted(fold_mod.MODIFIED_RULE_IDS), *fold_mod.INSERTED_RULE_IDS_IN_ORDER):
            assert rules[rule_id]["required_facts"] == fold_mod._fact_paths(rules[rule_id]["when"])

    def test_the_review_inventory_is_unchanged(self, seq29: dict[str, Any]) -> None:
        payload = RulePackPayload.model_validate(seq29)
        assert [row.rule_id for row in pack_review_rules(payload)] == [
            "review.e33.below-threshold-studio"
        ]
        assert pack_unknown_escalations(payload) == ()

    def test_no_e33_rule_or_product_moves(
        self, anchor: dict[str, Any], seq29: dict[str, Any]
    ) -> None:
        for rule_id, rule in _rules(seq29).items():
            if "e33" in rule_id:
                assert rule == _rules(anchor)[rule_id]
        for code, product in _products(seq29).items():
            if code.startswith("E33"):
                assert product == _products(anchor)[code]


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
            if "judge" not in judgement:
                assert judgement["semantic_change"] == "none"

    def test_stamp_is_the_earliest_successful_read_or_the_anchor_stamp(
        self, newest_ledger: Path, seq29: dict[str, Any], folded: tuple[Any, Any, str]
    ) -> None:
        stamps = {r["verified_at"] for r in _portals(seq29)}
        if folded[2] == "real":
            assert stamps == {min(row["fetched_at"] for row in load_ledger(newest_ledger).receipts)}
        else:
            assert stamps == {r["verified_at"] for r in _portals(_read_json(_SEQ28_SOURCE))}

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
        self, restamped: dict[str, Any], seq29: dict[str, Any]
    ) -> None:
        rebuilt = fold_mod.apply_content_edits(restamped, created_at=seq29["created_at"])
        assert canonicalize_json(rebuilt) == canonicalize_json(seq29)

    def test_guilt_a_ledger_that_did_not_produce_seq28_is_refused_by_the_dry_run(
        self, anchor: dict[str, Any], newest_ledger: Path, tmp_path: Path
    ) -> None:
        copy_dir = tmp_path / "ledger"
        shutil.copytree(newest_ledger, copy_dir)
        receipts_path = next(copy_dir.glob("*-receipts.jsonl"))
        lines = receipts_path.read_text(encoding="utf-8").splitlines()
        receipts_path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
        with pytest.raises(SystemExit):
            fold_mod.dry_run_from_anchor_ledger(
                anchor,
                copy_dir,
                _read_json(_CATALOGUE),
                trust_store=StaticTrustStore.from_env(),
                baseline_root=_RESEARCH,
                previous_source=_read_json(_SEQ27_SOURCE),
                previous_signed=_read_json(_SEQ27_SIGNED),
                observed_at=datetime.now(timezone.utc) + timedelta(days=2),
            )

    def test_guilt_the_real_fold_refuses_an_organ_candidate_that_differs(
        self, anchor: dict[str, Any], anchor_signed: dict[str, Any], newest_ledger: Path
    ) -> None:
        wrong = copy.deepcopy(anchor)
        wrong["sequence"] = 29
        with pytest.raises(SystemExit):
            fold_mod.fold(
                anchor,
                anchor_signed,
                newest_ledger,
                wrong,
                trust_store=StaticTrustStore.from_env(),
                baseline_root=_RESEARCH,
                observed_at=datetime.now(timezone.utc) + timedelta(days=2),
            )


class TestE28FForeignParent:
    _FACTS = _read_json(_PERSONAS / "E28F.json")["overrides"]

    def test_innocence_the_gold_persona_with_a_foreign_parent_keeps_e28f(
        self, pack: census.PackUnderTest
    ) -> None:
        assert "E28F" in _decide(pack, self._FACTS)["candidates"]

    def test_guilt_an_ikn_subsidiary_without_a_foreign_parent_loses_e28f(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> None:
        facts = {**self._FACTS, "investment.foreign_branch_or_subsidiary": _known(False)}
        assert "E28F" in _decide(old_pack, facts)["candidates"]
        assert "E28F" not in _decide(pack, facts)["candidates"]

    def test_guilt_an_unanswered_parent_question_does_not_support_e28f(
        self, pack: census.PackUnderTest
    ) -> None:
        facts = {**self._FACTS, "investment.foreign_branch_or_subsidiary": _UNKNOWN}
        assert "E28F" not in _decide(pack, facts)["candidates"]

    def test_the_rule_names_the_parent_fact_in_its_required_facts(
        self, seq29: dict[str, Any]
    ) -> None:
        assert _rules(seq29)[fold_mod.E28F_RULE_ID]["required_facts"] == [
            "intent.purposes",
            "investment.foreign_branch_or_subsidiary",
            "investment.ikn_subsidiary",
            "investment.meets_published_threshold",
        ]

    def test_guilt_the_builder_refuses_a_rule_that_already_reads_the_parent_fact(
        self, seq29: dict[str, Any]
    ) -> None:
        with pytest.raises(SystemExit):
            fold_mod.build_e28f_rule(_rules(seq29)[fold_mod.E28F_RULE_ID])


class TestE31DSponsorIndonesian:
    _PERSONA = _read_json(_PERSONAS / "E31D.json")

    def test_the_gold_persona_is_rederived_with_an_indonesian_step_parent(self) -> None:
        facts = self._PERSONA["overrides"]
        assert facts["family.sponsor_nationalities"]["value"] == ["ID"]
        assert "family.sponsor_status_code" not in facts

    def test_innocence_the_rederived_persona_is_supported_on_both_packs(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> None:
        for candidate_pack in (pack, old_pack):
            actual = _decide(candidate_pack, self._PERSONA["overrides"])
            assert actual["state"] == "SUPPORTED_CANDIDATES"
            assert actual["candidates"] == ["E31D"]

    def test_guilt_a_foreign_step_parent_loses_e31d_with_a_named_reason(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> None:
        facts = {**self._PERSONA["overrides"], "family.sponsor_nationalities": _known(["NL"])}
        assert _decide(old_pack, facts)["candidates"] == ["E31D"]
        actual = _decide(pack, facts)
        assert actual["state"] == "NO_SUPPORTED_PATH"
        assert actual["no_path_reason_codes"] == ["E31D_REQ_SPONSOR_INDONESIAN"]

    def test_innocence_a_dual_national_step_parent_keeps_e31d(
        self, pack: census.PackUnderTest
    ) -> None:
        facts = {**self._PERSONA["overrides"], "family.sponsor_nationalities": _known(["NL", "ID"])}
        assert _decide(pack, facts)["candidates"] == ["E31D"]

    def test_guilt_an_unasked_sponsor_nationality_asks_for_it(
        self, pack: census.PackUnderTest
    ) -> None:
        facts = {**self._PERSONA["overrides"], "family.sponsor_nationalities": _UNKNOWN}
        actual = _decide(pack, facts)
        assert actual["state"] == "NEEDS_INPUT"
        assert actual["missing_facts"] == ["family.sponsor_nationalities"]

    def test_innocence_other_relations_are_not_asked_about_the_step_parent(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> None:
        facts = _family("SIBLING", **{"person.birth_date": _known("2012-01-01")})
        assert _decide(pack, facts)["candidates"] == _decide(old_pack, facts)["candidates"]


class TestE31JMinorAndSingle:
    def test_the_cited_kepmen_row_says_under_18_and_never_married(self) -> None:
        """BUILD GATE: the rules cite the Kepmen Lampiran (e3572ad2); its extracted E31J row is the ground."""

        raw = (
            _REPO_ROOT / "research/legal/2026-05-26-kepmen-visa-taxonomy/01-raw-extraction.md"
        ).read_text(encoding="utf-8")
        row = next(line for line in raw.splitlines() if line.startswith("| **E31J**"))
        assert "belum berusia 18 (delapan belas) tahun dan belum kawin" in row
        assert (
            fold_mod.SRC_KEPMEN_LAMPIRAN
            in _rules(_read_json(_SEQ29_SOURCE))[fold_mod.E31J_ADULT_RULE_ID]["source_refs"]
        )

    def test_guilt_an_adult_sibling_loses_e31j(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> None:
        facts = _family("SIBLING", **{"person.birth_date": _known(_ADULT)})
        assert _decide(old_pack, facts)["candidates"] == ["E31J"]
        actual = _decide(pack, facts)
        assert actual["state"] == "NO_SUPPORTED_PATH"
        assert actual["no_path_reason_codes"] == ["E31J_REQ_UNDER_18"]

    def test_guilt_a_married_minor_sibling_loses_e31j(self, pack: census.PackUnderTest) -> None:
        facts = _family("SIBLING", **{"person.marital_status": _known("MARRIED")})
        actual = _decide(pack, facts)
        assert actual["state"] == "NO_SUPPORTED_PATH"
        assert actual["no_path_reason_codes"] == ["E31J_REQ_UNMARRIED"]

    def test_innocence_a_single_minor_sibling_is_supported(
        self, pack: census.PackUnderTest
    ) -> None:
        actual = _decide(pack, _family("SIBLING"))
        assert actual["state"] == "SUPPORTED_CANDIDATES"
        assert actual["candidates"] == ["E31J"]

    def test_the_boundary_is_the_eighteenth_birthday(self, pack: census.PackUnderTest) -> None:
        # The engine measures age at the pack's own as-of instant, so pin both sides of it.
        as_of = pack.as_of
        eighteen = as_of.replace(year=as_of.year - 18)
        day_before = (eighteen - timedelta(days=2)).date().isoformat()
        day_after = (eighteen + timedelta(days=2)).date().isoformat()
        adult = _decide(pack, _family("SIBLING", **{"person.birth_date": _known(day_before)}))
        minor = _decide(pack, _family("SIBLING", **{"person.birth_date": _known(day_after)}))
        assert adult["no_path_reason_codes"] == ["E31J_REQ_UNDER_18"]
        assert minor["candidates"] == ["E31J"]

    def test_the_advisor_check_rule_is_gone_and_its_replacements_are_last(
        self, seq29: dict[str, Any]
    ) -> None:
        rules = _rules(seq29)
        assert "el.e31j-dependency-age" not in rules
        for rule_id in (fold_mod.E31J_ADULT_RULE_ID, fold_mod.E31J_MARRIED_RULE_ID):
            assert rules[rule_id]["stage"] == "HARD_FILTER"
            assert rules[rule_id]["on_unknown"] == "NEEDS_INPUT"
            assert rules[rule_id]["product_version_ids"] == [fold_mod.E31J_PRODUCT_VERSION_ID]

    def test_innocence_the_other_relations_see_no_e31j_reason(
        self, pack: census.PackUnderTest
    ) -> None:
        for relation in ("SPOUSE", "PARENT", "OTHER"):
            facts = _family(relation, **{"person.birth_date": _known(_ADULT)})
            codes = _decide(pack, facts)["no_path_reason_codes"]
            assert not {"E31J_REQ_UNDER_18", "E31J_REQ_UNMARRIED"} & set(codes), relation


class TestE31EReasonsScopedToTheParentRelation:
    @pytest.mark.parametrize("relation", ["SPOUSE", "SIBLING", "DEPENDENT", "OTHER"])
    def test_guilt_seq28_showed_the_e31e_sentence_to_other_relations(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest, relation: str
    ) -> None:
        facts = _family(
            relation,
            **{
                "person.birth_date": _known(_ADULT),
                "person.marital_status": _known("MARRIED"),
                "family.sponsor_nationalities": _known(["ID"]),
                "family.marriage_registered": _known(False),
            },
        )
        before = set(_decide(old_pack, facts)["no_path_reason_codes"])
        after = set(_decide(pack, facts)["no_path_reason_codes"])
        if relation in {"SPOUSE", "DEPENDENT", "OTHER"}:
            assert {"REQ_UNDER_18", "REQ_UNMARRIED"} & before, relation
        assert not {"REQ_UNDER_18", "REQ_UNMARRIED"} & after, relation

    def test_innocence_an_adult_child_of_an_itas_holder_keeps_the_age_reason(
        self, pack: census.PackUnderTest
    ) -> None:
        facts = _family("PARENT", **{"person.birth_date": _known(_ADULT)})
        assert "REQ_UNDER_18" in _decide(pack, facts)["no_path_reason_codes"]

    def test_innocence_a_married_minor_child_of_an_itas_holder_keeps_the_marital_reason(
        self, pack: census.PackUnderTest
    ) -> None:
        facts = _family("PARENT", **{"person.marital_status": _known("MARRIED")})
        assert "REQ_UNMARRIED" in _decide(pack, facts)["no_path_reason_codes"]

    def test_innocence_the_e31e_support_witness_is_unchanged(
        self, pack: census.PackUnderTest, old_pack: census.PackUnderTest
    ) -> None:
        facts = _family("PARENT")
        assert "E31E" in _decide(old_pack, facts)["candidates"]
        assert "E31E" in _decide(pack, facts)["candidates"]

    def test_the_builder_refuses_an_already_scoped_rule(self, seq29: dict[str, Any]) -> None:
        with pytest.raises(SystemExit):
            fold_mod.build_scoped_e31e_rule(_rules(seq29)[fold_mod.E31E_ADULT_RULE_ID])


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
    def _signed_or_skip(self) -> dict[str, Any]:
        if not _SEQ29_SIGNED.exists():
            pytest.skip("seq-29 is unsigned until the separate signing ceremony")
        return _read_json(_SEQ29_SIGNED)

    def test_jcs_payload_equals_source(self, seq29: dict[str, Any]) -> None:
        signed = self._signed_or_skip()
        assert canonicalize_json(signed["payload"]) == canonicalize_json(seq29)

    def test_verifies_under_the_pinned_prod_key(self) -> None:
        signed = self._signed_or_skip()
        verified = verify_rule_pack(
            signed,
            trust_store=StaticTrustStore.from_env(),
            observed_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert verified.pack.protected.kid == "prod-2026-07-1"
        assert verified.pack.payload.sequence == 29

    def test_anchor_is_the_seq28_digest(self) -> None:
        signed = self._signed_or_skip()
        assert signed["payload"]["previous_payload_sha256"] == fold_mod.SEQ28_PAYLOAD_SHA256

    def test_guilt_one_flipped_byte_breaks_signature(self) -> None:
        signed = copy.deepcopy(self._signed_or_skip())
        signed["payload"]["created_by"] += "x"
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                signed,
                trust_store=StaticTrustStore.from_env(),
                observed_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
