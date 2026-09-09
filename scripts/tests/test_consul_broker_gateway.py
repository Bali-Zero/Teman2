"""Closed helper protocol, bounded replies, and generic error output."""

import asyncio
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from scripts import consul_broker
from scripts.conductor import consul_broker_client as transport
from scripts.conductor.protected_grants import parse_request


def request(verb, **fields):
    return parse_request(
        json.dumps(
            {"version": 1, "verb": verb, "grant_id": str(uuid4()), **fields}
        ).encode()
    )


def test_dispatch_routes_closed_verbs_and_validates_lease_before_backend():
    async def scenario():
        broker = SimpleNamespace(
            **{
                name: AsyncMock(return_value={"status": name})
                for name in ("admit", "check", "cancel", "checkpoint")
            }
        )
        grant = object()
        lease = {"run_id": "one", "owner_id": "service", "generation": 1}
        await consul_broker.dispatch(broker, grant, request("admit", binding={}))
        await consul_broker.dispatch(broker, grant, request("cancel"))
        await consul_broker.dispatch(
            broker, grant, request("check", lease=lease, binding={}, phase="turn")
        )
        await consul_broker.dispatch(
            broker, grant, request("checkpoint", lease=lease, binding={}, result={})
        )
        assert broker.check.await_args.args[1].generation == 1
        assert broker.cancel.await_args.args[1] is None
        for malformed in (
            {**lease, "generation": True},
            {**lease, "extra": "field"},
            {**lease, "owner_id": ""},
        ):
            with pytest.raises(PermissionError, match="lease_shape"):
                await consul_broker.dispatch(
                    broker, grant, request("cancel", lease=malformed)
                )
        assert broker.cancel.await_count == 1

    asyncio.run(scenario())


def test_protected_authority_is_checked_before_db_connect(monkeypatch):
    import asyncpg
    from backend.services.autonomous_lab import consul_native_broker

    connect = AsyncMock()
    monkeypatch.setattr(asyncpg, "connect", connect)
    # Real service identity check must reject this ordinary test process.
    monkeypatch.setattr(
        consul_native_broker.pwd,
        "getpwnam",
        lambda name: SimpleNamespace(pw_uid=65534, pw_name=name),
    )
    monkeypatch.setattr(consul_native_broker.os, "geteuid", lambda: 501)
    with pytest.raises(PermissionError, match="native_service_identity_required"):
        asyncio.run(consul_broker.handle(json.dumps(request("cancel")).encode()))
    connect.assert_not_awaited()


def test_entry_never_exposes_exception_or_caller_payload(monkeypatch, capsys):
    monkeypatch.setattr(consul_broker.sys, "argv", ["consul_broker"])
    monkeypatch.setattr(
        consul_broker.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"{}"))
    )
    monkeypatch.setattr(
        consul_broker,
        "handle",
        AsyncMock(side_effect=RuntimeError("private fixture payload")),
    )
    assert consul_broker.main() == 1
    out = capsys.readouterr()
    assert json.loads(out.out) == {
        "version": 1,
        "ok": False,
        "error": "request_refused",
    }
    assert not out.err


def test_installed_gateway_supplies_budget_and_closes_connection(monkeypatch):
    import asyncpg
    from backend.services.autonomous_lab import consul_native_broker as backend
    from scripts.conductor.native_canary_contract import CANARY_LEASE_SECONDS

    wire = request("cancel")
    grant = SimpleNamespace(grant_id=wire["grant_id"])
    conn = SimpleNamespace(close=AsyncMock(), set_type_codec=AsyncMock())
    monkeypatch.setattr(asyncpg, "connect", AsyncMock(return_value=conn))
    store = object()
    monkeypatch.setattr(backend, "service_state_store", lambda **_: store)
    monkeypatch.setattr(consul_broker, "load_config", lambda _: {"database_dsn": "fixture"})
    monkeypatch.setattr(consul_broker, "load_grant", lambda _: {})
    monkeypatch.setattr(backend.NativeGrant, "from_payload", lambda _: grant)
    observed = []

    async def cancel(self, actual_grant, lease):
        # Exercise the real constructor at the installed gateway boundary.
        assert self.conn is conn and self.store is store
        assert actual_grant is grant and lease is None
        observed.append(self.lease_seconds)
        return {"status": "revoked"}

    monkeypatch.setattr(backend.NativeBroker, "cancel", cancel)
    assert asyncio.run(consul_broker.handle(json.dumps(wire).encode())) == {
        "status": "revoked"
    }
    assert observed == [CANARY_LEASE_SECONDS]
    conn.close.assert_awaited_once_with(timeout=1)


class Writer:
    def __init__(self):
        self.data = b""

    def write(self, raw):
        self.data += raw

    async def drain(self):
        return None

    def close(self):
        return None


async def fake_process(raw):
    reader = asyncio.StreamReader()
    reader.feed_data(raw)
    reader.feed_eof()
    return SimpleNamespace(
        pid=999999999,
        stdin=Writer(),
        stdout=reader,
        returncode=0,
        wait=AsyncMock(return_value=0),
    )


def test_transport_uses_fixed_helper_and_excludes_service_credentials(monkeypatch):
    async def scenario():
        process = await fake_process(
            b'{"version":1,"ok":true,"result":{"status":"revoked"}}'
        )
        spawn = AsyncMock(return_value=process)
        monkeypatch.setattr(transport.asyncio, "create_subprocess_exec", spawn)
        # A separate service UID can refuse a kill even though its request ended.
        monkeypatch.setattr(
            transport.os,
            "killpg",
            lambda *args: (_ for _ in ()).throw(PermissionError()),
        )
        monkeypatch.setenv("DATABASE_URL", "fixture-never-forward")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-never-forward")
        result = await transport.helper_exchange(request("cancel"))
        assert result == {"status": "revoked"}
        assert spawn.await_args.args == (
            *transport.SSH_COMMAND,
            *transport.HELPER_COMMAND,
        )
        assert set(spawn.await_args.kwargs["env"]) <= {
            "HOME",
            "SSH_AUTH_SOCK",
            "PATH",
            "LANG",
        }
        assert spawn.await_args.kwargs["stderr"] == asyncio.subprocess.DEVNULL

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "raw",
    [
        b'{"version":1,"ok":false,"error":"private fixture payload"}',
        b'{"version":true,"ok":true,"result":{}}',
        b'{"version":1,"ok":true,"result":{},"extra":"forbidden"}',
        b'{"version":1,"ok":true,"ok":false,"result":{}}',
        b" " * (transport.MAX_RESPONSE_BYTES + 1),
    ],
)
def test_transport_refuses_oversized_or_ambiguous_reply_without_echo(raw, monkeypatch):
    async def scenario():
        process = await fake_process(raw)
        monkeypatch.setattr(
            transport.asyncio, "create_subprocess_exec", AsyncMock(return_value=process)
        )
        monkeypatch.setattr(transport.os, "killpg", lambda *args: None)
        with pytest.raises(transport.BrokerTransportError) as error:
            await transport.helper_exchange(request("cancel"), location="local")
        assert "private fixture" not in str(error.value)

    asyncio.run(scenario())
