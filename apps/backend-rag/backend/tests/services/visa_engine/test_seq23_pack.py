"""Gates for seq-23 (``fold_pack_seq23.py``): the eight one-off human-review
holds become named dead ends, four existing hard filters stop holding on an
unknown fact, and three new fallback dead ends carry the RETIREMENT/STUDY
thresholds their own SUPPORT rule already enforces. Slice A8-1
(``MANDATE-vo.md``, DRAFT-SPEC-A8-1.v2 §1). CANDIDATE ONLY — this fold is
never signed or activated by itself.

Ground: ``fold_pack_seq23.py``'s own docstring and DRAFT-SPEC-A8-1.v2 §1's
disposition table. The anchor is the REAL, production
``rulepack-prod-022.signed.json`` on disk, verified against the pinned
production public key — exactly as ``fold_pack_seq22.py``'s own gates verify
seq-20. If either on-disk artifact is missing these tests FAIL; they never
skip (cicatrix #2 — a green suite that ran no witness proves nothing).

Every behavioural witness is stated TWICE — guilt (the defect is present and
refused) and innocence (the legitimate shape the same guard still allows).
One test per §1 row (A8.2), the twin-basis antibody re-run on this fold's own
output (A8.3), and the derived review inventory (A8.4: ``pack_review_rules ==
1``, ``pack_unknown_escalations == 0``).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_pack import wrap_as_unsigned_pack
from backend.scripts.visa_engine.fold_pack_seq23 import (
    E33E_SUPPORT_RULE_ID,
    E33F_SUPPORT_RULE_ID,
    INSERTED_RULE_IDS,
    MODIFIED_RULE_IDS,
    NO_PREDECESSOR_INSERTED_RULE_IDS,
    REMOVED_RULE_IDS,
    REMOVED_TO_INSERTED,
    RETIREMENT_INCOME_FACT,
    SEQ22_PAYLOAD_SHA256,
    STUDIO_RULE_ID,
    STUDY_SUPPORT_RULE_ID,
    SYNTHESISED_TWIN_BASIS_FACTS,
    _assert_candidate_review_inventory,
    _assert_e33e_e33f_retirement_bounds_are_equal,
    _rule_pack_id,
    _rules_by_id,
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact,
    assert_only_expected_changes,
    fold,
)
from backend.services.visa_engine import compiler
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import RulePackPayload

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ22_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-022.source.json"
_SEQ22_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-022.signed.json"
_SEQ23_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-023.source.json"

#: The pinned production Ed25519 PUBLIC key — the same constant
#: `test_seq20_signed_bundle.py` verifies seq-20 with, and `test_seq22_pack.py`
#: verifies seq-20 with. A public key is not a secret.
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

#: Shortly after seq-22's own `signed_at` (2026-09-16T17:48:07Z) — fixed,
#: never `datetime.now()`, so this file never rots into a time-dependent red.
OBSERVED_AT = datetime(2026, 9, 16, 18, 0, 0, tzinfo=timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk. This must FAIL, not skip: a "
            "witness that never ran proves nothing (cicatrix #2)."
        )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq22_source() -> dict[str, Any]:
    return _read_json(_SEQ22_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq22_signed() -> dict[str, Any]:
    return _read_json(_SEQ22_SIGNED_PATH)


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


@pytest.fixture
def seq23_source(
    seq22_source: dict[str, Any],
    seq22_signed: dict[str, Any],
    prod_trust_store_env: None,
) -> dict[str, Any]:
    return fold(seq22_source, seq22_signed, observed_at=OBSERVED_AT)


def _compiled(payload_dict: dict[str, Any]) -> compiler.CompiledRulePack:
    payload = RulePackPayload.model_validate(payload_dict)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture
def seq23_compiled(seq23_source: dict[str, Any]) -> compiler.CompiledRulePack:
    return _compiled(seq23_source)


# ---------------------------------------------------------------------------
# Fold integrity — the anchor, the chain, the shape of the edit (A8.1, A8.1b).
# ---------------------------------------------------------------------------


class TestFoldIntegrity:
    def test_fold_refuses_without_a_verifiable_anchor(
        self,
        seq22_source: dict[str, Any],
        seq22_signed: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", raising=False)
        with pytest.raises(SystemExit) as excinfo:
            fold(seq22_source, seq22_signed, observed_at=OBSERVED_AT)
        assert "verify" in str(excinfo.value)

    def test_fold_refuses_a_source_that_is_not_the_signed_digest(
        self,
        seq22_source: dict[str, Any],
        seq22_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        """GUILT: flip one anchor byte -> the fold aborts naming the digest."""
        tampered = {**seq22_source, "version": "9999.9.9-tampered"}
        with pytest.raises(SystemExit) as excinfo:
            fold(tampered, seq22_signed, observed_at=OBSERVED_AT)
        assert "not the activated artifact" in str(excinfo.value)

    def test_fold_chains_to_seq22(self, seq23_source: dict[str, Any]) -> None:
        assert seq23_source["previous_payload_sha256"] == SEQ22_PAYLOAD_SHA256
        assert (
            SEQ22_PAYLOAD_SHA256
            == "3d7555afcc9496b451bc86235624b4a88d35aabb9df354778dcf9b0b3b276e37"
        )

    def test_fold_identity_fields(self, seq23_source: dict[str, Any]) -> None:
        assert seq23_source["sequence"] == 23
        assert seq23_source["rule_pack_id"] == str(_rule_pack_id(23))
        assert seq23_source["rule_pack_id"] == "a72aa24f-344a-58c1-809d-076a9227a1f0"
        assert seq23_source["rollback_of_payload_sha256"] is None

    def test_fold_retires_eight_inserts_eleven_modifies_four(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        before = set(_rules_by_id(seq22_source))
        after = set(_rules_by_id(seq23_source))
        assert before - after == REMOVED_RULE_IDS
        assert after - before == INSERTED_RULE_IDS
        assert len(REMOVED_RULE_IDS) == 8
        assert len(INSERTED_RULE_IDS) == 11
        assert len(NO_PREDECESSOR_INSERTED_RULE_IDS) == 3
        assert len(MODIFIED_RULE_IDS) == 4
        assert len(set(REMOVED_TO_INSERTED.values())) == 8

    def test_fold_edits_no_rule_outside_the_disposition_table(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        before = _rules_by_id(seq22_source)
        after = _rules_by_id(seq23_source)
        for rule_id, rule in after.items():
            if rule_id in INSERTED_RULE_IDS or rule_id in MODIFIED_RULE_IDS:
                continue
            assert canonicalize_json(rule) == canonicalize_json(before[rule_id]), rule_id

    def test_the_studio_rule_is_brought_forward_byte_identical(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        """INNOCENCE: D23 "OPTION B-STUDIO" stays untouched by this fold."""
        before = _rules_by_id(seq22_source)[STUDIO_RULE_ID]
        after = _rules_by_id(seq23_source)[STUDIO_RULE_ID]
        assert canonicalize_json(before) == canonicalize_json(after)

    def test_fold_touches_no_other_top_level_key(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        for key in set(seq22_source) - {
            "sequence",
            "version",
            "rule_pack_id",
            "created_at",
            "created_by",
            "previous_payload_sha256",
            "rollback_of_payload_sha256",
            "rules",
        }:
            assert canonicalize_json(seq23_source[key]) == canonicalize_json(seq22_source[key]), key

    def test_fold_is_deterministic(
        self,
        seq22_source: dict[str, Any],
        seq22_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        first = fold(seq22_source, seq22_signed, observed_at=OBSERVED_AT)
        second = fold(seq22_source, seq22_signed, observed_at=OBSERVED_AT)
        assert first == second

    def test_the_emitted_source_on_disk_is_what_this_fold_produces(
        self, seq23_source: dict[str, Any]
    ) -> None:
        on_disk = _read_json(_SEQ23_SOURCE_PATH)
        assert canonicalize_json(on_disk) == canonicalize_json(seq23_source)

    def test_output_refuses_a_signed_path(
        self, seq22_source: dict[str, Any], seq22_signed: dict[str, Any], tmp_path: Path
    ) -> None:
        """A8.1b: the fold's own CLI refuses to write a `.signed.json`
        output — exercised through the module's `main`, the same idiom
        `fold_pack_seq22.py`'s own test suite uses."""
        from backend.scripts.visa_engine import fold_pack_seq23

        seq22_path = tmp_path / "rulepack-prod-022.source.json"
        seq22_path.write_text(json.dumps(seq22_source), encoding="utf-8")
        signed_path = tmp_path / "rulepack-prod-022.signed.json"
        signed_path.write_text(json.dumps(seq22_signed), encoding="utf-8")
        output = tmp_path / "rulepack-prod-023.signed.json"
        with pytest.raises(SystemExit) as excinfo:
            fold_pack_seq23.main(
                ["--seq22-source", str(seq22_path), "--output", str(output)],
                observed_at=OBSERVED_AT,
            )
        assert "signed.json" in str(excinfo.value)
        assert not output.exists()

    def test_output_refuses_to_collide_with_an_input(
        self, seq22_source: dict[str, Any], seq22_signed: dict[str, Any], tmp_path: Path
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq23

        seq22_path = tmp_path / "rulepack-prod-022.source.json"
        seq22_path.write_text(json.dumps(seq22_source), encoding="utf-8")
        signed_path = tmp_path / "rulepack-prod-022.signed.json"
        signed_path.write_text(json.dumps(seq22_signed), encoding="utf-8")
        with pytest.raises(SystemExit) as excinfo:
            fold_pack_seq23.main(
                ["--seq22-source", str(seq22_path), "--output", str(seq22_path)],
                observed_at=OBSERVED_AT,
            )
        assert "same file" in str(excinfo.value)


# ---------------------------------------------------------------------------
# A8.2 — exactly §1, by id. One test per row: INNOCENCE the built rule is the
# copied/derived shape DRAFT-SPEC-A8-1.v2 §1 names; GUILT reverting the row
# in a scratch copy fails `assert_only_expected_changes` naming the rule id.
# ---------------------------------------------------------------------------


class TestDispositionTableRows:
    def test_calling_visa_nationality_is_copied_from_the_review_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)["review.calling-visa"]
        rule = _rules_by_id(seq23_source)["hf.calling-visa-nationality"]
        assert rule["when"] == donor["when"]
        assert rule["scope"] == "GLOBAL"
        assert rule["product_version_ids"] is None
        assert rule["stage"] == "HARD_FILTER"
        assert rule["effect"] == {
            "type": "EXCLUDE",
            "reason_code": "CALLING_VISA_NATIONALITY_NOT_ASSESSED",
        }
        assert rule["on_unknown"] == "NEEDS_INPUT"
        assert rule["source_refs"] == donor["source_refs"]
        assert rule["safety_critical"] == donor["safety_critical"] is True

    def test_b1_voa_dual_nationality_is_branch_one_of_the_citizenship_conflict_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        """The one row that is not a straight copy: branch 2 of
        `review.citizenship-conflict`'s `any` — the calling-visa dual
        nationality conflict — is deliberately absent, subsumed by
        `hf.calling-visa-nationality` above."""
        donor = _rules_by_id(seq22_source)["review.citizenship-conflict"]
        rule = _rules_by_id(seq23_source)["hf.b1.voa-dual-nationality"]
        assert rule["when"] == donor["when"]["args"][0]
        assert rule["when"] != donor["when"]["args"][1]
        b1_filter = _rules_by_id(seq22_source)["hf.b1.not-voa-nationality"]
        assert rule["scope"] == "PRODUCTS"
        assert rule["product_version_ids"] == b1_filter["product_version_ids"]
        assert rule["effect"]["reason_code"] == "VOA_DUAL_NATIONALITY_NOT_ASSESSED"
        assert rule["on_unknown"] == "NEEDS_INPUT"
        assert rule["source_refs"] == donor["source_refs"]

    def test_active_overstay_is_copied_from_the_review_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)["review.active-overstay"]
        rule = _rules_by_id(seq23_source)["hf.active-overstay"]
        assert donor["on_unknown"] == "NEEDS_INPUT", "NI was already kept on the review rule"
        assert rule["when"] == donor["when"]
        assert rule["scope"] == "GLOBAL"
        assert rule["effect"]["reason_code"] == "ACTIVE_OVERSTAY_SETTLE_FIRST"
        assert rule["on_unknown"] == "NEEDS_INPUT"

    def test_minor_without_confirmed_sponsor_is_copied_from_the_review_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)["review.minor-without-guardian"]
        rule = _rules_by_id(seq23_source)["hf.minor-without-confirmed-sponsor"]
        assert rule["when"] == donor["when"]
        assert rule["scope"] == "GLOBAL"
        assert rule["effect"]["reason_code"] == "MINOR_SPONSOR_NOT_CONFIRMED"
        assert rule["on_unknown"] == "NEEDS_INPUT"

    def test_bridging_adverse_history_is_copied_from_the_review_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)["review.bridging.adverse-history"]
        rule = _rules_by_id(seq23_source)["hf.bridging.adverse-history"]
        assert donor["on_unknown"] == "HUMAN_REVIEW", "this row is a '+ NI' flip, not a carry"
        assert rule["when"] == donor["when"]
        assert rule["scope"] == "PRODUCTS"
        assert rule["product_version_ids"] == donor["product_version_ids"]
        assert rule["effect"]["reason_code"] == "BRIDGING_ADVERSE_HISTORY_NOT_ASSESSED"
        assert rule["on_unknown"] == "NEEDS_INPUT"

    def test_e33_employment_not_covered_is_copied_from_the_review_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)["review.e33.work-rangkap-kegiatan"]
        rule = _rules_by_id(seq23_source)["hf.e33.employment-not-covered"]
        assert rule["when"] == donor["when"]
        assert rule["scope"] == "PRODUCTS"
        assert rule["product_version_ids"] == donor["product_version_ids"]
        assert rule["effect"]["reason_code"] == "E33_EMPLOYMENT_NOT_COVERED"
        assert rule["on_unknown"] == "NEEDS_INPUT"

    def test_e33g_local_market_is_copied_from_the_review_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)["review.e33g.local-market"]
        rule = _rules_by_id(seq23_source)["hf.e33g.local-market"]
        assert rule["when"] == donor["when"]
        assert rule["product_version_ids"] == donor["product_version_ids"]
        assert rule["effect"]["reason_code"] == "E33G_LOCAL_MARKET_NOT_ALLOWED"
        assert rule["on_unknown"] == "NEEDS_INPUT"

    def test_e33g_local_company_ownership_is_copied_from_the_review_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)["review.e33g.local-company-ownership"]
        rule = _rules_by_id(seq23_source)["hf.e33g.local-company-ownership"]
        assert rule["when"] == donor["when"]
        assert rule["product_version_ids"] == donor["product_version_ids"]
        assert rule["effect"]["reason_code"] == "E33G_LOCAL_COMPANY_NOT_ALLOWED"
        assert rule["on_unknown"] == "NEEDS_INPUT"

    def test_study_admission_or_sponsor_unconfirmed_negates_the_support_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)[STUDY_SUPPORT_RULE_ID]
        rule = _rules_by_id(seq23_source)["hf.study.admission-or-sponsor-unconfirmed"]
        assert rule["when"] == {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["STUDY"]},
                {
                    "op": "any",
                    "args": [
                        {"op": "eq", "fact": "study.admission_confirmed", "value": False},
                        {"op": "eq", "fact": "study.sponsor_confirmed", "value": False},
                    ],
                },
            ],
        }
        assert rule["scope"] == "PRODUCTS"
        assert rule["product_version_ids"] == donor["product_version_ids"]
        assert rule["source_refs"] == donor["source_refs"]
        assert rule["on_unknown"] == "NO_EFFECT"
        assert rule["safety_critical"] is False

    def test_e33e_retirement_income_below_minimum_negates_its_support_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)[E33E_SUPPORT_RULE_ID]
        rule = _rules_by_id(seq23_source)["hf.e33e.retirement-income-below-minimum"]
        assert rule["when"] == {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["RETIREMENT"]},
                {"op": "lt", "fact": RETIREMENT_INCOME_FACT, "value": 3000},
            ],
        }
        assert rule["product_version_ids"] == donor["product_version_ids"]
        assert rule["source_refs"] == donor["source_refs"]
        assert rule["on_unknown"] == "NO_EFFECT"

    def test_e33f_retirement_income_below_minimum_negates_its_support_rule(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        donor = _rules_by_id(seq22_source)[E33F_SUPPORT_RULE_ID]
        rule = _rules_by_id(seq23_source)["hf.e33f.retirement-income-below-minimum"]
        assert rule["when"] == {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["RETIREMENT"]},
                {"op": "lt", "fact": RETIREMENT_INCOME_FACT, "value": 3000},
            ],
        }
        assert rule["product_version_ids"] == donor["product_version_ids"]
        assert rule["source_refs"] == donor["source_refs"]
        assert rule["on_unknown"] == "NO_EFFECT"

    @pytest.mark.parametrize("rule_id", sorted(MODIFIED_RULE_IDS))
    def test_the_four_modified_hard_filters_flip_on_unknown_only(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any], rule_id: str
    ) -> None:
        before = _rules_by_id(seq22_source)[rule_id]
        after = _rules_by_id(seq23_source)[rule_id]
        assert before["on_unknown"] == "HUMAN_REVIEW"
        assert after["on_unknown"] == "NEEDS_INPUT"
        assert canonicalize_json({**before, "on_unknown": "NEEDS_INPUT"}) == canonicalize_json(after)

    @pytest.mark.parametrize("removed_id", sorted(REMOVED_RULE_IDS))
    def test_guilt_reverting_a_removed_row_fails_naming_the_rule_id(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any], removed_id: str
    ) -> None:
        """GUILT: put the retired review.* rule back in the output (a
        revert-in-a-scratch-copy) and `assert_only_expected_changes` refuses,
        naming the removed-rule mismatch."""
        tampered = copy.deepcopy(seq23_source)
        donor = copy.deepcopy(_rules_by_id(seq22_source)[removed_id])
        tampered["rules"].append(donor)
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq22_source, tampered)
        assert removed_id in str(excinfo.value)

    @pytest.mark.parametrize("inserted_id", sorted(INSERTED_RULE_IDS))
    def test_guilt_dropping_an_inserted_row_fails_naming_the_rule_id(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any], inserted_id: str
    ) -> None:
        """GUILT: drop one inserted hf.* rule in a scratch copy and
        `assert_only_expected_changes` refuses, naming the added-rule
        mismatch."""
        tampered = copy.deepcopy(seq23_source)
        tampered["rules"] = [r for r in tampered["rules"] if r["rule_id"] != inserted_id]
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq22_source, tampered)
        assert inserted_id in str(excinfo.value)

    @pytest.mark.parametrize("rule_id", sorted(MODIFIED_RULE_IDS))
    def test_guilt_reverting_a_modified_row_fails_naming_the_rule_id(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any], rule_id: str
    ) -> None:
        """GUILT: revert one modified rule's `on_unknown` back to
        HUMAN_REVIEW in a scratch copy — `assert_only_expected_changes`
        refuses, naming the rule id."""
        tampered = copy.deepcopy(seq23_source)
        for rule in tampered["rules"]:
            if rule["rule_id"] == rule_id:
                rule["on_unknown"] = "HUMAN_REVIEW"
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq22_source, tampered)
        assert rule_id in str(excinfo.value)

    def test_innocence_the_real_pack_passes_assert_only_expected_changes(
        self, seq22_source: dict[str, Any], seq23_source: dict[str, Any]
    ) -> None:
        assert_only_expected_changes(seq22_source, seq23_source)


