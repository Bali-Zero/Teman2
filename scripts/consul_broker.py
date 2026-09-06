"""Installed, separate-UID stdio gateway to the existing PostgreSQL lifecycle.

This module accepts no command/path/SQL or approval document from the caller.
Its immutable installed bootstrap supplies imports; fixed protected files supply
authority and connection configuration. Native inference stays in the caller's
unprivileged process, never in this service identity.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from typing import Any

from scripts.conductor.native_canary_contract import (
    CANARY_LEASE_SECONDS,
    HELPER_TIMEOUT_SECONDS,
)
from scripts.conductor.protected_grants import (
    MAX_REQUEST_BYTES,
    SERVICE_USER,
    load_config,
    load_grant,
    parse_request,
)


async def dispatch(broker: Any, grant: Any, request: dict[str, Any]) -> dict[str, Any]:
    """The only four operations exposed by the installed helper."""
    from backend.services.autonomous_lab.consul_store import Lease

    lease = None
    if "lease" in request:
        wire = request["lease"]
        if (
            not isinstance(wire, dict)
            or set(wire) != {"run_id", "owner_id", "generation"}
            or any(
                not isinstance(wire[key], str) or not wire[key]
                for key in ("run_id", "owner_id")
            )
            or type(wire["generation"]) is not int
            or wire["generation"] < 1
        ):
            raise PermissionError("lease_shape")
        lease = Lease(**wire)
    verb = request["verb"]
    if verb == "admit":
        return await broker.admit(grant, request["binding"])
    if verb == "cancel":
        return await broker.cancel(grant, lease)
    if verb == "check":
        return await broker.check(grant, lease, request["binding"], request["phase"])
    if verb == "checkpoint":
        return await broker.checkpoint(
            grant, lease, request["binding"], request["result"]
        )
    raise PermissionError("closed_verb_required")


async def handle(raw: bytes) -> dict[str, Any]:
    """Validate kernel identity and protected authority before connecting."""
    import asyncpg

    from backend.core.pg_json_codec import init_asyncpg_connection
    from backend.services.autonomous_lab.consul_native_broker import (
        NativeBroker,
        NativeGrant,
        service_state_store,
    )

    request = parse_request(raw)
    state_store = service_state_store(service_user=SERVICE_USER)
    config = load_config(os.geteuid())
    grant = NativeGrant.from_payload(load_grant(request["grant_id"]))
    if grant.grant_id != request["grant_id"]:
        raise PermissionError("grant_file_identity")
    async with asyncio.timeout(15):
        conn = await asyncpg.connect(
            config["database_dsn"], timeout=5, command_timeout=10
        )
        try:
            await init_asyncpg_connection(conn)
            broker = NativeBroker(
                conn,
                owner_id=f"consul:nuzantara:uid:{os.geteuid()}",
                state_store=state_store,
                lease_seconds=CANARY_LEASE_SECONDS,
            )
            return await dispatch(broker, grant, request)
        finally:
            await conn.close(timeout=1)


def main() -> int:
    """One bounded request and selected response, never raw exception details."""
    import json

    def deadline(signum: int, frame: Any) -> None:
        raise TimeoutError("helper_deadline")

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(HELPER_TIMEOUT_SECONDS)
    try:
        if len(sys.argv) != 1:
            raise PermissionError("no_arguments")
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        result = asyncio.run(handle(raw))
        reply = {"version": 1, "ok": True, "result": result}
        code = 0
    except Exception:
        # Exception text can contain a DSN, a JSON payload or provider metadata.
        reply, code = {"version": 1, "ok": False, "error": "request_refused"}, 1
    finally:
        signal.alarm(0)
    sys.stdout.write(json.dumps(reply, allow_nan=False, separators=(",", ":")) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
