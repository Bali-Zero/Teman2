"""Admission tests use canonical ROS objects; no model or database calls."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from backend.tests.unit.services.autonomous_lab.consul_fixtures import (
    make_request,
    reseal,
    with_intent,
)

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


@pytest.mark.parametrize("builder", ["astra", "fable"])
def test_both_consuls_can_build_with_independent_review(builder: Any) -> None:
    assert make_request(NOW, builder=builder).validate(NOW) is None


@pytest.mark.parametrize(
    "field", ["artifact", "effective_input", "configuration", "evidence", "runtime_binding"]
)
def test_changed_effective_bytes_invalidate_the_frozen_review(field: str) -> None:
    request = make_request(NOW)
    inputs = replace(request.inputs, **{field: b"changed"})
    assert inputs.digest != request.inputs.digest
    with pytest.raises(PermissionError, match="input_mismatch"):
        replace(request, inputs=inputs).validate(NOW)


def test_a_consul_cannot_review_its_own_artifact() -> None:
    request = make_request(NOW, builder="astra", reviewer="astra")
    with pytest.raises(PermissionError, match="independent_consul"):
        request.validate(NOW)


def test_declared_builder_must_match_the_intent_producer() -> None:
    request = with_intent(
        make_request(NOW), producer={"name": "com.balizero.consul.fable", "version": "4.0.0"}
    )
    with pytest.raises(PermissionError, match="independent_consul"):
        request.validate(NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"authorized_effects": ["com.example.effect.publish"]},
        {
            "authority": {
                "role": "other.role",
                "scope": "dual-consul-synthetic",
                "verified_at": (NOW - timedelta(seconds=12)).isoformat().replace("+00:00", "Z"),
            }
        },
        {
            "authority": {
                "role": "consul.synthetic_broker",
                "scope": "other-run",
                "verified_at": (NOW - timedelta(seconds=12)).isoformat().replace("+00:00", "Z"),
            }
        },
    ],
)
def test_approval_must_authorize_exact_effect_role_and_scope(changes: dict[str, Any]) -> None:
    request = make_request(NOW)
    with pytest.raises(PermissionError):
        replace(request, approval=reseal(request.approval, **changes)).validate(NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"action_type": "com.example.effect.publish"},
        {
            "authority_required": {
                "role": "other.role",
                "scope": "dual-consul-synthetic",
                "expires_after_seconds": 3600,
            }
        },
        {
            "authority_required": {
                "role": "consul.synthetic_broker",
                "scope": "other-run",
                "expires_after_seconds": 3600,
            }
        },
        {
            "authority_required": {
                "role": "consul.synthetic_broker",
                "scope": "dual-consul-synthetic",
                "expires_after_seconds": 10,
            }
        },
    ],
)
def test_intent_cannot_expand_the_grant(changes: dict[str, Any]) -> None:
    with pytest.raises(PermissionError):
        with_intent(make_request(NOW), **changes).validate(NOW)


@pytest.mark.parametrize("field", ["approval", "review"])
def test_expiry_is_exclusive(field: str) -> None:
    request = make_request(NOW)
    expired = reseal(getattr(request, field), expires_at=NOW.isoformat().replace("+00:00", "Z"))
    with pytest.raises((ValueError, PermissionError)):
        replace(request, **{field: expired}).validate(NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"verdict": "pass_with_limits"},
        {"limits": ["synthetic-limitation"]},
        {"checks": []},
        {"criteria_version": "outdated"},
        {
            "verifier": {
                "name": "com.balizero.consul.astra",
                "version": "4",
                "independence_class": "cross_family",
            }
        },
        {
            "verifier": {
                "name": "com.balizero.consul.fable",
                "version": "4",
                "independence_class": "self",
            }
        },
    ],
)
def test_review_must_be_current_independent_and_unrestricted(changes: dict[str, Any]) -> None:
    request = make_request(NOW)
    with pytest.raises(PermissionError, match="review"):
        replace(request, review=reseal(request.review, **changes)).validate(NOW)


@pytest.mark.parametrize("field", ["intent", "approval", "review"])
def test_model_copy_cannot_bypass_canonical_hash_checks(field: str) -> None:
    request = make_request(NOW)
    modified = getattr(request, field).model_copy(update={"object_hash": "0" * 64})
    with pytest.raises(ValidationError, match="object_hash"):
        replace(request, **{field: modified}).validate(NOW)


def test_nested_extension_mutation_is_revalidated_at_admission() -> None:
    request = make_request(NOW)
    review = reseal(
        request.review,
        extensions={
            "com.balizero.test": {
                "extension_version": "1.0.0",
                "payload": {"synthetic_tags": ["before"]},
            }
        },
    )
    request = replace(request, review=review)
    request.validate(NOW)
    review.extensions["com.balizero.test"].payload["synthetic_tags"].append("after")
    with pytest.raises(ValidationError, match="object_hash"):
        request.validate(NOW)
