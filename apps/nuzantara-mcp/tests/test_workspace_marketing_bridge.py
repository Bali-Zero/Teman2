"""Security and behavior tests for the ChatGPT Business marketing bridge."""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client

from nuzantara_mcp import server_workspace_marketing
from nuzantara_mcp import workspace_flowkit
from nuzantara_mcp import workspace_marketing_worker as worker
from nuzantara_mcp.server_workspace_marketing import mcp
from nuzantara_mcp.tools import workspace_marketing as marketing
from nuzantara_mcp.workspace_marketing_worker import (
    ANGLE_CODES,
    DISABLED_CODEX_FEATURES,
    _output_schema,
    _sol_argv,
    _sol_prompt,
    _validate_codes,
)

EXPECTED_TOOLS = {
    "workspace_health",
    "newsroom_list_pending",
    "newsroom_get_article",
    "wr2_list_review_queue",
    "wr2_get_review_item",
    "wr2_prepare_with_sol",
    "wr2_job_status",
    "flow_workspace_health",
    "flow_generate_image",
    "flow_generate_video",
}

FORBIDDEN_TOOL_TERMS = {
    "client",
    "crm",
    "document",
    "admin",
    "publish",
    "email",
    "whatsapp",
    "federation",
    "scraper",
    "upload",
    "path",
}


def _capture_tools(backend_call: AsyncMock) -> tuple[dict[str, Any], dict[str, Any]]:
    functions: dict[str, Any] = {}
    annotations: dict[str, Any] = {}

    class CaptureMCP:
        def tool(self, **kwargs: Any) -> Any:
            def decorator(function: Any) -> Any:
                functions[function.__name__] = function
                annotations[function.__name__] = kwargs.get("annotations", {})
                return function

            return decorator

    marketing.register(CaptureMCP(), backend_call)
    return functions, annotations


@pytest.mark.asyncio
async def test_server_is_exact_fail_closed_allowlist() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    names = {tool.name for tool in tools}
    assert names == EXPECTED_TOOLS
    assert not {
        name
        for name in names
        for forbidden in FORBIDDEN_TOOL_TERMS
        if forbidden in name
    }

    by_name = {tool.name: tool for tool in tools}
    assert by_name["workspace_health"].annotations.readOnlyHint is True
    assert by_name["wr2_prepare_with_sol"].annotations.readOnlyHint is False
    assert by_name["wr2_prepare_with_sol"].annotations.destructiveHint is True
    assert by_name["flow_generate_video"].annotations.openWorldHint is True
    assert mcp._mask_error_details is True


def test_workspace_server_never_imports_full_server_or_admin_client() -> None:
    source = inspect.getsource(server_workspace_marketing)
    marketing_source = inspect.getsource(marketing)
    flow_source = inspect.getsource(workspace_flowkit)

    assert "from nuzantara_mcp.server import" not in source
    assert "ADMIN_API_KEY" not in source
    assert "workspace_backend import call" in source
    assert "nuzantara_mcp.tools.flowkit" not in marketing_source
    assert "nuzantara_mcp.server" not in flow_source
    assert "create_subprocess_shell" not in flow_source


@pytest.mark.asyncio
async def test_masked_tool_errors_never_return_local_queue_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    missing_path = tmp_path / "private" / "human-review-queue.json"
    monkeypatch.setenv("WR2_QUEUE_PATH", str(missing_path))

    async with Client(mcp) as client:
        result = await client.call_tool(
            "wr2_list_review_queue",
            {"limit": 1},
            raise_on_error=False,
        )

    serialized = str(result)
    assert result.is_error is True
    assert str(missing_path) not in serialized
    assert "/Users/" not in serialized


