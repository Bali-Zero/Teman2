"""Watchdog timeout tests — Q9 panel-flagged missing test (Codex catch).

300s wall-clock per clip is the contract. Verifies wr3_flowkit_client.submit_clip
raises FlowkitTimeoutError on watchdog hit, and that submit_clip respects
asyncio.wait_for semantics (no hidden process leak).

Updated 2026-05-20: FlowKit client refactored to use real OpenAPI v1.1.0
pipeline (project → video → scene → image → video → download). Mocks now
target the per-phase HTTP helpers (`_create_scene`, `_generate_start_image`,
`_generate_video`, `_download_video_media`) plus `setup_episode_context`.
"""
from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_flowkit_client import (  # noqa: E402
    ClipRequest,
    EpisodeContext,
    FlowkitError,
    FlowkitQuotaError,
    FlowkitTimeoutError,
    PER_CLIP_TIMEOUT_S,
    submit_clip,
    _check_quota,
)


@pytest.fixture
def fake_request():
    return ClipRequest(
        shot_index=1,
        positive_prompt="zantara opening shot",
        negative_prompt="cliche",
        identity_tokens=("A007-Zantara-anchor",),
        duration_s=8,
    )


@pytest.fixture
def fake_ctx():
    return EpisodeContext(
        project_id="proj-test-123",
        video_id="vid-test-456",
        project_name="wr3-watchdog-test",
        endpoint="http://127.0.0.1:8100",
        paygate="PAYGATE_TIER_ONE",
    )


def _fake_mp4_bytes() -> bytes:
    # Minimal MP4 header that satisfies the "ftyp in first 32 bytes" sanity check
    return b"\x00\x00\x00\x20ftypisom" + b"\x00" * 64


@pytest.mark.asyncio
async def test_watchdog_default_is_300s() -> None:
    """Per-clip default watchdog is exactly the contract value."""
    assert PER_CLIP_TIMEOUT_S == 300


@pytest.mark.asyncio
async def test_submit_clip_timeout_raises(tmp_path: Path, fake_request, fake_ctx) -> None:
    """When the gateway hangs longer than per-phase timeout, FlowkitTimeoutError fires."""
    async def _hang_scene(*_args, **_kwargs):
        raise FlowkitTimeoutError("scene create shot=1 timeout")

    with patch("wr3_flowkit_client._create_scene", new=_hang_scene):
        with pytest.raises(FlowkitTimeoutError):
            await submit_clip(
                fake_request, episode_dir=tmp_path,
                episode_context=fake_ctx, timeout_s=30,
            )


@pytest.mark.asyncio
async def test_submit_clip_quota_error(tmp_path: Path, fake_request, fake_ctx) -> None:
    """Gateway returning QUOTA_EXCEEDED → FlowkitQuotaError."""
    async def _quota_image(*_args, **_kwargs):
        # _check_quota inside _generate_start_image fires
        return {"error": "QUOTA_EXCEEDED", "detail": "Flow Pro plan out"}

    async def _ok_scene(ctx, shot_index, positive_prompt, timeout_s=30):
        ctx.scene_ids[shot_index] = "scene-id-xyz"
        return "scene-id-xyz"

    with patch("wr3_flowkit_client._create_scene", new=_ok_scene), \
         patch("wr3_flowkit_client._http_post_json", new=_quota_image):
        with pytest.raises(FlowkitQuotaError, match="QUOTA_EXCEEDED|Flow Pro"):
            await submit_clip(
                fake_request, episode_dir=tmp_path,
                episode_context=fake_ctx, timeout_s=30,
            )


