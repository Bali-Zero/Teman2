"""F4: pack integrity checks the compiler must enforce, none of which the
Pydantic wire models catch on their own (uniqueItems is enforced only
*within* a single Rule's own list fields, never *across* the payload's
rules/products/source_records):

* duplicate rule_id / product_version_id / product_code / source_record_id
  within the payload
* a Rule.product_version_ids UUID that doesn't name any real product
  (dangling reference -> silent no-op today)
* a Rule.source_refs / VisaProductVersion.source_refs UUID that doesn't
  resolve to any source_record in the payload
"""

from __future__ import annotations

import pytest

from backend.services.visa_engine.compiler import compile_rule_pack
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import FactRegistry
from backend.services.visa_engine.models import RulePack

from ._builders import (
    new_uuid,
    product,
    rule,
    rule_pack_envelope,
    rule_pack_payload,
    source_record,
)

_HARD_FILTER_WHEN = {"op": "gt", "fact": "immigration.overstay_days", "value": 60}
_REQUIRED = ["immigration.overstay_days"]


def _compile(envelope: dict) -> None:
    pack = RulePack(**envelope)
    compile_rule_pack(pack, fact_registry=FactRegistry())


def _base_rule(rule_id: str, source_id: str, **overrides: object) -> dict:
    return rule(
        rule_id=rule_id,
        stage="HARD_FILTER",
        scope="GLOBAL",
        when=_HARD_FILTER_WHEN,
        effect={"type": "EXCLUDE", "reason_code": "OVERSTAY"},
        source_id=source_id,
        required_facts=_REQUIRED,
        **overrides,
    )


class TestDuplicateRuleId:
    def test_duplicate_rule_id_rejected(self) -> None:
        source_id = new_uuid()
        product_id = new_uuid()
        src = source_record(source_id=source_id)
        prod = product(product_id=product_id, source_id=source_id)
        rules = [
            _base_rule("same-id", source_id),
            _base_rule("same-id", source_id),
        ]
        payload = rule_pack_payload(rules=rules, products=[prod], source_records=[src])
        envelope = rule_pack_envelope(payload)
        with pytest.raises(RulePackCompilationError, match="rule_id"):
            _compile(envelope)


class TestDuplicateProductVersionId:
    def test_duplicate_product_version_id_rejected(self) -> None:
        source_id = new_uuid()
        shared_product_id = new_uuid()
        src = source_record(source_id=source_id)
        prod_a = product(product_id=shared_product_id, source_id=source_id, product_code="C1")
        prod_b = product(product_id=shared_product_id, source_id=source_id, product_code="C2")
        rules = [_base_rule("r1", source_id)]
        payload = rule_pack_payload(rules=rules, products=[prod_a, prod_b], source_records=[src])
        envelope = rule_pack_envelope(payload)
        with pytest.raises(RulePackCompilationError, match="product_version_id"):
            _compile(envelope)


class TestDuplicateProductCode:
    def test_duplicate_product_code_rejected(self) -> None:
        source_id = new_uuid()
        src = source_record(source_id=source_id)
        prod_a = product(product_id=new_uuid(), source_id=source_id, product_code="C1")
        prod_b = product(product_id=new_uuid(), source_id=source_id, product_code="C1")
        rules = [_base_rule("r1", source_id)]
        payload = rule_pack_payload(rules=rules, products=[prod_a, prod_b], source_records=[src])
        envelope = rule_pack_envelope(payload)
        with pytest.raises(RulePackCompilationError, match="product_code"):
            _compile(envelope)


class TestDuplicateSourceRecordId:
    def test_duplicate_source_record_id_rejected(self) -> None:
        shared_source_id = new_uuid()
        product_id = new_uuid()
        src_a = source_record(source_id=shared_source_id, source_key="key-a")
        src_b = source_record(source_id=shared_source_id, source_key="key-b")
        prod = product(product_id=product_id, source_id=shared_source_id)
        rules = [_base_rule("r1", shared_source_id)]
        payload = rule_pack_payload(rules=rules, products=[prod], source_records=[src_a, src_b])
        envelope = rule_pack_envelope(payload)
        with pytest.raises(RulePackCompilationError, match="source_record"):
            _compile(envelope)


class TestDanglingProductVersionIdReference:
    def test_rule_referencing_unknown_product_version_id_rejected(self) -> None:
        source_id = new_uuid()
        real_product_id = new_uuid()
        phantom_product_id = new_uuid()
        src = source_record(source_id=source_id)
        prod = product(product_id=real_product_id, source_id=source_id)
        products_rule = rule(
            rule_id="el-1",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[phantom_product_id],
            when={"op": "known", "fact": "intent.purposes"},
            effect={
                "type": "SUPPORT",
                "reason_code": "OK",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=["intent.purposes"],
        )
        payload = rule_pack_payload(rules=[products_rule], products=[prod], source_records=[src])
        envelope = rule_pack_envelope(payload)
        with pytest.raises(RulePackCompilationError, match="product_version_ids?"):
            _compile(envelope)


class TestDanglingSourceRefs:
    def test_rule_source_refs_referencing_unknown_source_rejected(self) -> None:
        source_id = new_uuid()
        phantom_source_id = new_uuid()
        product_id = new_uuid()
        src = source_record(source_id=source_id)
        prod = product(product_id=product_id, source_id=source_id)
        bad_rule = _base_rule("r1", source_id, source_refs=[phantom_source_id])
        payload = rule_pack_payload(rules=[bad_rule], products=[prod], source_records=[src])
        envelope = rule_pack_envelope(payload)
        with pytest.raises(RulePackCompilationError, match="source_refs?"):
            _compile(envelope)

    def test_product_source_refs_referencing_unknown_source_rejected(self) -> None:
        source_id = new_uuid()
        phantom_source_id = new_uuid()
        product_id = new_uuid()
        src = source_record(source_id=source_id)
        prod = product(product_id=product_id, source_id=source_id, source_refs=[phantom_source_id])
        good_rule = _base_rule("r1", source_id)
        payload = rule_pack_payload(rules=[good_rule], products=[prod], source_records=[src])
        envelope = rule_pack_envelope(payload)
        with pytest.raises(RulePackCompilationError, match="source_refs?"):
            _compile(envelope)
