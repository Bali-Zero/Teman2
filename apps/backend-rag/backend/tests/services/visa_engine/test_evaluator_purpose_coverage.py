"""Purpose-coverage hit policy (spec §4.2/§4.4, ``HitPolicy.
COVER_ALL_DECLARED_PURPOSES``): a product becomes SUPPORTED only when the
UNION of every TRUE SUPPORT rule's ``covered_purposes`` is a superset of the
applicant's FULL declared ``intent.purposes`` set — never a per-rule,
per-purpose partial match.

Complements the two gold personas (14/15) that exercise this at the
2-purpose/5-product-pack level; this file isolates the mechanic itself with
minimal 1-2-rule packs.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.enums import DecisionState, FactPath
from backend.services.visa_engine.evaluator import ProductProofStatus, evaluate, evaluate_product
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine.conftest import make_applicant_facts

_EFFECTIVE_AT = datetime(2026, 7, 18, tzinfo=timezone.utc)


def _facts(overrides: dict) -> M.ApplicantFacts:
    base = make_applicant_facts()
    data = base.facts.model_dump(by_alias=True, mode="json")
    data.update(overrides)
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=base.assessment_id,
        collected_at=base.collected_at,
        facts=data,
    )


def _known(value):
    return {"status": "KNOWN", "value": value}


def _unknown(reason: str = "NOT_PROVIDED"):
    return {"status": "UNKNOWN", "reason": reason}


def _proof(compiled, product_id: str, facts: M.ApplicantFacts, purposes: frozenset[str]):
    (product,) = [p for p in compiled.products if str(p.product_version_id) == product_id]
    snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=_EFFECTIVE_AT)
    rules = compiled.rules_for(product, effective_at=_EFFECTIVE_AT)
    return evaluate_product(product=product, rules=rules, facts=snapshot, purposes=purposes)


class TestExactCoverage:
    def test_single_rule_covering_exactly_the_declared_purposes_supports(self) -> None:
        product_id = B.new_uuid()
        src_id = B.new_uuid()
        prod = B.product(
            product_id=product_id, source_id=src_id, covered_purposes=["TOURISM", "STUDY"]
        )
        rule = B.rule(
            rule_id="el.exact",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
            effect={
                "type": "SUPPORT",
                "reason_code": "EXACT",
                "covered_purposes": ["TOURISM", "STUDY"],
            },
            source_id=src_id,
            required_facts=["study.admission_confirmed"],
        )
        payload = B.rule_pack_payload(
            rules=[rule], products=[prod], source_records=[B.source_record(source_id=src_id)]
        )
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        facts = _facts({"study.admission_confirmed": _known(True)})
        proof = _proof(compiled, product_id, facts, frozenset({"TOURISM", "STUDY"}))
        assert proof.status is ProductProofStatus.SUPPORTED
        assert proof.covered_purposes == frozenset({"TOURISM", "STUDY"})


class TestSupersetCoverage:
    def test_product_covering_a_superset_of_declared_purposes_still_supports(self) -> None:
        product_id = B.new_uuid()
        src_id = B.new_uuid()
        prod = B.product(
            product_id=product_id,
            source_id=src_id,
            covered_purposes=["TOURISM", "STUDY", "MEDICAL"],
        )
        rule = B.rule(
            rule_id="el.superset",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
            effect={
                "type": "SUPPORT",
                "reason_code": "SUPERSET",
                "covered_purposes": ["TOURISM", "STUDY", "MEDICAL"],
            },
            source_id=src_id,
            required_facts=["study.admission_confirmed"],
        )
        payload = B.rule_pack_payload(
            rules=[rule], products=[prod], source_records=[B.source_record(source_id=src_id)]
        )
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        facts = _facts({"study.admission_confirmed": _known(True)})
        # Applicant only declared TOURISM — a product covering more is still
        # a valid subset test (purposes <= covered), not an exact-match test.
        proof = _proof(compiled, product_id, facts, frozenset({"TOURISM"}))
        assert proof.status is ProductProofStatus.SUPPORTED


class TestUnionAcrossMultipleSupportRules:
    def test_two_support_rules_together_cover_the_full_declared_set(self) -> None:
        product_id = B.new_uuid()
        src_id = B.new_uuid()
        prod = B.product(
            product_id=product_id, source_id=src_id, covered_purposes=["TOURISM", "STUDY"]
        )
        rule_a = B.rule(
            rule_id="el.tourism-half",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "intent.stay_days", "value": 30},
            effect={
                "type": "SUPPORT",
                "reason_code": "TOURISM_HALF",
                "covered_purposes": ["TOURISM"],
            },
            source_id=src_id,
            required_facts=["intent.stay_days"],
        )
        rule_b = B.rule(
            rule_id="el.study-half",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
            effect={"type": "SUPPORT", "reason_code": "STUDY_HALF", "covered_purposes": ["STUDY"]},
            source_id=src_id,
            required_facts=["study.admission_confirmed"],
        )
        payload = B.rule_pack_payload(
            rules=[rule_a, rule_b],
            products=[prod],
            source_records=[B.source_record(source_id=src_id)],
        )
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        facts = _facts(
            {
                "intent.stay_days": _known(30),
                "study.admission_confirmed": _known(True),
            }
        )
        proof = _proof(compiled, product_id, facts, frozenset({"TOURISM", "STUDY"}))
        assert proof.status is ProductProofStatus.SUPPORTED
        assert proof.covered_purposes == frozenset({"TOURISM", "STUDY"})
        assert {rule.rule_id for rule in proof.support_rules} == {
            "el.tourism-half",
            "el.study-half",
        }


class TestPartialCoverageIsUnsupportedNotSupported:
    def test_missing_purpose_with_definite_false_rule_is_unsupported(self) -> None:
        product_id = B.new_uuid()
        src_id = B.new_uuid()
        prod = B.product(
            product_id=product_id, source_id=src_id, covered_purposes=["TOURISM", "STUDY"]
        )
        rule = B.rule(
            rule_id="el.study-only",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
            effect={"type": "SUPPORT", "reason_code": "STUDY_ONLY", "covered_purposes": ["STUDY"]},
            source_id=src_id,
            required_facts=["study.admission_confirmed"],
        )
        payload = B.rule_pack_payload(
            rules=[rule], products=[prod], source_records=[B.source_record(source_id=src_id)]
        )
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        # study.admission_confirmed definitely TRUE -> STUDY covered, but the
        # applicant ALSO declared TOURISM, which no rule on this product
        # covers at all -> UNSUPPORTED, never SUPPORTED.
        facts = _facts({"study.admission_confirmed": _known(True)})
        proof = _proof(compiled, product_id, facts, frozenset({"TOURISM", "STUDY"}))
        assert proof.status is ProductProofStatus.UNSUPPORTED
        assert proof.missing_purposes == frozenset({"TOURISM"})

    def test_missing_purpose_permanently_uncoverable_by_anything_is_unsupported_even_with_an_unrelated_unknown(
        self,
    ) -> None:
        """Gate round 1 P0-A fix (2026-07-19, Codex gate on PR5): the
        WRONG expectation this test previously encoded — asserting
        ``BLOCKED_UNKNOWN`` here — is exactly the bug the gate caught. TOURISM
        is never covered by ANY rule on this product, known or unknown — no
        future fact could ever change that, so resolving the STUDY-only
        unknown favorably would STILL leave TOURISM missing. The product must
        be definitively ``UNSUPPORTED`` right now, not deferred to
        ``BLOCKED_UNKNOWN`` (which would rank as ``NEEDS_INPUT`` globally — a
        BETTER state than the correct ``NO_SUPPORTED_PATH``, backwards from
        "UNKNOWN never increases eligibility"). Contrast with the differential
        test below, where the same shape of unknown genuinely CAN close the
        whole gap and BLOCKED_UNKNOWN is the right answer.
        """
        product_id = B.new_uuid()
        src_id = B.new_uuid()
        prod = B.product(
            product_id=product_id, source_id=src_id, covered_purposes=["TOURISM", "STUDY"]
        )
        rule = B.rule(
            rule_id="el.study-only",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
            effect={"type": "SUPPORT", "reason_code": "STUDY_ONLY", "covered_purposes": ["STUDY"]},
            source_id=src_id,
            required_facts=["study.admission_confirmed"],
        )
        payload = B.rule_pack_payload(
            rules=[rule], products=[prod], source_records=[B.source_record(source_id=src_id)]
        )
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        # study.admission_confirmed UNKNOWN: even if it resolves TRUE, only
        # STUDY becomes covered — TOURISM is never covered by any rule on
        # this product at all, so full coverage is permanently impossible
        # regardless of this unknown's resolution.
        facts = _facts({"study.admission_confirmed": _unknown()})
        proof = _proof(compiled, product_id, facts, frozenset({"TOURISM", "STUDY"}))
        assert proof.status is ProductProofStatus.UNSUPPORTED
        assert proof.missing_purposes == frozenset({"TOURISM"})

    def test_missing_purpose_genuinely_coverable_via_the_unknown_blocks(self) -> None:
        """Differential counterpart (gate round 1 P0-A, 2026-07-19): the SAME
        product also has a second, UNKNOWN rule that (if TRUE) would cover the
        one remaining gap-purpose no other rule covers — here resolving every
        unknown favorably WOULD fully close the coverage gap, so
        ``BLOCKED_UNKNOWN`` (worth asking) is the correct answer, unlike the
        permanently-uncoverable case above.
        """
        product_id = B.new_uuid()
        src_id = B.new_uuid()
        prod = B.product(
            product_id=product_id, source_id=src_id, covered_purposes=["TOURISM", "STUDY"]
        )
        rule_study = B.rule(
            rule_id="el.study-only",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
            effect={"type": "SUPPORT", "reason_code": "STUDY_ONLY", "covered_purposes": ["STUDY"]},
            source_id=src_id,
            required_facts=["study.admission_confirmed"],
        )
        rule_tourism_unknown = B.rule(
            rule_id="el.tourism-unknown",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "study.sponsor_confirmed", "value": True},
            effect={
                "type": "SUPPORT",
                "reason_code": "TOURISM_UNKNOWN",
                "covered_purposes": ["TOURISM"],
            },
            source_id=src_id,
            required_facts=["study.sponsor_confirmed"],
        )
        payload = B.rule_pack_payload(
            rules=[rule_study, rule_tourism_unknown],
            products=[prod],
            source_records=[B.source_record(source_id=src_id)],
        )
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        # Both study.admission_confirmed (covers STUDY) and
        # study.sponsor_confirmed (covers TOURISM) are UNKNOWN — resolving
        # BOTH favorably would fully cover {TOURISM, STUDY}, so this is worth
        # asking about (BLOCKED_UNKNOWN), unlike the permanently-uncoverable
        # case above.
        facts = _facts(
            {
                "study.admission_confirmed": _unknown(),
                "study.sponsor_confirmed": _unknown(),
            }
        )
        proof = _proof(compiled, product_id, facts, frozenset({"TOURISM", "STUDY"}))
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert proof.missing_facts == frozenset(
            {FactPath.STUDY_ADMISSION_CONFIRMED, FactPath.STUDY_SPONSOR_CONFIRMED}
        )

    def test_missing_purpose_with_unknown_rule_that_could_not_cover_it_is_unsupported(self) -> None:
        """An UNKNOWN support rule whose covered_purposes does NOT intersect
        the missing purposes can never resolve that gap — must not block on
        its account (an_unknown_support_rule_could_cover must be scoped to
        the ACTUAL missing purposes, not "any unknown rule anywhere")."""
        product_id = B.new_uuid()
        src_id = B.new_uuid()
        prod = B.product(
            product_id=product_id,
            source_id=src_id,
            covered_purposes=["TOURISM", "STUDY", "MEDICAL"],
        )
        rule_tourism = B.rule(
            rule_id="el.tourism",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "intent.stay_days", "value": 30},
            effect={"type": "SUPPORT", "reason_code": "TOURISM", "covered_purposes": ["TOURISM"]},
            source_id=src_id,
            required_facts=["intent.stay_days"],
        )
        rule_medical_unknown = B.rule(
            rule_id="el.medical-unrelated",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "study.sponsor_confirmed", "value": True},
            effect={"type": "SUPPORT", "reason_code": "MEDICAL", "covered_purposes": ["MEDICAL"]},
            source_id=src_id,
            required_facts=["study.sponsor_confirmed"],
        )
        payload = B.rule_pack_payload(
            rules=[rule_tourism, rule_medical_unknown],
            products=[prod],
            source_records=[B.source_record(source_id=src_id)],
        )
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        # Applicant declared TOURISM + STUDY only (never MEDICAL) — the
        # MEDICAL-scoped rule's unknown-ness is irrelevant to the STUDY gap.
        facts = _facts(
            {
                "intent.stay_days": _known(30),
                "study.sponsor_confirmed": _unknown(),
            }
        )
        proof = _proof(compiled, product_id, facts, frozenset({"TOURISM", "STUDY"}))
        assert proof.status is ProductProofStatus.UNSUPPORTED
        assert proof.missing_purposes == frozenset({"STUDY"})


# ---------------------------------------------------------------------------
# Gate round 2 (2026-07-20) P0-R2: joint satisfiability of the UNKNOWN
# support rules a product's coverage gap relies on. Round 1's own P0-A fix
# unioned every unknown SUPPORT rule's ``covered_purposes`` unconditionally
# — itself a Strong-Kleene violation whenever two of those rules can never
# both be TRUE at once (see module docstring / ``evaluator.py``'s
# ``_has_consistent_covering_subset``).
# ---------------------------------------------------------------------------


def _mutually_exclusive_marital_pack(product_id: str, src_id: str) -> M.RulePack:
    """One product covering {TOURISM, STUDY}: rule A covers TOURISM iff
    ``person.marital_status == MARRIED``; rule B covers STUDY iff
    ``person.marital_status == SINGLE``. No single resolution of
    ``marital_status`` can ever satisfy both — the two rules are jointly
    unsatisfiable regardless of which concrete value the fact takes.
    """
    prod = B.product(product_id=product_id, source_id=src_id, covered_purposes=["TOURISM", "STUDY"])
    rule_tourism_if_married = B.rule(
        rule_id="el.tourism-if-married",
        stage="ELIGIBILITY",
        scope="PRODUCTS",
        product_version_ids=[product_id],
        when={"op": "eq", "fact": "person.marital_status", "value": "MARRIED"},
        effect={"type": "SUPPORT", "reason_code": "TOURISM_MARRIED", "covered_purposes": ["TOURISM"]},
        source_id=src_id,
        required_facts=["person.marital_status"],
    )
    rule_study_if_single = B.rule(
        rule_id="el.study-if-single",
        stage="ELIGIBILITY",
        scope="PRODUCTS",
        product_version_ids=[product_id],
        when={"op": "eq", "fact": "person.marital_status", "value": "SINGLE"},
        effect={"type": "SUPPORT", "reason_code": "STUDY_SINGLE", "covered_purposes": ["STUDY"]},
        source_id=src_id,
        required_facts=["person.marital_status"],
    )
    payload = B.rule_pack_payload(
        rules=[rule_tourism_if_married, rule_study_if_single],
        products=[prod],
        source_records=[B.source_record(source_id=src_id)],
    )
    return M.RulePack.model_validate(B.rule_pack_envelope(payload))


class TestJointSatisfiabilityGateRound2:
    def test_mutually_exclusive_unknown_support_rules_are_unsupported_not_blocked(self) -> None:
        """The exact executed counterexample from the round-2 cross-family
        gate (Codex sol xhigh): declared purposes {TOURISM, STUDY}; rule A
        covers TOURISM iff marital_status==MARRIED; rule B covers STUDY iff
        marital_status==SINGLE; marital_status UNKNOWN. Every concrete
        resolution of marital_status (MARRIED or SINGLE) leaves exactly one
        purpose permanently uncovered on THIS product — no single value
        ever covers both — so the correct answer is UNSUPPORTED, not
        BLOCKED_UNKNOWN (which would make the UNKNOWN case strictly MORE
        favorable than every one of its own possible concrete
        resolutions, a direct Strong-Kleene violation).
        """
        product_id = B.new_uuid()
        src_id = B.new_uuid()
        pack = _mutually_exclusive_marital_pack(product_id, src_id)
        compiled = build_compiled_pack(pack)

        facts = _facts({"person.marital_status": _unknown()})
        proof = _proof(compiled, product_id, facts, frozenset({"TOURISM", "STUDY"}))
        assert proof.status is ProductProofStatus.UNSUPPORTED
        assert proof.missing_purposes == frozenset({"TOURISM", "STUDY"})

    def test_metamorphic_unknown_never_beats_every_concrete_resolution(self) -> None:
        """Gate round 2 P0-R2 metamorphic property: making a fact UNKNOWN
        must never yield a global ``DecisionState`` strictly more favorable
        (per the frozen precedence: HUMAN_REVIEW_REQUIRED >
        SUPPORTED_CANDIDATES > NEEDS_INPUT > NO_SUPPORTED_PATH) than the
        BEST state achievable under any concrete resolution of that same
        fact. On the mutually-exclusive-rules pack above, both concrete
        resolutions of ``marital_status`` (MARRIED, SINGLE) leave the
        product UNSUPPORTED -> global NO_SUPPORTED_PATH; the pre-round-2
        bug made the UNKNOWN case resolve to BLOCKED_UNKNOWN ->
        NEEDS_INPUT globally, which ranks strictly ABOVE NO_SUPPORTED_PATH
        — exactly the violation this test would have caught.
        """
        rank = {
            DecisionState.NO_SUPPORTED_PATH: 0,
            DecisionState.NEEDS_INPUT: 1,
            DecisionState.SUPPORTED_CANDIDATES: 2,
            DecisionState.HUMAN_REVIEW_REQUIRED: 3,
        }
        product_id = B.new_uuid()
        src_id = B.new_uuid()
        pack = _mutually_exclusive_marital_pack(product_id, src_id)
        compiled = build_compiled_pack(pack)
        effective_at = _EFFECTIVE_AT

        def _state_for(marital_status_value) -> DecisionState:
            facts = _facts(
                {
                    "intent.purposes": _known(["TOURISM", "STUDY"]),
                    "person.marital_status": (
                        _unknown()
                        if marital_status_value is None
                        else _known(marital_status_value)
                    ),
                }
            )
            decision = evaluate(facts, compiled, effective_at=effective_at, observed_at=effective_at)
            return decision.state

        state_married = _state_for("MARRIED")
        state_single = _state_for("SINGLE")
        state_unknown = _state_for(None)

        best_concrete_rank = max(rank[state_married], rank[state_single])
        assert rank[state_unknown] <= best_concrete_rank, (
            f"UNKNOWN resolved to {state_unknown!r} (rank {rank[state_unknown]}), "
            f"strictly more favorable than the best concrete resolution "
            f"(MARRIED={state_married!r}, SINGLE={state_single!r}, "
            f"best rank {best_concrete_rank})"
        )
        # Concretely for this pack: all three land at NO_SUPPORTED_PATH —
        # asserted directly too, since a metamorphic <= check alone would
        # not catch a regression that degrades ALL THREE equally.
        assert state_married is DecisionState.NO_SUPPORTED_PATH
        assert state_single is DecisionState.NO_SUPPORTED_PATH
        assert state_unknown is DecisionState.NO_SUPPORTED_PATH
