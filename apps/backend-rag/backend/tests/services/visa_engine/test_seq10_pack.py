"""E5 increment 4 — chain/re-stamp/cure gates for the assembled
``rulepack-prod-010.source.json`` (see
``backend.scripts.visa_engine.fold_pack_seq10``).

Six checks, each verified against the real files on disk:

(a) chain gate — seq-10's ``previous_payload_sha256`` equals the
    RECOMPUTED SHA256(JCS(...)) of seq-9's own source payload (never a
    declared-field-vs-declared-field comparison — the house pattern from
    ``test_pack_chain_and_pricing.py``'s TestChainGate, one generation
    later in the chain); ``sequence``/``rule_pack_id`` match the uuid5
    convention.
(b) re-stamp gate — all 17 re-stamped records carry the 2026-08-19
    ``verified_at`` values from ``source-restamp-edits.json`` and are
    otherwise byte-identical to seq-9; ``ee8fe5b8`` is gone and no
    dangling refs survive anywhere.
(c) cure structure — ``el.c2.corporate-sponsor-type`` absent,
    ``hf.e31c-marriage-not-registered`` present,
    ``el.e31c-mixed-marriage-parents`` tightened (4 conjuncts).
(d) the inc-2 lints run over EVERY seq-10 rule and find ZERO defects —
    this flips ``test_pack_chain_and_pricing.py``'s
    ``_KNOWN_PRE_EXISTING_LINT_RESIDUALS`` declaration to the cured
    state (that test keeps pinning seq-9's TRUE state; this one pins
    seq-10's).
(e) evaluator witnesses (house pattern
    ``test_seq9_new_rule_witnesses.py`` — per-product
    ``evaluate_product``, never the aggregated Decision): E31C
    guilt/innocence/tri-state for the marriage gate, WITH the seq-9
    defect pinned alongside (the CP3 probe's exact shape: seq-9 reached
    SUPPORTED with ``marriage_registered=false``; seq-10 EXCLUDES it);
    C2 behavior-preservation (same facts SUPPORT on both packs, the
    retired reason code absent from seq-10's proof).
(f) freshness — zero seq-10 sources are stale at the fold date under
    their own ``freshness_policy`` (the exact disease seq-9 shipped
    with: 18/29 past their 7-day window).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_claims import (
    lint_duplicate_subtree,
    lint_unsatisfiable_condition,
)
from backend.scripts.visa_engine.compile_pack import (
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.enums import FactPath
from backend.services.visa_engine.evaluator import ProductProof, ProductProofStatus
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _gold_fixtures as gf

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS_DIR = (
    _REPO_ROOT
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
)
_SEQ9_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-009.source.json"
_SEQ9_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-009.signed.json"
_SEQ10_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-010.source.json"

_RESTAMP_EDITS_PATH = (
    _REPO_ROOT
    / "research"
    / "visa"
    / "doctrine-factory"
    / "e5"
    / "inc4-pack-edits"
    / "source-restamp-edits.json"
)

_EE8FE5B8_ID = "ee8fe5b8-b0b4-544a-bf9a-fe53c3e316f2"
_RETIRED_RULE_ID = "el.c2.corporate-sponsor-type"
_EDITED_RULE_ID = "el.e31c-mixed-marriage-parents"
_INSERTED_RULE_ID = "hf.e31c-marriage-not-registered"

# Any instant on/after the inserted rule's valid_period.from
# (2026-08-19T00:00:00Z) and inside every inherited rule's window.
AT = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq9_source() -> dict[str, Any]:
    return _read_json(_SEQ9_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq10_source() -> dict[str, Any]:
    return _read_json(_SEQ10_SOURCE_PATH)


def _compiled(name: str) -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(_PACKS_DIR / name)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def seq10() -> compiler.CompiledRulePack:
    return _compiled("rulepack-prod-010.source.json")


@pytest.fixture(scope="module")
def seq9() -> compiler.CompiledRulePack:
    return _compiled("rulepack-prod-009.source.json")


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def _proof(
    compiled: compiler.CompiledRulePack, product_code: str, overrides: dict[str, Any]
) -> ProductProof:
    facts = gf.applicant_facts(overrides=overrides)
    snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=AT)
    product = next(p for p in compiled.products if p.product_code == product_code)
    rules = compiled.rules_for(product, effective_at=AT)
    purposes = frozenset(snapshot.values[FactPath.INTENT_PURPOSES].value)
    return evaluator.evaluate_product(
        product=product,
        rules=rules,
        facts=snapshot,
        purposes=purposes,
        fact_registry=DEFAULT_FACT_REGISTRY,
    )


def _reason_codes(proof: ProductProof) -> set[str]:
    return {r.code for r in proof.reasons}


# ---------------------------------------------------------------------------
# (a) chain + identity
# ---------------------------------------------------------------------------


class TestChainGate:
    def test_previous_payload_sha256_chains_to_recomputed_seq9(
        self, seq9_source: dict[str, Any], seq10_source: dict[str, Any]
    ) -> None:
        recomputed = hashlib.sha256(canonicalize_json(seq9_source)).hexdigest()
        seq9_signed = _read_json(_SEQ9_SIGNED_PATH)
        assert recomputed == seq9_signed["payload_sha256"]
        assert seq10_source["previous_payload_sha256"] == recomputed

    def test_sequence_is_10(self, seq10_source: dict[str, Any]) -> None:
        assert seq10_source["sequence"] == 10

    def test_rule_pack_id_matches_uuid5_convention(
        self, seq10_source: dict[str, Any]
    ) -> None:
        expected = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/10",
        )
        assert seq10_source["rule_pack_id"] == str(expected)
        # Formula sanity: the same convention reproduces seq-9's id.
        seq9_expected = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/9",
        )
        assert str(seq9_expected) == "66eb0b4c-58ee-56c3-812c-2acc26fff8ce"


# ---------------------------------------------------------------------------
# (b) re-stamp + drop + no dangling refs
# ---------------------------------------------------------------------------


class TestSourceRestamp:
    def test_all_17_restamps_applied_and_nothing_else_changed(
        self, seq9_source: dict[str, Any], seq10_source: dict[str, Any]
    ) -> None:
        edits = _read_json(_RESTAMP_EDITS_PATH)["restamps"]
        assert len(edits) == 17
        seq10_records = {r["source_record_id"]: r for r in seq10_source["source_records"]}
        seq9_records = {r["source_record_id"]: r for r in seq9_source["source_records"]}
        for edit in edits:
            record = seq10_records[edit["source_record_id"]]
            assert record["verified_at"] == edit["new_verified_at"]
            assert record["verified_by"] == edit["new_verified_by"]
            assert record["verified_at"].startswith("2026-08-19T")
            # Everything else byte-identical to seq-9.
            baseline = dict(seq9_records[edit["source_record_id"]])
            candidate = dict(record)
            for key in ("verified_at", "verified_by"):
                baseline.pop(key), candidate.pop(key)
            assert baseline == candidate

    def test_ee8fe5b8_is_gone_and_was_the_only_removal(
        self, seq9_source: dict[str, Any], seq10_source: dict[str, Any]
    ) -> None:
        seq9_ids = {r["source_record_id"] for r in seq9_source["source_records"]}
        seq10_ids = {r["source_record_id"] for r in seq10_source["source_records"]}
        assert seq9_ids - seq10_ids == {_EE8FE5B8_ID}
        assert not seq10_ids - seq9_ids

    def test_no_dangling_source_refs(self, seq10_source: dict[str, Any]) -> None:
        record_ids = {r["source_record_id"] for r in seq10_source["source_records"]}
        for rule in seq10_source["rules"]:
            for ref in rule["source_refs"]:
                assert ref in record_ids, f"{rule['rule_id']} dangles {ref}"
        for product in seq10_source["products"]:
            for ref in product.get("source_refs", []):
                assert ref in record_ids, f"{product['product_code']} dangles {ref}"

    def test_zero_stale_sources_at_the_fold_date(
        self, seq10_source: dict[str, Any]
    ) -> None:
        """The exact disease seq-9 shipped with (18/29 past their 7-day
        window) is cured: at the fold date every record with a
        MAX_AGE_SINCE_VERIFIED_AT policy is inside its window."""
        stale = []
        for record in seq10_source["source_records"]:
            policy = record.get("freshness_policy") or {}
            if policy.get("kind") != "MAX_AGE_SINCE_VERIFIED_AT":
                continue
            verified_at = datetime.fromisoformat(record["verified_at"].replace("Z", "+00:00"))
            age = (AT - verified_at).total_seconds()
            # Codex refuter finding 6: a FUTURE verified_at yields negative
            # age and would pass a max-age-only check — a stamp from the
            # future is a lie, not freshness.
            assert age >= 0, (
                f"{record['source_record_id']}: verified_at {record['verified_at']} "
                f"is in the future relative to the fold date {AT.isoformat()}"
            )
            if age > policy["max_age_seconds"]:
                stale.append(record["source_record_id"])
        assert stale == []


# ---------------------------------------------------------------------------
# (c) cure structure
# ---------------------------------------------------------------------------


class TestCureStructure:
    def test_c2_rule_retired_and_hf_inserted(self, seq10_source: dict[str, Any]) -> None:
        ids = {r["rule_id"] for r in seq10_source["rules"]}
        assert _RETIRED_RULE_ID not in ids
        assert _INSERTED_RULE_ID in ids

    def test_rule_count_is_seq9_minus_1_plus_1(
        self, seq9_source: dict[str, Any], seq10_source: dict[str, Any]
    ) -> None:
        assert len(seq10_source["rules"]) == len(seq9_source["rules"])

    def test_e31c_rule_tightened_to_four_conjuncts(
        self, seq10_source: dict[str, Any]
    ) -> None:
        rule = next(r for r in seq10_source["rules"] if r["rule_id"] == _EDITED_RULE_ID)
        args = rule["when"]["args"]
        assert len(args) == 4
        facts = {a["fact"] for a in args}
        assert facts == {
            "intent.purposes",
            "family.relation_to_sponsor",
            "family.sponsor_nationalities",
            "family.marriage_registered",
        }
        assert rule["effect"]["reason_code"] == "REQ_MIXED_MARRIAGE_PARENTS"
        assert rule["required_facts"] == sorted(facts)


# ---------------------------------------------------------------------------
# (d) inc-2 lints — ZERO findings on seq-10
# ---------------------------------------------------------------------------


class TestInc2LintsOverEverySeq10Rule:
    def test_zero_lint_findings(self, seq10_source: dict[str, Any]) -> None:
        flagged: set[str] = set()
        for rule in seq10_source["rules"]:
            unsat_findings, skip_note = lint_unsatisfiable_condition(
                rule_id=rule["rule_id"], when=rule["when"]
            )
            assert skip_note is None, f"{rule['rule_id']}: unexpected skip ({skip_note})"
            dup_findings = lint_duplicate_subtree(rule_id=rule["rule_id"], when=rule["when"])
            if unsat_findings or dup_findings:
                flagged.add(rule["rule_id"])
        assert flagged == set()


# ---------------------------------------------------------------------------
# (e) evaluator witnesses
# ---------------------------------------------------------------------------

_E31C_BASE = {
    "intent.purposes": _known(["FAMILY"]),
    "family.relation_to_sponsor": _known("PARENT"),
    "family.sponsor_nationalities": _known(["ID"]),
}


class TestE31CMarriageGateWitnesses:
    def test_guilt_unregistered_marriage_is_excluded(
        self, seq10: compiler.CompiledRulePack
    ) -> None:
        proof = _proof(
            seq10,
            "E31C",
            {**_E31C_BASE, "family.marriage_registered": _known(False)},
        )
        assert proof.status is ProductProofStatus.EXCLUDED
        assert "REQ_PARENTS_MARRIAGE_REGISTERED" in _reason_codes(proof)

    def test_seq9_defect_pinned_same_facts_reached_supported(
        self, seq9: compiler.CompiledRulePack
    ) -> None:
        """The CP3 probe's exact shape: on seq-9 an applicant with
        ``marriage_registered=false`` still reached SUPPORTED (the vacuous
        rule never tested the marriage). Pinned so the cure is measurable
        — if this ever starts failing, seq-9's bytes changed."""
        proof = _proof(
            seq9,
            "E31C",
            {**_E31C_BASE, "family.marriage_registered": _known(False)},
        )
        assert proof.status is ProductProofStatus.SUPPORTED

    def test_innocence_registered_marriage_wni_parent_is_supported(
        self, seq10: compiler.CompiledRulePack
    ) -> None:
        proof = _proof(
            seq10,
            "E31C",
            {**_E31C_BASE, "family.marriage_registered": _known(True)},
        )
        assert proof.status is ProductProofStatus.SUPPORTED
        # SUPPORT reasons live in support_rules, not reasons (ProductProof
        # populates `reasons` only for EXCLUDED/REVIEW).
        assert _EDITED_RULE_ID in {r.rule_id for r in proof.support_rules}

    def test_tristate_unknown_marriage_blocks_never_excludes(
        self, seq10: compiler.CompiledRulePack
    ) -> None:
        """``marriage_registered`` explicitly UNKNOWN (the gold baseline
        pins it KNOWN-false, so the override is required): the
        HARD_FILTER's ``on_unknown=NEEDS_INPUT`` must ask, never assume
        exclusion — and the product must not be conclusively SUPPORTED
        either (the tightened rule also needs the fact)."""
        proof = _proof(
            seq10,
            "E31C",
            {**_E31C_BASE, "family.marriage_registered": gf.unknown("NOT_ASKED")},
        )
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert proof.status is not ProductProofStatus.EXCLUDED

    def test_non_family_applicant_is_not_contaminated(
        self, seq9: compiler.CompiledRulePack, seq10: compiler.CompiledRulePack
    ) -> None:
        """Codex refuter finding 1 (2026-08-19), regression-pinned: the
        first draft's single-leaf HARD_FILTER (marriage==false alone, no
        purpose/relation conjuncts) turned a STUDY applicant's E31C proof
        from seq-9's silent UNSUPPORTED into BLOCKED_UNKNOWN demanding
        ``family.marriage_registered`` — the interview would ask a student
        about their parents' marriage. The scoped filter must be
        strong-Kleene FALSE (silent) outside the FAMILY+PARENT shape."""
        overrides = {
            "intent.purposes": _known(["STUDY"]),
            "family.relation_to_sponsor": _known("OTHER"),
            "family.marriage_registered": gf.unknown("NOT_ASKED"),
        }
        for pack in (seq9, seq10):
            proof = _proof(pack, "E31C", overrides)
            assert proof.status is ProductProofStatus.UNSUPPORTED
            assert FactPath.FAMILY_MARRIAGE_REGISTERED not in proof.missing_facts


_C2_BUSINESS_FACTS = {
    "intent.purposes": _known(["BUSINESS_MEETINGS"]),
    "family.sponsor_confirmed": _known(True),
    "intent.stay_days": _known(30),
}


class TestC2RetirementPreservesBehavior:
    def test_c2_still_supported_on_seq10(self, seq10: compiler.CompiledRulePack) -> None:
        proof = _proof(seq10, "C2", dict(_C2_BUSINESS_FACTS))
        assert proof.status is ProductProofStatus.SUPPORTED
        support_ids = {r.rule_id for r in proof.support_rules}
        assert "el.c2.business" in support_ids
        assert _RETIRED_RULE_ID not in support_ids

    def test_same_facts_supported_on_seq9_with_the_retired_rule(
        self, seq9: compiler.CompiledRulePack
    ) -> None:
        """Behavior-preservation baseline: seq-9 SUPPORTED the same facts,
        additionally via the false-promise rule the retirement removes."""
        proof = _proof(seq9, "C2", dict(_C2_BUSINESS_FACTS))
        assert proof.status is ProductProofStatus.SUPPORTED
        assert _RETIRED_RULE_ID in {r.rule_id for r in proof.support_rules}
