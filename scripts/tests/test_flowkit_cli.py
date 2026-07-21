"""Unit tests for the FlowKit JSON CLI bridge."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import sys

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import flowkit_cli  # noqa: E402


def test_classifies_auth_and_model_access_failures() -> None:
    assert flowkit_cli._classify_error_text(
        "invalid authentication credentials", status=401
    ) == ("flow_auth")
    assert flowkit_cli._classify_error_text("PUBLIC_ERROR_MODEL_ACCESS_DENIED") == (
        "model_access"
    )
    assert flowkit_cli._classify_error_text("No model for tier=PAYGATE_TIER_ONE") == (
        "model_access"
    )


@pytest.mark.asyncio
async def test_generate_video_requires_explicit_start_image() -> None:
    parser = flowkit_cli.build_parser()
    args = parser.parse_args(
        [
            "generate-video",
            "--prompt",
            "0-8s: editorial dolly toward the Bali Zero anchor.",
        ]
    )

    with pytest.raises(flowkit_cli.FlowKitBridgeError) as exc_info:
        await flowkit_cli.run(args)

    assert exc_info.value.kind == "missing_asset"
    assert "AVATAR" in str(exc_info.value)


@pytest.mark.asyncio
async def test_health_surfaces_credit_auth_blocker(monkeypatch) -> None:
    async def fake_safe_request_json(client, method, path, **kwargs):
        if path == "/health":
            return {"ok": True, "data": {"extension_connected": True}}
        if path == "/api/flow/status":
            return {"ok": True, "data": {"flow_key_present": False}}
        if path == "/api/flow/credits":
            return {
                "ok": False,
                "error_kind": "flow_auth",
                "status": 401,
                "detail": {"status": "UNAUTHENTICATED"},
            }
        raise AssertionError(path)

    monkeypatch.setattr(flowkit_cli, "_safe_request_json", fake_safe_request_json)

    result = await flowkit_cli.action_health(
        Namespace(base_url="http://127.0.0.1:8100", timeout=1.0)
    )

    assert result["ok"] is False
    assert result["extension_connected"] is True
    assert result["blocker"] == "flow_auth"
    assert "extension_connected alone is not enough" in result["next_action"]


@pytest.mark.asyncio
async def test_generate_image_timeout_is_one_overall_deadline(monkeypatch, tmp_path) -> None:
    async def slow_ensure_project(*_args, **_kwargs):
        await flowkit_cli.asyncio.sleep(0.03)
        return "project-1"

    async def slow_request(*_args, **_kwargs):
        await flowkit_cli.asyncio.sleep(0.03)
        return {
            "media": [
                {
                    "name": "media-1",
                    "image": {
                        "generatedImage": {
                            "mediaId": "media-1",
                            "fifeUrl": "https://example.invalid/hero.png",
                        }
                    },
                }
            ]
        }

    async def slow_download(*_args, **_kwargs):
        await flowkit_cli.asyncio.sleep(0.03)
        return tmp_path / "hero.png"

    monkeypatch.setattr(flowkit_cli, "_ensure_project", slow_ensure_project)
    monkeypatch.setattr(flowkit_cli, "_request_json", slow_request)
    monkeypatch.setattr(flowkit_cli, "_download_url", slow_download)
    args = Namespace(
        base_url="http://127.0.0.1:8100",
        timeout=0.05,
        project_id="",
        project="magazine",
        material="editorial hero",
        language="en",
        prompt="bounded prompt",
        orientation="LANDSCAPE",
        paygate_tier="PAYGATE_TIER_TIER1P5",
        dest=str(tmp_path / "hero.png"),
    )

    with pytest.raises(flowkit_cli.FlowKitBridgeError) as exc_info:
        await flowkit_cli.action_generate_image(args)

    assert exc_info.value.kind == "timeout"


def test_parse_video_response_accepts_flow_workflows_media_shape() -> None:
    parsed = flowkit_cli._parse_video_response(
        {
            "workflows": [{"name": "operations/video-123", "status": "RUNNING"}],
            "media": [{"name": "media/video-456"}],
        }
    )

    assert parsed["workflow_id"] == "operations/video-123"
    assert parsed["video_media_id"] == "media/video-456"
    assert parsed["status"] == "RUNNING"


def test_transient_media_error_matches_flow_pending_envelope() -> None:
    assert flowkit_cli._is_transient_media_error(
        {
            "ok": False,
            "detail": {"error": {"code": 404, "status": "NOT_FOUND"}},
        }
    )
    assert flowkit_cli._is_transient_media_error(
        {
            "ok": False,
            "detail": {"error": {"code": 500, "status": "INTERNAL"}},
        }
    )


@pytest.mark.asyncio
async def test_generate_video_uploads_start_image_before_submit(monkeypatch) -> None:
    captured: dict = {}

    async def fake_ensure_project(client, **kwargs):
        return "project-1"

    async def fake_create_video(client, **kwargs):
        return "video-1"

    async def fake_create_scene(client, **kwargs):
        return "scene-1"

    async def fake_upload_image(args):
        captured["upload_path"] = args.image_path
        captured["upload_project_id"] = args.project_id
        return {"ok": True, "media_id": "media/start-image-1"}

    async def fake_request_json(
        client, method, path, *, json_body=None, timeout_s=None
    ):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = json_body
        return {
            "workflows": [{"name": "operations/video-1"}],
            "media": [{"name": "media/video-1"}],
        }

    monkeypatch.setattr(flowkit_cli, "_ensure_project", fake_ensure_project)
    monkeypatch.setattr(flowkit_cli, "_create_video", fake_create_video)
    monkeypatch.setattr(flowkit_cli, "_create_scene", fake_create_scene)
    monkeypatch.setattr(flowkit_cli, "action_upload_image", fake_upload_image)
    monkeypatch.setattr(flowkit_cli, "_request_json", fake_request_json)

    result = await flowkit_cli.action_generate_video(
        Namespace(
            base_url="http://127.0.0.1:8100",
            timeout=1.0,
            video_timeout=1.0,
            project_id="",
            project="wr2-test",
            material="realistic",
            language="en",
            video_id="",
            scene_id="",
            prompt="0-8s: editorial dolly.",
            orientation="PORTRAIT",
            start_image_media_id="",
            start_image_path="/tmp/zer.jpg",
            paygate_tier="PAYGATE_TIER_TIER1P5",
            dest="",
            poll_interval=0.01,
        )
    )

    assert result["ok"] is True
    assert result["start_image_media_id"] == "media/start-image-1"
    assert captured["upload_path"] == "/tmp/zer.jpg"
    assert captured["upload_project_id"] == "project-1"
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/flow/generate-video"
    assert captured["body"]["start_image_media_id"] == "media/start-image-1"
    assert captured["body"]["user_paygate_tier"] == "PAYGATE_TIER_TIER1P5"
