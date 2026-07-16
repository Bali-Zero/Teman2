"""FlowKit tools for WR2/WR3 image and video generation.

The FlowKit runtime lives on Pro. When this MCP server runs from Air-M5 or
Mini, these tools execute the repo CLI over SSH and stage local assets/output
without installing FlowKit on the thin-client machine.
"""

from __future__ import annotations

import asyncio
import json
import shlex
import socket
import sys
import uuid
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
LOCAL_PYTHON = REPO_ROOT / "apps/backend-rag/.venv/bin/python"
LOCAL_CLI = REPO_ROOT / "scripts/flowkit_cli.py"
PRO_ALIAS = "pro"
PRO_REPO = "~/nuzantara"
PRO_PYTHON = "apps/backend-rag/.venv/bin/python"
PRO_REMOTE_CLI = "/tmp/nuz-flowkit-bridge/flowkit_cli.py"

RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_ASSET_CANDIDATES = [
    "/Users/balizero/Desktop/logo/zer.jpg",
    "/Users/balizero/Desktop/logo/zer.jpeg",
    "/Users/balizero/Desktop/logo/selfie_converted.jpg",
    "/Users/nuzantara/Desktop/logo/zer.jpg",
    "/Users/nuzantara/Desktop/logo/zer.jpeg",
    str(REPO_ROOT / "apps/mouth/public/avatars/default-active.svg"),
    str(REPO_ROOT / "apps/mouth/public/avatars/default-lead.svg"),
]


def _is_pro() -> bool:
    return socket.gethostname() == "Nuzantara"


def _local_python() -> str:
    if LOCAL_PYTHON.exists():
        return str(LOCAL_PYTHON)
    return sys.executable


async def _run_process(
    argv: list[str], *, timeout_s: int = 600
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout_s
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return 124, "", f"timeout after {timeout_s}s"
    return (
        int(process.returncode or 0),
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )


def _parse_cli_stdout(returncode: int, stdout: str, stderr: str) -> dict[str, Any]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return {
            "ok": False,
            "error_kind": "flowkit_error",
            "error": "FlowKit CLI returned no JSON",
            "returncode": returncode,
            "stderr": stderr.strip(),
        }
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error_kind": "flowkit_error",
            "error": "FlowKit CLI returned malformed JSON",
            "returncode": returncode,
            "stdout": stdout[-1200:],
            "stderr": stderr.strip(),
        }
    if isinstance(payload, dict):
        payload.setdefault("returncode", returncode)
        if stderr.strip():
            payload.setdefault("stderr", stderr.strip()[-1200:])
        return payload
    return {
        "ok": False,
        "error_kind": "flowkit_error",
        "error": "FlowKit CLI JSON was not an object",
        "returncode": returncode,
        "payload": payload,
    }


def _cli_argv(args: list[str]) -> list[str]:
    if _is_pro():
        return [_local_python(), str(LOCAL_CLI), *args]
    remote_cmd = f"cd {PRO_REPO} && {PRO_PYTHON} {shlex.quote(PRO_REMOTE_CLI)} {shlex.join(args)}"
    return ["ssh", "-o", "ConnectTimeout=5", PRO_ALIAS, remote_cmd]


async def _run_flowkit_cli(args: list[str], *, timeout_s: int = 600) -> dict[str, Any]:
    if not _is_pro():
        stage_error = await _stage_cli_for_pro()
        if stage_error:
            return stage_error
    returncode, stdout, stderr = await _run_process(
        _cli_argv(args), timeout_s=timeout_s
    )
    return _parse_cli_stdout(returncode, stdout, stderr)


async def _ssh_mkdir(path: str) -> dict[str, Any] | None:
    returncode, _, stderr = await _run_process(
        ["ssh", "-o", "ConnectTimeout=5", PRO_ALIAS, "mkdir", "-p", path],
        timeout_s=30,
    )
    if returncode != 0:
        return {
            "ok": False,
            "error_kind": "flowkit_error",
            "error": f"Failed to create Pro staging directory: {stderr.strip()}",
            "returncode": returncode,
        }
    return None


