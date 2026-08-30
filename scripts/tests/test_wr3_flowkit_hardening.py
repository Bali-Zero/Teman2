"""Fail-closed boundaries for the reusable WR3 FlowKit client APIs."""

from __future__ import annotations

import asyncio
import fcntl
import json
import sys
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_flowkit_client as fk  # noqa: E402


def _context(*, endpoint: str = "http://127.0.0.1:8100") -> fk.EpisodeContext:
    return fk.EpisodeContext(
        project_id="project-hardening",
        video_id="video-hardening",
        project_name="EP-flowkit-hardening",
        endpoint=endpoint,
        paygate="PAYGATE_TIER_ONE",
    )


def _request(*, shot_index: int = 1) -> fk.ClipRequest:
    return fk.ClipRequest(
        shot_index=shot_index,
        positive_prompt="One deliberate camera movement.",
        start_image_media_id="start-image-existing",
    )


def _mp4_bytes() -> bytes:
    return b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:8100",
        "http://localhost:8100",
        "http://127.0.0.1:8101",
        "http://user@127.0.0.1:8100",
        "http://127.0.0.1:8100/api",
        "http://127.0.0.1:8100?target=remote",
        "http://127.0.0.1:8100#fragment",
        "http://flowkit.test:8100",
    ],
)
async def test_submit_clip_rejects_unsafe_endpoint_before_client_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    calls = {"scene": 0}

    async def scene_must_not_run(*_args: Any, **_kwargs: Any) -> str:
        calls["scene"] += 1
        raise AssertionError("unsafe endpoint reached Flow client code")

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setattr(fk, "_create_scene", scene_must_not_run)

    with pytest.raises(fk.FlowkitError, match="loopback FlowKit gateway"):
        await fk.submit_clip(
            _request(),
            episode_dir=tmp_path,
            episode_context=_context(endpoint=endpoint),
        )

    assert calls == {"scene": 0}


@pytest.mark.asyncio
async def test_render_shot_pack_rejects_unsafe_context_before_any_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shot_pack_path = tmp_path / "shot-pack.json"
    shot_pack_path.write_text(json.dumps({"episode_id": "EP", "shots": []}))

    async def context_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("unsafe endpoint reached context setup")

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setattr(fk, "setup_episode_context", context_must_not_run)

    with pytest.raises(fk.FlowkitError, match="loopback FlowKit gateway"):
        await fk.render_shot_pack(
            shot_pack_path,
            tmp_path,
            episode_context=_context(endpoint="http://flowkit.test:8100"),
        )