@pytest.mark.asyncio
async def test_newsroom_projection_redacts_identifiers_and_raw_enrichment() -> None:
    backend_call = AsyncMock(
        side_effect=[
            {
                "items": [
                    {
                        "id": "news_123",
                        "title": "Call +39 333 123 4567 or user@example.com",
                        "category": "visa",
                        "content": "N" + "IK: 1234567890123456 public draft",
                        "source": "Official source",
                        "relevance_score": {"api_key": "must-not-leave"},
                        "enrichment": {"metadata": {"internal": "must-not-leave"}},
                    }
                ]
            },
            {
                "item_id": "news_123",
                "title": "Public title",
                "content": "N" + "PWP 123456789012345 and passport YA1234567",
                "source_name": "Official source",
                "source_url": "https://example.go.id/article?token=private#internal",
                "relevance_score": {"authorization": "must-not-leave"},
                "enrichment": {
                    "headline": "Safe headline",
                    "the_facts": ["Fact one"],
                    "metadata": {"secret_internal_key": "withheld"},
                },
            },
        ]
    )
    tools, _ = _capture_tools(backend_call)

    listing = await tools["newsroom_list_pending"](limit=50)
    article = await tools["newsroom_get_article"]("news_123")

    assert listing["count"] == 1
    assert "user@example.com" not in json.dumps(listing)
    assert "+39 333" not in json.dumps(listing)
    assert "1234567890123456" not in json.dumps(listing)
    assert "enrichment" not in listing["items"][0]
    assert "relevance_score" not in listing["items"][0]
    assert article["editorial"]["headline"] == "Safe headline"
    assert article["source_url"] == "https://example.go.id/article"
    assert "metadata" not in article["editorial"]
    assert "relevance_score" not in article
    assert "123456789012345" not in json.dumps(article)
    assert "YA1234567" not in json.dumps(article)
    assert backend_call.await_args_list[0].kwargs["params"] == {
        "limit": 25,
    }


@pytest.mark.asyncio
async def test_newsroom_rejects_dot_segment_item_id() -> None:
    tools, _ = _capture_tools(AsyncMock())

    with pytest.raises(ValueError, match="Invalid News Room item id"):
        await tools["newsroom_get_article"]("..")