# ---------------------------------------------------------------------------
# A8.3 — antibodies copied, not weakened.
# ---------------------------------------------------------------------------


class TestAntibodies:
    def test_innocence_the_real_pack_passes_the_twin_basis_guard(
        self, seq23_source: dict[str, Any]
    ) -> None:
        assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(seq23_source)

    @pytest.mark.parametrize("fact", SYNTHESISED_TWIN_BASIS_FACTS)
    def test_guilt_adding_a_twin_basis_fact_to_a_retirement_filter_aborts(
        self, seq23_source: dict[str, Any], fact: str
    ) -> None:
        """GUILT: add `secondhome.bank_deposit_usd` (or any of its three
        twin-basis siblings) to a retirement HARD_FILTER and the fold-time
        antibody refuses — same shape, same guard, on the NEW rules this
        fold inserts rather than the seq-21/22 rule the antibody was first
        written against."""
        tampered = copy.deepcopy(seq23_source)
        rules_by_id = _rules_by_id(tampered)
        target = rules_by_id["hf.e33e.retirement-income-below-minimum"]
        target["when"]["args"].append({"op": "eq", "fact": fact, "value": False})
        with pytest.raises(SystemExit) as excinfo:
            assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(tampered)
        assert "hf.e33e.retirement-income-below-minimum" in str(excinfo.value)

    def test_e33e_and_e33f_retirement_bounds_agree(self, seq23_source: dict[str, Any]) -> None:
        assert _assert_e33e_e33f_retirement_bounds_are_equal(seq23_source) == 3000

    def test_guilt_a_moved_retirement_bound_aborts_the_fold(
        self, seq23_source: dict[str, Any]
    ) -> None:
        """GUILT: change one donor SUPPORT rule's bound and the fold refuses
        rather than emit two RETIREMENT hard filters that disagree."""
        tampered = copy.deepcopy(seq23_source)
        rules_by_id = _rules_by_id(tampered)
        donor = rules_by_id[E33F_SUPPORT_RULE_ID]
        for node in donor["when"]["args"]:
            if node.get("fact") == RETIREMENT_INCOME_FACT and node.get("op") == "gte":
                node["value"] = 4000
        with pytest.raises(SystemExit) as excinfo:
            _assert_e33e_e33f_retirement_bounds_are_equal(tampered)
        assert "3000" in str(excinfo.value) or "4000" in str(excinfo.value)


