"""Gates for seq-15 (``rulepack-prod-015.source.json``): the E31B/E31D
fail-open repair.

What seq-15 is (full rationale in ``fold_pack_seq15.py``'s docstring): the
signed seq-13 payload, minus seq-14's two retired review rules (carried
forward verbatim), minus the two intent-only E31D duplicate SUPPORT rules,
with three predicate repairs — the two ``el.e31b-*`` rules' terminal
``op:known`` on ``family.sponsor_status_code`` becomes ``neq "NONE"``, and
``el.e31d-stepchild-support`` becomes the full conjunction its name claims
(STEPCHILD relation + both stepchild evidence facts).

The behavioral witnesses below are the acceptance criteria of
``research/visa/2026-08-15-gold-family-refuter.md`` (§Acceptance criteria)
made mechanical, guilt AND innocence (superscar #3):

guilt — the fail-open shapes measured on seq-13 (probes in
``research/visa/2026-08-28-visa-oracle-gold-coverage-and-divergence-
adjudication.md`` §5) no longer support:
  * sponsor with status ``NONE`` → E31B is not a candidate;
  * FAMILY intent alone → E31D is not a candidate;
  * UNKNOWN stepchild evidence → E31D is not a candidate (Kleene UNKNOWN,
    ``on_unknown: NEEDS_INPUT``).

innocence — the legitimate populations still get their product:
  * a spouse of a real ITAS holder (status ``E23``) keeps E31B;
  * a stepchild with both certificates confirmed keeps E31D;
  * gold persona 7 (spouse of a WNI) keeps E31A — the repair removes only
    the manufactured E31B/E31D offers, never the genuine spouse path.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_pack import (
    compile_rule_pack,
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.evaluate_path import apply_public_policy_adapters
from backend.services.visa_engine.models import DecisionState

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ13_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-013.source.json"
_SEQ15_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-015.source.json"

pytestmark = pytest.mark.skipif(
    not _SEQ15_SOURCE_PATH.exists(),
    reason="rulepack-prod-015.source.json does not exist on disk — run "
    "`python -m backend.scripts.visa_engine.fold_pack_seq15`",
)

_REMOVED_RULE_IDS = frozenset(
    {
        "review.e23u.requested-product",
        "review.e23v.requested-product",
        "el.e31d-step-parent-relation",
        "el.e31d-sponsor-mixed-marriage",
    }
)
_EDITED_RULE_IDS = frozenset(
    {
        "el.e31b-spouse-itas-support",
        "el.e31b-sponsor-itas-itap",
        "el.e31e-child-itas-support",
        "el.e31e-sponsor-itas-itap",
        "el.e31h-parent-itas-child-support",
        "el.e31h-sponsor-itas-itap",
        "el.e31j-sibling-itas-support",
        "el.e31j-sponsor-itas-itap",
        "el.e31j-dependency-age",
        "el.e31d-stepchild-support",
    }
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq13_source() -> dict[str, Any]:
    return _read_json(_SEQ13_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq15_source() -> dict[str, Any]:
    return _read_json(_SEQ15_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq15() -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(_SEQ15_SOURCE_PATH)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


# ---------------------------------------------------------------------------
# Structural gates
# ---------------------------------------------------------------------------


class TestFoldIntegrity:
    def test_fold_is_deterministic_and_matches_disk(self, seq15_source: dict[str, Any]) -> None:
        from backend.scripts.visa_engine.fold_pack_seq15 import assemble_payload

        assert assemble_payload() == seq15_source

    def test_compile_rule_pack_reports_ok(self) -> None:
        payload = load_rule_pack_payload(_SEQ15_SOURCE_PATH)
        report = compile_rule_pack(wrap_as_unsigned_pack(payload))
        assert report.ok, f"seq-15 does not compile clean: {report}"

    def test_rule_delta_is_exactly_the_declared_one(
        self, seq13_source: dict[str, Any], seq15_source: dict[str, Any]
    ) -> None:
        def canon(rule: dict[str, Any]) -> str:
            return json.dumps(rule, sort_keys=True, separators=(",", ":"))

        r13 = {r["rule_id"]: r for r in seq13_source["rules"]}
        r15 = {r["rule_id"]: r for r in seq15_source["rules"]}
        assert set(r13) - set(r15) == set(_REMOVED_RULE_IDS)
        assert set(r15) - set(r13) == set()
        drifted = {rid for rid in r15 if canon(r15[rid]) != canon(r13[rid])}
        assert drifted == set(_EDITED_RULE_IDS)

    def test_no_sponsor_status_known_terminal_survives_in_e31b(
        self, seq15_source: dict[str, Any]
    ) -> None:
        """The fail-open shape itself must be extinct in the repaired rules —
        matching on the predicate, not on a rule count, so a future edit that
        reintroduces the shape anywhere in an E31B rule goes red here."""

        def has_known_on_sponsor_status(node: Any) -> bool:
            if isinstance(node, dict):
                if node.get("op") == "known" and node.get("fact") == "family.sponsor_status_code":
                    return True
                return any(has_known_on_sponsor_status(v) for v in node.values())
            if isinstance(node, list):
                return any(has_known_on_sponsor_status(item) for item in node)
            return False

        # PACK-WIDE, not per-family: the round-2 grader found the class had
        # survived on E31E/E31H/E31J after round 1 repaired only E31B.
        for rule in seq15_source["rules"]:
            assert not has_known_on_sponsor_status(rule["when"]), rule["rule_id"]

    def test_e31b_sponsor_status_terminal_is_a_closed_stay_permit_set(
        self, seq15_source: dict[str, Any]
    ) -> None:
        """Round-2 shape (after the round-1 grader proved `neq NONE` still
        admitted tourist-visa sponsors): the terminal must be `op:in` over the
        catalog's own E-prefix stay-permit codes — no visit/entry visa (A/B/C/D
        prefix) and no "NONE" may appear in the set."""

        def find_sponsor_terminals(node: Any, acc: list[dict[str, Any]]) -> None:
            if isinstance(node, dict):
                if node.get("fact") == "family.sponsor_status_code":
                    acc.append(node)
                for value in node.values():
                    find_sponsor_terminals(value, acc)
            elif isinstance(node, list):
                for item in node:
                    find_sponsor_terminals(item, acc)

        catalog_stay_permits = {
            p["product_code"] for p in seq15_source["products"] if p["product_code"].startswith("E")
        }
        rules_with_terminals = 0
        for rule in seq15_source["rules"]:
            terminals: list[dict[str, Any]] = []
            find_sponsor_terminals(rule["when"], terminals)
            if not terminals:
                continue
            rules_with_terminals += 1
            for term in terminals:
                assert term["op"] == "in", (rule["rule_id"], term)
                values = set(term["values"])
                assert values == catalog_stay_permits, (rule["rule_id"], values)
                assert "NONE" not in values and "C1" not in values and "B1" not in values
        assert rules_with_terminals == 9, rules_with_terminals

    def test_e31d_support_requires_the_evidence_facts(self, seq15_source: dict[str, Any]) -> None:
        e31d_support = [
            r
            for r in seq15_source["rules"]
            if r["rule_id"].startswith("el.e31d") and r["effect"]["type"] == "SUPPORT"
        ]
        assert [r["rule_id"] for r in e31d_support] == ["el.e31d-stepchild-support"]
        (rule,) = e31d_support
        assert set(rule["required_facts"]) == {
            "intent.purposes",
            "family.relation_to_sponsor",
            "family.sponsor_confirmed",
            "family.stepchild_birth_certificate_confirmed",
            "family.stepchild_marriage_certificate_confirmed",
        }

    def test_chain_anchor_is_the_signed_seq13_payload(self, seq15_source: dict[str, Any]) -> None:
        """Activation's anti-rollback chain requires previous == the CURRENT
        production bundle's payload_sha256; seq-13 is the highest signed pack
        and the active one, so seq-15 must chain from it — never from the
        unsigned seq-14 candidate, which would make seq-15 unactivatable."""
        signed = _read_json(_PACKS_DIR / "rulepack-prod-013.signed.json")
        assert seq15_source["previous_payload_sha256"] == signed["payload_sha256"]
        assert seq15_source["sequence"] == 15


# ---------------------------------------------------------------------------
# Behavioral witnesses (offline replay path: compile → evaluate → adapters)
# ---------------------------------------------------------------------------


def _evaluate(
    seq15: compiler.CompiledRulePack, overrides: dict[str, dict[str, Any]]
) -> tuple[str, list[str]]:
    from backend.scripts.visa_engine.gold_replay_driver import (
        _offline_identity_provider,
        build_persona_request,
    )
    from backend.tests.services.visa_engine.test_evaluator_gold import Persona

    persona = Persona(
        id=0, label="seq15-witness", overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    request = build_persona_request(persona)
    facts = request.applicant_facts()
    now = datetime.now(timezone.utc)
    decision = evaluator.evaluate(
        facts,
        seq15,
        effective_at=now,
        observed_at=now,
        identity_provider=_offline_identity_provider,
    )
    decision = apply_public_policy_adapters(decision, facts, seq15)
    return decision.state.name, [c.product_code for c in decision.candidates]


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


_SPOUSE_BASE = {
    "intent.purposes": _known(["FAMILY"]),
    "family.relation_to_sponsor": _known("SPOUSE"),
    "family.marriage_registered": _known(True),
}


class TestGuilt:
    def test_sponsor_status_none_no_longer_supports_e31b(
        self, seq15: compiler.CompiledRulePack
    ) -> None:
        """The seq-13 probe: spouse + registered marriage + sponsor status
        ``NONE`` returned ``['C1','E31B','E31D']``. A sponsor with no stay
        permit cannot anchor a dependent permit."""
        state, candidates = _evaluate(
            seq15, {**_SPOUSE_BASE, "family.sponsor_status_code": _known("NONE")}
        )
        assert "E31B" not in candidates
        assert "E31D" not in candidates

    def test_family_intent_alone_no_longer_supports_e31d(
        self, seq15: compiler.CompiledRulePack
    ) -> None:
        """The seq-13 probe: a persona whose ONLY fact is FAMILY intent
        returned ``['C1','E31D']``."""
        state, candidates = _evaluate(seq15, {"intent.purposes": _known(["FAMILY"])})
        assert "E31D" not in candidates

    def test_unknown_stepchild_evidence_never_supports_e31d(
        self, seq15: compiler.CompiledRulePack
    ) -> None:
        """Refuter criterion: unknown required family discriminators must
        never yield SUPPORTED for E31D (Kleene UNKNOWN → on_unknown
        NEEDS_INPUT). The relation is STEPCHILD but both evidence facts stay
        NOT_ASKED (the gold baseline's default)."""
        state, candidates = _evaluate(
            seq15,
            {
                "intent.purposes": _known(["FAMILY"]),
                "family.relation_to_sponsor": _known("STEPCHILD"),
            },
        )
        assert "E31D" not in candidates

    def test_tourist_visa_sponsor_no_longer_supports_e31b(
        self, seq15: compiler.CompiledRulePack
    ) -> None:
        """Round-1 grader counterexample (gpt-5.6-sol, REJECT): with the first
        revision's `neq "NONE"`, a sponsor holding a C1 tourist visa still
        yielded E31B. The closed stay-permit set must reject it — and B1 too."""
        for visit_code in ("C1", "B1"):
            state, candidates = _evaluate(
                seq15, {**_SPOUSE_BASE, "family.sponsor_status_code": _known(visit_code)}
            )
            assert "E31B" not in candidates, visit_code

    def test_unconfirmed_sponsor_never_supports_e31d(
        self, seq15: compiler.CompiledRulePack
    ) -> None:
        """Round-1 grader's second blocker: a stepchild with both certificates
        but a wholly unconfirmed sponsor was still supported. sponsor_confirmed
        is false in the gold baseline, and explicitly false here."""
        state, candidates = _evaluate(
            seq15,
            {
                "intent.purposes": _known(["FAMILY"]),
                "family.relation_to_sponsor": _known("STEPCHILD"),
                "family.sponsor_confirmed": _known(False),
                "family.stepchild_birth_certificate_confirmed": _known(True),
                "family.stepchild_marriage_certificate_confirmed": _known(True),
            },
        )
        assert "E31D" not in candidates


class TestInnocence:
    def test_spouse_of_a_real_itas_holder_keeps_e31b(
        self, seq15: compiler.CompiledRulePack
    ) -> None:
        state, candidates = _evaluate(
            seq15, {**_SPOUSE_BASE, "family.sponsor_status_code": _known("E23")}
        )
        assert state == "SUPPORTED_CANDIDATES"
        assert "E31B" in candidates

    def test_stepchild_with_both_certificates_keeps_e31d(
        self, seq15: compiler.CompiledRulePack
    ) -> None:
        state, candidates = _evaluate(
            seq15,
            {
                "intent.purposes": _known(["FAMILY"]),
                "family.relation_to_sponsor": _known("STEPCHILD"),
                "family.sponsor_confirmed": _known(True),
                "family.stepchild_birth_certificate_confirmed": _known(True),
                "family.stepchild_marriage_certificate_confirmed": _known(True),
            },
        )
        assert state == "SUPPORTED_CANDIDATES"
        assert "E31D" in candidates

    def test_gold_persona_7_keeps_the_genuine_spouse_of_wni_path(
        self, seq15: compiler.CompiledRulePack
    ) -> None:
        """Persona 7 (spouse of a WNI; gold baseline carries sponsor status
        ``NONE``): the repair removes the two manufactured offers and ONLY
        them — E31A, the legitimate spouse-of-WNI product, must survive."""
        from backend.tests.services.visa_engine.test_evaluator_gold import PERSONAS

        persona_7 = PERSONAS[6]
        assert persona_7.id == 7
        state, candidates = _evaluate(seq15, dict(persona_7.overrides))
        assert state == "SUPPORTED_CANDIDATES"
        assert "E31A" in candidates
        assert "E31B" not in candidates
        assert "E31D" not in candidates
