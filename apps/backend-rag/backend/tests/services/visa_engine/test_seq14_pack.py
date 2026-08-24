"""Gates for seq-14 (``rulepack-prod-014.source.json``, see
``backend.scripts.visa_engine.fold_pack_seq14``).

The blocked5 lane (2026-08-24): seq-13 reaches 29/38 products. Five of the
nine still-blocked products (E23U, E23V, E33A, E33B, E33C) have their
doctrine CLOSED (``research/visa/doctrine-factory/claims/
e2c-blocked5-claim-ledger.md``, E2c mini-batch) but carried no
ELIGIBILITY/SUPPORT rule at all. This fold inserts exactly TWO new claim-
backed SUPPORT rules — E23U and E23V. E33A/E33B/E33C deliberately get NO
new rule (see the fold's own module docstring and the PR body for the
design-question writeup); reachability moves 29 -> 31.

This module SKIPS cleanly (not error, not red) while
``rulepack-prod-014.source.json`` does not exist on disk — run
``PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq14``
first. Once it exists, these checks run, each verified against the real
files on disk or the real evaluator:

(a) chain gate — seq-14's ``previous_payload_sha256`` equals the
    RECOMPUTED SHA256(JCS(...)) of seq-13's own signed payload
    declaration, cross-checked against a fresh re-hash of the seq-13
    SOURCE bytes.
(b) rule-set delta — mechanically diffed against seq-13: exactly the two
    new rule_ids added, zero removed, zero changed, products/
    source_records byte-identical.
(c) zero lint findings — ``lint_duplicate_subtree`` /
    ``lint_unsatisfiable_condition`` run over every seq-14 rule.
(d) ``compile_pack`` compiles seq-14 with zero errors.
(e) idempotence — calling ``assemble_payload()`` twice yields
    canonical-JSON-identical output.
(f) evaluator witnesses (house pattern, ``test_seq13_rules_pack.py``'s
    ``TestE31CNationalityGateWitnesses``): per-product ``evaluate_product``
    guilt/innocence/tri-state/non-contamination pairs for BOTH new rules,
    plus a pinned seq-13 regression showing the SAME facts reached
    UNSUPPORTED before this fold (the rule genuinely changes the outcome,
    not merely "a rule exists").
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_claims import (
    lint_duplicate_subtree,
    lint_unsatisfiable_condition,
)
from backend.scripts.visa_engine.compile_pack import (
    compile_rule_pack,
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.scripts.visa_engine.fold_pack_seq14 import FoldPackError, assemble_payload
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
_SEQ13_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-013.source.json"
_SEQ13_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-013.signed.json"
_SEQ14_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-014.source.json"

_E23U_RULE_ID = "el.e23u.diplomatic-household-support"
_E23V_RULE_ID = "el.e23v.trade-office-support"
_INSERTED_RULE_IDS = frozenset({_E23U_RULE_ID, _E23V_RULE_ID})
_REMOVED_RULE_IDS = frozenset(
    {"review.e23u.requested-product", "review.e23v.requested-product"}
)

# Any instant on/after both inserted rules' valid_period.from
# (2026-08-24T00:00:00Z) and inside every inherited rule's window.
AT = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.skipif(
    not _SEQ14_SOURCE_PATH.exists(),
    reason=(
        "rulepack-prod-014.source.json does not exist yet — run "
        "`PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq14` "
        "first. This module SKIPS, not reds, until then."
    ),
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@pytest.fixture(scope="module")
def seq13_source() -> dict[str, Any]:
    return _read_json(_SEQ13_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq14_source() -> dict[str, Any]:
    return _read_json(_SEQ14_SOURCE_PATH)


def _compiled(name: str) -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(_PACKS_DIR / name)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def seq14(seq14_source: dict[str, Any]) -> compiler.CompiledRulePack:
    del seq14_source  # ensures the skip guard has already run
    return _compiled("rulepack-prod-014.source.json")


@pytest.fixture(scope="module")
def seq13() -> compiler.CompiledRulePack:
    return _compiled("rulepack-prod-013.source.json")


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
# (a) chain gate
# ---------------------------------------------------------------------------


class TestChainGate:
    def test_previous_payload_sha256_chains_to_recomputed_seq13(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        recomputed = hashlib.sha256(canonicalize_json(seq13_source)).hexdigest()
        seq13_signed = _read_json(_SEQ13_SIGNED_PATH)
        assert seq13_signed["payload_sha256"] == recomputed
        assert seq14_source["previous_payload_sha256"] == recomputed

    def test_sequence_advanced_and_rule_pack_id_changed(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        assert seq13_source["sequence"] == 13
        assert seq14_source["sequence"] == 14
        assert seq14_source["rule_pack_id"] != seq13_source["rule_pack_id"]


# ---------------------------------------------------------------------------
# (b) rule-set delta — mechanical, never eyeballed
# ---------------------------------------------------------------------------


class TestRuleSetDelta:
    def test_delta_is_exactly_two_removed_and_two_inserted(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        """The two ``review.e23{u,v}.requested-product`` rules are REMOVED
        (see the fold's module docstring): keyed on
        ``intent.requested_product_code`` (hard-coded NOT_ASKED at
        ``fact-mapper.ts:597``), their permanent unknown blocks the WHOLE
        per-product proof to BLOCKED_UNKNOWN regardless of ELIGIBILITY's
        own verdict — proven live, not merely inert. Leaving them in place
        would make the two new SUPPORT rules below dead on arrival."""
        r13 = {r["rule_id"]: r for r in seq13_source["rules"]}
        r14 = {r["rule_id"]: r for r in seq14_source["rules"]}

        added = set(r14) - set(r13)
        removed = set(r13) - set(r14)
        changed = {rid for rid in (set(r13) & set(r14)) if _canon(r13[rid]) != _canon(r14[rid])}

        assert added == _INSERTED_RULE_IDS
        assert removed == _REMOVED_RULE_IDS
        assert changed == set()
        assert len(r14) == len(r13) - len(_REMOVED_RULE_IDS) + len(_INSERTED_RULE_IDS)

    def test_e33abc_rules_are_completely_untouched(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        """Explicit pin of the design decision: this fold makes ZERO
        changes to E33A/E33B/E33C — neither their HARD_FILTER nor their
        (still-inert) HUMAN_REVIEW rule. See the PR body's design-question
        writeup for why."""
        e33abc_rule_ids = {
            "review.e33a.central-government-invitation",
            "hf.e33a.sponsor-not-government",
            "review.e33b.expertise-qualification",
            "hf.e33b.sponsor-not-government-or-none",
            "review.e33c.central-government-invitation",
            "hf.e33c.sponsor-not-government-or-none",
        }
        r13 = {r["rule_id"]: r for r in seq13_source["rules"]}
        r14 = {r["rule_id"]: r for r in seq14_source["rules"]}
        for rid in e33abc_rule_ids:
            assert rid in r13 and rid in r14, rid
            assert _canon(r13[rid]) == _canon(r14[rid]), rid

    def test_products_and_source_records_are_byte_identical(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        assert _canon(seq14_source["products"]) == _canon(seq13_source["products"])
        assert _canon(seq14_source["source_records"]) == _canon(seq13_source["source_records"])

    def test_no_other_top_level_key_drifted(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        identity_keys = {
            "sequence",
            "version",
            "rule_pack_id",
            "previous_payload_sha256",
            "created_at",
            "created_by",
        }
        for key in set(seq13_source) | set(seq14_source):
            if key in identity_keys or key == "rules":
                continue
            assert _canon(seq14_source.get(key)) == _canon(seq13_source.get(key)), key


# ---------------------------------------------------------------------------
# (c) zero lint findings over every seq-14 rule
# ---------------------------------------------------------------------------


class TestZeroLintFindings:
    def test_duplicate_subtree_and_unsatisfiable_condition_are_clean(
        self, seq14_source: dict[str, Any]
    ) -> None:
        findings = []
        for rule in seq14_source["rules"]:
            when = rule["when"]
            findings.extend(lint_duplicate_subtree(rule_id=rule["rule_id"], when=when))
            unsat_findings, _skip_note = lint_unsatisfiable_condition(
                rule_id=rule["rule_id"], when=when
            )
            findings.extend(unsat_findings)
        assert findings == []


# ---------------------------------------------------------------------------
# (d) compile_pack RC 0
# ---------------------------------------------------------------------------


class TestCompilePackCompilesClean:
    def test_compile_rule_pack_reports_zero_errors(self) -> None:
        payload = load_rule_pack_payload(_SEQ14_SOURCE_PATH)
        report = compile_rule_pack(wrap_as_unsigned_pack(payload))
        assert report.ok, "; ".join(f"{e.code}: {e.message}" for e in report.errors)


# ---------------------------------------------------------------------------
# (e) idempotence
# ---------------------------------------------------------------------------


class TestFoldIsIdempotent:
    def test_assemble_payload_twice_is_byte_identical(self) -> None:
        first = assemble_payload()
        second = assemble_payload()
        assert _canon(first) == _canon(second)


# ---------------------------------------------------------------------------
# (f) evaluator witnesses — E23U
# ---------------------------------------------------------------------------

_E23U_BASE = {
    "intent.purposes": _known(["EMPLOYMENT"]),
    "sponsor.type": _known("INDIVIDUAL"),
    "work.employer_is_indonesian_entity": _known(False),
}


class TestE23UDiplomaticHouseholdSupportWitnesses:
    def test_innocence_individual_sponsor_non_indonesian_employer_is_supported(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        proof = _proof(seq14, "E23U", dict(_E23U_BASE))
        assert proof.status is ProductProofStatus.SUPPORTED
        assert _E23U_RULE_ID in {r.rule_id for r in proof.support_rules}

    def test_pinned_seq13_regression_same_facts_were_unsupported(
        self, seq13: compiler.CompiledRulePack
    ) -> None:
        """The rule genuinely CHANGES the outcome: before this fold, E23U
        had zero ELIGIBILITY-stage rules at all (only the inert
        HUMAN_REVIEW keyed on the never-askable
        ``intent.requested_product_code``), so the identical fact set
        never reached SUPPORTED on seq-13."""
        proof = _proof(seq13, "E23U", dict(_E23U_BASE))
        assert proof.status is not ProductProofStatus.SUPPORTED

    def test_guilt_employer_sponsor_is_not_supported(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        """A plain corporate-employer applicant (the shape plain E23
        already serves) must not satisfy E23U's INDIVIDUAL-sponsor gate."""
        overrides = {**_E23U_BASE, "sponsor.type": _known("EMPLOYER")}
        proof = _proof(seq14, "E23U", overrides)
        assert _E23U_RULE_ID not in {r.rule_id for r in proof.support_rules}

    def test_guilt_government_sponsor_is_not_supported(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        """A GOVERNMENT-sponsored applicant (E23V's own shape) must not
        satisfy E23U's INDIVIDUAL-sponsor gate — the two rules are
        mutually exclusive on ``sponsor.type`` by construction."""
        overrides = {**_E23U_BASE, "sponsor.type": _known("GOVERNMENT")}
        proof = _proof(seq14, "E23U", overrides)
        assert _E23U_RULE_ID not in {r.rule_id for r in proof.support_rules}

    def test_guilt_indonesian_employer_is_not_supported(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        overrides = {**_E23U_BASE, "work.employer_is_indonesian_entity": _known(True)}
        proof = _proof(seq14, "E23U", overrides)
        assert _E23U_RULE_ID not in {r.rule_id for r in proof.support_rules}

    def test_employment_purpose_conjunct_is_pinned(
        self, seq14_source: dict[str, Any]
    ) -> None:
        rule = next(r for r in seq14_source["rules"] if r["rule_id"] == _E23U_RULE_ID)
        assert {
            "fact": "intent.purposes",
            "values": ["EMPLOYMENT"],
            "op": "intersects",
        } in rule["when"]["args"]

    def test_tristate_unknown_sponsor_type_blocks_never_excludes(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        overrides = {**_E23U_BASE, "sponsor.type": gf.unknown("NOT_ASKED")}
        proof = _proof(seq14, "E23U", overrides)
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert proof.status is not ProductProofStatus.EXCLUDED

    def test_non_employment_applicant_is_not_contaminated(
        self, seq13: compiler.CompiledRulePack, seq14: compiler.CompiledRulePack
    ) -> None:
        overrides = {
            "intent.purposes": _known(["TOURISM"]),
            "sponsor.type": gf.unknown("NOT_ASKED"),
        }
        for pack in (seq13, seq14):
            proof = _proof(pack, "E23U", overrides)
            assert proof.status is not ProductProofStatus.SUPPORTED
            assert FactPath.SPONSOR_TYPE not in proof.missing_facts

    def test_plain_e23_is_not_contaminated_by_the_new_rule(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        """The E23U shape (individual sponsor, non-Indonesian employer)
        must never mark plain E23 SUPPORTED — the two products' SUPPORT
        rules require opposite values of
        ``work.employer_is_indonesian_entity``."""
        proof = _proof(seq14, "E23", dict(_E23U_BASE))
        assert proof.status is not ProductProofStatus.SUPPORTED


# ---------------------------------------------------------------------------
# (f) evaluator witnesses — E23V
# ---------------------------------------------------------------------------

_E23V_BASE = {
    "intent.purposes": _known(["EMPLOYMENT"]),
    "sponsor.type": _known("GOVERNMENT"),
    "work.employer_is_indonesian_entity": _known(False),
}


class TestE23VTradeOfficeSupportWitnesses:
    def test_innocence_government_sponsor_non_indonesian_employer_is_supported(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        proof = _proof(seq14, "E23V", dict(_E23V_BASE))
        assert proof.status is ProductProofStatus.SUPPORTED
        assert _E23V_RULE_ID in {r.rule_id for r in proof.support_rules}

    def test_pinned_seq13_regression_same_facts_were_unsupported(
        self, seq13: compiler.CompiledRulePack
    ) -> None:
        proof = _proof(seq13, "E23V", dict(_E23V_BASE))
        assert proof.status is not ProductProofStatus.SUPPORTED

    def test_guilt_individual_sponsor_is_not_supported(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        overrides = {**_E23V_BASE, "sponsor.type": _known("INDIVIDUAL")}
        proof = _proof(seq14, "E23V", overrides)
        assert _E23V_RULE_ID not in {r.rule_id for r in proof.support_rules}

    def test_guilt_indonesian_employer_is_not_supported(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        """A GOVERNMENT sponsor who IS an Indonesian-registered employer
        (a domestic government agency, not a foreign trade office) must
        not satisfy E23V's non-Indonesian-employer gate."""
        overrides = {**_E23V_BASE, "work.employer_is_indonesian_entity": _known(True)}
        proof = _proof(seq14, "E23V", overrides)
        assert _E23V_RULE_ID not in {r.rule_id for r in proof.support_rules}

    def test_employment_purpose_conjunct_is_pinned(
        self, seq14_source: dict[str, Any]
    ) -> None:
        rule = next(r for r in seq14_source["rules"] if r["rule_id"] == _E23V_RULE_ID)
        assert {
            "fact": "intent.purposes",
            "values": ["EMPLOYMENT"],
            "op": "intersects",
        } in rule["when"]["args"]

    def test_tristate_unknown_sponsor_type_blocks_never_excludes(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        overrides = {**_E23V_BASE, "sponsor.type": gf.unknown("NOT_ASKED")}
        proof = _proof(seq14, "E23V", overrides)
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert proof.status is not ProductProofStatus.EXCLUDED

    def test_non_employment_applicant_is_not_contaminated(
        self, seq13: compiler.CompiledRulePack, seq14: compiler.CompiledRulePack
    ) -> None:
        overrides = {
            "intent.purposes": _known(["TOURISM"]),
            "sponsor.type": gf.unknown("NOT_ASKED"),
        }
        for pack in (seq13, seq14):
            proof = _proof(pack, "E23V", overrides)
            assert proof.status is not ProductProofStatus.SUPPORTED
            assert FactPath.SPONSOR_TYPE not in proof.missing_facts

    def test_e33a_never_reaches_supported_for_the_same_facts(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        """Documents the known, disclosed fact-vocabulary ambiguity (PR
        body design-question): E23V's GOVERNMENT-sponsor facts are also
        consistent with E33A's real identity (Indonesian
        central-government invitation), which the pack's own
        ``sponsor.type`` vocabulary cannot distinguish from a foreign
        trade office. This test pins that the ambiguity is NOT live today
        — E33A carries no SUPPORT rule at all (untouched by this fold),
        so it can never spuriously reach SUPPORTED alongside E23V for the
        same fact pattern."""
        proof = _proof(seq14, "E33A", dict(_E23V_BASE))
        assert proof.status is not ProductProofStatus.SUPPORTED


# ---------------------------------------------------------------------------
# Fold-level fail-loud checks (chain mismatch)
# ---------------------------------------------------------------------------


class TestFoldFailsLoudOnDrift:
    def test_wrong_expected_seq13_hash_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.scripts.visa_engine.fold_pack_seq14 as mod

        monkeypatch.setattr(mod, "_EXPECTED_SEQ13_PAYLOAD_SHA256", "0" * 64)
        with pytest.raises(FoldPackError, match="not the one this fold was authored against"):
            mod.assemble_payload()
