"""Opt-in App Server qualification lane. No effect authority or scheduler.

The trusted host supplies a fresh authorization callback. This adapter only
admits tool-free, non-PII text with zero delegates; operational Astra stays
unqualified. Runtime configuration identity is not inference-response identity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable

from scripts.conductor.adapter_contracts import (
    DiscoveryKey,
    DiscoveryObservation,
    Requirements,
    admit,
)
from scripts.conductor.app_server_rpc import AppServerRPC, AppServerError
from scripts.conductor.contracts import TaskClass, TaskIntent
from scripts.conductor.codex_shadow_launch import DISABLED_FEATURES
from scripts.conductor.native_canary_contract import TURN_TIMEOUT_SECONDS


def digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class NativeBinding:
    mission_id: str
    input_hash: str
    discovery_key: DiscoveryKey
    model: str
    effort: str
    thread_id: str | None = None


Authorize = Callable[[NativeBinding, str], Awaitable[None]]


@dataclass(frozen=True)
class NativeResult:
    binding: NativeBinding
    turn_id: str
    status: str
    text: str
    native_usage: dict[str, Any]
    local_interrupted: bool = False
    remote_cancelled: None = None

    def checkpoint(self) -> dict[str, Any]:
        """Receipt-safe handoff; text and provider error payloads stay out."""
        return {
            "mission_id": self.binding.mission_id,
            "thread_id": self.binding.thread_id,
            "turn_id": self.turn_id,
            "input_hash": self.binding.input_hash,
            "output_hash": sha256(self.text.encode()).hexdigest(),
            "requested_model": self.binding.model,
            "runtime_model": self.binding.model,
            "inference_model": None,
            "identity_evidence": "request_observed",
            "model_evidence_source": "native_thread_configuration",
            "effort": self.binding.effort,
            "runtime_version": self.binding.discovery_key.runtime_version,
            "config_hash": self.binding.discovery_key.config_hash,
            "auth_context_hash": self.binding.discovery_key.auth_context_hash,
            "host": self.binding.discovery_key.host,
            "status": self.status,
            "native_usage": self.native_usage,
            "local_interrupted": self.local_interrupted,
            "remote_cancelled": self.remote_cancelled,
        }


class CodexShadow:
    """One process, one native mission; same-process continuity only.

    Authorization callbacks run before native start/resume/turn and after reply.
    They must consult the existing broker, not a model-supplied boolean. A callback
    cannot manufacture an executor service boundary; this remains shadow only.
    """

    def __init__(
        self,
        rpc: AppServerRPC,
        *,
        cwd: Path,
        runtime_version: str,
        host: str,
        authorize: Authorize,
        auth_fingerprint: Callable[[], str],
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.rpc, self.cwd = rpc, cwd.resolve()
        self.runtime_version, self.host = runtime_version, host
        self.authorize, self.clock = authorize, clock
        self.auth_fingerprint = auth_fingerprint
        self.turn_started = asyncio.Event()
        self._catalog: tuple[DiscoveryKey, datetime, list[dict[str, Any]]] | None = None
        self._binding: NativeBinding | None = None
        self._active_turn: str | None = None
        self._cancelled = False
        self._busy = False
        self.cancellation: dict[str, Any] = {}
        self._cancel_lock = asyncio.Lock()

    async def discover(self, model: str) -> tuple[DiscoveryObservation, frozenset[str]]:
        raw = await self.rpc.call(
            "config/read", {"cwd": str(self.cwd), "includeLayers": False}
        )
        config = raw["config"]
        validate_shadow_config(config)
        account = (await self.rpc.call("account/read", {"refreshToken": False})).get(
            "account"
        )
        if not isinstance(account, dict) or account.get("type") != "chatgpt":
            raise PermissionError("chatgpt_subscription_required")
        key = DiscoveryKey(
            self.runtime_version,
            digest(config),
            self.host,
            digest({"account": account, "credential": self.auth_fingerprint()}),
        )
        now = self.clock()
        if self._catalog is None or self._catalog[0] != key or now >= self._catalog[1]:
            models, cursor, seen = [], None, set()
            for _ in range(20):
                page = await self.rpc.call(
                    "model/list", {"cursor": cursor, "limit": 100}
                )
                models.extend(page["data"])
                cursor = page.get("nextCursor")
                if not cursor:
                    break
                if cursor in seen:
                    raise PermissionError("catalog_cursor_cycle")
                seen.add(cursor)
            else:
                raise PermissionError("catalog_page_limit")
            self._catalog = key, now + timedelta(minutes=5), models
        found = next((m for m in self._catalog[2] if m.get("model") == model), None)
        if found is None:
            raise PermissionError("model_unavailable")
        observation = DiscoveryObservation(
            key,
            "codex_app_server_shadow",
            model,
            None,
            "request_observed",
            now,
            self._catalog[1],
            frozenset({"text"}),
            worker_limit=0,
        )
        return observation, frozenset(
            x["reasoningEffort"] for x in found["supportedReasoningEfforts"]
        )

    async def invoke(
        self,
        task: TaskIntent,
        text: str,
        *,
        model: str,
        effort: str,
        requirements: Requirements = Requirements(),
        timeout: float = TURN_TIMEOUT_SECONDS,
    ) -> NativeResult:
        if self._busy or self._cancelled:
            raise PermissionError("mission_busy_or_cancelled")
        if (
            not text
            or len(text.encode()) > 32768
            or not 0 < timeout <= TURN_TIMEOUT_SECONDS
        ):
            raise ValueError("bounded_input_and_timeout_required")
        self._busy = True
        try:
            obs, efforts = await self.discover(model)
            if effort not in efforts or requirements.effort not in (None, effort):
                raise PermissionError("effort_unsupported")
            if effort == "ultra" and (
                not requirements.high_effort_authorized
                or task.task_class not in {TaskClass.ARCHITECTURE, TaskClass.HARD_BUILD}
            ):
                raise PermissionError("ultra_mission_justification_required")
            reasons = admit(
                "codex_app_server_shadow",
                model,
                task,
                obs,
                obs.key,
                self.clock(),
                replace(requirements, effort=None),
            )
            if reasons:
                raise PermissionError(",".join(reasons))
            binding = NativeBinding(
                task.task_id, sha256(text.encode()).hexdigest(), obs.key, model, effort
            )
            if self._binding is not None:
                # Changed input/config/account/model is a fresh review boundary.
                previous = replace(self._binding, thread_id=None)
                if previous != binding:
                    raise PermissionError("native_binding_changed")
                binding = self._binding
            await self.authorize(binding, "resume" if binding.thread_id else "start")
            params = {
                "model": model,
                "modelProvider": "openai",
                "cwd": str(self.cwd),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "config": {"model_reasoning_effort": effort},
            }
            if binding.thread_id:
                started = await self.rpc.call(
                    "thread/resume", {**params, "threadId": binding.thread_id}
                )
            else:
                started = await self.rpc.call(
                    "thread/start",
                    {
                        **params,
                        "ephemeral": False,
                        "environments": [],
                        "dynamicTools": [],
                        "allowProviderModelFallback": False,
                    },
                )
            sandbox = started.get("sandbox", {})
            if (
                started.get("cwd") != str(self.cwd)
                or started.get("model") != model
                or started.get("modelProvider") != "openai"
                or started.get("approvalPolicy") != "never"
                or started.get("reasoningEffort") != effort
                or sandbox.get("type") != "readOnly"
                # The pinned native schema defaults an omitted flag to false.
                or sandbox.get("networkAccess", False) is not False
            ):
                raise PermissionError("native_effective_binding_mismatch")
            binding = replace(binding, thread_id=started["thread"]["id"])
            if self._binding and binding.thread_id != self._binding.thread_id:
                raise PermissionError("native_thread_changed")
            self._binding = binding
            # Re-read native config/account immediately before spending a turn.
            current, _ = await self.discover(model)
            if current.key != binding.discovery_key or self._cancelled:
                raise PermissionError("native_binding_changed")
            # The authoritative fence follows discovery, directly before spend.
            await self.authorize(binding, "turn")
            if self._cancelled:
                raise PermissionError("mission_cancelled")
            turn = await self.rpc.call(
                "turn/start",
                {
                    "threadId": binding.thread_id,
                    "input": [{"type": "text", "text": text}],
                    "effort": effort,
                    "environments": [],
                },
            )
            self._active_turn = turn["turn"]["id"]
            self.turn_started.set()
            if self._cancelled:
                await self.cancel()
                raise PermissionError("mission_cancelled")
            try:
                result = await self._collect(binding, timeout)
                await self.authorize(binding, "complete")
                if self._cancelled:
                    return replace(result, status="interrupted", local_interrupted=True)
                return result
            except BaseException:
                await self.cancel()
                raise
            finally:
                self._active_turn = None
                self.turn_started.clear()
        except BaseException:
            await self.cancel()
            raise
        finally:
            self._busy = False

    async def _collect(self, binding: NativeBinding, timeout: float) -> NativeResult:
        text, usage = [], {}
        async with asyncio.timeout(timeout):
            while True:
                event = await self.rpc.next_notification(timeout=timeout)
                p = event["params"]
                if p.get("threadId") != binding.thread_id:
                    continue
                event_turn = p.get("turnId") or p.get("turn", {}).get("id")
                if event_turn != self._active_turn:
                    continue
                if (
                    event["method"] == "item/completed"
                    and p.get("item", {}).get("type") == "agentMessage"
                    and p["item"].get("phase") == "final_answer"
                ):
                    text.append(p["item"].get("text", ""))
                    if sum(len(x.encode()) for x in text) > 65536:
                        raise ValueError("selected_response_limit")
                elif event["method"] == "thread/tokenUsage/updated":
                    usage = p.get("tokenUsage", {})
                elif event["method"] == "turn/completed":
                    status = p["turn"]["status"]
                    if status == "completed" and not "".join(text).strip():
                        status = "incomplete"
                    return NativeResult(
                        binding, self._active_turn or "", status, "\n".join(text), usage
                    )

    async def cancel(self) -> None:
        # Revocation is the broker's job. No authorization callback can block
        # local stopping; an interrupt acknowledgement is not remote effect proof.
        self._cancelled = True
        async with self._cancel_lock:
            if self.cancellation.get("local_process_group_stopped"):
                return
            if not self.cancellation:
                self.cancellation = {
                    "thread_id": self._binding.thread_id if self._binding else None,
                    "turn_id": self._active_turn,
                    "interrupt_acknowledged": False,
                    "remote_cancelled": None,
                }
            try:
                if self._binding and self._active_turn:
                    await self.rpc.call(
                        "turn/interrupt",
                        {
                            "threadId": self._binding.thread_id,
                            "turnId": self._active_turn,
                        },
                        timeout=5,
                    )
                    self.cancellation["interrupt_acknowledged"] = True
            except AppServerError as error:
                self.cancellation["interrupt_error_code"] = error.code
            finally:
                await self.rpc.close()
                self.cancellation["local_process_group_stopped"] = (
                    self.rpc.local_stopped
                )


def validate_shadow_config(config: dict[str, Any]) -> None:
    if (
        config.get("model_provider") not in (None, "openai")
        or config.get("sandbox_mode") != "read-only"
    ):
        raise PermissionError("shadow_provider_or_sandbox")
    if (
        config.get("approval_policy") != "never"
        or config.get("web_search") != "disabled"
    ):
        raise PermissionError("shadow_approval_or_web")
    features = config.get("features", {})
    if any(features.get(name) is not False for name in DISABLED_FEATURES):
        raise PermissionError("shadow_tools_not_disabled")
    if any(
        config.get(name)
        for name in (
            "mcp_servers",
            "model_providers",
            "tools",
            "hooks",
            "notify",
            "plugins",
            "apps",
            "permissions",
            "skills",
        )
    ):
        raise PermissionError("shadow_external_surface")
    env = config.get("shell_environment_policy", {})
    if env.get("inherit") != "none" or env.get("set") != {}:
        raise PermissionError("shadow_environment_not_empty")
