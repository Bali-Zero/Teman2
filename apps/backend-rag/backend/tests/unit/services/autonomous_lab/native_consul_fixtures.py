"""Synthetic, canonically sealed native grant inputs; never an issuance API."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from backend.services.autonomous_lab.consul_native_broker import (
    AUTHORITY,
    CRITERIA,
    EFFECT,
    NativeGrant,
)
from backend.tests.unit.services.autonomous_lab.consul_fixtures import make_request, reseal

CANARY_MODEL = "gpt-6-astra"


class NativeCanaryRPC:
    """Only the deterministic native messages used by backend canary tests."""

    credential_fingerprint = "synthetic-credential-one"

    def __init__(self, reply_text: str) -> None:
        self.reply_text = reply_text
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.local_stopped = False

    async def call(self, method: str, params: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.calls.append((method, params))
        if method == "config/read":
            from scripts.conductor.codex_shadow_launch import DISABLED_FEATURES

            return {
                "config": {
                    "model_provider": "openai",
                    "sandbox_mode": "read-only",
                    "approval_policy": "never",
                    "web_search": "disabled",
                    "shell_environment_policy": {"inherit": "none", "set": {}},
                    "features": dict.fromkeys(DISABLED_FEATURES, False),
                }
            }
        if method == "account/read":
            return {
                "account": {
                    "type": "chatgpt",
                    "email": "synthetic@example.invalid",
                    "planType": "pro",
                }
            }
        if method == "model/list":
            return {
                "data": [
                    {
                        "model": CANARY_MODEL,
                        "supportedReasoningEfforts": [{"reasoningEffort": "medium"}],
                    }
                ]
            }
        if method == "thread/start":
            return {
                "thread": {"id": "thread-1"},
                "cwd": params["cwd"],
                "model": CANARY_MODEL,
                "modelProvider": "openai",
                "approvalPolicy": "never",
                "reasoningEffort": params["config"]["model_reasoning_effort"],
                "sandbox": {"type": "readOnly", "networkAccess": False},
            }
        if method == "turn/start":
            for event, payload in (
                (
                    "item/completed",
                    {
                        "item": {
                            "type": "agentMessage",
                            "text": self.reply_text,
                            "phase": "final_answer",
                        }
                    },
                ),
                (
                    "thread/tokenUsage/updated",
                    {
                        "tokenUsage": {
                            "total": {
                                "outputTokens": 5,
                                "reasoningOutputTokens": 2,
                                "cacheWriteInputTokens": 1,
                            }
                        }
                    },
                ),
                ("turn/completed", {"turn": {"id": "turn-1", "status": "completed"}}),
            ):
                self.events.put_nowait(
                    {
                        "method": event,
                        "params": {"threadId": "thread-1", "turnId": "turn-1", **payload},
                    }
                )
            return {"turn": {"id": "turn-1"}}
        if method == "turn/interrupt":
            return {}
        raise AssertionError(f"unexpected native test method: {method}")

    async def next_notification(self, **kwargs: Any) -> dict[str, Any]:
        return await self.events.get()

    async def close(self) -> None:
        self.local_stopped = True


def make_native_grant(
    now: datetime,
    run_id: str = "native-run",
    *,
    revision: int = 1,
    builder: str = "astra",
    binding: dict[str, Any] | None = None,
) -> NativeGrant:
    request = make_request(now, run_id, builder=builder, grant_revision=revision)
    selected = binding or {
        "mission_id": run_id,
        "input_hash": sha256(b"synthetic native prompt").hexdigest(),
        "discovery_key": {
            "runtime_version": "codex-cli 0.147.0@" + "b" * 64,
            "config_hash": "c" * 64,
            "host": "Nuzantara",
            "auth_context_hash": "a" * 64,
        },
        "model": "synthetic-test-model",
        "effort": "medium",
        "thread_id": None,
    }
    draft = NativeGrant(
        str(uuid5(NAMESPACE_URL, f"native-grant:{run_id}:{revision}")),
        selected,
        request.intent,
        request.approval,
        request.review,
    )
    intent = reseal(
        request.intent,
        action_type=EFFECT,
        expected_outcome_types=[EFFECT],
        arguments_ref=f"native:{run_id}",
        arguments_hash=draft.arguments_hash,
        input_revision_hash=draft.packet_hash,
        target={
            "system": "com.balizero.autonomous_lab",
            "object_ref": {
                "object_kind": "com.balizero.lab_run",
                "object_id": run_id,
                "object_hash": draft.packet_hash,
            },
        },
        authority_required={"role": AUTHORITY, "scope": run_id, "expires_after_seconds": 3600},
    )
    approval = reseal(
        request.approval,
        subject={
            "kind": "action_intent",
            "object_id": str(intent.action_intent_id),
            "object_hash": intent.object_hash,
        },
        bindings={"arguments_hash": draft.arguments_hash, "input_revision_hash": draft.packet_hash},
        authority={**request.approval.authority.model_dump(mode="json"), "role": AUTHORITY},
        authorized_effects=[EFFECT],
    )
    review = reseal(
        request.review,
        criteria_version=CRITERIA,
        target_objects=[
            {
                "object_kind": "action_intent",
                "object_id": str(intent.action_intent_id),
                "object_hash": intent.object_hash,
            }
        ],
    )
    grant = replace(draft, intent=intent, approval=approval, review=review)
    grant.validate(now)
    return grant


def grant_payload(grant: NativeGrant) -> dict[str, Any]:
    return {
        "grant_id": grant.grant_id,
        "binding": grant.binding,
        **{
            key: getattr(grant, key).model_dump(mode="json", exclude_unset=True)
            for key in ("intent", "approval", "review")
        },
    }


def active_binding(grant: NativeGrant) -> dict[str, Any]:
    return {**grant.binding, "thread_id": "synthetic-thread"}


def selected_result(grant: NativeGrant, *, status: str = "completed") -> dict[str, Any]:
    binding = active_binding(grant)
    return {
        "mission_id": grant.run_id,
        "thread_id": binding["thread_id"],
        "turn_id": "synthetic-turn",
        "input_hash": binding["input_hash"],
        "output_hash": sha256(b"synthetic reply").hexdigest(),
        "requested_model": binding["model"],
        "runtime_model": binding["model"],
        "inference_model": None,
        "identity_evidence": "request_observed",
        "model_evidence_source": "native_thread_configuration",
        "effort": binding["effort"],
        **binding["discovery_key"],
        "status": status,
        "native_usage": {
            "total": {
                "inputTokens": 10,
                "outputTokens": 2,
                "reasoningOutputTokens": 1,
                "totalTokens": 12,
            }
        },
        "local_interrupted": False,
        "remote_cancelled": None,
    }
