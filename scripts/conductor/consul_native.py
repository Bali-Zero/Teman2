"""Opt-in, one-turn canary consumer of the protected Pro broker.

Discovery spends no inference and yields the exact binding for the existing
review/grant issuer. Invocation needs a pre-issued, protected grant; this client
cannot approve itself. There is no scheduler, automatic fallback or retry.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, replace
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
import socket
from typing import Any

from scripts.conductor.codex_shadow import CodexShadow, NativeBinding
from scripts.conductor.codex_shadow_launch import launch_shadow
from scripts.conductor.consul_broker_client import ConsulBrokerClient, helper_exchange
from scripts.conductor.contracts import TaskClass, TaskIntent

CANARY_TEXT = "Reply with exactly DUAL_CONSUL_NATIVE_OK. Do not use tools."


def canary_task(mission_id: str) -> TaskIntent:
    return TaskIntent(
        mission_id,
        TaskClass.READ_ONLY,
        1,
        False,
        (),
        frozenset(),
        "consul-native-canary",
        100,
        frozenset({"text"}),
        frozenset(),
        False,
    )


async def invoke_canary(
    adapter: CodexShadow,
    broker: ConsulBrokerClient,
    mission_id: str,
    *,
    model: str,
    effort: str,
) -> dict[str, Any]:
    """An exception revokes the grant and always attempts native local stop."""
    try:
        result = await adapter.invoke(
            canary_task(mission_id), CANARY_TEXT, model=model, effort=effort
        )
        canary_passed = (
            result.status == "completed" and result.text == "DUAL_CONSUL_NATIVE_OK"
        )
        if result.status == "completed" and not canary_passed:
            # The invocation ended; a wrong marker is an observed failure,
            # not an uncertain remote effect or permission to spend again.
            result = replace(result, status="failed")
        checkpoint = await broker.checkpoint(result)
        return {
            "canary_passed": canary_passed,
            "native": result.checkpoint(),
            "broker": checkpoint,
        }
    except BaseException:
        await broker.cancel(adapter)
        raise


async def run(args: argparse.Namespace) -> dict[str, Any]:
    broker = (
        ConsulBrokerClient(
            args.grant_id, exchange=partial(helper_exchange, location=args.broker)
        )
        if args.grant_id
        else None
    )

    async def refuse(binding: NativeBinding, phase: str) -> None:
        raise PermissionError("discovery_only")

    async with launch_shadow(args.auth_home) as (rpc, cwd, metadata, fingerprint):
        adapter = CodexShadow(
            rpc,
            cwd=cwd,
            runtime_version=metadata["runtime_version"] + "@" + metadata["binary_hash"],
            host=socket.gethostname(),
            authorize=broker.authorize if broker else refuse,
            auth_fingerprint=fingerprint,
        )
        if args.discover:
            observation, efforts = await adapter.discover(args.model)
            if args.effort not in efforts:
                raise PermissionError("effort_unsupported")
            binding = NativeBinding(
                args.mission_id,
                sha256(CANARY_TEXT.encode()).hexdigest(),
                observation.key,
                args.model,
                args.effort,
            )
            return {
                "mode": "discovery",
                "binding": asdict(binding),
                "inference_performed": False,
            }
        assert broker is not None
        return await invoke_canary(
            adapter, broker, args.mission_id, model=args.model, effort=args.effort
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--auth-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--broker", choices=("local", "pro"), default="pro")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--discover", action="store_true")
    mode.add_argument("--grant-id")
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
    except Exception:
        result = {"status": "refused_or_incomplete", "remote_cancelled": None}
        code = 1
    else:
        code = 0 if args.discover or result.get("canary_passed") is True else 1
    # Receipt-safe fields only: never prompt/response text or free-form errors.
    import sys

    sys.stdout.write(json.dumps(result, allow_nan=False, separators=(",", ":")) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