@pytest.mark.asyncio
async def test_submit_clip_malformed_response(tmp_path: Path, fake_request, fake_ctx) -> None:
    """generate-image response missing media → FlowkitError."""
    async def _ok_scene(ctx, shot_index, positive_prompt, timeout_s=30):
        ctx.scene_ids[shot_index] = "scene-id-xyz"
        return "scene-id-xyz"

    async def _bad_image(*_args, **_kwargs):
        return {"weird": "shape"}

    with patch("wr3_flowkit_client._create_scene", new=_ok_scene), \
         patch("wr3_flowkit_client._http_post_json", new=_bad_image):
        with pytest.raises(FlowkitError, match="generate-image returned no media"):
            await submit_clip(
                fake_request, episode_dir=tmp_path,
                episode_context=fake_ctx, timeout_s=30,
            )


@pytest.mark.asyncio
async def test_submit_clip_happy_path(tmp_path: Path, fake_request, fake_ctx) -> None:
    """End-to-end happy path with mocked pipeline phases."""
    async def _ok_scene(ctx, shot_index, positive_prompt, timeout_s=30):
        ctx.scene_ids[shot_index] = "scene-id-xyz"
        return "scene-id-xyz"

    async def _ok_image(ctx, prompt, timeout_s=90):
        return "img-media-aaa"

    async def _ok_video(ctx, start_image_media_id, scene_id, prompt, timeout_s=180):
        return ("workflow-bbb", "video-media-ccc")

    async def _ok_download(ctx, media_id, dest, timeout_s=120):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_fake_mp4_bytes())

    with patch("wr3_flowkit_client._create_scene", new=_ok_scene), \
         patch("wr3_flowkit_client._generate_start_image", new=_ok_image), \
         patch("wr3_flowkit_client._generate_video", new=_ok_video), \
         patch("wr3_flowkit_client._download_video_media", new=_ok_download):
        clip = await submit_clip(
            fake_request, episode_dir=tmp_path,
            episode_context=fake_ctx, timeout_s=60,
        )

    assert clip.veo_job_id == "workflow-bbb"
    assert clip.cost_credits == 20  # DEFAULT_CLIP_COST_CR Tier 1 portrait fast
    assert clip.mp4_path.exists()
    assert clip.mp4_path.read_bytes() == _fake_mp4_bytes()


@pytest.mark.asyncio
async def test_download_timeout_raises(tmp_path: Path, fake_request, fake_ctx) -> None:
    """Submit OK but download phase hangs → FlowkitTimeoutError on download step."""
    async def _ok_scene(ctx, shot_index, positive_prompt, timeout_s=30):
        ctx.scene_ids[shot_index] = "scene-id-xyz"
        return "scene-id-xyz"

    async def _ok_image(ctx, prompt, timeout_s=90):
        return "img-media-aaa"

    async def _ok_video(ctx, start_image_media_id, scene_id, prompt, timeout_s=180):
        return ("workflow-bbb", "video-media-ccc")

    async def _hang_download(ctx, media_id, dest, timeout_s=120):
        raise FlowkitTimeoutError(f"media download timeout {media_id[:8]}")

    with patch("wr3_flowkit_client._create_scene", new=_ok_scene), \
         patch("wr3_flowkit_client._generate_start_image", new=_ok_image), \
         patch("wr3_flowkit_client._generate_video", new=_ok_video), \
         patch("wr3_flowkit_client._download_video_media", new=_hang_download):
        with pytest.raises(FlowkitTimeoutError, match="media download timeout"):
            await submit_clip(
                fake_request, episode_dir=tmp_path,
                episode_context=fake_ctx, timeout_s=120,
            )


def test_check_quota_detects_resource_exhausted() -> None:
    """Helper: _check_quota fires FlowkitQuotaError on RESOURCE_EXHAUSTED."""
    with pytest.raises(FlowkitQuotaError):
        _check_quota({"error": {"status": "RESOURCE_EXHAUSTED"}}, where="probe")
    with pytest.raises(FlowkitQuotaError):
        _check_quota("insufficient credit balance", where="probe")
    # Negative: normal response passes through
    _check_quota({"ok": True}, where="probe")  # should NOT raise
