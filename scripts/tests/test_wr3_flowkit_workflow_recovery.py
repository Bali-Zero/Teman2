"""Workflow-aware Flow media recovery and measured-cost accounting tests."""

from __future__ import annotations

import asyncio
import base64
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_flowkit_client as fk  # noqa: E402


PROJECT_ID = "project-exact"
WORKFLOW_ID = "workflow-exact"
MEDIA_ID = "media-exact"
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


@pytest.fixture
def ctx() -> fk.EpisodeContext:
    return fk.EpisodeContext(
        project_id=PROJECT_ID,
        video_id="video-shell",
        project_name="EP-workflow-recovery",
        endpoint="http://127.0.0.1:8100",
        paygate="PAYGATE_TIER_TIER1P5",
    )


def _completed_payload(
    *,
    project_id: str = PROJECT_ID,
    workflow_id: str = WORKFLOW_ID,
    primary_media_id: str = MEDIA_ID,
    media_id: str = MEDIA_ID,
    encoded_video: str | None = None,
    signed_url: str | None = None,
) -> dict:
    media = {
        "media_id": media_id,
        "url": signed_url,
        "encoded_video": encoded_video,
    }
    return {
        "project_id": project_id,
        "done": True,
        "status": "COMPLETED",
        "workflows": [
            {
                "name": workflow_id,
                "primary_media_id": primary_media_id,
                "project_id": project_id,
                "done": True,
                "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL",
                "error": None,
                "media": media,
            }
        ],
    }