async def _stage_cli_for_pro() -> dict[str, Any] | None:
    if not LOCAL_CLI.exists():
        return {
            "ok": False,
            "error_kind": "flowkit_error",
            "error": f"FlowKit CLI is missing locally: {LOCAL_CLI}",
        }

    mkdir_error = await _ssh_mkdir(str(Path(PRO_REMOTE_CLI).parent))
    if mkdir_error:
        return mkdir_error

    returncode, _, stderr = await _run_process(
        ["scp", str(LOCAL_CLI), f"{PRO_ALIAS}:{PRO_REMOTE_CLI}"],
        timeout_s=30,
    )
    if returncode != 0:
        return {
            "ok": False,
            "error_kind": "flowkit_error",
            "error": f"Failed to stage FlowKit CLI on Pro: {stderr.strip()}",
            "returncode": returncode,
        }
    return None


async def _stage_local_file_for_pro(path: str) -> tuple[str, dict[str, Any] | None]:
    if _is_pro():
        return path, None

    local_path = Path(path).expanduser()
    if not local_path.exists():
        return path, None

    remote_dir = f"/tmp/nuz-flowkit-assets/{uuid.uuid4().hex}"
    mkdir_error = await _ssh_mkdir(remote_dir)
    if mkdir_error:
        return path, mkdir_error

    remote_path = f"{remote_dir}/{local_path.name}"
    returncode, _, stderr = await _run_process(
        ["scp", str(local_path), f"{PRO_ALIAS}:{remote_path}"],
        timeout_s=60,
    )
    if returncode != 0:
        return path, {
            "ok": False,
            "error_kind": "flowkit_error",
            "error": f"Failed to stage asset on Pro: {stderr.strip()}",
            "returncode": returncode,
        }
    return remote_path, None


async def _prepare_remote_dest(path: str) -> tuple[str, dict[str, Any] | None]:
    if _is_pro() or not path:
        return path, None
    local_path = Path(path).expanduser()
    remote_dir = f"/tmp/nuz-flowkit-output/{uuid.uuid4().hex}"
    mkdir_error = await _ssh_mkdir(remote_dir)
    if mkdir_error:
        return path, mkdir_error
    return f"{remote_dir}/{local_path.name}", None


async def _copy_output_from_pro(
    remote_path: str, local_path: str
) -> dict[str, Any] | None:
    if _is_pro() or not remote_path or not local_path or remote_path == local_path:
        return None
    dest = Path(local_path).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    returncode, _, stderr = await _run_process(
        ["scp", f"{PRO_ALIAS}:{remote_path}", str(dest)],
        timeout_s=120,
    )
    if returncode != 0:
        return {
            "ok": False,
            "error_kind": "flowkit_error",
            "error": f"FlowKit output generated on Pro but copy-back failed: {stderr.strip()}",
            "returncode": returncode,
            "remote_path": remote_path,
        }
    return None


async def _path_exists_on_pro(path: str) -> bool:
    returncode, _, _ = await _run_process(
        ["ssh", "-o", "ConnectTimeout=5", PRO_ALIAS, "test", "-f", path],
        timeout_s=10,
    )
    return returncode == 0


def _is_uploadable(path: str) -> bool:
    return Path(path).suffix.lower() in RASTER_SUFFIXES


async def _resolve_asset_candidates(asset_path: str = "") -> dict[str, Any]:
    candidates = [asset_path] if asset_path else DEFAULT_ASSET_CANDIDATES
    seen: set[str] = set()
    local_matches: list[dict[str, Any]] = []
    pro_matches: list[dict[str, Any]] = []
    for raw_candidate in candidates:
        if not raw_candidate or raw_candidate in seen:
            continue
        seen.add(raw_candidate)
        local_path = Path(raw_candidate).expanduser()
        if local_path.exists():
            local_matches.append(
                {
                    "path": str(local_path),
                    "uploadable": _is_uploadable(str(local_path)),
                    "machine": socket.gethostname(),
                }
            )
        if not _is_pro() and raw_candidate.startswith("/Users/nuzantara/"):
            if await _path_exists_on_pro(raw_candidate):
                pro_matches.append(
                    {
                        "path": raw_candidate,
                        "uploadable": _is_uploadable(raw_candidate),
                        "machine": "Nuzantara",
                    }
                )

    recommended = ""
    for match in [*local_matches, *pro_matches]:
        if match["uploadable"]:
            recommended = str(match["path"])
            break

    return {
        "ok": bool(recommended),
        "local_matches": local_matches,
        "pro_matches": pro_matches,
        "recommended_start_image_path": recommended,
        "note": (
            "Use an explicit start_image_path or start_image_media_id. "
            "The bridge does not assume an AVATAR record exists."
        ),
    }


