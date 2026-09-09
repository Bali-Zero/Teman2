"""Offline fixtures for v4 admission boundaries and selected response evidence."""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.conductor.adapter_contracts import (
    SURFACES,
    DiscoveryKey,
    DiscoveryObservation,
    Requirements,
    admit,
    normalize_text,
    normalize_tp1,
    tp1_payload,
)
from scripts.conductor.contracts import TaskClass, TaskIntent


NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
KEY = DiscoveryKey("1.0", "config-sha256", "pro", "auth-context-sha256")
TASK = TaskIntent(
    "synthetic",
    TaskClass.READ_ONLY,
    1,
    False,
    (),
    frozenset(),
    "synthetic",
    100,
    frozenset({"text"}),
    frozenset(),
    False,
)


def observation(surface: str = "qwen_tp1", **changes: object) -> DiscoveryObservation:
    model = SURFACES[surface].model or "discovered-model"
    base = DiscoveryObservation(
        KEY,
        surface,
        model,
        model,
        "response_observed",
        NOW - timedelta(minutes=1),
        NOW + timedelta(minutes=1),
        frozenset({"text"}),
        worker_limit=0,
    )
    return replace(base, **changes)


def rejection(
    surface: str = "qwen_tp1",
    *,
    observed: DiscoveryObservation | None = None,
    required: Requirements = Requirements(),
    task: TaskIntent = TASK,
    key: DiscoveryKey = KEY,
) -> tuple[str, ...]:
    observed = observed or observation(surface)
    return admit(surface, observed.requested_model, task, observed, key, NOW, required)


@pytest.mark.parametrize("surface", SURFACES)
def test_surface_qualification_never_grants_native_effects(surface: str) -> None:
    reasons = rejection(surface, required=Requirements(high_effort_authorized=True))
    assert ("surface_unqualified" in reasons) is (not SURFACES[surface].text_qualified)
    assert not SURFACES[surface].operations
    for operation in ("invoke", "resume", "cancel"):
        assert "operation_unqualified" in rejection(
            surface, required=Requirements(operation=operation)
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("runtime_version", "2.0"),
        ("config_hash", "changed"),
        ("host", "air-m5"),
        ("auth_context_hash", "rotated"),
    ],
)
def test_discovery_cannot_cross_context(field: str, value: str) -> None:
    assert "discovery_context_mismatch" in rejection(key=replace(KEY, **{field: value}))


@pytest.mark.parametrize(
    "changes",
    [
        {"expires_at": NOW},
        {"observed_at": NOW + timedelta(seconds=1)},
        {"observed_at": NOW.replace(tzinfo=None)},
    ],
)
def test_stale_future_and_naive_discovery_is_rejected(changes: dict) -> None:
    assert "discovery_expired_or_invalid" in rejection(observed=observation(**changes))


@pytest.mark.parametrize("proof", ["request_observed", "unknown"])
def test_exact_identity_requires_response_observation(proof: str) -> None:
    observed = observation("gemini_agy", actual_model=None, identity_evidence=proof)
    assert not rejection("gemini_agy", observed=observed)
    assert "actual_model_unproven" in rejection(
        "gemini_agy", observed=observed, required=Requirements(exact_model=True)
    )


def test_wrong_model_capability_and_effects_cannot_be_admitted() -> None:
    assert "actual_model_mismatch" in rejection(
        observed=observation(actual_model="other")
    )
    assert "capabilities_unproven" in rejection(
        observed=observation(capabilities=frozenset())
    )
    assert "effects_unqualified" in rejection(task=replace(TASK, mutation=True))
    assert "effects_unqualified" in rejection(
        task=replace(TASK, required_tools=frozenset({"shell"}))
    )
    assert "pii_lane_unqualified" in rejection(task=replace(TASK, contains_pii=True))


def test_caps_require_separate_verified_enforcement_and_workers_are_observable() -> (
    None
):
    required = Requirements(output_cap=100, total_cap=200, workers=4)
    observed = observation(enforced_caps=(("output_tokens", 100),), worker_limit=4)
    reasons = rejection(observed=observed, required=required)
    assert "total_tokens_hard_cap_unproven" in reasons
    assert "delegation_limit_unproven" in reasons
    observed = replace(
        observed,
        enforced_caps=(("output_tokens", 100), ("total_tokens", 200)),
        delegation_observable=True,
    )
    assert not rejection(observed=observed, required=required)
    assert "delegation_limit_unproven" in rejection(
        observed=observed, required=Requirements(workers=2)
    )
    assert "worker_limit_invalid" in rejection(required=Requirements(workers=5))
    assert "delegation_must_be_disabled" in rejection(observed=observed)
    assert not rejection(observed=replace(observed, worker_limit=0))
    assert "output_tokens_hard_cap_unproven" in rejection(
        observed=observed, required=Requirements(output_cap=50)
    )


@pytest.mark.parametrize("limit", [None, False, True, 0.0, 1, 4])
def test_zero_workers_requires_proven_disabled_integer_limit(limit: object) -> None:
    assert "delegation_must_be_disabled" in rejection(
        observed=observation(worker_limit=limit)
    )
    assert not rejection(observed=observation(worker_limit=0))


@pytest.mark.parametrize(
    "surface,effort",
    [
        ("qwen_tp1", "max"),
        ("deepseek_tp1", "medium"),
        ("glm_tp1", "medium"),
        ("gemini_agy", "high"),
        ("kimi_text", "medium"),
    ],
)
def test_no_cross_provider_effort_translation(surface: str, effort: str) -> None:
    assert "effort_unqualified" in rejection(
        surface, required=Requirements(effort=effort)
    )


