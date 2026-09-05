"""Pure dual-consul admission and selected-response contracts; never launches a seat.

Discovery is supplied by a trusted runtime collector. These checks confer no effect
authority and qualify neither tool execution, native resume nor remote cancellation.
TP1 envelopes reuse the existing transport's shape, but not its reasoning fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import sys
from typing import Any, Literal, Mapping

from scripts.conductor.contracts import TaskClass, TaskIntent


IdentityEvidence = Literal["response_observed", "request_observed", "unknown"]


@dataclass(frozen=True)
class Surface:
    model: str | None
    text_qualified: bool = False
    effort: str | None = None
    operations: frozenset[str] = frozenset()


# Qualification belongs to each surface, never to a compatible protocol/family.
SURFACES = {
    "codex_app_server": Surface(None),
    "claude_interactive_text": Surface("claude-fable-5-1", True),
    "kimi_text": Surface("k3", True, "max"),
    "kimi_native": Surface("k3"),
    "qwen_tp1": Surface("qwen3.8-max", True, "medium"),
    "qwen_native": Surface(None),
    "deepseek_tp1": Surface("deepseek-v4-pro", True),
    "gemini_agy": Surface("gemini-3.1-pro-high", True),
    "glm_tp1": Surface("glm-5.2", True),
    "local_r1": Surface("deepseek-r1:32b"),
}


@dataclass(frozen=True)
class DiscoveryKey:
    runtime_version: str
    config_hash: str
    host: str
    auth_context_hash: str


@dataclass(frozen=True)
class DiscoveryObservation:
    key: DiscoveryKey
    surface_id: str
    requested_model: str
    actual_model: str | None
    identity_evidence: IdentityEvidence
    observed_at: datetime
    expires_at: datetime
    capabilities: frozenset[str] = frozenset()
    enforced_caps: tuple[tuple[str, int], ...] = ()
    worker_limit: int | None = None
    delegation_observable: bool = False


@dataclass(frozen=True)
class Requirements:
    exact_model: bool = False
    output_cap: int | None = None
    total_cap: int | None = None
    workers: int = 0
    effort: str | None = None
    high_effort_authorized: bool = False
    operation: str = "text_consultation"


def admit(
    surface_id: str,
    requested_model: str,
    task: TaskIntent,
    observation: DiscoveryObservation,
    expected_key: DiscoveryKey,
    now: datetime,
    requirements: Requirements = Requirements(),
) -> tuple[str, ...]:
    """Return all rejection reasons; an empty tuple admits text preparation only."""
    surface = SURFACES.get(surface_id)
    if surface is None:
        return ("unknown_surface",)
    reasons: list[str] = []
    if not surface.text_qualified:
        reasons.append("surface_unqualified")
    if requirements.operation != "text_consultation":
        reasons.append("operation_unqualified")
    if task.mutation or task.required_tools:
        reasons.append("effects_unqualified")
    if task.contains_pii:
        reasons.append("pii_lane_unqualified")
    if (
        observation.key != expected_key
        or observation.surface_id != surface_id
        or not all(vars(expected_key).values())
    ):
        reasons.append("discovery_context_mismatch")
    timestamps = (observation.observed_at, observation.expires_at, now)
    if any(value.tzinfo is None for value in timestamps) or not (
        observation.observed_at <= now < observation.expires_at
    ):
        reasons.append("discovery_expired_or_invalid")
    if (
        observation.requested_model != requested_model
        or surface.model is not None
        and surface.model != requested_model
    ):
        reasons.append("requested_model_mismatch")
    if requirements.exact_model and (
        observation.identity_evidence != "response_observed"
        or observation.actual_model != requested_model
    ):
        reasons.append("actual_model_unproven")
    if (
        observation.identity_evidence == "response_observed"
        and observation.actual_model != requested_model
    ):
        reasons.append("actual_model_mismatch")
    if (
        not ({"text"} | task.requires | task.required_modalities)
        <= observation.capabilities
    ):
        reasons.append("capabilities_unproven")
    if requirements.effort not in (None, surface.effort):
        reasons.append("effort_unqualified")
    if surface.effort == "max" and not requirements.high_effort_authorized:
        reasons.append("high_effort_requires_explicit_admission")
    for name, requested in (
        ("output_tokens", requirements.output_cap),
        ("total_tokens", requirements.total_cap),
    ):
        enforced = dict(observation.enforced_caps).get(name)
        if requested is not None and (
            type(requested) is not int
            or requested <= 0
            or type(enforced) is not int
            or not 0 < enforced <= requested
        ):
            reasons.append(f"{name}_hard_cap_unproven")
    if type(requirements.workers) is not int or not 0 <= requirements.workers <= 4:
        reasons.append("worker_limit_invalid")
    elif requirements.workers == 0 and (
        type(observation.worker_limit) is not int or observation.worker_limit != 0
    ):
        reasons.append("delegation_must_be_disabled")
    elif requirements.workers and (
        not observation.delegation_observable
        or type(observation.worker_limit) is not int
        or not 0 < observation.worker_limit <= requirements.workers
    ):
        reasons.append("delegation_limit_unproven")
    return tuple(reasons)


@dataclass(frozen=True)
class Reply:
    content: str
    status: Literal["complete", "incomplete", "unknown"]
    actual_model: str | None
    identity_evidence: IdentityEvidence
    finish_reason: str | None = None
    native_usage: tuple[tuple[str, int], ...] = ()
    remote_effect: str = "unknown"
    local_cancelled: bool = False
    remote_cancelled: bool | None = None


def normalize_text(
    content: object,
    finish_reason: object,
    *,
    actual_model: str | None = None,
    identity_evidence: IdentityEvidence = "unknown",
    local_cancelled: bool = False,
    remote_cancelled: bool | None = None,
) -> Reply:
    """Normalize collector-selected text; native lifecycle outcomes stay separate."""
    text = content if isinstance(content, str) else ""
    status = (
        "complete"
        if finish_reason in ("stop", "end_turn") and text.strip()
        else "unknown"
    )
    if finish_reason in ("length", "max_tokens") or local_cancelled:
        status = "incomplete"
    return Reply(
        text,
        status,
        actual_model,
        identity_evidence,
        finish_reason=finish_reason if isinstance(finish_reason, str) else None,
        local_cancelled=local_cancelled,
        remote_cancelled=remote_cancelled,
    )


def normalize_tp1(
    payload: Mapping[str, Any],
    *,
    local_cancelled: bool = False,
    remote_cancelled: bool | None = None,
) -> Reply:
    """Accept content only; preserve native counters without adding reasoning twice."""
    choices = payload.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else {}
    choice = choice if isinstance(choice, dict) else {}
    message = choice.get("message", {})
    message = message if isinstance(message, dict) else {}
    model = payload.get("model")
    model = model if isinstance(model, str) and model else None
    finish_reason = choice.get("finish_reason")
    result = normalize_text(
        message.get("content"),
        finish_reason if finish_reason in ("stop", "length") else None,
        actual_model=model,
        identity_evidence="response_observed" if model else "unknown",
        local_cancelled=local_cancelled,
        remote_cancelled=remote_cancelled,
    )
    usage = payload.get("usage", {})
    usage = usage if isinstance(usage, dict) else {}
    counters: list[tuple[str, int]] = []
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(name)
        if type(value) is int and value >= 0:
            counters.append((name, value))
    for group, name in (
        ("completion_tokens_details", "reasoning_tokens"),
        ("prompt_tokens_details", "cached_tokens"),
    ):
        details = usage.get(group, {})
        if isinstance(details, dict) and type(details.get(name)) is int:
            if details[name] >= 0:
                counters.append((f"{group}.{name}", details[name]))
    return Reply(
        **{
            **vars(result),
            "native_usage": tuple(counters),
            "finish_reason": finish_reason if isinstance(finish_reason, str) else None,
        }
    )


def tp1_payload(surface_id: str, prompt: str, output_cap: int) -> dict[str, Any]:
    """Prepare the existing TP1 user-only transport shape, never a network call."""
    if surface_id not in {"qwen_tp1", "deepseek_tp1", "glm_tp1"}:
        raise ValueError("not a qualified TP1 text surface")
    if type(output_cap) is not int or output_cap <= 0:
        raise ValueError("output_cap must be positive")
    surface = SURFACES[surface_id]
    body: dict[str, Any] = {
        "model": surface.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": output_cap,
    }
    if surface.effort is not None:
        body["reasoning_effort"] = surface.effort
    return body


def main() -> int:
    """Offline JSON admission: python -m scripts.conductor.adapter_contracts < packet.json.

    Packet fields: surface_id, requested_model, expected_key, now (ISO timestamp),
    task (TaskIntent), observation (DiscoveryObservation), requirements (optional).
    Both discovery keys carry runtime_version/config_hash/host/auth_context_hash.
    Observation timestamps are ISO strings; sets and cap pairs are JSON arrays.
    Stdout contains only admission/rejection metadata; no task content is echoed.
    """
    try:
        packet = json.load(sys.stdin)
        required = {
            "surface_id",
            "requested_model",
            "expected_key",
            "now",
            "task",
            "observation",
        }
        if not required <= set(packet) <= required | {"requirements"}:
            raise ValueError("invalid fields")
        task = dict(packet["task"])
        observed = dict(packet["observation"])
        requirements = dict(packet.get("requirements", {}))
        for record, fields in (
            (task, ("mutation", "contains_pii")),
            (observed, ("delegation_observable",)),
            (requirements, ("exact_model", "high_effort_authorized")),
        ):
            if any(
                field in record and type(record[field]) is not bool for field in fields
            ):
                raise ValueError("invalid boolean")
        task["task_class"] = TaskClass(task["task_class"])
        task["files"] = tuple(task["files"])
        for field in ("requires", "required_modalities", "required_tools"):
            task[field] = frozenset(task[field])
        observed["key"] = DiscoveryKey(**observed["key"])
        for field in ("observed_at", "expires_at"):
            observed[field] = datetime.fromisoformat(observed[field])
        observed["capabilities"] = frozenset(observed.get("capabilities", []))
        observed["enforced_caps"] = tuple(
            tuple(pair) for pair in observed.get("enforced_caps", [])
        )
        reasons = admit(
            packet["surface_id"],
            packet["requested_model"],
            TaskIntent(**task),
            DiscoveryObservation(**observed),
            DiscoveryKey(**packet["expected_key"]),
            datetime.fromisoformat(packet["now"]),
            Requirements(**requirements),
        )
    except (KeyError, TypeError, ValueError):
        sys.stderr.write("invalid admission packet; no preparation admitted\n")
        return 1
    sys.stdout.write(
        json.dumps(
            {
                "admitted": not reasons,
                "reasons": reasons,
                "scope": "text_preparation_only",
            }
        )
        + "\n"
    )
    return 2 if reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