# ---------------------------------------------------------------------------
# A8.4 — the inventory target, derived.
# ---------------------------------------------------------------------------


class TestDerivedInventory:
    def test_innocence_the_candidate_carries_exactly_one_review_rule_and_no_escalation(
        self, seq23_source: dict[str, Any]
    ) -> None:
        _assert_candidate_review_inventory(seq23_source)

    def test_guilt_keeping_human_review_on_a_bridging_filter_fails_naming_it(
        self, seq23_source: dict[str, Any]
    ) -> None:
        """GUILT: keep `HUMAN_REVIEW` on one bridging filter and the derived
        inventory refuses — `pack_unknown_escalations` is no longer empty."""
        tampered = copy.deepcopy(seq23_source)
        for rule in tampered["rules"]:
            if rule["rule_id"] == "hf.bridging.offshore":
                rule["on_unknown"] = "HUMAN_REVIEW"
        with pytest.raises(SystemExit) as excinfo:
            _assert_candidate_review_inventory(tampered)
        assert "hf.bridging.offshore" in str(excinfo.value)


# ---------------------------------------------------------------------------
# The pack still validates and compiles.
# ---------------------------------------------------------------------------


def test_the_candidate_payload_validates_against_the_model(seq23_source: dict[str, Any]) -> None:
    validated = RulePackPayload.model_validate(seq23_source)
    assert validated.sequence == 23


def test_the_candidate_pack_compiles(seq23_compiled: compiler.CompiledRulePack) -> None:
    assert seq23_compiled.sequence == 23
