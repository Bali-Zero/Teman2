from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from research_os.enums import RiskClass, Sensitivity
from research_os.primitives import (
    ActorRef,
    Classification,
    ExactObjectRef,
    ExtensionValue,
    Lineage,
    Producer,
    Retention,
    ValidTime,
    validate_extensions,
)

CORE_MODEL_PAYLOADS = [
    (ExactObjectRef, {"object_kind": "claim", "object_id": "synthetic-1", "object_hash": "a" * 64}),
    (
        ActorRef,
        {
            "scheme": "hmac-sha256",
            "key_version": "key-v1",
            "purpose": "audit",
            "pseudonym": "a" * 64,
        },
    ),
    (Retention, {"retention_class": "audit", "legal_hold": False}),
    (Producer, {"name": "builder", "version": "1.0.0"}),
    (Lineage, {"input_hashes": []}),
    (Classification, {"risk_class": "green", "sensitivity": "public"}),
    (ValidTime, {"valid_from": "2026-01-01T00:00:00Z", "valid_to": None}),
    (ExtensionValue, {"extension_version": "1.0.0", "payload": {"custom": True}}),
]


@pytest.mark.parametrize(("model", "payload"), CORE_MODEL_PAYLOADS)
def test_core_models_reject_unknown_top_level_fields(model: object, payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({**payload, "unexpected": True})  # type: ignore[attr-defined]


def test_registered_object_kind_and_producer_name_may_be_simple_identifiers() -> None:
    reference = ExactObjectRef(object_kind="claim", object_id="synthetic-1", object_hash="a" * 64)
    producer = Producer(name="builder", version="1.0.0")
    assert reference.object_kind == "claim"
    assert producer.name == "builder"


def test_naive_and_non_utc_datetimes_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ValidTime(valid_from=datetime(2026, 1, 1), valid_to=None)
    with pytest.raises(ValidationError):
        ValidTime(
            valid_from=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=8))),
            valid_to=None,
        )
    with pytest.raises(ValidationError):
        ValidTime.model_validate({"valid_from": "2026-01-01T00:00:00", "valid_to": None})


def test_valid_time_is_half_open_and_requires_increasing_end() -> None:
    instant = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        ValidTime(valid_from=instant, valid_to=instant)


def test_extensions_require_reverse_dns_and_cannot_shadow_core_fields() -> None:
    value = ExtensionValue(extension_version="1.0.0", payload={"custom_value": 1})
    with pytest.raises(ValueError, match="reverse-DNS"):
        validate_extensions({"not-a-namespace": value}, core_fields={"tenant"})
    with pytest.raises(ValueError, match="core field"):
        validate_extensions({"com.example.feature": ExtensionValue(extension_version="1.0.0", payload={"tenant": "other"})}, core_fields={"tenant"})


def test_classification_accepts_closed_enum_members() -> None:
    classification = Classification(risk_class=RiskClass.AMBER, sensitivity=Sensitivity.INTERNAL)
    assert classification.risk_class is RiskClass.AMBER
