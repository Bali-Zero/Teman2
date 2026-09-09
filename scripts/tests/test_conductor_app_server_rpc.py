"""Native transport contract tests using isolated fake executables, never a model."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal
import sys

import pytest

from scripts.conductor.app_server_rpc import AppServerError, AppServerRPC, _notification
from scripts.conductor.native_canary_contract import RPC_TIMEOUT_SECONDS


FAKE_SERVER = r"""
import json, os, signal, subprocess, sys

def emit(value):
    sys.stdout.write(json.dumps(value) + "\n")
    sys.stdout.flush()

def notice(method, params):
    emit({"method": method, "params": params})

initialized = False
late_id = None
for line in sys.stdin:
    msg = json.loads(line)
    method = msg.get("method")
    rid = msg.get("id")
    if method == "initialize":
        assert msg["params"]["capabilities"]["experimentalApi"] == (os.environ.get("EXPERIMENTAL") == "1")
        emit({"id": rid, "result": {"userAgent": "fake/1", "platformFamily": "unix",
             "platformOs": "test", "codexHome": "EXCLUDED_PATH"}})
    elif method == "initialized":
        initialized = True
    elif not initialized:
        sys.exit(2)
    elif method == "config/read":
        emit({"id": rid, "result": {"config": {"test": "selected-in-memory"}}})
    elif method == "events":
        notice("item/reasoning/textDelta", {"delta": "EXCLUDED_REASONING"})
        notice("thread/started", {"thread": {"id": "thread-1", "preview": "EXCLUDED_PREVIEW"}})
        notice("turn/started", {"threadId": "thread-1", "turn": {"id": "turn-1", "status": "inProgress", "items": ["EXCLUDED"]}})
        notice("item/completed", {"threadId": "thread-1", "turnId": "turn-1", "item": {"type": "commandExecution", "output": "EXCLUDED_TOOL"}})
        notice("item/completed", {"threadId": "thread-1", "turnId": "turn-1", "item": {"id": "message-1", "type": "agentMessage", "text": "Synthetic answer", "phase": "final_answer", "memoryCitation": "EXCLUDED"}})
        counters = {"inputTokens": 10, "cachedInputTokens": 5, "cacheWriteInputTokens": 2, "outputTokens": 20, "reasoningOutputTokens": 8, "totalTokens": 30, "raw": "EXCLUDED"}
        notice("thread/tokenUsage/updated", {"threadId": "thread-1", "turnId": "turn-1", "tokenUsage": {"last": counters, "total": counters, "modelContextWindow": 1000}})
        notice("turn/completed", {"threadId": "thread-1", "turn": {"id": "turn-1", "status": "completed", "items": ["EXCLUDED"], "error": {"message": "EXCLUDED"}}})
        emit({"id": rid, "result": {"ok": True}})
    elif method == "approvals":
        replies = []
        for number, name in enumerate(["item/commandExecution/requestApproval", "item/fileChange/requestApproval", "item/permissions/requestApproval", "execCommandApproval", "applyPatchApproval", "item/tool/call"]):
            emit({"id": "server-" + str(number), "method": name, "params": {"secret": "EXCLUDED"}})
            replies.append(json.loads(sys.stdin.readline()))
        emit({"id": rid, "result": {"replies": replies}})
    elif method == "late":
        late_id = rid
    elif method == "afterLate":
        emit({"id": late_id, "result": {"wrong": True}})
        emit({"id": rid, "result": {"right": True}})
    elif method == "error":
        sys.stderr.write("EXCLUDED_SECRET_STDERR\n")
        sys.stderr.flush()
        emit({"id": rid, "error": {"code": 42, "message": "EXCLUDED_PROVIDER_SECRET"}})
    elif method == "toolActivity":
        notice(msg["params"]["event"], {"threadId": "thread-1", "turnId": "turn-1",
            "item": {"id": "tool-1", "type": msg["params"]["type"],
                     "arguments": "EXCLUDED_TOOL_ARGUMENTS", "output": "EXCLUDED_TOOL_OUTPUT"}})
        emit({"id": rid, "result": {"ok": True}})
    elif method == "safeActivity":
        for kind in ("userMessage", "reasoning", "contextCompaction", "agentMessage"):
            for event in ("item/started", "item/completed"):
                notice(event, {"threadId": "thread-1", "turnId": "turn-1", "item": {
                    "id": kind, "type": kind,
                    "text": "Synthetic answer" if kind == "agentMessage" else "EXCLUDED_REASONING",
                    "reasoning": "EXCLUDED_REASONING"}})
        emit({"id": rid, "result": {"ok": True}})
    elif method == "unknownUsage":
        counters = {"inputTokens": 4, "outputTokens": 3, "reasoningOutputTokens": 2,
                    "cacheWriteInputTokens": 1, "totalTokens": 7,
                    "futureTokens": "EXCLUDED_UNKNOWN_VALUE"}
        notice("thread/tokenUsage/updated", {"threadId": "thread-1", "turnId": "turn-1",
            "tokenUsage": {"last": counters, "total": counters,
                           "futureRoot": {"private": "EXCLUDED_UNKNOWN_VALUE"}}})
        notice("item/completed", {"threadId": "thread-1", "turnId": "turn-1",
            "item": {"id": "reply", "type": "agentMessage", "phase": "final_answer", "text": "Synthetic answer"}})
        notice("turn/completed", {"threadId": "thread-1", "turn": {"id": "turn-1", "status": "completed"}})
        emit({"id": rid, "result": {"ok": True}})
    elif method == "eof":
        sys.exit(0)
    elif method == "oversize":
        sys.stdout.write("x" * 8192 + "\n")
        sys.stdout.flush()
    elif method == "overflow":
        for i in range(20):
            notice("thread/started", {"thread": {"id": str(i)}})
    elif method == "badframe":
        sys.stdout.write("NOT_JSON_SECRET\n")
        sys.stdout.flush()
    elif method == "spawn":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        child = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        emit({"id": rid, "result": {"child": child.pid}})
