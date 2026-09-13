"""Bounded client of the provisioned Consul helper; no database credentials.

The launcher invokes this client, while the qualified native sandbox disables
model tools. The sudo rule covers the caller UID, not individual processes;
the separate service UID protects database credentials, not caller reachability.
SSH transports to Pro. A transport timeout leaves remote status unknown.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import os
import signal
from typing import Any, Awaitable, Callable, Literal

from scripts.conductor.codex_shadow import CodexShadow, NativeBinding, NativeResult
from scripts.conductor.native_canary_contract import HELPER_TIMEOUT_SECONDS
from scripts.conductor.protected_grants import (
    MAX_REQUEST_BYTES,
    grant_name,
    strict_json,
)

HELPER_COMMAND = (
    "/usr/bin/sudo",
    "-n",
    "-u",
    "_nuz_consul",
    "/usr/local/libexec/nuzantara-consul-broker",
)
SSH_COMMAND = (
    "/usr/bin/ssh",
    "-T",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=5",
    "pro",
)
MAX_RESPONSE_BYTES = 65536
Exchange = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class BrokerTransportError(RuntimeError):
    """Stable local error; neither helper stderr nor credentials are rendered."""


async def _bounded_output(reader: asyncio.StreamReader) -> bytes:
    output = bytearray()
    while len(output) <= MAX_RESPONSE_BYTES:
        chunk = await reader.read(min(8192, MAX_RESPONSE_BYTES + 1 - len(output)))
        if not chunk:
            return bytes(output)
        output.extend(chunk)
    raise BrokerTransportError("response_too_large")


async def helper_exchange(
    request: dict[str, Any], *, location: Literal["local", "pro"] = "pro"
) -> dict[str, Any]:
    if location not in {"local", "pro"}:
        raise ValueError("fixed_broker_location_required")
    raw = json.dumps(request, allow_nan=False, separators=(",", ":")).encode()
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("request_too_large")
    argv = HELPER_COMMAND if location == "local" else (*SSH_COMMAND, *HELPER_COMMAND)
    env = {
        key: os.environ[key] for key in ("HOME", "SSH_AUTH_SOCK") if key in os.environ
    }
    env.update(PATH="/usr/bin:/bin", LANG="C.UTF-8")
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    try:
        async with asyncio.timeout(HELPER_TIMEOUT_SECONDS):
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(raw)
            await process.stdin.drain()
            process.stdin.close()
            output = await _bounded_output(process.stdout)
            await process.wait()
        reply = strict_json(output)
        if type(reply.get("version")) is not int or reply["version"] != 1:
            raise BrokerTransportError("invalid_reply")
        if process.returncode != 0 or reply.get("ok") is not True:
            # Do not copy free-form remote error strings into caller output.
            raise BrokerTransportError("broker_refused")
        if set(reply) != {"version", "ok", "result"} or not isinstance(
            reply["result"], dict
        ):
            raise BrokerTransportError("invalid_reply")
        return reply["result"]
    except (TimeoutError, ValueError, OSError) as exc:
        raise BrokerTransportError("broker_exchange_incomplete") from exc
    finally:
        # Even a root child exit does not establish that its group has stopped.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=1)
        except TimeoutError:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        # A different-UID sudo child may outlive our signal permission. The
        # installed helper has its own deadline; no local kill proves remote
        # rollback or provider cancellation.
        try:
            await asyncio.wait_for(process.wait(), timeout=1)
        except TimeoutError:
            pass


class ConsulBrokerClient:
    """One protected grant, one started invocation; retries never mint authority."""

    def __init__(self, grant_id: str, *, exchange: Exchange = helper_exchange) -> None:
        grant_name(grant_id)
        self.grant_id, self.exchange = grant_id, exchange
        self.lease: dict[str, Any] | None = None
        self.binding: NativeBinding | None = None
        self.cancelled = False
        self.cancellation: dict[str, Any] = {}

    async def _call(self, verb: str, **fields: Any) -> dict[str, Any]:
        return await self.exchange(
            {"version": 1, "verb": verb, "grant_id": self.grant_id, **fields}
        )

    async def authorize(self, binding: NativeBinding, phase: str) -> None:
        if self.cancelled:
            raise PermissionError("mission_cancelled")
        wire = asdict(binding)
        if self.lease is None:
            if phase != "start":
                raise PermissionError("admission_required")
            reply = await self._call("admit", binding=wire)
            if self.cancelled:
                raise PermissionError("mission_cancelled")
            lease = reply.get("lease")
            if (
                not isinstance(lease, dict)
                or set(lease) != {"run_id", "owner_id", "generation"}
                or lease["run_id"] != binding.mission_id
                or not isinstance(lease["owner_id"], str)
                or not lease["owner_id"]
                or type(lease["generation"]) is not int
                or lease["generation"] < 1
            ):
                raise BrokerTransportError("invalid_lease")
            self.lease = lease
        else:
            await self._call("check", lease=self.lease, binding=wire, phase=phase)
            if self.cancelled:
                raise PermissionError("mission_cancelled")
        self.binding = binding

    async def checkpoint(self, result: NativeResult) -> dict[str, Any]:
        if self.cancelled or self.lease is None or self.binding != result.binding:
            raise PermissionError("current_completed_binding_required")
        reply = await self._call(
            "checkpoint",
            lease=self.lease,
            binding=asdict(result.binding),
            result=result.checkpoint(),
        )
        if self.cancelled:
            raise PermissionError("mission_cancelled")
        return reply

    async def cancel(self, adapter: CodexShadow) -> dict[str, Any]:
        self.cancelled = True

        async def revoke() -> None:
            try:
                fields = {"lease": self.lease} if self.lease is not None else {}
                self.cancellation["revocation"] = await self._call("cancel", **fields)
                self.cancellation["revocation_confirmed"] = True
            except Exception:
                self.cancellation["revocation_confirmed"] = False

        # Stop locally while the independent remote revocation is in flight.
        # A stalled broker must never leave a fresh native turn admissible.
        revocation = asyncio.create_task(revoke())
        try:
            await adapter.cancel()
            self.cancellation["native"] = dict(adapter.cancellation)
        finally:
            await revocation
        return dict(self.cancellation)
