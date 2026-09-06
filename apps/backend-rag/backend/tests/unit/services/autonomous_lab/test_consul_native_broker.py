"""Boundary tests without a provider, database, service install, or credentials."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.services.autonomous_lab.consul_native_broker import (
    NativeGrant,
    _result,
    service_state_store,
)
from backend.tests.unit.services.autonomous_lab.consul_fixtures import make_request, reseal
from backend.tests.unit.services.autonomous_lab.native_consul_fixtures import (
    active_binding,
    grant_payload,
    make_native_grant,
    selected_result,
)

NOW = datetime(2026, 9, 6, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("builder", ["astra", "fable"])
def test_both_consuls_have_the_same_native_grant_contract(builder: str) -> None:
    grant = make_native_grant(NOW, builder=builder)
    restored = NativeGrant.from_payload(grant_payload(grant))
    restored.validate(NOW)
    assert restored.pins == grant.pins
    assert restored.check_binding(active_binding(grant))["thread_id"] == "synthetic-thread"


@pytest.mark.parametrize(
    "key",
    [
        "mission_id",
        "input_hash",
        "model",
        "effort",
        "runtime_version",
        "config_hash",
        "host",
        "auth_context_hash",
    ],
)
def test_changed_native_binding_is_rejected(key: str) -> None:
    grant = make_native_grant(NOW)
    binding = deepcopy(active_binding(grant))
    target = binding if key in binding else binding["discovery_key"]
    target[key] = "f" * 64 if key.endswith("hash") else "changed"
    with pytest.raises(PermissionError):
        grant.check_binding(binding)


def test_synthetic_approval_never_authorizes_native_spend() -> None:
    native = make_native_grant(NOW)
    synthetic = make_request(NOW, native.run_id)
    with pytest.raises(PermissionError, match="native_grant_scope_mismatch"):
        replace(
            native, intent=synthetic.intent, approval=synthetic.approval, review=synthetic.review
        ).validate(NOW)


def test_mutable_nested_grant_cannot_evade_frozen_hashes() -> None:
    grant = make_native_grant(NOW)
    grant.binding["input_hash"] = "e" * 64
    with pytest.raises(PermissionError, match="native_grant_scope_mismatch"):
        grant.validate(NOW)


@pytest.mark.parametrize("unqualified_role", ["builder", "reviewer"])
def test_consul_names_require_exact_registered_identities(unqualified_role: str) -> None:
    grant = make_native_grant(NOW)
    intent = grant.intent
    if unqualified_role == "builder":
        intent = reseal(intent, producer={"name": "astra", "version": intent.producer.version})
    approval = reseal(
        grant.approval,
        subject={
            **grant.approval.subject.model_dump(mode="json"),
            "object_hash": intent.object_hash,
        },
    )
    verifier = grant.review.verifier.model_dump(mode="json")
    if unqualified_role == "reviewer":
        verifier["name"] = "fable"
    review = reseal(
        grant.review,
        verifier=verifier,
        target_objects=[
            {
                "object_kind": "action_intent",
                "object_id": str(intent.action_intent_id),
                "object_hash": intent.object_hash,
            }
        ],
    )
    with pytest.raises(PermissionError, match="native_review_missing_or_mismatched"):
        replace(grant, intent=intent, approval=approval, review=review).validate(NOW)


@pytest.mark.parametrize("change", ["self_review", "expired_review", "expired_grant", "wrong_role"])
def test_invalid_authority_and_review_are_rejected(change: str) -> None:
    grant = make_native_grant(NOW)
    at = NOW
    if change == "self_review":
        grant = replace(
            grant,
            review=reseal(
                grant.review,
                verifier={
                    **grant.review.verifier.model_dump(mode="json"),
                    "name": grant.intent.producer.name,
                },
            ),
        )
    elif change == "expired_review":
        at = NOW + timedelta(minutes=4, seconds=1)
    elif change == "expired_grant":
        at = NOW + timedelta(minutes=6)
    else:
        grant = replace(
            grant,
            approval=reseal(
                grant.approval,
                authority={**grant.approval.authority.model_dump(mode="json"), "role": "operator"},
            ),
        )
    with pytest.raises((PermissionError, ValueError)):
        grant.validate(at)


@pytest.mark.parametrize(
    "change",
    [
        "raw_text",
        "sql",
        "effect",
        "runtime_model",
        "thread_id",
        "usage_text",
        "usage_boolean",
        "remote_cancelled",
        "inference_model",
    ],
)
def test_checkpoint_accepts_only_selected_native_metadata(change: str) -> None:
    grant = make_native_grant(NOW)
    result = selected_result(grant)
    if change == "usage_text":
        result["native_usage"]["total"]["raw_text"] = "discard this"
    elif change == "usage_boolean":
        result["native_usage"]["total"]["inputTokens"] = True
    else:
        result[change] = "unapproved"
    with pytest.raises(PermissionError):
        _result(active_binding(grant), result)


def test_reasoning_tokens_remain_native_counters_not_an_added_total() -> None:
    grant = make_native_grant(NOW)
    result = _result(active_binding(grant), selected_result(grant))
    assert result["native_usage"]["total"]["totalTokens"] == 12


def test_rpc_usage_projection_survives_native_checkpoint_and_broker_validation() -> None:
    from scripts.conductor.adapter_contracts import DiscoveryKey
    from scripts.conductor.app_server_rpc import _notification
    from scripts.conductor.codex_shadow import NativeBinding, NativeResult

    grant = make_native_grant(NOW)
    wire = active_binding(grant)
    counters = {
        "inputTokens": 10,
        "cachedInputTokens": 3,
        "cacheWriteInputTokens": 2,
        "outputTokens": 5,
        "reasoningOutputTokens": 2,
        "totalTokens": 15,
    }
    event = _notification(
        "thread/tokenUsage/updated",
        {
            "threadId": wire["thread_id"],
            "turnId": "synthetic-turn",
            "tokenUsage": {
                "last": counters,
                "total": {**counters, "unapprovedCounter": 9},
                "modelContextWindow": 32000,
            },
        },
    )
    assert event is not None
    binding = NativeBinding(**{**wire, "discovery_key": DiscoveryKey(**wire["discovery_key"])})
    checkpoint = NativeResult(
        binding, "synthetic-turn", "completed", "synthetic reply", event["params"]["tokenUsage"]
    ).checkpoint()
    selected = _result(wire, checkpoint)
    assert selected["native_usage"] == {
        "last": counters,
        "total": counters,
        "modelContextWindow": 32000,
        "unknownCounters": {"names": ["total.unapprovedCounter"], "omitted": False},
    }
    # The broker keeps its own closed-field boundary even after RPC projection.
    checkpoint["native_usage"]["total"]["unapprovedCounter"] = 9
    with pytest.raises(PermissionError, match="native_usage_shape"):
        _result(wire, checkpoint)


@pytest.mark.parametrize(
    "marker",
    [
        {"names": [], "omitted": False},
        {"names": ["root.future"], "omitted": 1},
        {"names": ["root.future", "root.future"], "omitted": False},
        {"names": ["total.z", "last.a"], "omitted": False},
        {"names": ["root.not allowed"], "omitted": True},
        {"names": [f"root.future{i:02d}" for i in range(17)], "omitted": True},
        {"names": ["root.future"], "omitted": False, "value": "discard"},
    ],
)
def test_unknown_counter_marker_has_a_closed_bounded_shape(marker: dict[str, object]) -> None:
    grant = make_native_grant(NOW)
    result = selected_result(grant)
    result["native_usage"]["unknownCounters"] = marker
    with pytest.raises(PermissionError, match="native_usage_shape"):
        _result(active_binding(grant), result)


def test_unknown_counter_unrenderable_names_remain_an_explicit_omission() -> None:
    grant = make_native_grant(NOW)
    result = selected_result(grant)
    result["native_usage"]["unknownCounters"] = {"names": [], "omitted": True}
    assert _result(active_binding(grant), result)["native_usage"]["unknownCounters"] == {
        "names": [],
        "omitted": True,
    }


@pytest.mark.parametrize(
    "uid,user,hostname",
    [
        (501, "nuzantara", "Nuzantara"),
        (0, "root", "Nuzantara"),
        (550, "consul-executor", "Air-M5"),
        (501, "consul-executor", "Nuzantara"),
    ],
)
def test_service_placement_refuses_human_root_other_host_and_forged_identity(
    uid: int,
    user: str,
    hostname: str,
) -> None:
    account_uid = 550 if user == "consul-executor" else uid
    with (
        patch(
            "backend.services.autonomous_lab.consul_native_broker.pwd.getpwnam",
            return_value=SimpleNamespace(pw_uid=account_uid, pw_name=user),
        ),
        patch("backend.services.autonomous_lab.consul_native_broker.os.geteuid", return_value=uid),
        patch(
            "backend.services.autonomous_lab.consul_native_broker.socket.gethostname",
            return_value=hostname,
        ),
    ):
        with pytest.raises(PermissionError, match="native_service_identity_required"):
            service_state_store(service_user=user)


def test_distinct_kernel_service_identity_can_use_existing_pro_lifecycle() -> None:
    with (
        patch(
            "backend.services.autonomous_lab.consul_native_broker.pwd.getpwnam",
            return_value=SimpleNamespace(pw_uid=550, pw_name="consul-executor"),
        ),
        patch("backend.services.autonomous_lab.consul_native_broker.os.geteuid", return_value=550),
        patch(
            "backend.services.autonomous_lab.consul_native_broker.socket.gethostname",
            return_value="Nuzantara",
        ),
    ):
        assert service_state_store(service_user="consul-executor").placement.can_claim_runs
