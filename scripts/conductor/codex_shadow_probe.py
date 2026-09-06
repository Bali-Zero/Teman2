"""Manual synthetic qualification consumer; never installed as a scheduler.

Default: discovery only. --catalog lists hidden and visible models without
inference, including when the requested model is unavailable. --invoke spends
two bounded native turns to exercise
same-mission continuity. --cancel spends one turn, immediately interrupts, stops
its supervised process group and records remote cancellation as unknown.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import socket
from typing import Any
from uuid import uuid4

from scripts.conductor.app_server_rpc import AppServerError
from scripts.conductor.codex_shadow import (
    CodexShadow,
    NativeBinding,
    digest,
    validate_shadow_config,
)
from scripts.conductor.codex_shadow_launch import launch_shadow
from scripts.conductor.contracts import TaskClass, TaskIntent


SOURCE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_MODULES = (
    "adapter_contracts.py",
    "contracts.py",
    "app_server_rpc.py",
    "codex_shadow.py",
    "codex_shadow_launch.py",
    "codex_shadow_probe.py",
)


def source_producer() -> dict[str, Any]:
    """Bind receipts to exact producer bytes, independent of Git dirty state."""
    files = {
        "scripts/conductor/" + name: sha256(
            (SOURCE_ROOT / "scripts/conductor" / name).read_bytes()
        ).hexdigest()
        for name in SOURCE_MODULES
    }
    return {"files": files, "manifest_sha256": digest(files)}


async def probe(auth_home: Path, model: str, mode: str) -> dict[str, Any]:
    producer = source_producer()
    result = await (
        _catalog_probe(auth_home, model)
        if mode == "catalog"
        else _mission_probe(auth_home, model, mode)
    )
    if source_producer() != producer:
        raise RuntimeError("source_producer_changed")
    result["source_producer"] = producer
    result["source_verification"] = "unchanged"
    return result


async def _catalog_probe(auth_home: Path, model: str) -> dict[str, Any]:
    """One-shot native catalog evidence; deliberately independent of admission."""
    started = datetime.now(timezone.utc)
    async with launch_shadow(auth_home) as (rpc, cwd, runtime, fingerprint):
        raw = await rpc.call("config/read", {"cwd": str(cwd), "includeLayers": False})
        config = raw["config"]
        if not isinstance(config, dict):
            raise ValueError("catalog_config_invalid")
        validate_shadow_config(config)
        account = (await rpc.call("account/read", {"refreshToken": False})).get(
            "account"
        )
        if not isinstance(account, dict) or account.get("type") != "chatgpt":
            raise PermissionError("chatgpt_subscription_required")
        auth_context_hash = digest({"account": account, "credential": fingerprint()})
        pages, cursor, seen = [], None, set()
        for number in range(1, 21):
            page = await rpc.call(
                "model/list", {"cursor": cursor, "limit": 100, "includeHidden": True}
            )
            if not isinstance(page["data"], list) or len(page["data"]) > 100:
                raise ValueError("catalog_page_invalid")
            models = []
            for entry in page["data"]:
                # Provider descriptions, upgrade copy, and unknown metadata stay
                # out of shared evidence, even when embedded in effort options.
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("supportedReasoningEfforts"), list)
                    or any(
                        not isinstance(option, dict)
                        for option in entry["supportedReasoningEfforts"]
                    )
                ):
                    raise ValueError("catalog_model_invalid")
                selected = {
                    key: entry[key]
                    for key in (
                        "id",
                        "model",
                        "hidden",
                        "isDefault",
                        "defaultReasoningEffort",
                    )
                }
                if any(
                    type(selected[key]) is not bool for key in ("hidden", "isDefault")
                ):
                    raise ValueError("catalog_model_invalid")
                efforts = [
                    option["reasoningEffort"]
                    for option in entry["supportedReasoningEfforts"]
                ]
                if any(
                    not isinstance(value, str) or not value
                    for value in (
                        selected["id"],
                        selected["model"],
                        selected["defaultReasoningEffort"],
                        *efforts,
                    )
                ):
                    raise ValueError("catalog_model_invalid")
                selected["supportedReasoningEfforts"] = efforts
                models.append(selected)
            cursor = page.get("nextCursor")
            if cursor is not None and not isinstance(cursor, str):
                raise ValueError("catalog_cursor_invalid")
            pages.append({"page": number, "models": models, "has_more": bool(cursor)})
            if not cursor:
                break
            if cursor in seen:
                raise PermissionError("catalog_cursor_cycle")
            seen.add(cursor)
        else:
            raise PermissionError("catalog_page_limit")
        result = {
            "observed_at": started.isoformat(),
            "mode": "catalog",
            "runtime": runtime,
            "host": socket.gethostname(),
            "requested_model": model,
            "config_hash": digest(config),
            "auth_context_hash": auth_context_hash,
            "catalog": {
                "include_hidden": True,
                "pages": pages,
                "complete": True,
                "requested_model_available": any(
                    entry["model"] == model
                    for page in pages
                    for entry in page["models"]
                ),
            },
            "inference_calls": 0,
            "effect_authority": "none",
            "fleet_activation": False,
        }
    if not rpc.local_stopped:
        raise RuntimeError("local_process_group_not_stopped")
    result["local_process_group_stopped"] = True
    return result


async def _mission_probe(auth_home: Path, model: str, mode: str) -> dict:
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
            "host": socket.gethostname(),
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
    mode.add_argument("--catalog", action="store_true")
    args = parser.parse_args()
    producer = None
    try:
        producer = source_producer()
        result = asyncio.run(
            probe(
                args.auth_home,
                args.model,
                "catalog"
                if args.catalog
                else "invoke"
                if args.invoke
                else "cancel"
                if args.cancel
                else "discovery",
            )
        )
    except (
        AppServerError,
        PermissionError,
        RuntimeError,
        ValueError,
        OSError,
        TimeoutError,
        KeyError,
    ) as error:
        # Never serialize provider payloads, filesystem exceptions, or auth data.
        print(
            json.dumps(
                {
                    "status": "qualification_failed",
                    "error_type": type(error).__name__,
                    "source_producer": producer,
                    "source_verification": "not_completed",
                }
            )
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
