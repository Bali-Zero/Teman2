"""Regression tests for FlowKit's single-field video prompt contract."""

from __future__ import annotations

import json
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
    FlowkitGenerationAmbiguousError,
    FlowkitRetrievalError,
    FlowkitTimeoutError,
    _compose_flow_prompt,
    render_shot_pack,
    submit_clip,
)


def test_compose_flow_prompt_leaves_positive_unchanged_when_negative_empty() -> None:
    positive = "  Preserve this positive prompt exactly.  "

    assert _compose_flow_prompt(positive, "") == positive
    assert _compose_flow_prompt(positive, "   \n") == positive


def test_compose_flow_prompt_appends_negative_constraints_exactly_once() -> None:
    positive = "Zantara crosses a quiet threshold in one continuous move."
    negative = "visible text, camera overlays, framing guides"
    expected = f"{positive}\nThe generated video must avoid {negative}."

    composed = _compose_flow_prompt(positive, negative)

    assert composed == expected
    assert composed.count(negative) == 1
    assert _compose_flow_prompt(composed, negative) == composed


@pytest.mark.asyncio
async def test_submit_clip_sends_positive_and_negative_in_exact_flow_http_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real submit call chain must put both fields into Flow's one prompt."""
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    captured: dict[str, object] = {}
    positive = "A measured forward track follows Zantara through warm daylight."
    negative = "visible text, camera UI, aspect-ratio labels"

    context = EpisodeContext(
        project_id="project-1",
        video_id="video-1",
        project_name="prompt-composition-test",
        endpoint="http://127.0.0.1:8100",
        paygate="PAYGATE_TIER_TIER1P5",
    )
    request = ClipRequest(
        shot_index=2,
        positive_prompt=positive,
        negative_prompt=negative,
        start_image_media_id="anchor-media-1",
    )

    async def _scene(
        ctx: EpisodeContext,
        *,
        shot_index: int,
        positive_prompt: str,
        timeout_s: int = 30,
    ) -> str:
        return "scene-2"

    async def _post(
        url: str, payload: dict[str, object], timeout_s: int
    ) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        return {
            "workflows": [{"name": "workflow-2"}],
            "media": [{"name": "video-media-2"}],
        }

    async def _download(
        ctx: EpisodeContext,
        *,
        media_id: str,
        dest: Path,
        timeout_s: int = 120,
        poll_interval_s: int = 10,
        workflow_id: str | None = None,
    ) -> None:
        captured["download_workflow_id"] = workflow_id
        captured["download_media_id"] = media_id
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 64)

    with (
        patch("wr3_flowkit_client._create_scene", new=_scene),
        patch("wr3_flowkit_client._http_post_json", new=_post),
        patch("wr3_flowkit_client._download_video_media", new=_download),
        patch("wr3_flowkit_client.assert_spend_authorized"),
        patch("wr3_flowkit_client.record_spend"),
    ):
        await submit_clip(request, episode_dir=tmp_path, episode_context=context)

    assert captured["url"] == "http://127.0.0.1:8100/api/flow/generate-video"
    assert captured["payload"] == {
        "start_image_media_id": "anchor-media-1",
        "prompt": (f"{positive}\nThe generated video must avoid {negative}."),
        "project_id": "project-1",
        "scene_id": "scene-2",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "user_paygate_tier": "PAYGATE_TIER_TIER1P5",
    }
    assert captured["download_workflow_id"] == "workflow-2"
    assert captured["download_media_id"] == "video-media-2"


@pytest.mark.asyncio
async def test_render_shot_pack_never_resubmits_after_generation_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retrieval error is a recovery boundary, not a generation retry."""
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    calls = {"generate": 0, "download": 0}
    shot_pack_path = tmp_path / "shot-pack.json"
    shot_pack_path.write_text(
        json.dumps(
            {
                "episode_id": "no-resubmit-regression",
                "shots": [
                    {
                        "index": 7,
                        "positive_prompt": "One approved movement.",
                        "start_image_media_id": "start-media-7",
                    }
                ],
            }
        )
    )
    context = EpisodeContext(
        project_id="project-7",
        video_id="video-7",
        project_name="no-resubmit-regression",
        endpoint="http://127.0.0.1:8100",
        paygate="PAYGATE_TIER_TIER1P5",
    )

    async def _scene(*_args, **_kwargs) -> str:
        return "scene-7"

    async def _generate(*_args, **_kwargs) -> tuple[str, str]:
        calls["generate"] += 1
        return "workflow-7", "video-media-7"

    async def _download(*_args, **kwargs) -> None:
        calls["download"] += 1
        assert kwargs["workflow_id"] == "workflow-7"
        assert kwargs["media_id"] == "video-media-7"
        raise FlowkitTimeoutError("signed URL not yet available")

    with (
        patch("wr3_flowkit_client._create_scene", new=_scene),
        patch("wr3_flowkit_client._generate_video", new=_generate),
        patch("wr3_flowkit_client._download_video_media", new=_download),
    ):
        with pytest.raises(
            FlowkitRetrievalError,
            match="recover the existing workflow and do not resubmit",
        ) as exc_info:
            await render_shot_pack(
                shot_pack_path,
                tmp_path,
                episode_context=context,
                max_retries_per_shot=2,
            )

    assert calls == {"generate": 1, "download": 1}
    assert exc_info.value.workflow_id == "workflow-7"
    assert exc_info.value.media_id == "video-media-7"


@pytest.mark.asyncio
async def test_render_shot_pack_never_resubmits_ambiguous_generate_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dispatched charging POST without IDs is never a safe retry."""
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    shot_pack_path = tmp_path / "shot-pack.json"
    shot_pack_path.write_text(
        json.dumps(
            {
                "episode_id": "ambiguous-generate-regression",
                "shots": [{"index": 8, "positive_prompt": "One charged boundary."}],
            }
        )
    )
    context = EpisodeContext(
        project_id="project-8",
        video_id="video-8",
        project_name="ambiguous-generate-regression",
        endpoint="http://127.0.0.1:8100",
        paygate="PAYGATE_TIER_TIER1P5",
    )
    calls = 0

    async def ambiguous_submit(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise FlowkitGenerationAmbiguousError(
            project_id="project-8",
            scene_id="scene-8",
            cause=TimeoutError("gateway response lost"),
        )

    monkeypatch.setattr("wr3_flowkit_client.submit_clip", ambiguous_submit)

    with pytest.raises(FlowkitGenerationAmbiguousError):
        await render_shot_pack(
            shot_pack_path,
            tmp_path,
            episode_context=context,
            max_retries_per_shot=2,
        )

    assert calls == 1