def test_kimi_inherited_max_requires_deliberate_mission_admission() -> None:
    assert "high_effort_requires_explicit_admission" in rejection("kimi_text")
    assert not rejection(
        "kimi_text", required=Requirements(high_effort_authorized=True)
    )


@pytest.mark.parametrize("surface", ["qwen_tp1", "deepseek_tp1", "glm_tp1"])
def test_tp1_fields_are_user_only_and_effort_is_route_specific(surface: str) -> None:
    body = tp1_payload(surface, "Synthetic prompt", 100)
    assert body["messages"] == [{"role": "user", "content": "Synthetic prompt"}]
    assert body["model"] == SURFACES[surface].model
    expected = {"model", "messages", "max_tokens"}
    if surface == "qwen_tp1":
        expected.add("reasoning_effort")
        assert body["reasoning_effort"] == "medium"
    assert set(body) == expected


@pytest.mark.parametrize(
    "finish,status", [("stop", "complete"), ("length", "incomplete"), (None, "unknown")]
)
def test_reply_completion_and_remote_outcome_are_independent(
    finish: str | None, status: str
) -> None:
    reply = normalize_tp1(
        {
            "model": "qwen3.8-max",
            "choices": [
                {
                    "message": {
                        "content": "Selected answer",
                        "reasoning_content": "EXCLUDED",
                    },
                    "finish_reason": finish,
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 30,
                "total_tokens": 40,
                "completion_tokens_details": {"reasoning_tokens": 20},
                "prompt_tokens_details": {"cached_tokens": 5},
                "api_key": "EXCLUDED",
            },
        }
    )
    assert reply.status == status
    assert reply.remote_effect == "unknown"
    assert reply.actual_model == "qwen3.8-max"
    assert reply.identity_evidence == "response_observed"
    assert dict(reply.native_usage)["total_tokens"] == 40
    assert dict(reply.native_usage)["prompt_tokens_details.cached_tokens"] == 5
    assert len(reply.native_usage) == 5
    assert reply.finish_reason == finish
    assert "EXCLUDED" not in repr(reply)


def test_reasoning_only_missing_identity_and_late_reply_after_cancel_are_not_success() -> (
    None
):
    reply = normalize_tp1(
        {
            "choices": [
                {"message": {"reasoning_content": "EXCLUDED"}, "finish_reason": "stop"}
            ]
        }
    )
    assert reply.content == "" and reply.status == "unknown"
    assert reply.identity_evidence == "unknown" and reply.actual_model is None
    late = normalize_text("Late answer", "stop", local_cancelled=True)
    assert late.status == "incomplete" and late.local_cancelled
    assert late.remote_cancelled is None and late.remote_effect == "unknown"


@pytest.mark.parametrize(
    "payload",
    [{}, {"choices": None}, {"choices": [None]}, {"choices": [{"message": None}]}],
)
def test_malformed_envelopes_never_become_complete(payload: dict) -> None:
    assert normalize_tp1(payload).status == "unknown"


def test_native_claude_completion_does_not_change_tp1_finish_contract() -> None:
    native = normalize_text("Selected answer", "end_turn")
    assert native.status == "complete" and native.finish_reason == "end_turn"
    assert normalize_text("Partial", "max_tokens").status == "incomplete"
    incompatible = normalize_tp1(
        {"choices": [{"message": {"content": "answer"}, "finish_reason": "end_turn"}]}
    )
    assert incompatible.status == "unknown"
    assert incompatible.finish_reason == "end_turn"


def _admission_packet() -> dict:
    """The CLI's documented packet, kept synthetic and free of prompt text."""
    return {
        "surface_id": "qwen_tp1",
        "requested_model": "qwen3.8-max",
        "expected_key": asdict(KEY),
        "now": NOW.isoformat(),
        "task": asdict(TASK),
        "observation": asdict(observation()),
        "requirements": {"exact_model": True},
    }


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, frozenset):
        return sorted(value)
    raise TypeError("unsupported fixture value")


@pytest.mark.parametrize(
    "proof,exit_code", [("response_observed", 0), ("request_observed", 2)]
)
def test_offline_cli_is_a_real_admission_consumer(proof: str, exit_code: int) -> None:
    packet = _admission_packet()
    packet["observation"]["identity_evidence"] = proof
    result = subprocess.run(
        [sys.executable, "-m", "scripts.conductor.adapter_contracts"],
        cwd=Path(__file__).resolve().parents[2],
        input=json.dumps(packet, default=_json_default),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == exit_code, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["admitted"] is (exit_code == 0)
    assert receipt["scope"] == "text_preparation_only"
    if exit_code:
        assert "actual_model_unproven" in receipt["reasons"]


@pytest.mark.parametrize("change", ["unknown_field", "string_boolean"])
def test_invalid_cli_packet_rejects_without_echoing_content(change: str) -> None:
    packet = _admission_packet()
    if change == "unknown_field":
        packet["prompt"] = "EXCLUDED"
    else:
        packet["requirements"]["exact_model"] = "false"
    result = subprocess.run(
        [sys.executable, "-m", "scripts.conductor.adapter_contracts"],
        cwd=Path(__file__).resolve().parents[2],
        input=json.dumps(packet, default=_json_default),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1 and not result.stdout
    assert "EXCLUDED" not in result.stderr
