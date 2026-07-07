"""Unit tests for FlowKit MCP tools."""

from __future__ import annotations

import pytest

from nuzantara_mcp.tools import flowkit
from nuzantara_mcp.tools.flowkit import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    tools: dict = {}

    def capture_tool():
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn

        return decorator

    mock_mcp.tool = capture_tool
    register(mock_mcp, mock_call, mock_call_safe)
    return tools


@pytest.mark.asyncio
async def test_flowkit_health_routes_to_cli(
    mock_mcp, mock_call, mock_call_safe, monkeypatch
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    captured: dict = {}

    async def fake_run(args, *, timeout_s=600):
        captured["args"] = args
        captured["timeout_s"] = timeout_s
        return {"ok": True}

    monkeypatch.setattr(flowkit, "_is_pro", lambda: False)
    monkeypatch.setattr(flowkit, "_run_flowkit_cli", fake_run)

    result = await tools["flowkit_health"]()

    assert result["ok"] is True
    assert result["executed_on"] == "Pro"
    assert captured["args"] == ["health"]


@pytest.mark.asyncio
async def test_run_flowkit_cli_stages_cli_on_m5(monkeypatch) -> None:
    calls: dict = {"staged": False}

    async def fake_stage_cli():
        calls["staged"] = True
        return None

    async def fake_process(argv, *, timeout_s=600):
        calls["argv"] = argv
        calls["timeout_s"] = timeout_s
        return 0, '{"ok": true}\n', ""

    monkeypatch.setattr(flowkit, "_is_pro", lambda: False)
    monkeypatch.setattr(flowkit, "_stage_cli_for_pro", fake_stage_cli)
    monkeypatch.setattr(flowkit, "_run_process", fake_process)

    result = await flowkit._run_flowkit_cli(["health"], timeout_s=11)

    assert result["ok"] is True
    assert calls["staged"] is True
    assert calls["timeout_s"] == 11
    assert calls["argv"][0] == "ssh"
    assert "/tmp/nuz-flowkit-bridge/flowkit_cli.py" in calls["argv"][-1]


@pytest.mark.asyncio
async def test_generate_video_requires_start_image(
    mock_mcp, mock_call, mock_call_safe, monkeypatch
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    async def fake_resolve(asset_path: str = ""):
        return {
            "ok": True,
            "recommended_start_image_path": "/Users/balizero/Desktop/logo/zer.jpg",
        }

    monkeypatch.setattr(flowkit, "_resolve_asset_candidates", fake_resolve)

    result = await tools["flowkit_generate_video"](prompt="0-8s: slow push-in.")

    assert result["ok"] is False
    assert result["error_kind"] == "missing_asset"
    assert "AVATAR" in result["error"]
    assert result["asset_probe"]["recommended_start_image_path"].endswith("zer.jpg")


@pytest.mark.asyncio
async def test_generate_video_stages_m5_asset_for_pro(
    mock_mcp,
    mock_call,
    mock_call_safe,
    monkeypatch,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    captured: dict = {}

    async def fake_stage(path: str):
        return "/tmp/nuz-flowkit-assets/abc/zer.jpg", None

    async def fake_dest(path: str):
        return "", None

    async def fake_run(args, *, timeout_s=600):
        captured["args"] = args
        captured["timeout_s"] = timeout_s
        return {"ok": True, "video_media_id": "media-1"}

    monkeypatch.setattr(flowkit, "_stage_local_file_for_pro", fake_stage)
    monkeypatch.setattr(flowkit, "_prepare_remote_dest", fake_dest)
    monkeypatch.setattr(flowkit, "_run_flowkit_cli", fake_run)

    result = await tools["flowkit_generate_video"](
        prompt="0-8s: editorial dolly move.",
        start_image_path="/Users/balizero/Desktop/logo/zer.jpg",
        paygate_tier="PAYGATE_TIER_TIER1P5",
    )

    assert result["ok"] is True
    assert result["local_source_path"] == "/Users/balizero/Desktop/logo/zer.jpg"
    assert result["pro_staged_path"] == "/tmp/nuz-flowkit-assets/abc/zer.jpg"
    assert captured["args"][0] == "generate-video"
    assert captured["args"][captured["args"].index("--start-image-path") + 1] == (
        "/tmp/nuz-flowkit-assets/abc/zer.jpg"
    )
    assert captured["args"][captured["args"].index("--paygate-tier") + 1] == (
        "PAYGATE_TIER_TIER1P5"
    )


@pytest.mark.asyncio
async def test_generate_image_copies_remote_output_back_to_m5(
    mock_mcp,
    mock_call,
    mock_call_safe,
    monkeypatch,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    async def fake_prepare(path: str):
        return "/tmp/nuz-flowkit-output/abc/hero.png", None

    async def fake_copy(remote_path: str, local_path: str):
        assert remote_path == "/tmp/nuz-flowkit-output/abc/hero.png"
        assert local_path == "/Users/balizero/Desktop/hero.png"
        return None

    async def fake_run(args, *, timeout_s=600):
        assert args[0] == "generate-image"
        return {
            "ok": True,
            "media_id": "image-1",
            "local_path": "/tmp/nuz-flowkit-output/abc/hero.png",
        }

    monkeypatch.setattr(flowkit, "_prepare_remote_dest", fake_prepare)
    monkeypatch.setattr(flowkit, "_copy_output_from_pro", fake_copy)
    monkeypatch.setattr(flowkit, "_run_flowkit_cli", fake_run)

    result = await tools["flowkit_generate_image"](
        prompt="Bali Zero editorial hero",
        dest_path="/Users/balizero/Desktop/hero.png",
    )

    assert result["ok"] is True
    assert result["remote_path"] == "/tmp/nuz-flowkit-output/abc/hero.png"
    assert result["local_path"] == "/Users/balizero/Desktop/hero.png"
