"""PR5 cross-family adversarial gate, round 1 (2026-07-19) — Codex GPT-5.6-sol
xhigh + Kimi K3, two independent seats, ``GATE: FIX-FIRST``, convergent on the
load-bearing finding (P0-C). This file carries every NEW test the round
required that did not fit as a targeted fix to an existing file:

- P0-C: the GLOBAL HUMAN_REVIEW pre-pass's 3 counterexamples (unknown
  purposes / zero active products / a GLOBAL hard-filter excluding
  everything first) — each previously produced the WRONG state.
- P1 item 4: the placeholder identity provider's fail-closed environment
  guard.
- P1 item 5: ``on_unknown=HUMAN_REVIEW``'s distinct semantics (guilt +
  innocence, all three stages).
- P1 item 6: the deterministic MINIMAL missing_facts set (not a union).
- P1 item 7 (general form): no legal Reason ever ships with empty
  source_refs, exercised via a from-scratch pack rather than the
  already-covered empty-pack case in ``test_evaluator_edge_cases.py``.
- Ranking tie-determinism (P1 item 8a, second half — the differential
  value-binding half lives in ``test_evaluator_gold.py``'s persona-17
  metamorphic test).

The two corrected wrong-expectation tests (purpose-coverage P0-A,
state-precedence P0-B) stay in their original files
(``test_evaluator_purpose_coverage.py``/``test_evaluator_state_precedence.py``)
since they are fixes to pre-existing tests, not new ones.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.errors import PlaceholderIdentityNotAllowedError
from backend.services.visa_engine.evaluator import (
    ProductProofStatus,
    evaluate,
    evaluate_product,
)
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine.conftest import make_applicant_facts

_EFFECTIVE_AT = datetime(2026, 7, 18, tzinfo=timezone.utc)


def _known(value):
    return {"status": "KNOWN", "value": value}


def _unknown(reason: str = "NOT_PROVIDED"):
    return {"status": "UNKNOWN", "reason": reason}


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


# ---------------------------------------------------------------------------
# P0-C: GLOBAL HUMAN_REVIEW pre-pass counterexamples
# ---------------------------------------------------------------------------

_REVIEW_FACT = "person.marital_status"  # arbitrary, unrelated to purposes/products
_HARD_FILTER_FACT = "immigration.currently_in_indonesia"


def _pack_with_global_review_and_hard_filter(*, product_effective: bool) -> M.RulePack:
    source_id = B.new_uuid()
    product_id = B.new_uuid()
    src = B.source_record(source_id=source_id)
    valid_period = (
        {"from": "2026-01-01T00:00:00Z", "to": None}
        if product_effective
        else {"from": "2099-01-01T00:00:00Z", "to": None}
    )
    prod = B.product(
        product_id=product_id,
        source_id=source_id,
        covered_purposes=["TOURISM"],
        valid_period=valid_period,
    )
    global_review = B.rule(
        rule_id="review.global-trigger",
        stage="HUMAN_REVIEW",
        scope="GLOBAL",
        when={"op": "eq", "fact": _REVIEW_FACT, "value": "MARRIED"},
        effect={"type": "REQUIRE_REVIEW", "reason_code": "GLOBAL_REVIEW_TRIGGER"},
        source_id=source_id,
        required_facts=[_REVIEW_FACT],
    )
    global_hard_filter = B.rule(
        rule_id="hf.global-exclude-everything",
        stage="HARD_FILTER",
        scope="GLOBAL",
        when={"op": "eq", "fact": _HARD_FILTER_FACT, "value": True},
        effect={"type": "EXCLUDE", "reason_code": "GLOBAL_EXCLUDE_EVERYTHING"},
        source_id=source_id,
        required_facts=[_HARD_FILTER_FACT],
    )
    eligibility = B.rule(
        rule_id="el.tourism",
        stage="ELIGIBILITY",
        scope="PRODUCTS",
        product_version_ids=[product_id],
        when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
        effect={"type": "SUPPORT", "reason_code": "TOURISM", "covered_purposes": ["TOURISM"]},
        source_id=source_id,
        required_facts=["intent.purposes"],
        valid_period=valid_period,
    )
    payload = B.rule_pack_payload(
        rules=[global_review, global_hard_filter, eligibility],
        products=[prod],
        source_records=[src],
    )
    return M.RulePack.model_validate(B.rule_pack_envelope(payload))


class TestGlobalHumanReviewPrePassCounterexamples:
    """Each of these previously (pre-gate-round-1) produced the WRONG state
    because the GLOBAL HUMAN_REVIEW rule was only ever surfaced via
    ``rules_for(product, ...)`` — unreachable in each of these three shapes.
    """

    def test_global_review_true_with_unknown_purposes_wins_over_needs_input(self) -> None:
        pack = build_compiled_pack(_pack_with_global_review_and_hard_filter(product_effective=True))
        facts = _facts(
            {
                _REVIEW_FACT: _known("MARRIED"),
                _HARD_FILTER_FACT: _known(False),
                "intent.purposes": _unknown("NOT_PROVIDED"),
            }
        )
        decision = evaluate(facts, pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)
        assert decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
        assert [r.code for r in decision.review_reasons] == ["GLOBAL_REVIEW_TRIGGER"]

    def test_global_review_true_with_zero_active_products_wins_over_no_supported_path(
        self,
    ) -> None:
        pack = build_compiled_pack(
            _pack_with_global_review_and_hard_filter(product_effective=False)
        )
        facts = _facts(
            {
                _REVIEW_FACT: _known("MARRIED"),
                _HARD_FILTER_FACT: _known(False),
                "intent.purposes": _known(["TOURISM"]),
            }
        )
        decision = evaluate(facts, pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)
        assert decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
        assert [r.code for r in decision.review_reasons] == ["GLOBAL_REVIEW_TRIGGER"]

    def test_global_review_true_with_global_hard_filter_excluding_everything_still_wins(
        self,
    ) -> None:
        pack = build_compiled_pack(_pack_with_global_review_and_hard_filter(product_effective=True))
        facts = _facts(
            {
                _REVIEW_FACT: _known("MARRIED"),
                _HARD_FILTER_FACT: _known(True),
                "intent.purposes": _known(["TOURISM"]),
            }
        )
        decision = evaluate(facts, pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)
        assert decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
        assert [r.code for r in decision.review_reasons] == ["GLOBAL_REVIEW_TRIGGER"]
        assert decision.candidates == ()


# ---------------------------------------------------------------------------
# P1 item 4: placeholder identity provider environment guard
# ---------------------------------------------------------------------------


def _minimal_pack(*, environment: str) -> M.RulePack:
    source_id = B.new_uuid()
    product_id = B.new_uuid()
    src = B.source_record(source_id=source_id)
    prod = B.product(product_id=product_id, source_id=source_id, covered_purposes=["TOURISM"])
    eligibility = B.rule(
        rule_id="el.tourism",
        stage="ELIGIBILITY",
        scope="PRODUCTS",
        product_version_ids=[product_id],
        when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
        effect={"type": "SUPPORT", "reason_code": "TOURISM", "covered_purposes": ["TOURISM"]},
        source_id=source_id,
        required_facts=["intent.purposes"],
    )
    payload = B.rule_pack_payload(
        rules=[eligibility], products=[prod], source_records=[src], environment=environment
    )
    return M.RulePack.model_validate(B.rule_pack_envelope(payload))


class TestPlaceholderIdentityEnvironmentGuard:
    def test_test_environment_pack_uses_the_placeholder_without_raising(self) -> None:
        pack = build_compiled_pack(_minimal_pack(environment="TEST"))
        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        decision = evaluate(facts, pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)
        assert decision.state is DecisionState.SUPPORTED_CANDIDATES

    def test_production_environment_pack_raises_with_the_default_placeholder(self) -> None:
        pack = build_compiled_pack(_minimal_pack(environment="PRODUCTION"))
        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        with pytest.raises(PlaceholderIdentityNotAllowedError):
            evaluate(facts, pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)

    def test_staging_environment_pack_also_raises(self) -> None:
        pack = build_compiled_pack(_minimal_pack(environment="STAGING"))
        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        with pytest.raises(PlaceholderIdentityNotAllowedError):
            evaluate(facts, pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)

    def test_production_environment_pack_succeeds_with_an_injected_real_provider(self) -> None:
        """The guard blocks the DEFAULT placeholder, not injection itself —
        a caller supplying its own (fake-but-not-the-placeholder) provider
        must still work fine even against a PRODUCTION pack."""
        import uuid as uuid_module

        from backend.services.visa_engine.evaluator import DecisionIdentity
        from backend.services.visa_engine.models import Fingerprint

        def _fake_real_provider(facts, rule_pack_ref, effective_at, environment):
            return DecisionIdentity(
                decision_id=uuid_module.uuid5(uuid_module.NAMESPACE_URL, "fake"),
                public_id="f" * 20,
                facts_fingerprint=Fingerprint(
                    algorithm="HMAC-SHA256", key_id="fake-real-key", digest="a" * 64
                ),
            )

        pack = build_compiled_pack(_minimal_pack(environment="PRODUCTION"))
        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        decision = evaluate(
            facts,
            pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            identity_provider=_fake_real_provider,
        )
        assert decision.state is DecisionState.SUPPORTED_CANDIDATES
        assert decision.public_id == "f" * 20


# ---------------------------------------------------------------------------
# P1 item 5: on_unknown=HUMAN_REVIEW distinct semantics (guilt + innocence)
# ---------------------------------------------------------------------------

_UNDER_TEST_FACT = "work.employer_is_indonesian_entity"
_BASELINE_ELIGIBILITY = {"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]}


def _applicant_facts_for(fact_value: bool | None) -> M.ApplicantFacts:
    base = make_applicant_facts()
    data = base.facts.model_dump(by_alias=True, mode="json")
    data["intent.purposes"] = {"status": "KNOWN", "value": ["TOURISM"]}
    data[_UNDER_TEST_FACT] = _unknown() if fact_value is None else _known(fact_value)
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=base.assessment_id,
        collected_at=base.collected_at,
        facts=data,
    )


def _build_pack_on_unknown_human_review(*, stage_under_test: str):
    from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY

    source_id = B.new_uuid()
    product_id = B.new_uuid()
    src = B.source_record(source_id=source_id)
    prod = B.product(product_id=product_id, source_id=source_id, covered_purposes=["TOURISM"])
    when = {"op": "eq", "fact": _UNDER_TEST_FACT, "value": True}
    rules = []

    if stage_under_test == "HARD_FILTER":
        rules.append(
            B.rule(
                rule_id="under-test",
                stage="HARD_FILTER",
                scope="GLOBAL",
                when=when,
                effect={"type": "EXCLUDE", "reason_code": "TEST_EXCLUDE"},
                source_id=source_id,
                required_facts=[_UNDER_TEST_FACT],
                on_unknown="HUMAN_REVIEW",
            )
        )
    elif stage_under_test == "HUMAN_REVIEW":
        rules.append(
            B.rule(
                rule_id="under-test",
                stage="HUMAN_REVIEW",
                scope="GLOBAL",
                when=when,
                effect={"type": "REQUIRE_REVIEW", "reason_code": "TEST_REVIEW"},
                source_id=source_id,
                required_facts=[_UNDER_TEST_FACT],
                on_unknown="HUMAN_REVIEW",
            )
        )
    else:
        assert stage_under_test == "ELIGIBILITY"
        rules.append(
            B.rule(
                rule_id="under-test",
                stage="ELIGIBILITY",
                scope="PRODUCTS",
                product_version_ids=[str(product_id)],
                when=when,
                effect={
                    "type": "SUPPORT",
                    "reason_code": "TEST_SUPPORT",
                    "covered_purposes": ["TOURISM"],
                },
                source_id=source_id,
                required_facts=[_UNDER_TEST_FACT],
                on_unknown="HUMAN_REVIEW",
            )
        )

    if stage_under_test != "ELIGIBILITY":
        rules.append(
            B.rule(
                rule_id="baseline-eligibility",
                stage="ELIGIBILITY",
                scope="PRODUCTS",
                product_version_ids=[product_id],
                when=_BASELINE_ELIGIBILITY,
                effect={
                    "type": "SUPPORT",
                    "reason_code": "BASELINE_SUPPORT",
                    "covered_purposes": ["TOURISM"],
                },
                source_id=source_id,
                required_facts=["intent.purposes"],
            )
        )

    payload = B.rule_pack_payload(rules=rules, products=[prod], source_records=[src])
    pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
    compiled = build_compiled_pack(pack)

    def _proof_for(fact_value: bool | None):
        facts = _applicant_facts_for(fact_value)
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=_EFFECTIVE_AT)
        (product,) = [p for p in compiled.products if str(p.product_version_id) == product_id]
        rules_for_product = compiled.rules_for(product, effective_at=_EFFECTIVE_AT)
        return evaluate_product(
            product=product,
            rules=rules_for_product,
            facts=snapshot,
            purposes=frozenset({"TOURISM"}),
        )

    return _proof_for


class TestOnUnknownHumanReviewHardFilter:
    def test_unknown_escalates_to_review_not_needs_input(self) -> None:
        """Guilt: the whole point of on_unknown=HUMAN_REVIEW."""
        proof_for = _build_pack_on_unknown_human_review(stage_under_test="HARD_FILTER")
        proof = proof_for(None)
        assert proof.status is ProductProofStatus.REVIEW
        assert [r.code for r in proof.reasons] == ["TEST_EXCLUDE"]

    def test_known_true_still_excludes(self) -> None:
        """Innocence: a definite TRUE hard-filter still excludes regardless
        of on_unknown policy — on_unknown only governs the UNKNOWN case."""
        proof_for = _build_pack_on_unknown_human_review(stage_under_test="HARD_FILTER")
        proof = proof_for(True)
        assert proof.status is ProductProofStatus.EXCLUDED

    def test_known_false_still_proceeds_to_supported(self) -> None:
        """Innocence: a definite FALSE never triggers review."""
        proof_for = _build_pack_on_unknown_human_review(stage_under_test="HARD_FILTER")
        proof = proof_for(False)
        assert proof.status is ProductProofStatus.SUPPORTED


class TestOnUnknownHumanReviewHumanReviewStage:
    def test_unknown_escalates_to_review(self) -> None:
        proof_for = _build_pack_on_unknown_human_review(stage_under_test="HUMAN_REVIEW")
        proof = proof_for(None)
        assert proof.status is ProductProofStatus.REVIEW
        assert [r.code for r in proof.reasons] == ["TEST_REVIEW"]

    def test_known_true_still_reviews(self) -> None:
        proof_for = _build_pack_on_unknown_human_review(stage_under_test="HUMAN_REVIEW")
        proof = proof_for(True)
        assert proof.status is ProductProofStatus.REVIEW

    def test_known_false_still_proceeds_to_supported(self) -> None:
        proof_for = _build_pack_on_unknown_human_review(stage_under_test="HUMAN_REVIEW")
        proof = proof_for(False)
        assert proof.status is ProductProofStatus.SUPPORTED


class TestOnUnknownHumanReviewEligibilityStage:
    def test_unknown_escalates_to_review_not_blocked_unknown(self) -> None:
        proof_for = _build_pack_on_unknown_human_review(stage_under_test="ELIGIBILITY")
        proof = proof_for(None)
        assert proof.status is ProductProofStatus.REVIEW
        assert [r.code for r in proof.reasons] == ["TEST_SUPPORT"]

    def test_known_true_supports(self) -> None:
        proof_for = _build_pack_on_unknown_human_review(stage_under_test="ELIGIBILITY")
        proof = proof_for(True)
        assert proof.status is ProductProofStatus.SUPPORTED

    def test_known_false_is_unsupported(self) -> None:
        proof_for = _build_pack_on_unknown_human_review(stage_under_test="ELIGIBILITY")
        proof = proof_for(False)
        assert proof.status is ProductProofStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# P1 item 6: deterministic MINIMAL missing_facts set (not a union)
# ---------------------------------------------------------------------------


class TestMinimalMissingFactsSet:
    def test_smallest_blocked_proof_wins_not_the_union(self) -> None:
        source_id = B.new_uuid()
        id_a = B.new_uuid()
        id_b = B.new_uuid()
        src = B.source_record(source_id=source_id)
        prod_a = B.product(
            product_id=id_a, source_id=source_id, product_code="AAAA", covered_purposes=["TOURISM"]
        )
        prod_b = B.product(
            product_id=id_b, source_id=source_id, product_code="BBBB", covered_purposes=["TOURISM"]
        )
        # Product A: ONE unknown fact blocks it.
        rule_a = B.rule(
            rule_id="el.a",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[id_a],
            when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
            effect={"type": "SUPPORT", "reason_code": "A_SUPPORT", "covered_purposes": ["TOURISM"]},
            source_id=source_id,
            required_facts=["study.admission_confirmed"],
        )
        # Product B: FIVE unknown facts all needed to determine it.
        five_facts = [
            "work.employer_is_indonesian_entity",
            "work.serves_indonesian_clients",
            "work.indonesia_source_compensation",
            "work.indonesian_work_sponsor_confirmed",
            "investment.pt_pma_committed",
        ]
        rule_b = B.rule(
            rule_id="el.b",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[id_b],
            when={
                "op": "all",
                "args": [{"op": "eq", "fact": f, "value": True} for f in five_facts],
            },
            effect={"type": "SUPPORT", "reason_code": "B_SUPPORT", "covered_purposes": ["TOURISM"]},
            source_id=source_id,
            required_facts=five_facts,
        )
        payload = B.rule_pack_payload(
            rules=[rule_a, rule_b], products=[prod_a, prod_b], source_records=[src]
        )
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        facts = _facts(
            {
                "intent.purposes": _known(["TOURISM"]),
                "study.admission_confirmed": _unknown(),
                **{f: _unknown() for f in five_facts},
            }
        )
        decision = evaluate(facts, compiled, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)
        assert decision.state is DecisionState.NEEDS_INPUT
        assert tuple(m.value for m in decision.missing_facts) == ("study.admission_confirmed",)


# ---------------------------------------------------------------------------
# Ranking tie-determinism (P1 item 8a, second half)
# ---------------------------------------------------------------------------


class TestRankingTieDeterminism:
    def test_tied_score_breaks_by_product_code_not_by_uuid_order(self) -> None:
        source_id = B.new_uuid()
        raw_id_1 = B.new_uuid()
        raw_id_2 = B.new_uuid()
        src = B.source_record(source_id=source_id)

        # Deliberately assign product_code so it DISAGREES with the UUIDs'
        # own sort order (AAA gets the LARGER uuid) — if the tie-break
        # secretly used product_version_id before product_code, ZZZ would
        # incorrectly rank first; product_code must decide it.
        id_for_aaa = max(raw_id_1, raw_id_2)
        id_for_zzz = min(raw_id_1, raw_id_2)
        assert id_for_aaa > id_for_zzz

        prod_aaa = B.product(
            product_id=id_for_aaa,
            source_id=source_id,
            product_code="AAA",
            covered_purposes=["TOURISM"],
        )
        prod_zzz = B.product(
            product_id=id_for_zzz,
            source_id=source_id,
            product_code="ZZZ",
            covered_purposes=["TOURISM"],
        )
        rule_aaa = B.rule(
            rule_id="el.aaa",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[id_for_aaa],
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={
                "type": "SUPPORT",
                "reason_code": "AAA_SUPPORT",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=["intent.purposes"],
        )
        rule_zzz = B.rule(
            rule_id="el.zzz",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[id_for_zzz],
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={
                "type": "SUPPORT",
                "reason_code": "ZZZ_SUPPORT",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=["intent.purposes"],
        )
        payload = B.rule_pack_payload(
            rules=[rule_aaa, rule_zzz], products=[prod_aaa, prod_zzz], source_records=[src]
        )
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        decision = evaluate(facts, compiled, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)

        assert decision.state is DecisionState.SUPPORTED_CANDIDATES
        assert [c.score for c in decision.candidates] == [0, 0]  # genuinely tied
        assert [c.product_code for c in decision.candidates] == ["AAA", "ZZZ"]

        # Determinism: re-running produces the identical order every time.
        decision_again = evaluate(
            facts, compiled, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT
        )
        assert [c.product_code for c in decision_again.candidates] == ["AAA", "ZZZ"]


# ---------------------------------------------------------------------------
# P1 item 7 (general form): no legal Reason ever ships with empty source_refs
# ---------------------------------------------------------------------------


class TestNoUncitedLegalReason:
    def test_fallback_no_path_reason_derives_citations_from_evaluated_products(self) -> None:
        """Distinct from the empty-pack case in test_evaluator_edge_cases.py
        — here at least one product WAS evaluated (genuinely UNSUPPORTED,
        no named EXCLUDE rule anywhere), so the fallback must derive its
        citation from that product's own catalog source_refs.
        """
        source_id = B.new_uuid()
        product_id = B.new_uuid()
        src = B.source_record(source_id=source_id)
        prod = B.product(product_id=product_id, source_id=source_id, covered_purposes=["FAMILY"])
        # A rule that can never be TRUE for these facts and has no EXCLUDE
        # counterpart anywhere in the pack — every product is simply
        # UNSUPPORTED, no named disqualifying reason exists.
        rule = B.rule(
            rule_id="el.family",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "eq", "fact": "family.sponsor_confirmed", "value": True},
            effect={"type": "SUPPORT", "reason_code": "FAMILY", "covered_purposes": ["FAMILY"]},
            source_id=source_id,
            required_facts=["family.sponsor_confirmed"],
        )
        payload = B.rule_pack_payload(rules=[rule], products=[prod], source_records=[src])
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        facts = _facts(
            {
                "intent.purposes": _known(["FAMILY"]),
                "family.sponsor_confirmed": _known(False),
            }
        )
        decision = evaluate(facts, compiled, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)

        assert decision.state is DecisionState.NO_SUPPORTED_PATH
        assert (
            decision.no_path_reasons[0].code == "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES"
        )
        assert decision.no_path_reasons[0].source_refs
        assert set(decision.no_path_reasons[0].source_refs) == {uuid.UUID(source_id)}
