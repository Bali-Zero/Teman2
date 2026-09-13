"""Native shadow admission, continuity and late-result boundaries, no network."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.conductor.adapter_contracts import Requirements
from scripts.conductor.app_server_rpc import AppServerError
from scripts.conductor.codex_shadow import CodexShadow, validate_shadow_config
from scripts.conductor.codex_shadow_launch import DISABLED_FEATURES
from scripts.conductor.contracts import TaskClass, TaskIntent

MODEL = "gpt-6-astra"
CONFIG = {
    "model_provider": "openai",
    "sandbox_mode": "read-only",
    "approval_policy": "never",
    "web_search": "disabled",
    "shell_environment_policy": {"inherit": "none", "set": {}},
    "features": {name: False for name in DISABLED_FEATURES},
}
TASK = TaskIntent(
    "synthetic-shadow",
    TaskClass.READ_ONLY,
    1,
    False,
    (),
    frozenset(),
    "shadow",
    100,
    frozenset({"text"}),
    frozenset(),
    False,
)


class FakeRPC:
    def __init__(self) -> None:
        self.calls = []
        self.events = asyncio.Queue()
        self.config = deepcopy(CONFIG)
        self.account = {
            "type": "chatgpt",
            "email": "synthetic@example.invalid",
            "planType": "pro",
        }
        self.runtime_model = MODEL
        self.local_stopped = False
        self.emit_reply = True
        self.turn_started = asyncio.Event()
        self.credential_fingerprint = "synthetic-credential-one"

    async def call(self, method: str, params: dict, **kwargs: object) -> dict:
        self.calls.append((method, params))
        if method == "config/read":
            return {"config": deepcopy(self.config)}
        if method == "account/read":
            return {"account": deepcopy(self.account)}
        if method == "model/list":
            return {
                "data": [
                    {
                        "model": MODEL,
                        "supportedReasoningEfforts": [
                            {"reasoningEffort": x} for x in ("medium", "ultra")
                        ],
                    }
                ]
            }
        if method in {"thread/start", "thread/resume"}:
            return {
                "thread": {"id": "thread-1"},
                "cwd": params["cwd"],
                "model": self.runtime_model,
                "modelProvider": "openai",
                "approvalPolicy": "never",
                "reasoningEffort": params.get("config", {}).get(
                    "model_reasoning_effort"
                ),
                "sandbox": {"type": "readOnly", "networkAccess": False},
            }
        if method == "turn/start":
            self.turn_started.set()
            if self.emit_reply:
                for method, payload in [
                    (
                        "item/completed",
                        {
                            "item": {
                                "type": "agentMessage",
                                "text": "SYNTHETIC_OK",
                                "phase": "final_answer",
                            }
                        },
                    ),
                    (
                        "thread/tokenUsage/updated",
                        {
                            "tokenUsage": {
                                "total": {"outputTokens": 5, "reasoningOutputTokens": 2}
                            }
                        },
                    ),
                    (
                        "turn/completed",
                        {"turn": {"id": "turn-1", "status": "completed"}},
                    ),
                ]:
                    self.events.put_nowait(
                        {
                            "method": method,
                            "params": {
                                "threadId": "thread-1",
                                "turnId": "turn-1",
                                **payload,
                            },
                        }
                    )
            return {"turn": {"id": "turn-1"}}
        return {}

    async def next_notification(self, **kwargs: object) -> dict:
        return await self.events.get()

    async def close(self) -> None:
        self.local_stopped = True


def make(rpc: FakeRPC, calls: list, *, deny: str = "") -> CodexShadow:
    async def authorize(binding, operation):
        calls.append((binding, operation))
        if operation == deny:
            raise PermissionError("grant_revoked")

    return CodexShadow(
        rpc,
        cwd=Path("/tmp"),
        runtime_version="0.147.0",
        host="synthetic-host",
        authorize=authorize,
        auth_fingerprint=lambda: rpc.credential_fingerprint,
        clock=lambda: datetime(2026, 9, 6, tzinfo=timezone.utc),
    )


def run(coro):
    return asyncio.run(coro)


def test_native_continuity_reauthorizes_and_reuses_catalog_only() -> None:
    async def scenario():
        rpc, checks = FakeRPC(), []
        adapter = make(rpc, checks)
        first = await adapter.invoke(TASK, "synthetic", model=MODEL, effort="medium")
        second = await adapter.invoke(TASK, "synthetic", model=MODEL, effort="medium")
        assert first.binding == second.binding
        assert [x[1] for x in checks] == [
            "start",
            "turn",
            "complete",
            "resume",
            "turn",
            "complete",
        ]
        assert sum(m == "model/list" for m, _ in rpc.calls) == 1
        assert sum(m == "config/read" for m, _ in rpc.calls) == 4
        checkpoint = second.checkpoint()
        assert checkpoint["native_usage"]["total"]["outputTokens"] == 5
        assert checkpoint["inference_model"] is None
        assert checkpoint["identity_evidence"] == "request_observed"
        assert checkpoint["model_evidence_source"] == "native_thread_configuration"
        assert "SYNTHETIC_OK" not in str(checkpoint)
        start = next(p for m, p in rpc.calls if m == "thread/start")
        assert (
            start["environments"] == [] and start["allowProviderModelFallback"] is False
        )

    run(scenario())


@pytest.mark.parametrize(
    "phases", [("commentary",), (None,), ("commentary", "final_answer")]
)
def test_only_final_phase_counts_as_complete_answer(
    phases: tuple[str | None, ...],
) -> None:
    class PhasedRPC(FakeRPC):
        async def call(self, method: str, params: dict, **kwargs: object) -> dict:
            result = await super().call(method, params, **kwargs)
            if method == "turn/start":
                while not self.events.empty():
                    self.events.get_nowait()
                for phase in phases:
                    self.events.put_nowait(
                        {
                            "method": "item/completed",
                            "params": {
                                "threadId": "thread-1",
                                "turnId": "turn-1",
                                "item": {
                                    "type": "agentMessage",
                                    "text": str(phase),
                                    "phase": phase,
                                },
                            },
                        }
                    )
                self.events.put_nowait(
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "thread-1",
                            "turn": {"id": "turn-1", "status": "completed"},
                        },
                    }
                )
            return result

    async def scenario() -> None:
        result = await make(PhasedRPC(), []).invoke(
            TASK, "synthetic", model=MODEL, effort="medium"
        )
        assert result.status == (
            "completed" if "final_answer" in phases else "incomplete"
        )
        assert result.text == ("final_answer" if "final_answer" in phases else "")

    run(scenario())


@pytest.mark.parametrize("network", [True, None, 0, ""])
def test_only_false_network_flag_admits_read_only_turn(network: object) -> None:
    class NetworkRPC(FakeRPC):
        async def call(self, method: str, params: dict, **kwargs: object) -> dict:
            result = await super().call(method, params, **kwargs)
            if method == "thread/start":
                result["sandbox"]["networkAccess"] = network
            return result

    async def scenario() -> None:
        rpc = NetworkRPC()
        with pytest.raises(PermissionError, match="native_effective_binding_mismatch"):
            await make(rpc, []).invoke(TASK, "synthetic", model=MODEL, effort="medium")
        assert not any(m == "turn/start" for m, _ in rpc.calls)

    run(scenario())


@pytest.mark.parametrize("operation", ["start", "turn", "complete"])
def test_revoked_grant_blocks_native_start_or_acceptance(operation: str) -> None:
    async def scenario():
        rpc = FakeRPC()
        with pytest.raises(PermissionError, match="grant_revoked"):
            await make(rpc, [], deny=operation).invoke(
                TASK, "synthetic", model=MODEL, effort="medium"
            )
        assert rpc.local_stopped
        if operation != "complete":
            assert not any(m == "turn/start" for m, _ in rpc.calls)

    run(scenario())


@pytest.mark.parametrize("change", ["mission", "input", "account", "config", "model"])
def test_resume_never_reuses_a_changed_binding(change: str) -> None:
    async def scenario():
        rpc = FakeRPC()
        adapter = make(rpc, [])
        await adapter.invoke(TASK, "synthetic", model=MODEL, effort="medium")
        task, text = TASK, "synthetic"
        if change == "mission":
            task = replace(task, task_id="unrelated")
        if change == "input":
            text = "changed"
        if change == "account":
            rpc.account["email"] = "rotated@example.invalid"
        if change == "config":
            rpc.config["developer_instructions"] = "changed"
        if change == "model":
            rpc.runtime_model = "unexpected"
        with pytest.raises(PermissionError, match="binding"):
            await adapter.invoke(task, text, model=MODEL, effort="medium")
        assert sum(m == "turn/start" for m, _ in rpc.calls) == 1

    run(scenario())


@pytest.mark.parametrize(
    "requirement",
    [
        Requirements(exact_model=True),
        Requirements(output_cap=10),
        Requirements(total_cap=100),
        Requirements(workers=1),
        Requirements(operation="effects"),
    ],
)
def test_unproved_requirements_do_not_spend_a_turn(requirement: Requirements) -> None:
    async def scenario():
        rpc = FakeRPC()
        with pytest.raises(PermissionError):
            await make(rpc, []).invoke(
                TASK,
                "synthetic",
                model=MODEL,
                effort="medium",
                requirements=requirement,
            )
        assert not any(m == "thread/start" for m, _ in rpc.calls)

    run(scenario())


def test_timeout_interrupts_then_stops_without_remote_cancel_claim() -> None:
    async def scenario():
        rpc = FakeRPC()
        rpc.emit_reply = False
        adapter = make(rpc, [])
        with pytest.raises(TimeoutError):
            await adapter.invoke(
                TASK, "synthetic", model=MODEL, effort="medium", timeout=0.01
            )
        assert rpc.local_stopped and any(m == "turn/interrupt" for m, _ in rpc.calls)
        with pytest.raises(PermissionError, match="cancelled"):
            await adapter.invoke(TASK, "synthetic", model=MODEL, effort="medium")

    run(scenario())


def test_interrupt_rejection_still_stops_and_records_only_local_error_code() -> None:
    class RejectInterruptRPC(FakeRPC):
        async def call(self, method: str, params: dict, **kwargs: object) -> dict:
            if method == "turn/interrupt":
                self.calls.append((method, params))
                raise AppServerError("rpc_error")
            return await super().call(method, params, **kwargs)

    async def scenario() -> None:
        rpc = RejectInterruptRPC()
        rpc.emit_reply = False
        adapter = make(rpc, [])
        with pytest.raises(TimeoutError):
            await adapter.invoke(
                TASK, "synthetic", model=MODEL, effort="medium", timeout=0.01
            )
        await asyncio.gather(adapter.cancel(), adapter.cancel())
        assert sum(m == "turn/interrupt" for m, _ in rpc.calls) == 1
        assert adapter.cancellation["interrupt_acknowledged"] is False
        assert adapter.cancellation["interrupt_error_code"] == "rpc_error"
        assert adapter.cancellation["remote_cancelled"] is None
        assert rpc.local_stopped

    run(scenario())


def test_native_working_directory_drift_prevents_turn() -> None:
    class DriftRPC(FakeRPC):
        async def call(self, method: str, params: dict, **kwargs: object) -> dict:
            result = await super().call(method, params, **kwargs)
            if method == "thread/start":
                result["cwd"] = "/unexpected-workspace"
            return result

    async def scenario() -> None:
        rpc = DriftRPC()
        with pytest.raises(PermissionError, match="native_effective_binding_mismatch"):
            await make(rpc, []).invoke(TASK, "synthetic", model=MODEL, effort="medium")
        assert not any(m == "turn/start" for m, _ in rpc.calls)
        assert rpc.local_stopped

    run(scenario())


def test_inherit_none_does_not_hide_explicit_global_values() -> None:
    config = deepcopy(CONFIG)
    config["shell_environment_policy"]["set"] = {
        "SYNTHETIC_CANARY": "synthetic-not-a-credential"
    }
    with pytest.raises(PermissionError, match="environment_not_empty"):
        validate_shadow_config(config)


def test_cancel_while_turn_start_awaits_rejects_late_rpc_and_completion() -> None:
    class LateStartRPC(FakeRPC):
        def __init__(self) -> None:
            super().__init__()
            self.waiting = asyncio.Event()
            self.release = asyncio.Event()

        async def call(self, method: str, params: dict, **kwargs: object) -> dict:
            if method == "turn/start":
                self.waiting.set()
                await self.release.wait()
            return await super().call(method, params, **kwargs)

        async def close(self) -> None:
            await super().close()
            self.release.set()

    async def scenario() -> None:
        rpc, checks = LateStartRPC(), []
        adapter = make(rpc, checks)
        task = asyncio.create_task(
            adapter.invoke(TASK, "synthetic", model=MODEL, effort="medium")
        )
        await asyncio.wait_for(rpc.waiting.wait(), 0.5)
        await adapter.cancel()
        with pytest.raises(PermissionError, match="cancelled"):
            await asyncio.wait_for(task, 0.5)
        assert rpc.local_stopped
        assert not any(operation == "complete" for _, operation in checks)
        assert not rpc.events.empty()  # The late success exists but was never accepted.
        with pytest.raises(PermissionError, match="cancelled"):
            await adapter.invoke(TASK, "synthetic", model=MODEL, effort="medium")

    run(scenario())


@pytest.mark.parametrize("blocked_method", ["thread/start", "turn/start"])
def test_native_start_rpc_timeout_stops_process(blocked_method: str) -> None:
    class TimeoutRPC(FakeRPC):
        async def call(self, method: str, params: dict, **kwargs: object) -> dict:
            if method == blocked_method:
                self.calls.append((method, params))
                raise AppServerError("rpc_timeout")
            return await super().call(method, params, **kwargs)

    async def scenario() -> None:
        rpc, checks = TimeoutRPC(), []
        with pytest.raises(AppServerError, match="rpc_timeout"):
            await make(rpc, checks).invoke(
                TASK, "synthetic", model=MODEL, effort="medium"
            )
        assert rpc.local_stopped
        assert not any(operation == "complete" for _, operation in checks)
        if blocked_method == "thread/start":
            assert not any(method == "turn/start" for method, _ in rpc.calls)

    run(scenario())


@pytest.mark.parametrize("change", ["config", "account"])
def test_discovery_change_during_start_authorization_prevents_turn(change: str) -> None:
    async def scenario() -> None:
        rpc = FakeRPC()

        async def authorize(binding: object, operation: str) -> None:
            if operation == "start":
                if change == "config":
                    rpc.config["developer_instructions"] = "changed after discovery"
                else:
                    rpc.account["email"] = "rotated@example.invalid"

        adapter = CodexShadow(
            rpc,
            cwd=Path("/tmp"),
            runtime_version="0.147.0",
            host="synthetic-host",
            authorize=authorize,
            auth_fingerprint=lambda: rpc.credential_fingerprint,
        )
        with pytest.raises(PermissionError, match="native_binding_changed"):
            await adapter.invoke(TASK, "synthetic", model=MODEL, effort="medium")
        assert rpc.local_stopped
        assert any(method == "thread/start" for method, _ in rpc.calls)
        assert not any(method == "turn/start" for method, _ in rpc.calls)

    run(scenario())


@pytest.mark.parametrize(
    "model,effort,requirements,reason",
    [
        ("gpt-not-in-catalog", "medium", Requirements(), "model_unavailable"),
        (MODEL, "max", Requirements(), "effort_unsupported"),
        (MODEL, "medium", Requirements(effort="xhigh"), "effort_unsupported"),
        (MODEL, "ultra", Requirements(), "ultra_mission_justification_required"),
        (
            MODEL,
            "ultra",
            Requirements(high_effort_authorized=True),
            "ultra_mission_justification_required",
        ),
    ],
)
def test_unsupported_model_effort_and_unjustified_ultra_never_start_thread(
    model: str,
    effort: str,
    requirements: Requirements,
    reason: str,
) -> None:
    async def scenario() -> None:
        rpc = FakeRPC()
        with pytest.raises(PermissionError, match=reason):
            await make(rpc, []).invoke(
                TASK, "synthetic", model=model, effort=effort, requirements=requirements
            )
        assert rpc.local_stopped
        assert not any(
            method in {"thread/start", "turn/start"} for method, _ in rpc.calls
        )

    run(scenario())


def test_supported_ultra_requires_both_explicit_admission_and_justified_class() -> None:
    async def scenario() -> None:
        rpc = FakeRPC()
        task = replace(TASK, task_class=TaskClass.ARCHITECTURE)
        result = await make(rpc, []).invoke(
            task,
            "synthetic",
            model=MODEL,
            effort="ultra",
            requirements=Requirements(high_effort_authorized=True),
        )
        assert result.status == "completed"
        assert (
            next(params for method, params in rpc.calls if method == "turn/start")[
                "effort"
            ]
            == "ultra"
        )

    run(scenario())


def test_catalog_token_capacity_cannot_prove_exact_model_or_total_spend_cap() -> None:
    class AdvertisedCapacityRPC(FakeRPC):
        async def call(self, method: str, params: dict, **kwargs: object) -> dict:
            result = await super().call(method, params, **kwargs)
            if method == "model/list":
                result["data"][0].update(
                    {"contextWindow": 1000000, "maxOutputTokens": 1000}
                )
            return result

    async def scenario() -> None:
        rpc = AdvertisedCapacityRPC()
        with pytest.raises(PermissionError) as error:
            await make(rpc, []).invoke(
                TASK,
                "synthetic",
                model=MODEL,
                effort="medium",
                requirements=Requirements(exact_model=True, total_cap=1000000),
            )
        assert "actual_model_unproven" in str(error.value)
        assert "total_tokens_hard_cap_unproven" in str(error.value)
        assert rpc.local_stopped
        assert not any(method == "thread/start" for method, _ in rpc.calls)

    run(scenario())


def test_catalog_cursor_cycle_fails_before_native_launch() -> None:
    class CyclingCatalogRPC(FakeRPC):
        async def call(self, method: str, params: dict, **kwargs: object) -> dict:
            result = await super().call(method, params, **kwargs)
            if method == "model/list":
                result["nextCursor"] = "repeated-cursor"
            return result

    async def scenario() -> None:
        rpc = CyclingCatalogRPC()
        with pytest.raises(PermissionError, match="catalog_cursor_cycle"):
            await make(rpc, []).invoke(TASK, "synthetic", model=MODEL, effort="medium")
        assert sum(method == "model/list" for method, _ in rpc.calls) == 2
        assert rpc.local_stopped
        assert not any(method == "thread/start" for method, _ in rpc.calls)

    run(scenario())


def test_effective_effort_mismatch_prevents_turn_start() -> None:
    class WrongEffortRPC(FakeRPC):
        async def call(self, method: str, params: dict, **kwargs: object) -> dict:
            result = await super().call(method, params, **kwargs)
            if method in {"thread/start", "thread/resume"}:
                result["reasoningEffort"] = "max"
            return result

    async def scenario() -> None:
        rpc = WrongEffortRPC()
        with pytest.raises(PermissionError, match="native_effective_binding_mismatch"):
            await make(rpc, []).invoke(TASK, "synthetic", model=MODEL, effort="medium")
        assert rpc.local_stopped
        assert not any(method == "turn/start" for method, _ in rpc.calls)

    run(scenario())


def test_maximum_mission_timeout_respects_transport_wait_bound() -> None:
    class BoundedWaitRPC(FakeRPC):
        async def next_notification(self, **kwargs: object) -> dict:
            if not 0 < kwargs.get("timeout", 0) <= 60:
                raise AppServerError("invalid_timeout")
            return await super().next_notification(**kwargs)

    async def scenario() -> None:
        rpc = BoundedWaitRPC()
        result = await make(rpc, []).invoke(
            TASK, "synthetic", model=MODEL, effort="medium", timeout=60
        )
        assert result.status == "completed"

    run(scenario())


def test_out_of_range_mission_timeout_rejects_before_discovery() -> None:
    async def scenario() -> None:
        rpc = FakeRPC()
        with pytest.raises(ValueError, match="bounded_input_and_timeout_required"):
            await make(rpc, []).invoke(
                TASK, "synthetic", model=MODEL, effort="medium", timeout=120
            )
        assert not rpc.calls

    run(scenario())


def test_same_account_credential_rotation_invalidates_binding_and_catalog() -> None:
    async def scenario() -> None:
        rpc = FakeRPC()
        adapter = make(rpc, [])
        await adapter.invoke(TASK, "synthetic", model=MODEL, effort="medium")
        original_account = deepcopy(rpc.account)
        rpc.credential_fingerprint = "synthetic-credential-two"
        with pytest.raises(PermissionError, match="native_binding_changed"):
            await adapter.invoke(TASK, "synthetic", model=MODEL, effort="medium")
        assert rpc.account == original_account
        assert sum(method == "model/list" for method, _ in rpc.calls) == 2
        assert sum(method == "turn/start" for method, _ in rpc.calls) == 1
        assert rpc.local_stopped

    run(scenario())
