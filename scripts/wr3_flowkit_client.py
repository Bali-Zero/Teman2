#!/usr/bin/env python3
"""WR3 Flow gateway client — Veo 3.1 Fast Tier_ONE clip generation.

Speaks to the live FlowKit gateway API (OpenAPI v1.1.0) running locally on
http://127.0.0.1:8100. Veo API is the SINGLE cloud touchpoint in the WR3 hot
path. All orchestration happens locally (Symbiosis Law 6).

Pipeline per episode (4 steps, all synchronous on portrait fast tier):

  1. setup_episode_context(name)
       → POST /api/projects          → project_id
       → POST /api/videos             → video_id
     Returns EpisodeContext (re-used across all shots).

  2. submit_clip(request, episode_context)
       per shot:
       2a. POST /api/scenes                  → scene_id
       2b. POST /api/flow/generate-image     → start_image media_id (synchronous)
       2c. POST /api/flow/generate-video     → workflow + media (synchronous on
                                                veo_3_1_i2v_s_fast_portrait Tier 1)
       2d. GET  /api/flow/media/<media_id>   → JSON {video:{encodedVideo: base64}}
       2e. base64-decode → write episode_dir/clips/NN.mp4

Settings:
  endpoint        WR3_FLOWKIT_ENDPOINT (default http://127.0.0.1:8100)
  paygate         WR3_FLOWKIT_PAYGATE   (default PAYGATE_TIER_ONE — 20 cr/clip)
  watchdog        300s wall-clock per clip (Symbiosis Law 4 — degrade-loud on timeout)
  retry policy    up to 2 retries with strengthened prompt; 3rd fail → b-roll-curator fallback

Output:
  apps/war-room/output/episode/<slug>/clips/<n>.mp4
  apps/war-room/output/episode/<slug>/_flowkit_context.json  (project_id, video_id, per-shot scenes)
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

DEFAULT_ENDPOINT = os.environ.get("WR3_FLOWKIT_ENDPOINT", "http://127.0.0.1:8100")
DEFAULT_PAYGATE = os.environ.get("WR3_FLOWKIT_PAYGATE", "PAYGATE_TIER_ONE")
PER_CLIP_TIMEOUT_S = int(os.environ.get("WR3_FLOWKIT_TIMEOUT_S", "300"))
# Tier 1 fast portrait: 20 credits/clip (empirical 2026-05-20).
DEFAULT_CLIP_COST_CR = int(os.environ.get("WR3_FLOWKIT_CLIP_COST", "20"))

# Backwards-compat alias — older callers passed plan="pro".
DEFAULT_PLAN = DEFAULT_PAYGATE


@dataclass(frozen=True)
class ClipRequest:
    shot_index: int
    positive_prompt: str
    negative_prompt: str = ""
    identity_tokens: tuple[str, ...] = ()  # e.g. ("A007-Zantara-anchor",)
    duration_s: int = 8
    resolution: str = "720x1280"  # 9:16 portrait
    aspect: str = "9:16"
    # Optional pre-generated start image media_id. When None the client
    # generates one via /api/flow/generate-image from positive_prompt.
    start_image_media_id: str | None = None
    image_prompt: str | None = None  # used if start_image_media_id is None


@dataclass(frozen=True)
class ClipResult:
    shot_index: int
    mp4_path: Path
    duration_ms: int
    cost_credits: int
    veo_job_id: str
    cascade_used: bool = False


@dataclass
class EpisodeContext:
    """Holds the FlowKit project+video IDs shared across all shots of one episode.

    Created once by setup_episode_context() at the start of an episode run,
    then passed to every submit_clip() invocation. Persisted to disk at
    episode_dir/_flowkit_context.json so reruns can resume without re-creating
    Flow resources.
    """
    project_id: str
    video_id: str
    project_name: str
    endpoint: str
    paygate: str
    scene_ids: dict[int, str] = field(default_factory=dict)  # shot_index → scene_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "video_id": self.video_id,
            "project_name": self.project_name,
            "endpoint": self.endpoint,
            "paygate": self.paygate,
            "scene_ids": {str(k): v for k, v in self.scene_ids.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpisodeContext":
        return cls(
            project_id=data["project_id"],
            video_id=data["video_id"],
            project_name=data["project_name"],
            endpoint=data.get("endpoint", DEFAULT_ENDPOINT),
            paygate=data.get("paygate", DEFAULT_PAYGATE),
            scene_ids={int(k): v for k, v in (data.get("scene_ids") or {}).items()},
        )


class FlowkitError(Exception):
    """Base for flowkit-layer errors."""


class FlowkitTimeoutError(FlowkitError):
    """Watchdog 300s exceeded for one clip."""


class FlowkitQuotaError(FlowkitError):
    """Flow Pro plan quota exceeded. Episode parked, Telegram P0 fires."""


async def _http_post_json(
    url: str, payload: dict[str, Any], timeout_s: int
) -> dict[str, Any]:
    """Minimal JSON POST using stdlib + asyncio.to_thread (no httpx import for parity)."""
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    def _do() -> dict[str, Any]:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return await asyncio.to_thread(_do)


async def _http_get_json(url: str, timeout_s: int) -> dict[str, Any]:
    import urllib.request

    def _do() -> dict[str, Any]:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return await asyncio.to_thread(_do)


async def _http_get_bytes(url: str, timeout_s: int) -> bytes:
    import urllib.request

    def _do() -> bytes:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return resp.read()

    return await asyncio.to_thread(_do)


def _check_quota(resp_body: str | dict, *, where: str) -> None:
    """Detect quota/credit-exhausted upstream errors. Raises FlowkitQuotaError.

    Only fires on EXPLICIT error markers. Substring match on bare "credit" is
    too broad — successful responses include {"remainingCredits": N} which
    must not trigger quota path. We check (a) {"error": ...} envelope and
    (b) explicit quota tokens, never naked "credit".
    """
    # String inputs (legacy upstream message body) — keep tight signal list.
    if isinstance(resp_body, str):
        text = resp_body
        tight = ("QUOTA_EXCEEDED", "RESOURCE_EXHAUSTED", "insufficient credit", "insufficient_funds")
        if any(n.lower() in text.lower() for n in tight):
            raise FlowkitQuotaError(f"{where}: {text[:200]}")
        return

    # Dict input — only inspect the {"error": …} envelope, never the success body.
    err_block = resp_body.get("error") if isinstance(resp_body, dict) else None
    if not err_block:
        return
    err_text = json.dumps(err_block).lower() if isinstance(err_block, dict) else str(err_block).lower()
    tight = ("quota_exceeded", "resource_exhausted", "insufficient credit", "insufficient_funds", "quota")
    if any(n in err_text for n in tight):
        raise FlowkitQuotaError(f"{where}: {err_text[:200]}")


# ---------------------------------------------------------------------------
# Step 1 — per-episode project + video setup (call once per episode)
# ---------------------------------------------------------------------------


async def setup_episode_context(
    name: str,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    paygate: str = DEFAULT_PAYGATE,
    timeout_s: int = 30,
) -> EpisodeContext:
    """Create the FlowKit project + video shell for ONE episode.

    Returns EpisodeContext to thread through every subsequent submit_clip call.
    """
    # 1a. Create project — minimal body. Empirical 2026-05-20: passing
    # tool_name / material / allow_* causes upstream Google Flow API to return
    # 502 "Failed to parse Flow response: 'result'". Defaults applied server-side.
    project_url = urljoin(endpoint + "/", "api/projects")
    project_body: dict[str, Any] = {"name": name}
    try:
        proj_resp = await asyncio.wait_for(
            _http_post_json(project_url, project_body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError(f"project create timeout {timeout_s}s") from e

    project_id = proj_resp.get("id")
    if not project_id:
        raise FlowkitError(f"project create returned no id: {proj_resp}")

    # 1b. Create video shell — only fields we actually need at this point.
    video_url = urljoin(endpoint + "/", "api/videos")
    video_body: dict[str, Any] = {
        "project_id": project_id,
        "title": name,
        "orientation": "VERTICAL",
    }
    try:
        vid_resp = await asyncio.wait_for(
            _http_post_json(video_url, video_body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError(f"video create timeout {timeout_s}s") from e

    video_id = vid_resp.get("id")
    if not video_id:
        raise FlowkitError(f"video create returned no id: {vid_resp}")

    return EpisodeContext(
        project_id=project_id,
        video_id=video_id,
        project_name=name,
        endpoint=endpoint,
        paygate=paygate,
    )


async def _create_scene(
    ctx: EpisodeContext,
    *,
    shot_index: int,
    positive_prompt: str,
    timeout_s: int = 30,
) -> str:
    """POST /api/scenes — returns scene_id. Caches on EpisodeContext.scene_ids."""
    if shot_index in ctx.scene_ids:
        return ctx.scene_ids[shot_index]

    url = urljoin(ctx.endpoint + "/", "api/scenes")
    body = {
        "video_id": ctx.video_id,
        "display_order": shot_index,
        "prompt": positive_prompt,
        "chain_type": "ROOT",
    }
    try:
        resp = await asyncio.wait_for(
            _http_post_json(url, body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError(f"scene create shot={shot_index} timeout") from e

    scene_id = resp.get("id")
    if not scene_id:
        raise FlowkitError(f"scene create returned no id shot={shot_index}: {resp}")
    ctx.scene_ids[shot_index] = scene_id
    return scene_id


async def _generate_start_image(
    ctx: EpisodeContext,
    *,
    prompt: str,
    timeout_s: int = 90,
) -> str:
    """POST /api/flow/generate-image — returns media_id (synchronous response)."""
    url = urljoin(ctx.endpoint + "/", "api/flow/generate-image")
    body = {
        "prompt": prompt,
        "project_id": ctx.project_id,
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "user_paygate_tier": ctx.paygate,
    }
    try:
        resp = await asyncio.wait_for(
            _http_post_json(url, body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError("generate-image timeout") from e

    _check_quota(resp, where="generate-image")

    media = resp.get("media") or []
    if not media or not media[0].get("name"):
        raise FlowkitError(f"generate-image returned no media: {str(resp)[:200]}")
    return media[0]["name"]


async def _generate_video(
    ctx: EpisodeContext,
    *,
    start_image_media_id: str,
    scene_id: str,
    prompt: str,
    timeout_s: int = 180,
) -> tuple[str, str]:
    """POST /api/flow/generate-video — returns (workflow_id, video_media_id).

    Veo 3.1 Fast Tier_ONE portrait is synchronous → media is ready
    immediately upon HTTP 200. No polling required for this tier.
    """
    url = urljoin(ctx.endpoint + "/", "api/flow/generate-video")
    body = {
        "start_image_media_id": start_image_media_id,
        "prompt": prompt,
        "project_id": ctx.project_id,
        "scene_id": scene_id,
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "user_paygate_tier": ctx.paygate,
    }
    try:
        resp = await asyncio.wait_for(
            _http_post_json(url, body, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError("generate-video timeout") from e

    _check_quota(resp, where="generate-video")

    workflows = resp.get("workflows") or []
    media = resp.get("media") or []
    if not workflows or not media:
        raise FlowkitError(f"generate-video missing workflows/media: {str(resp)[:200]}")
    workflow_id = workflows[0].get("name") or workflows[0].get("id") or ""
    video_media_id = media[0].get("name") or ""
    if not video_media_id:
        raise FlowkitError(f"generate-video no media_id: {str(resp)[:200]}")
    return workflow_id, video_media_id


async def _download_video_media(
    ctx: EpisodeContext,
    *,
    media_id: str,
    dest: Path,
    timeout_s: int = 120,
) -> None:
    """GET /api/flow/media/<media_id> → JSON {video:{encodedVideo: base64}} → MP4."""
    url = urljoin(ctx.endpoint + "/", f"api/flow/media/{media_id}")
    try:
        payload = await asyncio.wait_for(
            _http_get_json(url, timeout_s=timeout_s),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError(f"media download timeout {media_id[:8]}") from e

    video = payload.get("video") or {}
    encoded = video.get("encodedVideo")
    if not encoded:
        raise FlowkitError(
            f"media {media_id[:8]} has no encodedVideo. "
            f"Keys present: {list(payload.keys())}, video keys: {list(video.keys())}"
        )

    try:
        mp4_bytes = base64.b64decode(encoded)
    except Exception as e:
        raise FlowkitError(f"media {media_id[:8]} base64 decode failed: {e}") from e

    # Sanity: ISO Media MP4 starts with "ftyp" at offset 4
    if len(mp4_bytes) < 32 or b"ftyp" not in mp4_bytes[:32]:
        raise FlowkitError(
            f"media {media_id[:8]} decoded bytes don't look like MP4 (len={len(mp4_bytes)})"
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(mp4_bytes)


# ---------------------------------------------------------------------------
# Step 2 — per-shot pipeline
# ---------------------------------------------------------------------------


async def submit_clip(
    request: ClipRequest,
    *,
    episode_dir: Path,
    episode_context: EpisodeContext | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
    paygate: str = DEFAULT_PAYGATE,
    timeout_s: int = PER_CLIP_TIMEOUT_S,
    # Legacy kwarg — older callers passed plan="pro". We map to paygate Tier 1.
    plan: str | None = None,
) -> ClipResult:
    """Submit a single Veo clip job. Watchdog timeout enforced by asyncio.wait_for.

    Raises FlowkitTimeoutError on watchdog hit, FlowkitQuotaError on plan exhaust,
    FlowkitError on any other gateway response.

    episode_context MUST be provided in real use. The legacy single-call
    path (no context) is preserved for tests by lazily creating a throwaway
    project — but in production wr3-clip-renderer creates the context once
    upstream and threads it through.
    """
    if plan is not None and paygate == DEFAULT_PAYGATE:
        # legacy plan="pro" → Tier 1
        paygate = DEFAULT_PAYGATE

    if episode_context is None:
        # Lazy fallback — should NOT be hit in production. Logged via stderr.
        import sys as _sys
        print(
            f"[wr3-flowkit] WARN: submit_clip called without episode_context — "
            f"creating throwaway project for shot {request.shot_index}",
            file=_sys.stderr,
        )
        episode_context = await setup_episode_context(
            name=f"wr3-throwaway-{request.shot_index}",
            endpoint=endpoint,
            paygate=paygate,
        )

    started = asyncio.get_event_loop().time()

    # 2a. Scene (one per shot index)
    scene_id = await _create_scene(
        episode_context,
        shot_index=request.shot_index,
        positive_prompt=request.positive_prompt,
        timeout_s=30,
    )

    # 2b. Start image — either pre-supplied or generated from image_prompt
    if request.start_image_media_id:
        start_image_id = request.start_image_media_id
    else:
        img_prompt = request.image_prompt or request.positive_prompt
        start_image_id = await _generate_start_image(
            episode_context, prompt=img_prompt, timeout_s=90,
        )

    # 2c. Video generation (synchronous on portrait fast Tier 1)
    workflow_id, video_media_id = await _generate_video(
        episode_context,
        start_image_media_id=start_image_id,
        scene_id=scene_id,
        prompt=request.positive_prompt,
        timeout_s=min(timeout_s - 30, 180),
    )

    # 2d-e. Download base64 → MP4
    mp4_path = episode_dir / "clips" / f"{request.shot_index:02d}.mp4"
    await _download_video_media(
        episode_context,
        media_id=video_media_id,
        dest=mp4_path,
        timeout_s=120,
    )

    duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
    return ClipResult(
        shot_index=request.shot_index,
        mp4_path=mp4_path,
        duration_ms=duration_ms,
        cost_credits=DEFAULT_CLIP_COST_CR,
        veo_job_id=workflow_id,
    )


async def render_shot_pack(
    shot_pack_path: Path,
    episode_dir: Path,
    *,
    episode_context: EpisodeContext | None = None,
    max_retries_per_shot: int = 2,
    endpoint: str = DEFAULT_ENDPOINT,
    paygate: str = DEFAULT_PAYGATE,
    # Legacy
    plan: str | None = None,
) -> list[ClipResult]:
    """Render every shot in shot-pack.json sequentially.

    On per-shot failure: 2 retries with strengthened prompt. 3rd fail signals
    caller (wr3-clip-renderer agent) to dispatch wr3-b-roll-curator fallback.

    Creates a per-episode FlowKit project+video if episode_context is None
    (derives name from shot-pack JSON or path stem).
    """
    shot_pack = json.loads(shot_pack_path.read_text())
    shots = shot_pack.get("shots") or []
    results: list[ClipResult] = []

    if episode_context is None:
        episode_name = (
            shot_pack.get("episode_id")
            or shot_pack.get("topic", "")[:60]
            or episode_dir.name
            or f"wr3-{shot_pack_path.stem}"
        )
        episode_context = await setup_episode_context(
            name=episode_name, endpoint=endpoint, paygate=paygate,
        )
        # Persist context for resume
        ctx_path = episode_dir / "_flowkit_context.json"
        ctx_path.parent.mkdir(parents=True, exist_ok=True)
        ctx_path.write_text(json.dumps(episode_context.to_dict(), indent=2))

    for shot in shots:
        request = ClipRequest(
            shot_index=shot["index"],
            positive_prompt=shot.get("positive_prompt", ""),
            negative_prompt=shot.get("negative_prompt", ""),
            identity_tokens=tuple(shot.get("identity_tokens") or []),
            duration_s=int(shot.get("duration_s", 8)),
            resolution=shot.get("resolution", "720x1280"),
            aspect=shot.get("aspect", "9:16"),
            start_image_media_id=shot.get("start_image_media_id"),
            image_prompt=shot.get("image_prompt"),
        )

        last_error: Exception | None = None
        for attempt in range(max_retries_per_shot + 1):
            try:
                clip = await submit_clip(
                    request,
                    episode_dir=episode_dir,
                    episode_context=episode_context,
                    endpoint=endpoint,
                    paygate=paygate,
                )
                results.append(clip)
                break
            except FlowkitQuotaError:
                raise  # bubble up to clip-renderer for Telegram P0
            except FlowkitError as e:
                last_error = e
                if attempt == max_retries_per_shot:
                    raise FlowkitError(
                        f"shot {request.shot_index} failed {attempt+1} attempts; "
                        f"b-roll-curator fallback required. last_error={last_error}"
                    ) from e
        else:
            assert last_error is not None
            raise last_error

    return results


if __name__ == "__main__":
    import sys

    print("WR3 Flowkit client — stub smoke test", file=sys.stderr)
    print(f"endpoint={DEFAULT_ENDPOINT} paygate={DEFAULT_PAYGATE} timeout_s={PER_CLIP_TIMEOUT_S}", file=sys.stderr)