@pytest.mark.asyncio
async def test_workflow_recovery_accepts_only_matching_ids_and_signed_origin(
    ctx: fk.EpisodeContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signed_url = f"https://flow-content.google/video/{MEDIA_ID}?sig=redacted"
    calls: dict[str, object] = {}

    async def fake_post(url: str, payload: dict, timeout_s: int) -> dict:
        calls["url"] = url
        calls["payload"] = payload
        return _completed_payload(signed_url=signed_url)

    async def fake_download(url: str, timeout_s: int) -> bytes:
        calls["download_url"] = url
        return MP4_BYTES

    monkeypatch.setattr(fk, "_http_post_json", fake_post)
    monkeypatch.setattr(fk, "_http_get_flow_content_bytes", fake_download)
    dest = tmp_path / "clip.mp4"

    await fk._download_video_media(
        ctx,
        workflow_id=WORKFLOW_ID,
        media_id=MEDIA_ID,
        dest=dest,
        timeout_s=30,
        poll_interval_s=0,
    )

    assert dest.read_bytes() == MP4_BYTES
    assert calls["download_url"] == signed_url
    assert str(calls["url"]).endswith("/api/flow/check-omni-status")
    assert calls["payload"] == {
        "project_id": PROJECT_ID,
        "include_encoded_video": True,
        "workflows": [
            {
                "name": WORKFLOW_ID,
                "primary_media_id": MEDIA_ID,
                "project_id": PROJECT_ID,
            }
        ],
    }


@pytest.mark.asyncio
async def test_workflow_recovery_decodes_encoded_video_atomically(
    ctx: fk.EpisodeContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encoded = base64.b64encode(MP4_BYTES).decode("ascii")

    async def fake_post(url: str, payload: dict, timeout_s: int) -> dict:
        return _completed_payload(encoded_video=encoded)

    async def forbidden_url_download(*_args, **_kwargs) -> bytes:
        raise AssertionError("encoded_video recovery must not download a URL")

    monkeypatch.setattr(fk, "_http_post_json", fake_post)
    monkeypatch.setattr(fk, "_http_get_flow_content_bytes", forbidden_url_download)
    dest = tmp_path / "clip.mp4"
    dest.write_bytes(b"old-destination")

    await fk._download_video_media(
        ctx,
        workflow_id=WORKFLOW_ID,
        media_id=MEDIA_ID,
        dest=dest,
        timeout_s=30,
        poll_interval_s=0,
    )

    assert dest.read_bytes() == MP4_BYTES
    assert list(tmp_path.glob(".clip.mp4.*.tmp")) == []


@pytest.mark.asyncio
async def test_invalid_encoded_video_never_replaces_existing_destination(
    ctx: fk.EpisodeContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_post(url: str, payload: dict, timeout_s: int) -> dict:
        return _completed_payload(
            encoded_video=base64.b64encode(b"not-an-mp4").decode("ascii")
        )

    monkeypatch.setattr(fk, "_http_post_json", fake_post)
    dest = tmp_path / "clip.mp4"
    dest.write_bytes(b"keep-existing")

    with pytest.raises(fk.FlowkitError, match="don't look like MP4"):
        await fk._download_video_media(
            ctx,
            workflow_id=WORKFLOW_ID,
            media_id=MEDIA_ID,
            dest=dest,
            timeout_s=30,
            poll_interval_s=0,
        )

    assert dest.read_bytes() == b"keep-existing"
    assert list(tmp_path.glob(".clip.mp4.*.tmp")) == []


@pytest.mark.asyncio
async def test_workflow_recovery_refuses_non_allowlisted_url_without_touching_dest(
    ctx: fk.EpisodeContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_post(url: str, payload: dict, timeout_s: int) -> dict:
        return _completed_payload(
            signed_url=f"https://flow-content.google.evil/{MEDIA_ID}"
        )

    async def forbidden_url_download(*_args, **_kwargs) -> bytes:
        raise AssertionError("disallowed URL must never be fetched")

    monkeypatch.setattr(fk, "_http_post_json", fake_post)
    monkeypatch.setattr(fk, "_http_get_flow_content_bytes", forbidden_url_download)
    dest = tmp_path / "clip.mp4"
    dest.write_bytes(b"keep-me")

    with pytest.raises(fk.FlowkitError, match=r"outside.*flow-content\.google"):
        await fk._download_video_media(
            ctx,
            workflow_id=WORKFLOW_ID,
            media_id=MEDIA_ID,
            dest=dest,
            timeout_s=30,
            poll_interval_s=0,
        )

    assert dest.read_bytes() == b"keep-me"


@pytest.mark.asyncio
async def test_workflow_recovery_refuses_project_mismatch(
    ctx: fk.EpisodeContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_post(url: str, payload: dict, timeout_s: int) -> dict:
        return _completed_payload(
            project_id="project-other",
            encoded_video=base64.b64encode(MP4_BYTES).decode("ascii"),
        )

    monkeypatch.setattr(fk, "_http_post_json", fake_post)

    with pytest.raises(fk.FlowkitError, match="project mismatch"):
        await fk._download_video_media(
            ctx,
            workflow_id=WORKFLOW_ID,
            media_id=MEDIA_ID,
            dest=tmp_path / "clip.mp4",
            timeout_s=30,
            poll_interval_s=0,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response_workflow_id", "response_media_id"),
    [("workflow-other", MEDIA_ID), (WORKFLOW_ID, "media-other")],
)
async def test_workflow_recovery_refuses_workflow_or_media_mismatch(
    ctx: fk.EpisodeContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    response_workflow_id: str,
    response_media_id: str,
) -> None:
    async def fake_post(url: str, payload: dict, timeout_s: int) -> dict:
        return _completed_payload(
            workflow_id=response_workflow_id,
            primary_media_id=response_media_id,
            media_id=response_media_id,
            encoded_video=base64.b64encode(MP4_BYTES).decode("ascii"),
        )

    monkeypatch.setattr(fk, "_http_post_json", fake_post)
    dest = tmp_path / "clip.mp4"

    with pytest.raises(fk.FlowkitError, match="workflow/media mismatch"):
        await fk._download_video_media(
            ctx,
            workflow_id=WORKFLOW_ID,
            media_id=MEDIA_ID,
            dest=dest,
            timeout_s=30,
            poll_interval_s=0,
        )

    assert not dest.exists()


@pytest.mark.asyncio
async def test_generate_video_uses_explicit_measured_clip_cost_for_ledger(
    ctx: fk.EpisodeContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setenv(
        "WR3_SPEND_DECISION",
        f"{ctx.project_name}:pytest:{date.today().isoformat()}",
    )
    monkeypatch.setenv(
        "WR3_SPEND_DECISION_LOG",
        str(tmp_path / "spend-decisions.jsonl"),
    )
    recorded: list[dict] = []

    async def fake_post(url: str, payload: dict, timeout_s: int) -> dict:
        return {
            "workflows": [{"name": WORKFLOW_ID}],
            "media": [{"name": MEDIA_ID}],
        }

    monkeypatch.setattr(fk, "_http_post_json", fake_post)
    monkeypatch.setattr(fk, "record_spend", lambda **kwargs: recorded.append(kwargs))

    result = await fk._generate_video(
        ctx,
        start_image_media_id="start-image",
        scene_id="scene",
        prompt="one measured generation",
        shot_index=105,
        clip_cost_cr=10,
    )

    assert result == (WORKFLOW_ID, MEDIA_ID)
    assert len(recorded) == 1
    assert recorded[0]["credits"] == 10
    assert recorded[0]["clip_cost_cr"] == 10


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "post_result",
    [
        asyncio.TimeoutError("response timeout after dispatch"),
        {"unexpected": "response without durable workflow identifiers"},
    ],
)
async def test_generate_video_ambiguous_response_is_hard_no_resubmit_boundary(
    ctx: fk.EpisodeContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    post_result: BaseException | dict,
) -> None:
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setenv(
        "WR3_SPEND_DECISION",
        f"{ctx.project_name}:pytest:{date.today().isoformat()}",
    )
    monkeypatch.setenv(
        "WR3_SPEND_DECISION_LOG",
        str(tmp_path / "spend-decisions.jsonl"),
    )
    calls = {"post": 0, "ledger": 0}

    async def ambiguous_post(url: str, payload: dict, timeout_s: int) -> dict:
        calls["post"] += 1
        if isinstance(post_result, BaseException):
            raise post_result
        return post_result

    def ledger_must_not_claim_unknown_ids(**kwargs: object) -> None:
        calls["ledger"] += 1

    monkeypatch.setattr(fk, "_http_post_json", ambiguous_post)
    monkeypatch.setattr(fk, "record_spend", ledger_must_not_claim_unknown_ids)

    with pytest.raises(
        fk.FlowkitGenerationAmbiguousError,
        match="do not resubmit automatically",
    ) as exc_info:
        await fk._generate_video(
            ctx,
            start_image_media_id="start-image",
            scene_id="scene-ambiguous",
            prompt="one dispatched generation",
            shot_index=106,
            clip_cost_cr=10,
        )

    assert calls == {"post": 1, "ledger": 0}
    assert exc_info.value.project_id == ctx.project_id
    assert exc_info.value.scene_id == "scene-ambiguous"
