#!/usr/bin/env python3
"""WR3 Flow gateway client — Veo 3.1 Fast Tier_ONE clip generation.

Reuses the FlowKit gateway pattern from WR2 (scripts/wr2_flowkit_client.py).
Veo API is the SINGLE cloud touchpoint in the WR3 hot path. All orchestration
happens locally (Symbiosis Law 6).

Settings:
  endpoint        WR3_FLOWKIT_ENDPOINT (default http://127.0.0.1:8100)
  plan            "pro" (10 cr / clip 720x1280 9:16 8s)
  watchdog        300s wall-clock per clip (Symbiosis Law 4 — degrade-loud on timeout)
  retry policy    up to 2 retries with strengthened prompt; 3rd fail → b-roll-curator fallback

Output:
  apps/war-room/output/episode/<slug>/clips/<n>.mp4
  apps/war-room/output/episode/<slug>/identity-report.json (post-render ArcFace gate handled separately)
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

DEFAULT_ENDPOINT = os.environ.get("WR3_FLOWKIT_ENDPOINT", "http://127.0.0.1:8100")
DEFAULT_PLAN = os.environ.get("WR3_FLOWKIT_PLAN", "pro")
PER_CLIP_TIMEOUT_S = int(os.environ.get("WR3_FLOWKIT_TIMEOUT_S", "300"))


@dataclass(frozen=True)
class ClipRequest:
    shot_index: int
    positive_prompt: str
    negative_prompt: str = ""
    identity_tokens: tuple[str, ...] = ()  # e.g. ("A007-Zantara-anchor",)
    duration_s: int = 8
    resolution: str = "720x1280"  # 9:16 portrait
    aspect: str = "9:16"


@dataclass(frozen=True)
class ClipResult:
    shot_index: int
    mp4_path: Path
    duration_ms: int
    cost_credits: int
    veo_job_id: str
    cascade_used: bool = False


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


async def _download(url: str, dest: Path, timeout_s: int) -> None:
    import urllib.request

    def _do() -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            data = resp.read()
        dest.write_bytes(data)

    await asyncio.to_thread(_do)


async def submit_clip(
    request: ClipRequest,
    *,
    episode_dir: Path,
    endpoint: str = DEFAULT_ENDPOINT,
    plan: str = DEFAULT_PLAN,
    timeout_s: int = PER_CLIP_TIMEOUT_S,
) -> ClipResult:
    """Submit a single Veo clip job. Watchdog timeout enforced by asyncio.wait_for.

    Raises FlowkitTimeoutError on watchdog hit, FlowkitQuotaError on plan exhaust,
    FlowkitError on any other gateway response.
    """
    payload = {
        "plan": plan,
        "tier": "fast_tier_one",
        "shot_index": request.shot_index,
        "positive_prompt": request.positive_prompt,
        "negative_prompt": request.negative_prompt,
        "identity_tokens": list(request.identity_tokens),
        "duration_s": request.duration_s,
        "resolution": request.resolution,
        "aspect": request.aspect,
        "native_audio": False,  # Veo 3.1 Fast — audio assembled post-render
    }
    started = asyncio.get_event_loop().time()
    submit_url = urljoin(endpoint + "/", "v1/clip/submit")
    try:
        resp = await asyncio.wait_for(
            _http_post_json(submit_url, payload, timeout_s=30),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError(
            f"shot {request.shot_index}: gateway submit timeout {timeout_s}s"
        ) from e

    if resp.get("error") == "QUOTA_EXCEEDED":
        raise FlowkitQuotaError(
            f"Flow Pro plan exhausted: {resp.get('detail', '')}"
        )

    veo_job_id = resp.get("job_id")
    download_url = resp.get("mp4_url")
    cost_credits = int(resp.get("cost_credits", 10))
    if not veo_job_id or not download_url:
        raise FlowkitError(f"shot {request.shot_index}: malformed gateway resp {resp}")

    mp4_path = episode_dir / "clips" / f"{request.shot_index:02d}.mp4"
    try:
        await asyncio.wait_for(
            _download(download_url, mp4_path, timeout_s=60),
            timeout=max(60, timeout_s - 30),
        )
    except asyncio.TimeoutError as e:
        raise FlowkitTimeoutError(
            f"shot {request.shot_index}: mp4 download timeout"
        ) from e

    duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
    return ClipResult(
        shot_index=request.shot_index,
        mp4_path=mp4_path,
        duration_ms=duration_ms,
        cost_credits=cost_credits,
        veo_job_id=veo_job_id,
    )


async def render_shot_pack(
    shot_pack_path: Path,
    episode_dir: Path,
    *,
    max_retries_per_shot: int = 2,
    endpoint: str = DEFAULT_ENDPOINT,
    plan: str = DEFAULT_PLAN,
) -> list[ClipResult]:
    """Render every shot in shot-pack.json sequentially.

    On per-shot failure: 2 retries with strengthened prompt. 3rd fail signals
    caller (wr3-clip-renderer agent) to dispatch wr3-b-roll-curator fallback.
    """
    shot_pack = json.loads(shot_pack_path.read_text())
    shots = shot_pack.get("shots") or []
    results: list[ClipResult] = []

    for shot in shots:
        request = ClipRequest(
            shot_index=shot["index"],
            positive_prompt=shot.get("positive_prompt", ""),
            negative_prompt=shot.get("negative_prompt", ""),
            identity_tokens=tuple(shot.get("identity_tokens") or []),
            duration_s=int(shot.get("duration_s", 8)),
            resolution=shot.get("resolution", "720x1280"),
            aspect=shot.get("aspect", "9:16"),
        )

        last_error: Exception | None = None
        for attempt in range(max_retries_per_shot + 1):
            try:
                clip = await submit_clip(
                    request, episode_dir=episode_dir, endpoint=endpoint, plan=plan
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
    print(f"endpoint={DEFAULT_ENDPOINT} plan={DEFAULT_PLAN} timeout_s={PER_CLIP_TIMEOUT_S}", file=sys.stderr)
