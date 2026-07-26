"""Empty-pack / no-active-products / all-excluded edge cases (task TDD item
#5): every one of these must still resolve to ``NO_SUPPORTED_PATH`` WITH at
least one reason — ``models.Decision`` itself enforces "non-empty
no_path_reasons for this state", so a bug here surfaces as a
``ValidationError`` from ``evaluate()``, never a silently-empty response.

Note: ``RulePackPayload.products`` requires ``min_length=1`` at the model
layer (a literally empty product list cannot even be constructed) — the
"no products" case here is therefore modeled as "zero products are ACTIVE
and effective at the query instant" (the realistic shape this actually
takes in production: every product deprecated, or none in force yet), which
is what makes ``evaluate()``'s own product-selection filter yield an empty
list to iterate.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.evaluator import evaluate
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine.conftest import make_applicant_facts

_EFFECTIVE_AT = datetime(2026, 7, 18, tzinfo=timezone.utc)


def _facts() -> M.ApplicantFacts:
    base = make_applicant_facts()
    data = base.facts.model_dump(by_alias=True, mode="json")
    data["intent.purposes"] = {"status": "KNOWN", "value": ["TOURISM"]}
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=base.assessment_id,
        collected_at=base.collected_at,
        facts=data,
    )


class TestNoActiveProducts:
    def test_only_deprecated_product_yields_no_supported_path_with_a_reason(self) -> None:
        source_id = B.new_uuid()
        product_id = B.new_uuid()
        src = B.source_record(source_id=source_id)
        prod = B.product(
            product_id=product_id,
            source_id=source_id,
            covered_purposes=["TOURISM"],
            status="DEPRECATED",
        )
        rule = B.rule(
            rule_id="el.tourism",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={"type": "SUPPORT", "reason_code": "TOURISM", "covered_purposes": ["TOURISM"]},
            source_id=source_id,
            required_facts=["intent.purposes"],
        )
        payload = B.rule_pack_payload(rules=[rule], products=[prod], source_records=[src])
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        decision = evaluate(
            _facts(), compiled, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT
        )

        assert decision.state is DecisionState.NO_SUPPORTED_PATH
        assert decision.no_path_reasons  # non-empty — Decision's own invariant
        # Gate round 1 P1 fix (2026-07-19): the fallback code is namespaced
        # OPERATIONAL_* (never a legal conclusion) and must always carry a
        # citation — here derived from the pack's own source_records since
        # zero products were ever ACTIVE/effective to derive from.
        assert (
            decision.no_path_reasons[0].code == "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES"
        )
        assert decision.no_path_reasons[0].source_refs, (
            "fallback reason must still carry a citation"
        )
        assert decision.candidates == ()

    def test_product_not_yet_effective_at_query_instant_is_excluded_from_selection(self) -> None:
        source_id = B.new_uuid()
        product_id = B.new_uuid()
        src = B.source_record(source_id=source_id)
        future_period = {"from": "2099-01-01T00:00:00Z", "to": None}
        prod = B.product(
            product_id=product_id,
            source_id=source_id,
            covered_purposes=["TOURISM"],
            valid_period=future_period,
        )
        rule = B.rule(
            rule_id="el.tourism",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={"type": "SUPPORT", "reason_code": "TOURISM", "covered_purposes": ["TOURISM"]},
            source_id=source_id,
            required_facts=["intent.purposes"],
            valid_period=future_period,
        )
        payload = B.rule_pack_payload(rules=[rule], products=[prod], source_records=[src])
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        decision = evaluate(
            _facts(), compiled, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT
        )

        assert decision.state is DecisionState.NO_SUPPORTED_PATH
        assert decision.no_path_reasons


class TestAllExcluded:
    def test_every_product_excluded_by_a_named_global_rule(self) -> None:
        source_id = B.new_uuid()
        product_ids = [B.new_uuid(), B.new_uuid()]
        src = B.source_record(source_id=source_id)
        products = [
            B.product(
                product_id=pid,
                source_id=source_id,
                product_code=f"P{i}",
                covered_purposes=["TOURISM"],
            )
            for i, pid in enumerate(product_ids)
        ]
        hard_filter = B.rule(
            rule_id="hf.always",
            stage="HARD_FILTER",
            scope="GLOBAL",
            when={"op": "eq", "fact": "immigration.currently_in_indonesia", "value": False},
            effect={"type": "EXCLUDE", "reason_code": "ALWAYS_EXCLUDED_TEST"},
            source_id=source_id,
            required_facts=["immigration.currently_in_indonesia"],
        )
        payload = B.rule_pack_payload(rules=[hard_filter], products=products, source_records=[src])
        pack = M.RulePack.model_validate(B.rule_pack_envelope(payload))
        compiled = build_compiled_pack(pack)

        base = make_applicant_facts()
        data = base.facts.model_dump(by_alias=True, mode="json")
        data["intent.purposes"] = {"status": "KNOWN", "value": ["TOURISM"]}
        data["immigration.currently_in_indonesia"] = {"status": "KNOWN", "value": False}
        facts = M.ApplicantFacts(
            schema_version="1.0.0",
            assessment_id=base.assessment_id,
            collected_at=base.collected_at,
            facts=data,
        )

        decision = evaluate(facts, compiled, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)

        assert decision.state is DecisionState.NO_SUPPORTED_PATH
        # Deduped: the SAME GLOBAL rule fired identically for both products —
        # one Reason, not two.
        assert [r.code for r in decision.no_path_reasons] == ["ALWAYS_EXCLUDED_TEST"]
        assert decision.candidates == ()
