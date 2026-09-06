"""Manual synthetic qualification consumer; never installed as a scheduler.

Default: discovery only. --invoke spends two bounded native turns to exercise
same-mission continuity. --cancel spends one turn, immediately interrupts, stops
its supervised process group and records remote cancellation as unknown.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
from uuid import uuid4

from scripts.conductor.app_server_rpc import AppServerError
from scripts.conductor.codex_shadow import CodexShadow, NativeBinding
from scripts.conductor.codex_shadow_launch import launch_shadow
from scripts.conductor.contracts import TaskClass, TaskIntent


async def probe(auth_home: Path, model: str, mode: str) -> dict:
    started = datetime.now(timezone.utc)
    mission_id = "native-shadow-" + str(uuid4())
    task = TaskIntent(
        mission_id,
        TaskClass.READ_ONLY,
        1,
        False,
        (),
        frozenset(),
        "dual-consul-synthetic-shadow",
        100,
        frozenset({"text"}),
        frozenset(),
        False,
    )
    # Only synthetic text enters this built-in probe. It is not an arbitrary
    # prompt runner and this local check is not an operational broker grant.
    prompt = "Reply with exactly DUAL_CONSUL_NATIVE_OK. Do not use tools."
    authorization_checks: list[str] = []
    revoked = False

    async def authorize(binding: NativeBinding, operation: str) -> None:
        from hashlib import sha256

        if (
            revoked
            or binding.mission_id != mission_id
            or binding.input_hash != sha256(prompt.encode()).hexdigest()
            or datetime.now(timezone.utc) >= started + timedelta(minutes=3)
        ):
            raise PermissionError("synthetic_probe_scope_expired_or_revoked")
        authorization_checks.append(operation)

    results: list[dict] = []
    async with launch_shadow(auth_home) as (rpc, cwd, runtime, fingerprint):
        adapter = CodexShadow(
            rpc,
            cwd=cwd,
            runtime_version=runtime["runtime_version"] + "@" + runtime["binary_hash"],
            host=socket.gethostname(),
            authorize=authorize,
            auth_fingerprint=fingerprint,
        )
        observation, efforts = await adapter.discover(model)
        if mode == "invoke":
            for _ in range(2):
                result = await adapter.invoke(
                    task, prompt, model=model, effort="medium"
                )
                if (
                    result.status != "completed"
                    or result.text.strip() != "DUAL_CONSUL_NATIVE_OK"
                ):
                    raise RuntimeError("synthetic_reply_incomplete_or_mismatched")
                results.append(result.checkpoint())
        elif mode == "cancel":
            invocation = asyncio.create_task(
                adapter.invoke(task, prompt, model=model, effort="medium")
            )
            try:
                await asyncio.wait_for(adapter.turn_started.wait(), 20)
                revoked = True
                await adapter.cancel()
                try:
                    result = await invocation
                    results.append(result.checkpoint())
                except (AppServerError, PermissionError):
                    results.append(
                        {"status": "cancelled_locally", "remote_cancelled": None}
                    )
            finally:
                if not invocation.done():
                    invocation.cancel()
                await asyncio.gather(invocation, return_exceptions=True)
        selected = {
            "observed_at": started.isoformat(),
            "mode": mode,
            "mission_id": mission_id,
            "runtime": runtime,
            "model": model,
            "supported_efforts": sorted(efforts),
            "config_hash": observation.key.config_hash,
            "auth_context_hash": observation.key.auth_context_hash,
            "authorization_checks": authorization_checks,
            "results": results,
            "cancellation": adapter.cancellation,
            "remote_cancelled": None,
            "effect_authority": "none",
            "fleet_activation": False,
        }
    selected["local_process_group_stopped"] = rpc.local_stopped
    if not rpc.local_stopped:
        raise RuntimeError("local_process_group_not_stopped")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auth-home", type=Path, required=True)
    parser.add_argument("--model", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--invoke", action="store_true")
    mode.add_argument("--cancel", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(
            probe(
                args.auth_home,
                args.model,
                "invoke" if args.invoke else "cancel" if args.cancel else "discovery",
            )
        )
    except (
        AppServerError,
        PermissionError,
        RuntimeError,
        ValueError,
        OSError,
        TimeoutError,
    ) as error:
        # Never serialize provider payloads, filesystem exceptions, or auth data.
        print(
            json.dumps(
                {"status": "qualification_failed", "error_type": type(error).__name__}
            )
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
