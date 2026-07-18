"""Model strictness tests: extra fields rejected, models frozen (mutation
raises), UNKNOWN facts require one of the 5 reason codes.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from backend.services.visa_engine.fact_registry import UnknownReason
from backend.services.visa_engine.models import ApplicantFacts, Rule

from ._builders import applicant_facts_envelope, minimal_valid_envelope


def test_applicant_facts_rejects_extra_top_level_field() -> None:
    payload = applicant_facts_envelope()
    payload["unexpected_field"] = "nope"
    with pytest.raises(ValidationError):
        ApplicantFacts(**payload)


def test_applicant_facts_rejects_extra_fact_field() -> None:
    payload = applicant_facts_envelope()
    payload["facts"]["some.unregistered.path"] = {"status": "KNOWN", "value": True}
    with pytest.raises(ValidationError):
        ApplicantFacts(**payload)


def test_applicant_facts_is_frozen() -> None:
    facts = ApplicantFacts(**applicant_facts_envelope())
    with pytest.raises(ValidationError):
        facts.schema_version = "2.0.0"  # type: ignore[misc]


def test_applicant_facts_data_is_frozen() -> None:
    facts = ApplicantFacts(**applicant_facts_envelope())
    with pytest.raises(ValidationError):
        facts.facts.person_birth_date = facts.facts.person_birth_date  # type: ignore[misc]


def test_unknown_fact_requires_valid_reason_enum() -> None:
    payload = applicant_facts_envelope(
        **{"person.birth_date": {"status": "UNKNOWN", "reason": "SOME_MADE_UP_REASON"}}
    )
    with pytest.raises(ValidationError):
        ApplicantFacts(**payload)


def test_unknown_fact_missing_reason_rejected() -> None:
    payload = applicant_facts_envelope()
    payload["facts"]["person.birth_date"] = {"status": "UNKNOWN"}
    with pytest.raises(ValidationError):
        ApplicantFacts(**payload)


@pytest.mark.parametrize("reason", list(UnknownReason))
def test_unknown_fact_accepts_every_valid_reason(reason: UnknownReason) -> None:
    payload = applicant_facts_envelope(
        **{"person.birth_date": {"status": "UNKNOWN", "reason": reason.value}}
    )
    facts = ApplicantFacts(**payload)
    assert facts.facts.person_birth_date.reason is reason


def test_known_fact_rejects_wrong_value_type() -> None:
    payload = applicant_facts_envelope(
        **{"intent.stay_days": {"status": "KNOWN", "value": "not-an-integer"}}
    )
    with pytest.raises(ValidationError):
        ApplicantFacts(**payload)


def test_rule_is_frozen() -> None:
    envelope = minimal_valid_envelope()
    rule_dict = envelope["payload"]["rules"][0]
    rule = Rule(**rule_dict)
    with pytest.raises(ValidationError):
        rule.priority = 999  # type: ignore[misc]


def test_rule_rejects_extra_field() -> None:
    envelope = minimal_valid_envelope()
    rule_dict = dict(envelope["payload"]["rules"][0])
    rule_dict["not_a_real_field"] = 1
    with pytest.raises(ValidationError):
        Rule(**rule_dict)


def test_rule_global_scope_rejects_product_version_ids() -> None:
    envelope = minimal_valid_envelope()
    rule_dict = dict(envelope["payload"]["rules"][0])
    assert rule_dict["scope"] == "GLOBAL"
    rule_dict["product_version_ids"] = [str(uuid.uuid4())]
    with pytest.raises(ValidationError):
        Rule(**rule_dict)


def test_rule_products_scope_requires_product_version_ids() -> None:
    envelope = minimal_valid_envelope()
    rule_dict = dict(envelope["payload"]["rules"][1])
    assert rule_dict["scope"] == "PRODUCTS"
    del rule_dict["product_version_ids"]
    with pytest.raises(ValidationError):
        Rule(**rule_dict)


def test_rule_stage_effect_mismatch_rejected() -> None:
    envelope = minimal_valid_envelope()
    rule_dict = dict(envelope["payload"]["rules"][0])
    assert rule_dict["stage"] == "HARD_FILTER"
    rule_dict["effect"] = {"type": "ADD_SCORE", "reason_code": "WRONG_EFFECT", "points": 1}
    with pytest.raises(ValidationError):
        Rule(**rule_dict)
