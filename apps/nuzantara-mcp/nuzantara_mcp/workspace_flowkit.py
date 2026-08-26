"""Pro-only FlowKit runner for the private marketing workspace MCP.

This module is deliberately independent from ``nuzantara_mcp.tools.flowkit``
and the full MCP catalog. It accepts only the three closed argv shapes emitted
by ``tools.workspace_marketing`` and never invokes a shell or remote staging.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
FLOWKIT_PYTHON = REPO_ROOT / "apps/backend-rag/.venv/bin/python"
FLOWKIT_CLI = REPO_ROOT / "scripts/flowkit_cli.py"
PRO_HOSTNAME = "Nuzantara"
FLOW_PROJECT_NAME = "bali-zero-marketing-workspace"
FLOW_PAYGATE_TIER = "PAYGATE_TIER_TIER1P5"
ALLOWED_ORIENTATIONS = frozenset({"PORTRAIT", "LANDSCAPE"})


def _valid_value(value: str) -> bool:
    return bool(value) and not value.startswith("-") and "\x00" not in value


def _validate_args(args: list[str]) -> None:
    if args == ["health"]:
        return
    if len(args) == 9 and args[0] == "generate-image":
        expected = ("--prompt", "--orientation", "--project", "--paygate-tier")
        if tuple(args[index] for index in (1, 3, 5, 7)) != expected:
            raise RuntimeError("FlowKit image request shape is not allowed")
        if (
            not _valid_value(args[2])
            or args[4] not in ALLOWED_ORIENTATIONS
            or args[6] != FLOW_PROJECT_NAME
            or args[8] != FLOW_PAYGATE_TIER
        ):
            raise RuntimeError("FlowKit image request value is not allowed")
        return
    if len(args) in {11, 13} and args[0] == "generate-video":
        expected = (
            "--prompt",
            "--orientation",
            "--project",
            "--paygate-tier",
            "--start-image-media-id",
        )
        if tuple(args[index] for index in (1, 3, 5, 7, 9)) != expected:
            raise RuntimeError("FlowKit video request shape is not allowed")
        if (
            not _valid_value(args[2])
            or args[4] not in ALLOWED_ORIENTATIONS
            or args[6] != FLOW_PROJECT_NAME
            or args[8] != FLOW_PAYGATE_TIER
            or not _valid_value(args[10])
        ):
            raise RuntimeError("FlowKit video request value is not allowed")
        if len(args) == 13 and (args[11] != "--scene-id" or not _valid_value(args[12])):
            raise RuntimeError("FlowKit video scene is not allowed")
        return
    raise RuntimeError("FlowKit command is not allowed")


def _normalized_failure(error_kind: str = "flowkit_unavailable") -> dict[str, Any]:
    return {"ok": False, "status": "unavailable", "error_kind": error_kind}


def _flowkit_env() -> dict[str, str]:
    allowed = {
        "FLOWKIT_BASE_URL",
        "FLOWKIT_TIMEOUT_S",
        "FLOWKIT_VIDEO_TIMEOUT_S",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "TMPDIR",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed}
    standard_path = (
        "/opt/homebrew/bin:/Users/nuzantara/.local/bin:"
        "/usr/local/bin:/usr/bin:/bin"
    )
    current_path = env.get("PATH", "")
    env["PATH"] = f"{standard_path}:{current_path}" if current_path else standard_path
    return env


async def run(args: list[str], *, timeout_s: int = 600) -> dict[str, Any]:
    """Execute one closed FlowKit argv shape on Pro and return JSON only."""

    _validate_args(args)
    if socket.gethostname() != PRO_HOSTNAME:
        return _normalized_failure()
    if not FLOWKIT_PYTHON.is_file() or not FLOWKIT_CLI.is_file():
        return _normalized_failure()

    process = await asyncio.create_subprocess_exec(
        str(FLOWKIT_PYTHON),
        str(FLOWKIT_CLI),
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=_flowkit_env(),
        start_new_session=True,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        await _terminate_process_group(process)
        return _normalized_failure("flowkit_timeout")
    except asyncio.CancelledError:
        await asyncio.shield(_terminate_process_group(process))
        raise
    if process.returncode != 0:
        return _normalized_failure("flowkit_error")

    lines = [line for line in stdout.decode(errors="replace").splitlines() if line.strip()]
    if not lines:
        return _normalized_failure("flowkit_error")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return _normalized_failure("flowkit_error")
    return payload if isinstance(payload, dict) else _normalized_failure("flowkit_error")


async def _terminate_process_group(process: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=10)
    except asyncio.TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        await process.wait()