@pytest.mark.asyncio
async def test_ambiguous_start_image_is_durable_no_resubmit_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"scene": 0, "post": 0}
    secret_url = "https://flow-content.google/image/x?signature=must-not-persist"

    async def fake_scene(*_args: Any, **_kwargs: Any) -> str:
        calls["scene"] += 1
        return "scene-image-ambiguous"

    async def ambiguous_post(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls["post"] += 1
        raise asyncio.TimeoutError(secret_url)

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setattr(fk, "_create_scene", fake_scene)
    monkeypatch.setattr(fk, "_http_post_json", ambiguous_post)
    monkeypatch.setattr(fk, "assert_spend_authorized", lambda **_kwargs: None)
    monkeypatch.setattr(fk, "record_spend", lambda **_kwargs: None)

    request = fk.ClipRequest(
        shot_index=5,
        positive_prompt="Generate one charged start frame.",
    )
    for _ in range(2):
        with pytest.raises(
            fk.FlowkitNoResubmitError,
            match="do not resubmit|must not be resubmitted",
        ):
            await fk.submit_clip(
                request,
                episode_dir=tmp_path,
                episode_context=_context(),
            )

    assert calls == {"scene": 1, "post": 1}
    receipt_path = tmp_path / ".wr3-flowkit-shot-0005.json"
    receipt_text = receipt_path.read_text()
    receipt = json.loads(receipt_text)
    assert receipt["schema_version"] == "wr3.flowkit-shot-receipt.v1"
    assert receipt["status"] == "start_image_ambiguous"
    assert receipt["project_id"] == "project-hardening"
    assert receipt["video_id"] == "video-hardening"
    assert receipt["scene_id"] == "scene-image-ambiguous"
    assert receipt["shot_index"] == 5
    assert "signature" not in receipt_text
    assert "flow-content.google" not in receipt_text
    assert list(tmp_path.glob("..wr3-flowkit-shot-0005.json.*.tmp")) == []


@pytest.mark.asyncio
async def test_completed_submit_clip_cannot_generate_again(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"scene": 0, "generate": 0, "download": 0}

    async def fake_scene(*_args: Any, **_kwargs: Any) -> str:
        calls["scene"] += 1
        return "scene-complete"

    async def fake_generate(*_args: Any, **_kwargs: Any) -> tuple[str, str]:
        calls["generate"] += 1
        return "workflow-complete", "media-complete"

    async def fake_download(
        _ctx: fk.EpisodeContext,
        *,
        media_id: str,
        dest: Path,
        timeout_s: int,
        workflow_id: str,
    ) -> None:
        calls["download"] += 1
        assert media_id == "media-complete"
        assert workflow_id == "workflow-complete"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setattr(fk, "_create_scene", fake_scene)
    monkeypatch.setattr(fk, "_generate_video", fake_generate)
    monkeypatch.setattr(fk, "_download_video_media", fake_download)

    request = _request(shot_index=6)
    result = await fk.submit_clip(
        request,
        episode_dir=tmp_path,
        episode_context=_context(),
    )
    with pytest.raises(fk.FlowkitNoResubmitError, match="must not be resubmitted"):
        await fk.submit_clip(
            request,
            episode_dir=tmp_path,
            episode_context=_context(),
        )

    assert result.veo_job_id == "workflow-complete"
    assert calls == {"scene": 1, "generate": 1, "download": 1}
    receipt = json.loads((tmp_path / ".wr3-flowkit-shot-0006.json").read_text())
    assert receipt["status"] == "completed"
    assert receipt["workflow_id"] == "workflow-complete"
    assert receipt["media_id"] == "media-complete"


@pytest.mark.asyncio
async def test_submit_clip_rejects_concurrent_destination_lock_before_client_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"scene": 0}

    async def scene_must_not_run(*_args: Any, **_kwargs: Any) -> str:
        calls["scene"] += 1
        raise AssertionError("concurrent run reached client code")

    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)
    monkeypatch.setattr(fk, "_create_scene", scene_must_not_run)
    tmp_path.mkdir(parents=True, exist_ok=True)
    lock_path = tmp_path / ".wr3-flowkit-shot-0007.lock"

    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(fk.FlowkitNoResubmitError, match="already in progress"):
            await fk.submit_clip(
                _request(shot_index=7),
                episode_dir=tmp_path,
                episode_context=_context(),
            )

    assert calls == {"scene": 0}


@pytest.mark.asyncio
async def test_render_shot_pack_receipt_blocks_a_second_public_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shot_pack_path = tmp_path / "shot-pack.json"
    shot_pack_path.write_text(json.dumps({"episode_id": "EP-pack", "shots": []}))
    monkeypatch.delenv("WR3_ZERO_SPEND", raising=False)

    assert (
        await fk.render_shot_pack(
            shot_pack_path,
            tmp_path,
            episode_context=_context(),
        )
        == []
    )
    with pytest.raises(fk.FlowkitNoResubmitError, match="must not be rerun"):
        await fk.render_shot_pack(
            shot_pack_path,
            tmp_path,
            episode_context=_context(),
        )

    receipt = json.loads((tmp_path / ".wr3-flowkit-render-receipt.json").read_text())
    assert receipt["schema_version"] == "wr3.flowkit-render-receipt.v1"
    assert receipt["status"] == "completed"