def register(mcp, _call=None, _call_safe=None) -> None:
    """Register FlowKit tools."""

    @mcp.tool()
    async def flowkit_health() -> dict[str, Any]:
        """Check FlowKit readiness on Pro, usable from Air-M5 via SSH."""
        payload = await _run_flowkit_cli(["health"], timeout_s=60)
        payload["executed_on"] = "Pro" if not _is_pro() else "local-Pro"
        return payload

    @mcp.tool()
    async def flowkit_resolve_asset(asset_path: str = "") -> dict[str, Any]:
        """Find a usable raster start-image asset before video generation."""
        return await _resolve_asset_candidates(asset_path)

    @mcp.tool()
    async def flowkit_upload_image(
        image_path: str,
        project_name: str = "mcp-flowkit",
        project_id: str = "",
    ) -> dict[str, Any]:
        """Upload a local image to FlowKit and return the media_id."""
        staged_path, stage_error = await _stage_local_file_for_pro(image_path)
        if stage_error:
            return stage_error
        args = [
            "upload-image",
            "--image-path",
            staged_path,
            "--project",
            project_name,
        ]
        if project_id:
            args.extend(["--project-id", project_id])
        payload = await _run_flowkit_cli(args, timeout_s=180)
        if staged_path != image_path:
            payload["local_source_path"] = image_path
            payload["pro_staged_path"] = staged_path
        return payload

    @mcp.tool()
    async def flowkit_generate_image(
        prompt: str,
        orientation: str = "PORTRAIT",
        project_name: str = "mcp-flowkit",
        dest_path: str = "",
        paygate_tier: str = "PAYGATE_TIER_TIER1P5",
    ) -> dict[str, Any]:
        """Generate a Nano Banana Pro image through FlowKit on Pro."""
        remote_dest, dest_error = await _prepare_remote_dest(dest_path)
        if dest_error:
            return dest_error
        args = [
            "generate-image",
            "--prompt",
            prompt,
            "--orientation",
            orientation,
            "--project",
            project_name,
            "--paygate-tier",
            paygate_tier,
        ]
        if remote_dest:
            args.extend(["--dest", remote_dest])
        payload = await _run_flowkit_cli(args, timeout_s=240)
        if payload.get("ok") and remote_dest and dest_path and remote_dest != dest_path:
            copy_error = await _copy_output_from_pro(remote_dest, dest_path)
            if copy_error:
                return copy_error
            payload["remote_path"] = payload.get("local_path", remote_dest)
            payload["local_path"] = str(Path(dest_path).expanduser())
        return payload

    @mcp.tool()
    async def flowkit_generate_video(
        prompt: str,
        project_name: str = "mcp-flowkit",
        start_image_media_id: str = "",
        start_image_path: str = "",
        scene_id: str = "",
        orientation: str = "PORTRAIT",
        dest_path: str = "",
        paygate_tier: str = "PAYGATE_TIER_TIER1P5",
    ) -> dict[str, Any]:
        """Generate an 8s Veo video from a real start image."""
        if not start_image_media_id and not start_image_path:
            asset_probe = await _resolve_asset_candidates()
            return {
                "ok": False,
                "error_kind": "missing_asset",
                "error": (
                    "Missing start image. Pass start_image_media_id or "
                    "start_image_path; no AVATAR row is assumed."
                ),
                "asset_probe": asset_probe,
            }

        staged_path = start_image_path
        if start_image_path:
            staged_path, stage_error = await _stage_local_file_for_pro(start_image_path)
            if stage_error:
                return stage_error

        remote_dest, dest_error = await _prepare_remote_dest(dest_path)
        if dest_error:
            return dest_error

        args = [
            "generate-video",
            "--prompt",
            prompt,
            "--orientation",
            orientation,
            "--project",
            project_name,
            "--paygate-tier",
            paygate_tier,
        ]
        if start_image_media_id:
            args.extend(["--start-image-media-id", start_image_media_id])
        if staged_path:
            args.extend(["--start-image-path", staged_path])
        if scene_id:
            args.extend(["--scene-id", scene_id])
        if remote_dest:
            args.extend(["--dest", remote_dest])

        payload = await _run_flowkit_cli(args, timeout_s=720)
        if staged_path != start_image_path:
            payload["local_source_path"] = start_image_path
            payload["pro_staged_path"] = staged_path
        if payload.get("ok") and remote_dest and dest_path and remote_dest != dest_path:
            copy_error = await _copy_output_from_pro(remote_dest, dest_path)
            if copy_error:
                return copy_error
            payload["remote_path"] = payload.get("local_path", remote_dest)
            payload["local_path"] = str(Path(dest_path).expanduser())
        return payload
