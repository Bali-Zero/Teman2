#!/usr/bin/env python3
"""FlowKit command bridge for WR2/WR3 and MCP tools.

The FlowKit agent is intentionally local to the Pro machine. This CLI speaks to
that local HTTP API and emits one JSON object to stdout so MCP wrappers and
operators can distinguish token, asset, and model-access failures.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

import httpx


JsonDict = dict[str, Any]
Orientation = Literal["PORTRAIT", "LANDSCAPE"]

DEFAULT_BASE_URL = os.environ.get("FLOWKIT_BASE_URL", "http://127.0.0.1:8100")
DEFAULT_TIMEOUT_S = float(os.environ.get("FLOWKIT_TIMEOUT_S", "30"))
DEFAULT_VIDEO_TIMEOUT_S = float(os.environ.get("FLOWKIT_VIDEO_TIMEOUT_S", "240"))
DEFAULT_PAYGATE_TIER = os.environ.get(
    "FLOWKIT_PAYGATE_TIER",
    "PAYGATE_TIER_TIER1P5",
)

IMAGE_ASPECT_RATIOS = {
    "PORTRAIT": "IMAGE_ASPECT_RATIO_PORTRAIT",
    "LANDSCAPE": "IMAGE_ASPECT_RATIO_LANDSCAPE",
}
VIDEO_ASPECT_RATIOS = {
    "PORTRAIT": "VIDEO_ASPECT_RATIO_PORTRAIT",
    "LANDSCAPE": "VIDEO_ASPECT_RATIO_LANDSCAPE",
}


class FlowKitBridgeError(Exception):
    """Structured FlowKit bridge failure."""

    def __init__(
        self,
        *,
        kind: str,
        message: str,
        status: int | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.detail = detail

    def to_payload(self) -> JsonDict:
        payload: JsonDict = {
            "ok": False,
            "error_kind": self.kind,
            "error": str(self),
        }
        if self.status is not None:
            payload["status"] = self.status
        if self.detail is not None:
            payload["detail"] = self.detail
        payload["next_action"] = _next_action_for_kind(self.kind)
        return payload


def _classify_error_text(text: str, *, status: int | None = None) -> str:
    """Map FlowKit/Google error text to operator-actionable buckets."""
    lowered = text.lower()
    if (
        status == 401
        or "unauthenticated" in lowered
        or "invalid authentication" in lowered
    ):
        return "flow_auth"
    if "no_flow_key" in lowered:
        return "flow_token_missing"
    if "extension not connected" in lowered or "connection refused" in lowered:
        return "flowkit_unavailable"
    if (
        "model_access_denied" in lowered
        or "public_error_model_access_denied" in lowered
        or "no model for tier=" in lowered
    ):
        return "model_access"
    if "file not found" in lowered or "missing start image" in lowered:
        return "missing_asset"
    if "unsafe_generation" in lowered:
        return "unsafe_generation"
    if (
        "quota_exceeded" in lowered
        or "resource_exhausted" in lowered
        or "insufficient credit" in lowered
    ):
        return "quota"
    if "timeout" in lowered:
        return "timeout"
    return "flowkit_error"


def _next_action_for_kind(kind: str) -> str:
    actions = {
        "flow_auth": (
            "Refresh https://labs.google/fx/tools/flow on Pro, click the FlowKit "
            "extension icon, then rerun health; extension_connected alone is not enough."
        ),
        "flow_token_missing": (
            "Refresh the Flow tab on Pro so the extension captures a fresh Bearer token."
        ),
        "flowkit_unavailable": (
            "Start FlowKit on Pro: cd ~/flowkit && source venv/bin/activate && "
            "python -m agent.main."
        ),
        "model_access": (
            "Check /api/flow/credits and ~/flowkit/agent/models.json. For Ultra video, "
            "PAYGATE_TIER_TIER1P5 must map to veo_3_1_i2v_s_fast_portrait_ultra."
        ),
        "missing_asset": (
            "Pass --start-image-media-id or --start-image-path. Do not assume an AVATAR "
            "database row exists."
        ),
        "unsafe_generation": "Rewrite the prompt to remove restricted/named-public-figure triggers.",
        "quota": "Wait for credit reset or choose a lower-cost path before retrying.",
        "timeout": "Check FlowKit worker status and rerun with a longer timeout if the job is pending.",
    }
    return actions.get(
        kind, "Inspect the returned FlowKit detail and retry after fixing the blocker."
    )


def _json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)


def _emit(payload: JsonDict, *, exit_code: int = 0) -> int:
    sys.stdout.write(_json_text(payload) + "\n")
    return exit_code


def _compact_detail(data: Any, *, limit: int = 1200) -> Any:
    if isinstance(data, (str, int, float, bool)) or data is None:
        return data
    text = _json_text(data)
    if len(text) <= limit:
        return data
    return text[:limit]


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    json_body: JsonDict | None = None,
    timeout_s: float | None = None,
) -> JsonDict:
    try:
        resp = await client.request(method, path, json=json_body, timeout=timeout_s)
    except (httpx.HTTPError, OSError) as exc:
        text = str(exc)
        raise FlowKitBridgeError(
            kind=_classify_error_text(text),
            message=f"FlowKit {method} {path} unreachable: {text}",
        ) from exc

    try:
        data = resp.json()
    except ValueError:
        data = {"raw_body": resp.text[:1200]}

    if resp.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else data
        text = _json_text(detail)
        raise FlowKitBridgeError(
            kind=_classify_error_text(text, status=resp.status_code),
            message=f"FlowKit {method} {path} status={resp.status_code}",
            status=resp.status_code,
            detail=_compact_detail(detail),
        )

    if isinstance(data, dict):
        detail = data.get("detail")
        error = data.get("error")
        if detail or error:
            err_detail = detail or error
            text = _json_text(err_detail)
            raise FlowKitBridgeError(
                kind=_classify_error_text(text, status=resp.status_code),
                message=f"FlowKit {method} {path} returned an error envelope",
                status=resp.status_code,
                detail=_compact_detail(err_detail),
            )
        return data

    raise FlowKitBridgeError(
        kind="flowkit_error",
        message=f"FlowKit {method} {path} returned non-object JSON",
        status=resp.status_code,
        detail=_compact_detail(data),
    )


async def _safe_request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    json_body: JsonDict | None = None,
    timeout_s: float | None = None,
) -> JsonDict:
    try:
        data = await _request_json(
            client,
            method,
            path,
            json_body=json_body,
            timeout_s=timeout_s,
        )
        return {"ok": True, "data": data}
    except FlowKitBridgeError as exc:
        payload = exc.to_payload()
        payload["ok"] = False
        return payload


async def _ensure_project(
    client: httpx.AsyncClient,
    *,
    name: str,
    material: str,
    language: str,
    timeout_s: float,
) -> str:
    body = {"name": name, "material": material, "language": language}
    data = await _request_json(
        client,
        "POST",
        "/api/projects",
        json_body=body,
        timeout_s=timeout_s,
    )
    project_id = (
        data.get("id")
        or data.get("project_id")
        or (data.get("project") or {}).get("id")
    )
    if not isinstance(project_id, str) or not project_id:
        raise FlowKitBridgeError(
            kind="flowkit_error",
            message="FlowKit project create returned no project id",
            detail=_compact_detail(data),
        )
    return project_id


async def _create_video(
    client: httpx.AsyncClient,
    *,
    project_id: str,
    title: str,
    orientation: Orientation,
    timeout_s: float,
) -> str:
    body = {
        "project_id": project_id,
        "title": title,
        "orientation": "VERTICAL" if orientation == "PORTRAIT" else "HORIZONTAL",
    }
    data = await _request_json(
        client,
        "POST",
        "/api/videos",
        json_body=body,
        timeout_s=timeout_s,
    )
    video_id = (
        data.get("id") or data.get("video_id") or (data.get("video") or {}).get("id")
    )
    if not isinstance(video_id, str) or not video_id:
        raise FlowKitBridgeError(
            kind="flowkit_error",
            message="FlowKit video create returned no video id",
            detail=_compact_detail(data),
        )
    return video_id


async def _create_scene(
    client: httpx.AsyncClient,
    *,
    video_id: str,
    scene_id: str | None,
    prompt: str,
    timeout_s: float,
) -> str:
    if scene_id:
        return scene_id
    body = {
        "video_id": video_id,
        "display_order": 1,
        "prompt": prompt,
        "chain_type": "ROOT",
    }
    data = await _request_json(
        client,
        "POST",
        "/api/scenes",
        json_body=body,
        timeout_s=timeout_s,
    )
    created_scene_id = (
        data.get("id") or data.get("scene_id") or (data.get("scene") or {}).get("id")
    )
    if not isinstance(created_scene_id, str) or not created_scene_id:
        raise FlowKitBridgeError(
            kind="flowkit_error",
            message="FlowKit scene create returned no scene id",
            detail=_compact_detail(data),
        )
    return created_scene_id


def _parse_image_response(data: JsonDict) -> JsonDict:
    media = data.get("media")
    if not isinstance(media, list) or not media:
        raise FlowKitBridgeError(
            kind="flowkit_error",
            message="FlowKit generate-image response has no media array",
            detail=_compact_detail(data),
        )
    first = media[0] if isinstance(media[0], dict) else {}
    generated = (first.get("image") or {}).get("generatedImage") or {}
    media_id = generated.get("mediaId") or first.get("name")
    fife_url = generated.get("fifeUrl")
    dimensions = first.get("dimensions") or {}
    if not isinstance(media_id, str) or not media_id:
        raise FlowKitBridgeError(
            kind="flowkit_error",
            message="FlowKit generate-image response missing mediaId",
            detail=_compact_detail(data),
        )
    result: JsonDict = {
        "media_id": media_id,
        "model": generated.get("modelNameType") or "",
        "seed": generated.get("seed") or 0,
        "width": dimensions.get("width") or 0,
        "height": dimensions.get("height") or 0,
    }
    if isinstance(fife_url, str) and fife_url:
        result["fife_url"] = fife_url
    return result


def _parse_video_response(data: JsonDict) -> JsonDict:
    workflows = data.get("workflows") or data.get("operations") or []
    media = data.get("media") or []
    first_workflow = workflows[0] if isinstance(workflows, list) and workflows else {}
    first_media = media[0] if isinstance(media, list) and media else {}
    workflow_id = (
        first_workflow.get("name")
        or first_workflow.get("id")
        or first_workflow.get("operation")
        or ""
    )
    video_media_id = (
        first_media.get("name")
        or first_media.get("mediaId")
        or first_workflow.get("_primary_media_id")
        or ""
    )
    status = first_workflow.get("status") or first_media.get("status") or ""
    if not isinstance(video_media_id, str) or not video_media_id:
        raise FlowKitBridgeError(
            kind="flowkit_error",
            message="FlowKit generate-video response missing video media id",
            detail=_compact_detail(data),
        )
    return {
        "workflow_id": workflow_id,
        "video_media_id": video_media_id,
        "status": status,
        "raw": data,
    }


async def _download_url(
    client: httpx.AsyncClient,
    url: str,
    dest_path: Path,
    *,
    timeout_s: float,
) -> Path:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=timeout_s)
    except httpx.HTTPError as exc:
        raise FlowKitBridgeError(
            kind=_classify_error_text(str(exc)),
            message=f"FlowKit media download failed: {exc}",
        ) from exc
    if resp.status_code != 200:
        raise FlowKitBridgeError(
            kind=_classify_error_text(resp.text, status=resp.status_code),
            message=f"FlowKit media download status={resp.status_code}",
            status=resp.status_code,
            detail=resp.text[:1200],
        )
    if not resp.content:
        raise FlowKitBridgeError(
            kind="flowkit_error",
            message="FlowKit media download returned zero bytes",
        )
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(resp.content)
    return dest_path


async def _download_video_media(
    client: httpx.AsyncClient,
    *,
    media_id: str,
    dest_path: Path,
    timeout_s: float,
    poll_interval_s: float,
) -> Path:
    deadline = asyncio.get_running_loop().time() + timeout_s
    last_payload: JsonDict = {}
    while asyncio.get_running_loop().time() < deadline:
        payload = await _safe_request_json(
            client,
            "GET",
            f"/api/flow/media/{media_id}",
            timeout_s=min(30.0, timeout_s),
        )
        if payload.get("ok"):
            data = payload.get("data") or {}
            last_payload = data if isinstance(data, dict) else {}
            video = last_payload.get("video") or {}
            encoded = video.get("encodedVideo") or last_payload.get("encodedVideo")
            if isinstance(encoded, str) and encoded:
                mp4_bytes = base64.b64decode(encoded)
                if len(mp4_bytes) < 32 or b"ftyp" not in mp4_bytes[:32]:
                    raise FlowKitBridgeError(
                        kind="flowkit_error",
                        message="FlowKit media bytes do not look like MP4",
                        detail={"bytes": len(mp4_bytes)},
                    )
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_bytes(mp4_bytes)
                return dest_path
            fife_url = video.get("fifeUrl") or video.get("url")
            if isinstance(fife_url, str) and fife_url:
                return await _download_url(
                    client,
                    fife_url,
                    dest_path,
                    timeout_s=min(60.0, timeout_s),
                )
        else:
            kind = payload.get("error_kind")
            status = payload.get("status")
            transient = (
                kind in {"timeout"}
                or status in {404, 500, 503}
                or _is_transient_media_error(payload)
            )
            if not transient:
                raise FlowKitBridgeError(
                    kind=str(kind or "flowkit_error"),
                    message="FlowKit media endpoint returned terminal error",
                    status=status if isinstance(status, int) else None,
                    detail=_compact_detail(payload),
                )
            last_payload = payload
        await asyncio.sleep(poll_interval_s)

    raise FlowKitBridgeError(
        kind="timeout",
        message=f"FlowKit media {media_id[:8]} not ready after {timeout_s:.0f}s",
        detail=_compact_detail(last_payload),
    )


def _is_transient_media_error(payload: JsonDict) -> bool:
    detail = payload.get("detail")
    if not isinstance(detail, dict):
        return False
    error = detail.get("error")
    if not isinstance(error, dict):
        return False
    code = error.get("code")
    status = str(error.get("status", "")).upper()
    return code in (404, "404", 500, "500", 503, "503") or status in {
        "NOT_FOUND",
        "INTERNAL",
        "UNAVAILABLE",
    }


async def action_health(args: argparse.Namespace) -> JsonDict:
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        timeout=args.timeout,
    ) as client:
        health = await _safe_request_json(
            client, "GET", "/health", timeout_s=args.timeout
        )
        flow_status = await _safe_request_json(
            client,
            "GET",
            "/api/flow/status",
            timeout_s=args.timeout,
        )
        credits = await _safe_request_json(
            client,
            "GET",
            "/api/flow/credits",
            timeout_s=args.timeout,
        )

    extension_connected = bool((health.get("data") or {}).get("extension_connected"))
    token_ok = bool(credits.get("ok"))
    ready = bool(health.get("ok") and extension_connected and token_ok)

    blocker = ""
    if not health.get("ok"):
        blocker = str(health.get("error_kind") or "flowkit_unavailable")
    elif not extension_connected:
        blocker = "flowkit_unavailable"
    elif not token_ok:
        blocker = str(credits.get("error_kind") or "flow_auth")

    return {
        "ok": ready,
        "base_url": args.base_url,
        "extension_connected": extension_connected,
        "health": health,
        "flow_status": flow_status,
        "credits": credits,
        "blocker": blocker,
        "next_action": _next_action_for_kind(blocker) if blocker else "",
    }


async def action_upload_image(args: argparse.Namespace) -> JsonDict:
    image_path = Path(args.image_path).expanduser()
    if not image_path.exists():
        raise FlowKitBridgeError(
            kind="missing_asset",
            message=f"Image asset not found: {image_path}",
            detail={"image_path": str(image_path)},
        )

    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        timeout=args.timeout,
    ) as client:
        project_id = args.project_id or await _ensure_project(
            client,
            name=args.project,
            material=args.material,
            language=args.language,
            timeout_s=args.timeout,
        )
        data = await _request_json(
            client,
            "POST",
            "/api/flow/upload-image",
            json_body={
                "file_path": str(image_path),
                "project_id": project_id,
                "file_name": args.file_name or image_path.name,
            },
            timeout_s=args.timeout,
        )

    media_id = data.get("media_id") or data.get("_mediaId")
    if not isinstance(media_id, str) or not media_id:
        raise FlowKitBridgeError(
            kind="flowkit_error",
            message="FlowKit upload-image returned no media_id",
            detail=_compact_detail(data),
        )
    return {
        "ok": True,
        "action": "upload-image",
        "project_id": project_id,
        "media_id": media_id,
        "image_path": str(image_path),
        "raw": data.get("raw", data),
    }


async def action_generate_image(args: argparse.Namespace) -> JsonDict:
    try:
        async with asyncio.timeout(args.timeout):
            async with httpx.AsyncClient(
                base_url=args.base_url.rstrip("/"),
                timeout=args.timeout,
            ) as client:
                project_id = args.project_id or await _ensure_project(
                    client,
                    name=args.project,
                    material=args.material,
                    language=args.language,
                    timeout_s=args.timeout,
                )
                data = await _request_json(
                    client,
                    "POST",
                    "/api/flow/generate-image",
                    json_body={
                        "prompt": args.prompt,
                        "project_id": project_id,
                        "aspect_ratio": IMAGE_ASPECT_RATIOS[args.orientation],
                        "user_paygate_tier": args.paygate_tier,
                    },
                    timeout_s=args.timeout,
                )
                result = _parse_image_response(data)
                if args.dest:
                    fife_url = result.get("fife_url")
                    if not isinstance(fife_url, str) or not fife_url:
                        raise FlowKitBridgeError(
                            kind="flowkit_error",
                            message="FlowKit image response has no fife_url to download",
                            detail=_compact_detail(result),
                        )
                    local_path = await _download_url(
                        client,
                        fife_url,
                        Path(args.dest).expanduser(),
                        timeout_s=args.timeout,
                    )
                    result["local_path"] = str(local_path)
    except TimeoutError as exc:
        raise FlowKitBridgeError(
            kind="timeout",
            message="FlowKit image generation exceeded its overall deadline",
        ) from exc

    result.update(
        {
            "ok": True,
            "action": "generate-image",
            "project_id": project_id,
            "orientation": args.orientation,
            "paygate_tier": args.paygate_tier,
        }
    )
    return result


async def action_generate_video(args: argparse.Namespace) -> JsonDict:
    if not args.start_image_media_id and not args.start_image_path:
        raise FlowKitBridgeError(
            kind="missing_asset",
            message=(
                "Missing start image. Provide --start-image-media-id or "
                "--start-image-path; the bridge will not assume an AVATAR row exists."
            ),
            detail={
                "candidate_m5_path": "/Users/balizero/Desktop/logo/zer.jpg",
                "candidate_pro_path": "/Users/nuzantara/Desktop/logo/zer.jpg",
            },
        )

    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        timeout=max(args.timeout, args.video_timeout),
    ) as client:
        project_id = args.project_id or await _ensure_project(
            client,
            name=args.project,
            material=args.material,
            language=args.language,
            timeout_s=args.timeout,
        )
        video_id = args.video_id or await _create_video(
            client,
            project_id=project_id,
            title=args.project,
            orientation=args.orientation,
            timeout_s=args.timeout,
        )
        scene_id = await _create_scene(
            client,
            video_id=video_id,
            scene_id=args.scene_id,
            prompt=args.prompt,
            timeout_s=args.timeout,
        )

        start_image_media_id = args.start_image_media_id
        if not start_image_media_id:
            upload_args = argparse.Namespace(
                image_path=args.start_image_path,
                project_id=project_id,
                project=args.project,
                material=args.material,
                language=args.language,
                file_name=Path(args.start_image_path).name,
                base_url=args.base_url,
                timeout=args.timeout,
            )
            upload = await action_upload_image(upload_args)
            start_image_media_id = upload["media_id"]

        data = await _request_json(
            client,
            "POST",
            "/api/flow/generate-video",
            json_body={
                "start_image_media_id": start_image_media_id,
                "prompt": args.prompt,
                "project_id": project_id,
                "scene_id": scene_id,
                "aspect_ratio": VIDEO_ASPECT_RATIOS[args.orientation],
                "user_paygate_tier": args.paygate_tier,
            },
            timeout_s=args.video_timeout,
        )
        result = _parse_video_response(data)

        if args.dest:
            downloaded = await _download_video_media(
                client,
                media_id=result["video_media_id"],
                dest_path=Path(args.dest).expanduser(),
                timeout_s=args.video_timeout,
                poll_interval_s=args.poll_interval,
            )
            result["local_path"] = str(downloaded)

    result.update(
        {
            "ok": True,
            "action": "generate-video",
            "project_id": project_id,
            "video_id": video_id,
            "scene_id": scene_id,
            "start_image_media_id": start_image_media_id,
            "orientation": args.orientation,
            "paygate_tier": args.paygate_tier,
        }
    )
    return result


def _add_common_http(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)


def _add_common_project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default="mcp-flowkit")
    parser.add_argument("--project-id", default="")
    parser.add_argument("--material", default="realistic")
    parser.add_argument("--language", default="en")
    parser.add_argument("--paygate-tier", default=DEFAULT_PAYGATE_TIER)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FlowKit JSON bridge")
    subparsers = parser.add_subparsers(dest="action", required=True)

    health = subparsers.add_parser("health", help="Check FlowKit readiness")
    _add_common_http(health)

    upload = subparsers.add_parser("upload-image", help="Upload a local image asset")
    _add_common_http(upload)
    _add_common_project(upload)
    upload.add_argument("--image-path", required=True)
    upload.add_argument("--file-name", default="")

    image = subparsers.add_parser("generate-image", help="Generate a Flow image")
    _add_common_http(image)
    _add_common_project(image)
    image.add_argument("--prompt", required=True)
    image.add_argument(
        "--orientation", choices=["PORTRAIT", "LANDSCAPE"], default="PORTRAIT"
    )
    image.add_argument("--dest", default="")

    video = subparsers.add_parser(
        "generate-video", help="Generate a Flow video from a start image"
    )
    _add_common_http(video)
    _add_common_project(video)
    video.add_argument("--prompt", required=True)
    video.add_argument(
        "--orientation", choices=["PORTRAIT", "LANDSCAPE"], default="PORTRAIT"
    )
    video.add_argument("--video-id", default="")
    video.add_argument("--scene-id", default="")
    video.add_argument("--start-image-media-id", default="")
    video.add_argument("--start-image-path", default="")
    video.add_argument("--dest", default="")
    video.add_argument("--video-timeout", type=float, default=DEFAULT_VIDEO_TIMEOUT_S)
    video.add_argument("--poll-interval", type=float, default=10.0)

    return parser


async def run(args: argparse.Namespace) -> JsonDict:
    if args.action == "health":
        return await action_health(args)
    if args.action == "upload-image":
        return await action_upload_image(args)
    if args.action == "generate-image":
        return await action_generate_image(args)
    if args.action == "generate-video":
        return await action_generate_video(args)
    raise FlowKitBridgeError(
        kind="flowkit_error", message=f"Unknown action: {args.action}"
    )


def _legacy_argv(argv: list[str]) -> list[str]:
    """Keep compatibility with the early WIP form: --prompt ... --dest ..."""
    if argv and argv[0].startswith("-"):
        return ["generate-image", *argv]
    return argv


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(_legacy_argv(list(argv or sys.argv[1:])))
    try:
        payload = asyncio.run(run(args))
    except FlowKitBridgeError as exc:
        return _emit(exc.to_payload(), exit_code=2)
    except Exception as exc:  # pragma: no cover - last-resort CLI guard
        kind = _classify_error_text(str(exc))
        return _emit(
            {
                "ok": False,
                "error_kind": kind,
                "error": str(exc),
                "next_action": _next_action_for_kind(kind),
            },
            exit_code=2,
        )
    return _emit(payload, exit_code=0 if payload.get("ok", True) else 2)


if __name__ == "__main__":
    raise SystemExit(main())
