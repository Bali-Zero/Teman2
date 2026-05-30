"""Anchor start-image i2v tests (2026-05-30 identity-gate fix).

Root cause: when a shot has no start_image_media_id, submit_clip generated the
i2v start image FROM THE TEXT PROMPT, so Veo rendered a generic woman instead of
the A007 Zantara anchor → ArcFace cosine ~0.12, identity gate 0/18.

Fix: an EpisodeContext.anchor_image_path uploads the anchor PNG once via
/api/flow/upload-image and uses that media_id as the i2v start image for every
shot (verified cosine 0.91, gate PASS). These tests pin the contract:

- anchor present → uploaded once, used as start image, _generate_start_image NOT called
- explicit per-shot start_image_media_id still wins
- no anchor → text-prompt path preserved (no regression for faceless episodes)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_flowkit_client import (  # noqa: E402
    ClipRequest,
    EpisodeContext,
    FlowkitError,
    submit_clip,
)


def _ctx(anchor: str | None = None) -> EpisodeContext:
    return EpisodeContext(
        project_id="proj-1",
        video_id="vid-1",
        project_name="wr3-anchor-test",
        endpoint="http://127.0.0.1:8100",
        paygate="PAYGATE_TIER_TIER1P5",
        anchor_image_path=anchor,
    )


def _req(idx: int = 1, start_image: str | None = None) -> ClipRequest:
    return ClipRequest(
        shot_index=idx,
        positive_prompt="Zantara, woman ~35, mediterranean features",
        identity_tokens=("A007",),
        start_image_media_id=start_image,
    )


def _mp4() -> bytes:
    return b"\x00\x00\x00\x20ftypisom" + b"\x00" * 64


async def _ok_scene(ctx, *, shot_index, positive_prompt, timeout_s=30):
    return f"scene-{shot_index}"


async def _ok_video(ctx, *, start_image_media_id, scene_id, prompt, timeout_s=180):
    # echo the start image id back so the test can assert which id Veo received
    return (f"wf-{start_image_media_id}", f"vmedia-{start_image_media_id}")


async def _ok_download(ctx, *, media_id, dest, timeout_s=120, poll_interval_s=10):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_mp4())


@pytest.mark.asyncio
async def test_anchor_uploaded_and_used_as_start_image(tmp_path: Path) -> None:
    ctx = _ctx(anchor="/abs/zantara-face-anchor-v1.png")
    upload = AsyncMock(return_value="anchor-media-xyz")
    gen_img = AsyncMock(return_value="should-not-be-used")
    captured = {}

    async def _capture_video(c, *, start_image_media_id, scene_id, prompt, timeout_s=180):
        captured["start"] = start_image_media_id
        return ("wf", "vmedia")

    with patch("wr3_flowkit_client._create_scene", new=_ok_scene), \
         patch("wr3_flowkit_client._upload_image_asset", new=upload), \
         patch("wr3_flowkit_client._generate_start_image", new=gen_img), \
         patch("wr3_flowkit_client._generate_video", new=_capture_video), \
         patch("wr3_flowkit_client._download_video_media", new=_ok_download):
        await submit_clip(_req(), episode_dir=tmp_path, episode_context=ctx)

    assert captured["start"] == "anchor-media-xyz"
    upload.assert_awaited_once()
    assert ctx.anchor_media_id == "anchor-media-xyz"
    gen_img.assert_not_awaited()


@pytest.mark.asyncio
async def test_anchor_uploaded_once_across_shots(tmp_path: Path) -> None:
    ctx = _ctx(anchor="/abs/anchor.png")
    upload = AsyncMock(return_value="anchor-media-1")

    with patch("wr3_flowkit_client._create_scene", new=_ok_scene), \
         patch("wr3_flowkit_client._upload_image_asset", new=upload), \
         patch("wr3_flowkit_client._generate_video", new=_ok_video), \
         patch("wr3_flowkit_client._download_video_media", new=_ok_download):
        for i in range(1, 4):
            await submit_clip(_req(idx=i), episode_dir=tmp_path, episode_context=ctx)

    upload.assert_awaited_once()  # cached on ctx.anchor_media_id after first shot


@pytest.mark.asyncio
async def test_explicit_start_image_wins_over_anchor(tmp_path: Path) -> None:
    ctx = _ctx(anchor="/abs/anchor.png")
    upload = AsyncMock(return_value="anchor-media")
    captured = {}

    async def _capture_video(c, *, start_image_media_id, scene_id, prompt, timeout_s=180):
        captured["start"] = start_image_media_id
        return ("wf", "vmedia")

    with patch("wr3_flowkit_client._create_scene", new=_ok_scene), \
         patch("wr3_flowkit_client._upload_image_asset", new=upload), \
         patch("wr3_flowkit_client._generate_video", new=_capture_video), \
         patch("wr3_flowkit_client._download_video_media", new=_ok_download):
        await submit_clip(_req(start_image="explicit-id-999"),
                          episode_dir=tmp_path, episode_context=ctx)

    assert captured["start"] == "explicit-id-999"
    upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_anchor_falls_back_to_text_prompt(tmp_path: Path) -> None:
    ctx = _ctx(anchor=None)
    gen_img = AsyncMock(return_value="text-generated-img")
    upload = AsyncMock(return_value="should-not-upload")
    captured = {}

    async def _capture_video(c, *, start_image_media_id, scene_id, prompt, timeout_s=180):
        captured["start"] = start_image_media_id
        return ("wf", "vmedia")

    with patch("wr3_flowkit_client._create_scene", new=_ok_scene), \
         patch("wr3_flowkit_client._generate_start_image", new=gen_img), \
         patch("wr3_flowkit_client._upload_image_asset", new=upload), \
         patch("wr3_flowkit_client._generate_video", new=_capture_video), \
         patch("wr3_flowkit_client._download_video_media", new=_ok_download):
        await submit_clip(_req(), episode_dir=tmp_path, episode_context=ctx)

    assert captured["start"] == "text-generated-img"
    gen_img.assert_awaited_once()
    upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_render_shot_pack_reads_anchor_from_root(tmp_path: Path) -> None:
    import json

    from wr3_flowkit_client import render_shot_pack

    shot_pack = {
        "episode_id": "anchor-root-test",
        "anchor_image_path": "/abs/from-root.png",
        "shots": [],  # empty → no rendering, just verify ctx gets the anchor
    }
    sp_path = tmp_path / "shot-pack.json"
    sp_path.write_text(json.dumps(shot_pack))
    ctx = _ctx(anchor=None)

    await render_shot_pack(sp_path, tmp_path, episode_context=ctx)

    assert ctx.anchor_image_path == "/abs/from-root.png"


@pytest.mark.asyncio
async def test_upload_image_asset_raises_on_no_media_id(tmp_path: Path) -> None:
    from wr3_flowkit_client import _upload_image_asset

    async def _no_media(url, body, timeout_s):
        return {"raw": {}}  # no media_id

    ctx = _ctx()
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG")
    with patch("wr3_flowkit_client._http_post_json", new=_no_media):
        with pytest.raises(FlowkitError, match="upload|media_id"):
            await _upload_image_asset(ctx, image_path=img)