@pytest.mark.asyncio
async def test_flow_video_download_accepts_allowlisted_fixture() -> None:
    content = _mp4_bytes()
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        return httpx.Response(
            200,
            headers={
                "content-type": "video/mp4",
                "content-length": str(len(content)),
            },
            content=content,
        )

    result = await fk._http_get_flow_content_bytes(
        "https://flow-content.google/video/media-1?signature=ephemeral",
        timeout_s=5,
        transport=httpx.MockTransport(handler),
    )

    assert result == content
    assert requested_hosts == ["flow-content.google"]


@pytest.mark.asyncio
async def test_flow_video_download_accepts_allowlisted_redirect_chain() -> None:
    content = _mp4_bytes()
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        if request.url.host == "flow-content.google":
            return httpx.Response(
                302,
                headers={
                    "location": (
                        "https://lh3.googleusercontent.com/generated/video.mp4"
                        "?signature=ephemeral"
                    )
                },
            )
        return httpx.Response(
            200,
            headers={"content-type": "video/mp4"},
            content=content,
        )

    result = await fk._http_get_flow_content_bytes(
        "https://flow-content.google/video/media-1?signature=ephemeral",
        timeout_s=5,
        transport=httpx.MockTransport(handler),
    )

    assert result == content
    assert requested_hosts == ["flow-content.google", "lh3.googleusercontent.com"]


@pytest.mark.asyncio
async def test_flow_video_download_rejects_unapproved_initial_host() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            headers={"content-type": "video/mp4"},
            content=_mp4_bytes(),
        )

    with pytest.raises(fk.FlowkitError, match="approved HTTPS media hosts"):
        await fk._http_get_flow_content_bytes(
            "https://cdn.invalid/video.mp4?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )

    assert calls == 0


@pytest.mark.asyncio
async def test_flow_video_download_rejects_unapproved_redirect() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            302,
            headers={"location": "https://cdn.invalid/video.mp4?signature=ephemeral"},
        )

    with pytest.raises(fk.FlowkitError, match="approved HTTPS media hosts"):
        await fk._http_get_flow_content_bytes(
            "https://flow-content.google/video/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )

    assert calls == 1


@pytest.mark.asyncio
async def test_flow_video_download_enforces_redirect_limit() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"location": "/video/next"})

    with pytest.raises(fk.FlowkitError, match="redirect limit"):
        await fk._http_get_flow_content_bytes(
            "https://flow-content.google/video/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )

    assert calls == 4


@pytest.mark.asyncio
async def test_flow_video_download_rejects_oversize_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fk, "FLOW_MEDIA_MAX_BYTES", 64, raising=False)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "video/mp4",
                "content-length": "65",
            },
            content=b"",
        )

    with pytest.raises(fk.FlowkitError, match="Content-Length exceeds"):
        await fk._http_get_flow_content_bytes(
            "https://flow-content.google/video/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )


@pytest.mark.asyncio
async def test_flow_video_download_enforces_streaming_byte_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _mp4_bytes()
    monkeypatch.setattr(fk, "FLOW_MEDIA_MAX_BYTES", len(content) - 1, raising=False)

    class UnboundedStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield content

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "video/mp4"},
            stream=UnboundedStream(),
        )

    with pytest.raises(fk.FlowkitError, match="download exceeds"):
        await fk._http_get_flow_content_bytes(
            "https://flow-content.google/video/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content_type", "content", "error_match"),
    [
        ("text/html", _mp4_bytes(), "unsupported Content-Type"),
        ("video/mp4", b"not-an-mp4", "valid MP4"),
    ],
)
async def test_flow_video_download_rejects_mime_or_magic_mismatch(
    content_type: str,
    content: bytes,
    error_match: str,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": content_type},
            content=content,
        )

    with pytest.raises(fk.FlowkitError, match=error_match):
        await fk._http_get_flow_content_bytes(
            "https://flow-content.google/video/media-1?signature=ephemeral",
            timeout_s=5,
            transport=httpx.MockTransport(handler),
        )
