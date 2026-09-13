"""No network: real native adapter flow against a closed broker transport."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from scripts.conductor.consul_broker_client import (
    ConsulBrokerClient,
    BrokerTransportError,
)
from scripts.conductor.consul_native import invoke_canary
from scripts.tests.test_codex_shadow import FakeRPC, MODEL, make


class Exchange:
    def __init__(self) -> None:
        self.calls = []
        self.revoked = False
        self.started = False
        self.completed = False

    async def __call__(self, request):
        self.calls.append(request)
        verb = request["verb"]
        if verb == "cancel":
            self.revoked = True
            return {"status": "revoked", "remote_cancelled": None}
        if self.revoked:
            raise PermissionError("revoked")
        if verb == "admit":
            return {
                "lease": {
                    "run_id": request["binding"]["mission_id"],
                    "owner_id": "service",
                    "generation": 1,
                }
            }
        if verb == "check":
            if request["phase"] == "turn":
                if self.started:
                    raise PermissionError("needs_reconcile")
                self.started = True
            if request["phase"] == "complete":
                self.completed = True
            return {"status": "authorized"}
        if verb == "checkpoint":
            assert self.started and self.completed
            return {
                "status": "recorded"
                if request["result"]["status"] == "completed"
                else "failed",
                "receipt_hash": "a" * 64,
            }
        raise AssertionError(verb)


class CanaryRPC(FakeRPC):
    reply_text = "DUAL_CONSUL_NATIVE_OK"

    async def next_notification(self, **kwargs):
        event = await super().next_notification(**kwargs)
        if event["method"] == "item/completed":
            event["params"]["item"]["text"] = self.reply_text
        return event


def bound(exchange):
    rpc = CanaryRPC()
    adapter = make(rpc, [])
    client = ConsulBrokerClient(str(uuid4()), exchange=exchange)
    adapter.authorize = client.authorize
    return rpc, adapter, client


def test_consumer_uses_admission_fence_completion_and_checkpoint_without_text():
    async def scenario():
        exchange = Exchange()
        rpc, adapter, client = bound(exchange)
        result = await invoke_canary(
            adapter, client, "one-mission", model=MODEL, effort="medium"
        )
        assert [x["verb"] for x in exchange.calls] == [
            "admit",
            "check",
            "check",
            "checkpoint",
        ]
        assert [x.get("phase") for x in exchange.calls] == [
            None,
            "turn",
            "complete",
            None,
        ]
        assert result["broker"]["status"] == "recorded"
        assert result["canary_passed"] is True
        assert "SYNTHETIC_OK" not in str(exchange.calls) + str(result)
        assert result["native"]["remote_cancelled"] is None
        assert sum(method == "turn/start" for method, _ in rpc.calls) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("text", ["wrong", "", "DUAL_CONSUL_NATIVE_OK plus extra"])
def test_canary_mismatch_is_known_failure_without_replay_or_raw_text(text):
    async def scenario():
        exchange = Exchange()
        rpc, adapter, client = bound(exchange)
        rpc.reply_text = text
        result = await invoke_canary(
            adapter, client, "one-mission", model=MODEL, effort="medium"
        )
        assert result["canary_passed"] is False
        assert result["native"]["status"] == ("incomplete" if not text else "failed")
        assert result["broker"]["status"] == "failed"
        assert not exchange.revoked
        assert "text" not in exchange.calls[-1]["result"]
        assert sum(m == "turn/start" for m, _ in rpc.calls) == 1

    asyncio.run(scenario())


def test_late_authorization_after_cancel_never_starts_turn_while_remote_revocation_stalls():
    async def scenario():
        exchange = Exchange()
        authorized, cancel_pending = asyncio.Event(), asyncio.Event()
        release_auth, release_cancel = asyncio.Event(), asyncio.Event()

        async def delayed(request):
            if request.get("phase") == "turn":
                result = await exchange(request)
                authorized.set()
                await release_auth.wait()
                return result
            if request["verb"] == "cancel":
                cancel_pending.set()
                await release_cancel.wait()
            return await exchange(request)

        rpc, adapter, client = bound(delayed)
        task = asyncio.create_task(
            invoke_canary(adapter, client, "one-mission", model=MODEL, effort="medium")
        )
        await authorized.wait()
        cancel = asyncio.create_task(client.cancel(adapter))
        await cancel_pending.wait()
        assert rpc.local_stopped
        release_auth.set()
        await asyncio.sleep(0)
        assert not any(m == "turn/start" for m, _ in rpc.calls)
        release_cancel.set()
        await cancel
        with pytest.raises(PermissionError, match="mission_cancelled"):
            await task
        assert exchange.revoked

    asyncio.run(scenario())


@pytest.mark.parametrize("boundary", ["turn", "complete", "checkpoint"])
def test_revocation_refuses_spend_or_late_checkpoint_and_stops_native(boundary):
    async def scenario():
        exchange = Exchange()

        async def revoke(request):
            if request.get("phase") == boundary or request["verb"] == boundary:
                exchange.revoked = True
            return await exchange(request)

        rpc, adapter, client = bound(revoke)
        with pytest.raises(PermissionError, match="revoked"):
            await invoke_canary(
                adapter, client, "one-mission", model=MODEL, effort="medium"
            )
        assert rpc.local_stopped
        assert client.cancellation["revocation_confirmed"]
        assert client.cancellation["native"]["remote_cancelled"] is None
        assert sum(m == "turn/start" for m, _ in rpc.calls) == (
            0 if boundary == "turn" else 1
        )

    asyncio.run(scenario())


def test_database_outage_does_not_prevent_local_stop_or_claim_remote_cancellation():
    async def scenario():
        async def unavailable(request):
            raise BrokerTransportError("offline")

        rpc, adapter, client = bound(unavailable)
        with pytest.raises(BrokerTransportError):
            await invoke_canary(
                adapter, client, "one-mission", model=MODEL, effort="medium"
            )
        assert rpc.local_stopped
        assert client.cancellation["revocation_confirmed"] is False
        assert client.cancellation["native"]["remote_cancelled"] is None

    asyncio.run(scenario())


def test_cancellation_of_running_consumer_stops_process_and_revokes():
    async def scenario():
        exchange = Exchange()
        rpc, adapter, client = bound(exchange)
        rpc.emit_reply = False
        task = asyncio.create_task(
            invoke_canary(adapter, client, "one-mission", model=MODEL, effort="medium")
        )
        await rpc.turn_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert exchange.revoked and rpc.local_stopped

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "lease",
    [
        {},
        {"run_id": "wrong", "owner_id": "s", "generation": 1},
        {"run_id": "one-mission", "owner_id": "s", "generation": True},
    ],
)
def test_bad_admission_reply_never_spends(lease):
    async def scenario():
        rpc, adapter, client = bound(AsyncMock(return_value={"lease": lease}))
        with pytest.raises(BrokerTransportError, match="invalid_lease"):
            await invoke_canary(
                adapter, client, "one-mission", model=MODEL, effort="medium"
            )
        assert not any(m == "turn/start" for m, _ in rpc.calls)

    asyncio.run(scenario())


def test_authoritative_turn_check_occurs_after_last_discovery():
    async def scenario():
        exchange = Exchange()
        rpc, adapter, client = bound(exchange)
        original = rpc.call

        async def call(method, params, **kwargs):
            if method == "turn/start":
                assert rpc.calls[-1][0] == "account/read"
                assert exchange.calls[-1].get("phase") == "turn"
            return await original(method, params, **kwargs)

        rpc.call = call
        await invoke_canary(
            adapter, client, "one-mission", model=MODEL, effort="medium"
        )

    asyncio.run(scenario())


def test_revocation_during_final_discovery_is_observed_before_turn():
    async def scenario():
        exchange = Exchange()
        rpc, adapter, client = bound(exchange)
        original = rpc.call

        async def call(method, params, **kwargs):
            result = await original(method, params, **kwargs)
            if method == "account/read" and any(
                m == "thread/start" for m, _ in rpc.calls
            ):
                exchange.revoked = True
            return result

        rpc.call = call
        with pytest.raises(PermissionError, match="revoked"):
            await invoke_canary(
                adapter, client, "one-mission", model=MODEL, effort="medium"
            )
        assert not any(m == "turn/start" for m, _ in rpc.calls)

    asyncio.run(scenario())
