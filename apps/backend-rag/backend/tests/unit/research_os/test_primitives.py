from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.enums import RiskClass, Sensitivity
from research_os.hashing import object_hash
from research_os.models.revocation_receipt import RevocationReceipt
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
def test_core_models_reject_unknown_top_level_fields(
    model: object, payload: dict[str, object]
) -> None:
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
        validate_extensions({"not-a-namespace": value})
    with pytest.raises(ValueError, match="core field"):
        validate_extensions(
            {
                "com.example.feature": ExtensionValue(
                    extension_version="1.0.0",
                    payload={"tenant": "other"},
                )
            }
        )


def test_extension_namespace_rejects_trailing_hyphen() -> None:
    value = ExtensionValue(extension_version="1.0.0", payload={"custom_value": 1})

    with pytest.raises(ValueError, match="reverse-DNS"):
        validate_extensions({"com.example.edge-": value})


def _revocation_with_extension(payload: dict[str, object]) -> dict[str, object]:
    candidate = dict(payload)
    candidate["object_hash"] = object_hash(candidate)
    return candidate


def test_revocation_extension_cannot_introduce_unrevoke(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    payload["extensions"] = {
        "com.example.revocation": {
            "extension_version": "1.0.0",
            "payload": {"unrevoke": True},
        }
    }

    with pytest.raises(ValidationError, match="core field"):
        RevocationReceipt.model_validate(_revocation_with_extension(payload))


def test_revocation_extension_cannot_hide_reserved_field_at_nested_depth(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    payload["extensions"] = {
        "com.example.revocation": {
            "extension_version": "1.0.0",
            "payload": {"wrapper": {"tenant": "other"}},
        }
    }

    with pytest.raises(ValidationError, match="core field"):
        RevocationReceipt.model_validate(_revocation_with_extension(payload))


def test_classification_accepts_closed_enum_members() -> None:
    classification = Classification(risk_class=RiskClass.AMBER, sensitivity=Sensitivity.INTERNAL)
    assert classification.risk_class is RiskClass.AMBER