"""


@pytest.fixture
def server(tmp_path: Path) -> Path:
    script = tmp_path / "fake_app_server.py"
    script.write_text(FAKE_SERVER, encoding="utf-8")
    return script


def rpc(server: Path, **kwargs: object) -> AppServerRPC:
    env = {"EXPERIMENTAL": "1"} if kwargs.get("experimental_api") else {}
    return AppServerRPC(
        [sys.executable, "-u", str(server)],
        server.parent,
        env,
        rpc_timeout=RPC_TIMEOUT_SECONDS,
        shutdown_timeout=0.2,
        **kwargs,
    )


def test_initialize_call_and_interleaved_selected_notifications(server: Path) -> None:
    async def scenario() -> None:
        client = rpc(server, experimental_api=True)
        async with client:
            assert client.initialization == {
                "userAgent": "fake/1",
                "platformFamily": "unix",
                "platformOs": "test",
            }
            assert await client.call("config/read", {}) == {
                "config": {"test": "selected-in-memory"}
            }
            assert await client.call("events", {}) == {"ok": True}
            events = [await client.next_notification() for _ in range(5)]
            assert [event["method"] for event in events] == [
                "thread/started",
                "turn/started",
                "item/completed",
                "thread/tokenUsage/updated",
                "turn/completed",
            ]
            assert events[1]["params"]["turn"] == {
                "id": "turn-1",
                "status": "inProgress",
            }
            assert events[2]["params"]["turnId"] == "turn-1"
            assert events[3]["params"]["tokenUsage"]["total"]["totalTokens"] == 30
            assert (
                events[3]["params"]["tokenUsage"]["total"]["reasoningOutputTokens"] == 8
            )
            assert "EXCLUDED" not in json.dumps(events)
            with pytest.raises(AppServerError, match="notification_timeout"):
                await client.next_notification(timeout=0.01)
        assert client.local_stopped
        await client.close()
        assert client.local_stopped

    asyncio.run(scenario())


def test_server_approvals_never_grant_permissions(server: Path) -> None:
    async def scenario() -> None:
        async with rpc(server) as client:
            replies = (await client.call("approvals", {}))["replies"]
            assert [reply.get("result") for reply in replies[:5]] == [
                {"decision": "decline"},
                {"decision": "decline"},
                {"permissions": {}, "scope": "turn"},
                {"decision": "abort"},
                {"decision": "abort"},
            ]
            assert replies[5]["error"]["code"] == -32601
            assert "EXCLUDED" not in json.dumps(replies)

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel", [False, True])
def test_late_response_cannot_satisfy_a_new_call(server: Path, cancel: bool) -> None:
    async def scenario() -> None:
        async with rpc(server) as client:
            if cancel:
                task = asyncio.create_task(client.call("late", {}))
                await asyncio.sleep(0.02)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                with pytest.raises(AppServerError, match="rpc_timeout"):
                    await client.call("late", {}, timeout=0.02)
            assert not client.local_stopped
            assert await client.call("afterLate", {}) == {"right": True}

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "method,code",
    [
        ("eof", "eof"),
        ("oversize", "frame_limit"),
        ("overflow", "notification_overflow"),
        ("badframe", "protocol_error"),
    ],
)
def test_eof_and_capacity_fail_closed(server: Path, method: str, code: str) -> None:
    async def scenario() -> None:
        client = rpc(server, queue_limit=1, frame_limit=2048)
        async with client:
            with pytest.raises(AppServerError) as error:
                await client.call(method, {})
            assert error.value.code == code
            with pytest.raises(AppServerError):
                await client.next_notification()
        assert client.local_stopped

    asyncio.run(scenario())


def test_provider_errors_and_stderr_never_surface(
    server: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    async def scenario() -> None:
        async with rpc(server) as client:
            with pytest.raises(AppServerError) as error:
                await client.call("error", {})
            assert str(error.value) == "app_server:rpc_error"
            assert error.value.__cause__ is None

    asyncio.run(scenario())
    assert "EXCLUDED" not in str(capsys.readouterr())


def test_process_group_shutdown_reaches_descendants(server: Path) -> None:
    async def scenario() -> None:
        client = rpc(server)
        async with client:
            child = (await client.call("spawn", {}))["child"]
            assert os.getpgid(child) == client.pid
        assert client.local_stopped
        with pytest.raises(ProcessLookupError):
            os.kill(child, 0)

    asyncio.run(scenario())


def test_cancel_context_stops_local_process(server: Path) -> None:
    async def scenario() -> None:
        client = rpc(server)
        started = asyncio.Event()

        async def session() -> None:
            async with client:
                started.set()
                await client.call("late", {})

        task = asyncio.create_task(session())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert client.local_stopped

    asyncio.run(scenario())


@pytest.mark.parametrize("denied_signal", [signal.SIGTERM, 0])
def test_transient_signal_denial_requires_later_confirmed_group_exit(
    server: Path, monkeypatch: pytest.MonkeyPatch, denied_signal: int
) -> None:
    async def scenario() -> None:
        client = rpc(server)
        await client.__aenter__()
        original = os.killpg
        denied = False

        def transient(pgid: int, sig: int) -> None:
            nonlocal denied
            if pgid == client.pid and sig == denied_signal and not denied:
                denied = True
                raise PermissionError("transient group permission")
            original(pgid, sig)

        try:
            with monkeypatch.context() as patch:
                patch.setattr(os, "killpg", transient)
                await client.close()
            assert denied and client.local_stopped
            with pytest.raises(ProcessLookupError):
                original(client.pid, 0)
        finally:
            await client.close()

    asyncio.run(scenario())


def test_persistent_signal_denial_never_claims_a_stopped_group(
    server: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        client = rpc(server)
        await client.__aenter__()
        client._shutdown_timeout = 0.01
        original = os.killpg

        def denied(pgid: int, sig: int) -> None:
            if pgid == client.pid:
                raise PermissionError("group absence unproven")
            original(pgid, sig)

        try:
            with monkeypatch.context() as patch:
                patch.setattr(os, "killpg", denied)
                await asyncio.wait_for(client.close(), 1)
            # Closing stdin lets the actual child exit, but a leader receipt
            # alone cannot prove all its descendants or the group are gone.
            assert client._process.returncode is not None
            assert not client.local_stopped
        finally:
            await client.close()
        assert client.local_stopped

    asyncio.run(scenario())


@pytest.mark.parametrize("event", ["item/started", "item/completed"])
@pytest.mark.parametrize("kind", ["commandExecution", "collabAgentToolCall"])
def test_shadow_rejects_tool_or_delegation_activity_without_retaining_output(
    server: Path,
    event: str,
    kind: str,
) -> None:
    async def scenario() -> None:
        client = rpc(server, reject_tool_activity=True)
        async with client:
            with pytest.raises(AppServerError) as error:
                await client.call("toolActivity", {"event": event, "type": kind})
            assert str(error.value) == "app_server:tool_activity_unqualified"
            assert error.value.__cause__ is None
            with pytest.raises(AppServerError, match="tool_activity_unqualified"):
                await client.next_notification()
        assert client.local_stopped

    asyncio.run(scenario())


def test_shadow_allows_innocuous_item_types_and_retains_only_agent_text(
    server: Path,
) -> None:
    async def scenario() -> None:
        async with rpc(server, reject_tool_activity=True) as client:
            assert await client.call("safeActivity", {}) == {"ok": True}
            event = await client.next_notification()
            assert event["params"]["item"] == {
                "id": "agentMessage",
                "type": "agentMessage",
                "text": "Synthetic answer",
            }
            assert "EXCLUDED" not in json.dumps(event)
            with pytest.raises(AppServerError, match="notification_timeout"):
                await client.next_notification(timeout=0.01)

    asyncio.run(scenario())


def test_unknown_native_counters_survive_real_notifications_into_checkpoint(
    server: Path,
) -> None:
    from scripts.conductor.adapter_contracts import DiscoveryKey
    from scripts.conductor.codex_shadow import CodexShadow, NativeBinding

    async def scenario() -> None:
        async def authorize(binding: NativeBinding, phase: str) -> None:
            raise AssertionError(
                "this fixture only collects an existing synthetic turn"
            )

        async with rpc(server) as client:
            adapter = CodexShadow(
                client,
                cwd=server.parent,
                runtime_version="fake/1",
                host="synthetic",
                authorize=authorize,
                auth_fingerprint=lambda: "synthetic",
            )
            binding = NativeBinding(
                "mission",
                "a" * 64,
                DiscoveryKey("fake/1", "b" * 64, "synthetic", "c" * 64),
                "synthetic-model",
                "medium",
                "thread-1",
            )
            adapter._active_turn = "turn-1"
            await client.call("unknownUsage", {})
            checkpoint = (await adapter._collect(binding, 1)).checkpoint()
            usage = checkpoint["native_usage"]
            assert usage["total"]["totalTokens"] == 7
            assert usage["total"]["reasoningOutputTokens"] == 2
            assert usage["last"]["cacheWriteInputTokens"] == 1
            assert usage["unknownCounters"] == {
                "names": ["last.futureTokens", "root.futureRoot", "total.futureTokens"],
                "omitted": False,
            }
            assert "EXCLUDED_UNKNOWN_VALUE" not in json.dumps(checkpoint)

    asyncio.run(scenario())


@pytest.mark.parametrize("safe_count", [0, 24])
def test_unknown_counter_names_are_bounded_and_unsafe_names_are_not_retained(
    safe_count: int,
) -> None:
    unsafe = [
        "redacted@example.invalid",
        "/private/EXCLUDED",
        "EXCLUDED\nLINE",
        "x" * 65,
    ]
    counters = {name: "EXCLUDED_VALUE" for name in unsafe}
    counters.update(
        {f"future{i:02}": {"private": "EXCLUDED_VALUE"} for i in range(safe_count)}
    )
    counters["inputTokens"] = 9
    event = _notification(
        "thread/tokenUsage/updated",
        {
            "threadId": "thread-1",
            "turnId": "turn-1",
            "tokenUsage": {"last": counters, "total": {}},
        },
    )
    selected = event["params"]["tokenUsage"]
    assert selected["last"] == {"inputTokens": 9}
    assert selected["unknownCounters"] == {
        "names": [f"last.future{i:02}" for i in range(min(safe_count, 16))],
        "omitted": True,
    }
    assert "EXCLUDED" not in json.dumps(selected)
    assert "@example" not in json.dumps(selected)