@pytest.mark.asyncio
async def test_wr2_queue_never_returns_local_paths(tmp_path: Path, monkeypatch) -> None:
    queue_path = tmp_path / "human-review-queue.json"
    queue_path.write_text(
        json.dumps(
            [
                {
                    "item_id": "wr2-safe-1",
                    "topic": "PMA clarity",
                    "state": "applied_ready_for_damar",
                    "slide_count": {"api_key": "must-not-leave"},
                    "caption": "Public caption",
                    "critic_summary": "Pass",
                    "slides_dir": "/Users/nuzantara/private/slides",
                    "carousel_path": "/Users/nuzantara/private/carousel",
                    "drive_url": "https://drive.google.com/private",
                    "damar_notes": "Internal team note must stay on Pro",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("WR2_QUEUE_PATH", str(queue_path))
    tools, _ = _capture_tools(AsyncMock())

    listing = await tools["wr2_list_review_queue"]()
    detail = await tools["wr2_get_review_item"]("wr2-safe-1")
    serialized = json.dumps({"listing": listing, "detail": detail})

    assert listing["items"][0]["ref_code"].startswith("WR2-")
    assert listing["items"][0]["slide_count"] is None
    assert detail["caption"] == "Public caption"
    assert "/Users/" not in serialized
    assert "slides_dir" not in serialized
    assert "drive.google.com" not in serialized
    assert "damar_notes" not in serialized
    assert "Internal team note" not in serialized


@pytest.mark.asyncio
async def test_write_tools_are_fail_closed_until_armed(monkeypatch) -> None:
    monkeypatch.delenv("WORKSPACE_MARKETING_WRITES_ENABLED", raising=False)
    tools, _ = _capture_tools(AsyncMock())

    with pytest.raises(RuntimeError, match="not armed"):
        await tools["flow_generate_image"](
            "A detailed public editorial image prompt",
            "flow-image-0001",
            "SETUJU",
        )
    with pytest.raises(RuntimeError, match="not armed"):
        await tools["wr2_prepare_with_sol"](
            "Public policy explainer",
            "Indonesian founders",
            "wr2-disarmed-001",
            "SETUJU",
        )
    with pytest.raises(RuntimeError, match="not armed"):
        await tools["flow_generate_video"](
            "Public Bali Zero motion treatment",
            "media-safe-1",
            "flow-disarmed-video-1",
            "SETUJU",
        )

@pytest.mark.asyncio
async def test_flow_generation_has_fixed_tier_no_paths_and_idempotency(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    captured: list[list[str]] = []

    async def fake_flow(args: list[str], *, timeout_s: int) -> dict[str, Any]:
        captured.append(args)
        return {
            "ok": True,
            "media_id": "media-safe-1",
            "local_path": "/Users/nuzantara/private/output.png",
            "stderr": "private diagnostic",
        }

    monkeypatch.setattr(marketing, "_run_flowkit_cli", fake_flow)
    tools, _ = _capture_tools(AsyncMock())

    first = await tools["flow_generate_image"](
        "Original Bali Zero editorial visual without text",
        "flow-image-0001",
        "SETUJU",
    )
    second = await tools["flow_generate_image"](
        "Original Bali Zero editorial visual without text",
        "flow-image-0001",
        "SETUJU",
    )

    assert first == second
    assert first["media_id"] == "media-safe-1"
    assert "local_path" not in first
    assert "stderr" not in first
    assert len(captured) == 1
    args = captured[0]
    assert args[args.index("--project") + 1] == marketing.FLOW_PROJECT_NAME
    assert args[args.index("--paygate-tier") + 1] == marketing.FLOW_PAYGATE_TIER
    assert "--dest" not in args


@pytest.mark.asyncio
async def test_flow_health_error_never_returns_raw_path_or_diagnostic(monkeypatch) -> None:
    monkeypatch.setattr(
        marketing,
        "_run_flowkit_cli",
        AsyncMock(
            return_value={
                "ok": False,
                "error_kind": "flowkit_error",
                "error": "Missing /Users/nuzantara/private/flowkit.py",
                "message": "secret diagnostic",
                "stderr": "private stderr",
            }
        ),
    )
    tools, _ = _capture_tools(AsyncMock())

    result = await tools["flow_workspace_health"]()
    serialized = json.dumps(result)

    assert result["ok"] is False
    assert result["message"] == "FlowKit is unavailable or not connected on Pro."
    assert "/Users/" not in serialized
    assert "secret diagnostic" not in serialized
    assert "private stderr" not in serialized


@pytest.mark.asyncio
async def test_flow_failure_is_recorded_and_replayed_without_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    failing_flow = AsyncMock(side_effect=RuntimeError("/Users/private/token"))
    monkeypatch.setattr(marketing, "_run_flowkit_cli", failing_flow)
    tools, _ = _capture_tools(AsyncMock())

    with pytest.raises(RuntimeError, match="generation failed on Pro"):
        await tools["flow_generate_image"](
            "Original Bali Zero editorial visual without text",
            "flow-image-failure-1",
            "SETUJU",
        )
    replay = await tools["flow_generate_image"](
        "Original Bali Zero editorial visual without text",
        "flow-image-failure-1",
        "SETUJU",
    )

    assert replay == {"ok": False, "status": "failed"}
    assert failing_flow.await_count == 1
    assert "/Users/" not in json.dumps(replay)


@pytest.mark.asyncio
async def test_flow_daily_limit_accepts_one_then_rejects_next_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKSPACE_MARKETING_FLOW_DAILY_LIMIT", "1")
    monkeypatch.setattr(
        marketing,
        "_run_flowkit_cli",
        AsyncMock(return_value={"ok": True, "media_id": "media-safe-1"}),
    )
    tools, _ = _capture_tools(AsyncMock())

    accepted = await tools["flow_generate_image"](
        "Original Bali Zero editorial visual without text",
        "flow-image-0001",
        "SETUJU",
    )
    with pytest.raises(RuntimeError, match="Daily Flow generation limit reached"):
        await tools["flow_generate_image"](
            "A different Bali Zero editorial visual without text",
            "flow-image-0002",
            "SETUJU",
        )

    assert accepted["ok"] is True


@pytest.mark.asyncio
async def test_wr2_sol_preparation_is_confirmed_idempotent_and_uses_opaque_job(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(marketing, "_spawn_wr2_worker", AsyncMock(return_value=321))
    tools, _ = _capture_tools(AsyncMock())

    first = await tools["wr2_prepare_with_sol"](
        "Why a PT PMA structure changes decision risk",
        "Foreign founders in Indonesia",
        "wr2-request-0001",
        "SETUJU",
        ["instagram", "x"],
        "id",
        "Human, precise, no template feel.",
    )
    second = await tools["wr2_prepare_with_sol"](
        "Why a PT PMA structure changes decision risk",
        "Foreign founders in Indonesia",
        "wr2-request-0001",
        "SETUJU",
        ["instagram", "x"],
        "id",
        "Human, precise, no template feel.",
    )

    assert len(first["job_id"]) == 32
    assert second["job_id"] == first["job_id"]
    assert second["status"] == "already_accepted"
    marketing._spawn_wr2_worker.assert_awaited_once()


@pytest.mark.asyncio
async def test_wr2_sol_cap_allows_one_active_job_and_blocks_another(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKSPACE_MARKETING_SOL_MAX_ACTIVE", "1")
    monkeypatch.setattr(marketing, "_spawn_wr2_worker", AsyncMock(return_value=321))
    tools, _ = _capture_tools(AsyncMock())

    await tools["wr2_prepare_with_sol"](
        "Public policy explainer",
        "Indonesian founders",
        "wr2-request-cap-01",
        "SETUJU",
    )
    with pytest.raises(RuntimeError, match="SOL daily or active-job limit reached"):
        await tools["wr2_prepare_with_sol"](
            "Another public policy explainer",
            "Indonesian founders",
            "wr2-request-cap-02",
            "SETUJU",
        )


def test_sol_claim_reserves_visible_queued_job_inside_capacity_lock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKSPACE_MARKETING_SOL_MAX_ACTIVE", "1")
    first_job_id = "a" * 32
    first_payload = {
        "job_id": first_job_id,
        "status": "queued",
        "created_at": "2026-08-25T10:00:00+00:00",
    }

    _, _, created = marketing._claim_sol_operation(
        "wr2-atomic-cap-01",
        {"topic": "First"},
        first_payload,
    )

    assert created is True
    reserved = json.loads((tmp_path / "jobs" / f"{first_job_id}.json").read_text())
    assert reserved["status"] == "queued"
    with pytest.raises(RuntimeError, match="SOL daily or active-job limit reached"):
        marketing._claim_sol_operation(
            "wr2-atomic-cap-02",
            {"topic": "Second"},
            {
                "job_id": "b" * 32,
                "status": "queued",
                "created_at": "2026-08-25T10:00:01+00:00",
            },
        )


@pytest.mark.asyncio
async def test_team_inputs_reject_private_identifiers_and_local_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    tools, _ = _capture_tools(AsyncMock())

    with pytest.raises(ValueError, match="private or local-only"):
        await tools["flow_generate_image"](
            "Create a visual for +39 333 123 4567",
            "flow-private-001",
            "SETUJU",
        )
    with pytest.raises(ValueError, match="private or local-only"):
        await tools["wr2_prepare_with_sol"](
            "Read /Users/nuzantara/private/file",
            "Indonesian founders",
            "wr2-private-001",
            "SETUJU",
        )
    with pytest.raises(ValueError, match="Invalid Flow media id"):
        await tools["flow_generate_video"](
            "Public Bali Zero motion treatment without private data",
            "/Users/nuzantara/private/start.png",
            "flow-private-path-1",
            "SETUJU",
        )
    with pytest.raises(ValueError, match="command-line option"):
        await tools["flow_generate_image"](
            "--paygate-tier=PAYGATE_TIER_ULTRA",
            "flow-option-injection-1",
            "SETUJU",
        )
    with pytest.raises(ValueError, match="Invalid Flow media id"):
        await tools["flow_generate_video"](
            "Public Bali Zero motion treatment without private data",
            "--project",
            "flow-option-injection-2",
            "SETUJU",
        )


def test_team_input_rejects_oversize_instead_of_truncating_before_scan() -> None:
    with pytest.raises(ValueError, match="exceeds the allowed length"):
        marketing._public_team_input(
            "A" * 1_001 + " user@example.com",
            field="creative_notes",
            limit=1_000,
        )


def test_workspace_flowkit_runner_rejects_unapproved_argv_shapes() -> None:
    with pytest.raises(RuntimeError, match="not allowed"):
        workspace_flowkit._validate_args(["publish", "--project", "other"])
    with pytest.raises(RuntimeError, match="not allowed"):
        workspace_flowkit._validate_args(
            [
                "generate-image",
                "--prompt",
                "--project=other",
                "--orientation",
                "PORTRAIT",
                "--project",
                workspace_flowkit.FLOW_PROJECT_NAME,
                "--paygate-tier",
                workspace_flowkit.FLOW_PAYGATE_TIER,
            ]
        )


def test_workspace_flowkit_environment_drops_server_credentials(monkeypatch) -> None:
    monkeypatch.setenv("NUZANTARA_WORKSPACE_MARKETING_API_KEY", "private-route-key")
    monkeypatch.setenv("DATABASE_URL", "private-db")
    monkeypatch.setenv("FLOWKIT_BASE_URL", "http://127.0.0.1:8100")

    env = workspace_flowkit._flowkit_env()

    assert env["FLOWKIT_BASE_URL"] == "http://127.0.0.1:8100"
    assert "NUZANTARA_WORKSPACE_MARKETING_API_KEY" not in env
    assert "DATABASE_URL" not in env


def test_public_source_url_is_https_without_userinfo_query_or_fragment() -> None:
    assert marketing._public_source_url("http://example.go.id/article") == ""
    assert marketing._public_source_url("https://user:pass@example.go.id/article") == ""
    assert (
        marketing._public_source_url("https://example.go.id/article?token=x#private")
        == "https://example.go.id/article"
    )


@pytest.mark.asyncio
async def test_armed_write_rejects_missing_or_wrong_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    tools, _ = _capture_tools(AsyncMock())

    for confirmation in ("", "yes", "approved"):
        with pytest.raises(ValueError, match="explicitly confirm"):
            await tools["flow_generate_image"](
                "Original Bali Zero editorial image treatment",
                "flow-confirmation-01",
                confirmation,
            )


def test_worker_is_schema_closed_and_prompt_forbids_external_content() -> None:
    job = {
        "topic": "Public policy explainer",
        "audience": "Indonesian team",
        "platforms": ["instagram"],
        "language": "id",
        "creative_notes": "Original and precise",
    }

    sol_prompt = _sol_prompt(job)
    schema = _output_schema()
    payload = {
        "angle": sorted(ANGLE_CODES)[0],
        "human_tension": "trust",
        "narrative_arc": "hook-frame-discovery-close",
        "visual_mode": "editorial-documentary",
        "anti_cliches": ["avoid-template-repetition"],
        "platform_focus": {
            "instagram": "saveability",
            "x": "conversation",
            "facebook": "shareability",
        },
    }

    assert "Do not use shell, filesystem, network" in sol_prompt
    assert "free-form prose" in sol_prompt
    assert schema["additionalProperties"] is False
    assert _validate_codes(payload) == payload
    with pytest.raises(RuntimeError, match="invalid strategy shape"):
        _validate_codes({**payload, "free_text": "attempted exfiltration"})


def test_worker_disables_codex_tools_and_mutable_configuration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "nuzantara_mcp.workspace_marketing_worker._binary",
        lambda _name: "/opt/homebrew/bin/codex",
    )

    argv = _sol_argv(tmp_path)

    assert argv[:4] == [
        "/opt/homebrew/bin/codex",
        "exec",
        "-m",
        "gpt-5.6-sol",
    ]
    assert "--ignore-user-config" in argv
    assert "--ignore-rules" in argv
    assert "--strict-config" in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in argv
    assert 'web_search="disabled"' in argv
    assert 'model_reasoning_effort="xhigh"' in argv
    assert argv.count("--disable") == len(DISABLED_CODEX_FEATURES)
    for feature in (
        "apps",
        "browser_use",
        "image_generation",
        "multi_agent",
        "shell_tool",
        "unified_exec",
    ):
        assert ["--disable", feature] == argv[
            argv.index(feature) - 1 : argv.index(feature) + 1
        ]


@pytest.mark.asyncio
async def test_worker_cancellation_kills_process_group_and_keeps_log_private(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FakeProcess:
        pid = 4321
        returncode: int | None = None

        def __init__(self) -> None:
            self.started = asyncio.Event()

        async def communicate(self, _payload: bytes) -> None:
            self.started.set()
            await asyncio.Event().wait()

        async def wait(self) -> int:
            self.returncode = -15
            return self.returncode

    process = FakeProcess()
    signals: list[tuple[int, int]] = []

    async def fake_create_subprocess_exec(*_args: str, **_kwargs: Any) -> FakeProcess:
        return process

    monkeypatch.setattr(
        worker.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(
        worker.os,
        "killpg",
        lambda pid, sent_signal: signals.append((pid, sent_signal)),
    )

    log_path = tmp_path / "sol.log"
    task = asyncio.create_task(
        worker._run_to_files(
            ["/opt/homebrew/bin/codex", "exec"],
            cwd=tmp_path,
            prompt="bounded test",
            log_path=log_path,
            timeout_seconds=900,
        )
    )
    await process.started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert signals == [(process.pid, worker.signal.SIGTERM)]
    assert log_path.stat().st_mode & 0o777 == 0o600


def test_worker_environment_is_explicit_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "private-db")
    monkeypatch.setenv("BREVO_API_KEY", "private-key")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    worker_env = marketing._worker_env()

    assert "DATABASE_URL" not in worker_env
    assert "BREVO_API_KEY" not in worker_env
    assert set(worker_env) <= {
        "CODEX_HOME",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "TMPDIR",
        "WORKSPACE_MARKETING_STATE_DIR",
    }
