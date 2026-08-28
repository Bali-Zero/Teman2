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
    "intel_editorial_health",
    "newsroom_list_pending",
    "newsroom_get_article",
    "newsroom_fact_gate",
    "newsroom_update_article",
    "newsroom_attach_cover",
    "newsroom_publish",
    "newsroom_verify_live",
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
    assert by_name["newsroom_fact_gate"].annotations.readOnlyHint is False
    assert by_name["newsroom_publish"].annotations.readOnlyHint is False
    assert by_name["newsroom_publish"].annotations.destructiveHint is True
    assert by_name["newsroom_publish"].annotations.idempotentHint is True
    assert by_name["newsroom_verify_live"].annotations.readOnlyHint is False
    assert by_name["newsroom_verify_live"].annotations.destructiveHint is True
    assert by_name["wr2_prepare_with_sol"].annotations.readOnlyHint is False
    assert by_name["wr2_prepare_with_sol"].annotations.destructiveHint is True
    assert by_name["flow_generate_video"].annotations.openWorldHint is True
    assert {name for name in names if "publish" in name} == {"newsroom_publish"}
    assert mcp._mask_error_details is True


def test_workspace_server_instructions_route_news_room_and_flow_correctly() -> None:
    assert "News Room covers use native ImageGen" in mcp.instructions
    assert (
        "Confirmed Flow image and video generation remain available"
        in mcp.instructions
    )
    assert "Flow is video-only" not in mcp.instructions


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


def test_public_sanitizer_removes_spaced_indonesian_identifiers() -> None:
    raw_identifiers = "; ".join(
        (
            "NIK: " + "1234 5678 9012 3456",
            "NPWP " + "12.345.678.9-012.345",
            "passport " + "YA 123 4567",
        )
    )
    cleaned = marketing._clean_text(raw_identifiers)

    assert "1234 5678" not in cleaned
    assert "12.345.678" not in cleaned
    assert "YA 123 4567" not in cleaned
    assert cleaned.count("[identifier removed]") == 3


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
        "limit": 50,
        "offset": 0,
    }


@pytest.mark.asyncio
async def test_workspace_health_requires_live_v2_contract_and_write_arm(
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    backend_call = AsyncMock(
        return_value={
            "contract": marketing.NEWSROOM_CONTRACT,
            "ready": True,
            "capabilities": {
                name: "ready" for name in marketing.REQUIRED_NEWSROOM_CAPABILITIES
            },
        }
    )
    tools, _ = _capture_tools(backend_call)

    result = await tools["workspace_health"]()

    assert result["ok"] is True
    assert result["ready"] is True
    assert result["backend_reachable"] is True
    backend_call.assert_awaited_once_with("/api/workspace-marketing/capabilities")


@pytest.mark.asyncio
async def test_workspace_health_fails_closed_on_missing_capability(monkeypatch) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    backend_call = AsyncMock(
        return_value={
            "contract": marketing.NEWSROOM_CONTRACT,
            "ready": True,
            "capabilities": {"list_pending": "ready"},
        }
    )
    tools, _ = _capture_tools(backend_call)

    result = await tools["workspace_health"]()

    assert result["ok"] is False
    assert result["ready"] is False


@pytest.mark.asyncio
async def test_intel_health_triggers_plan_b_on_zero_enrichment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    (pipeline_dir / "run_20260827_010004.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "started_at": "2026-08-27T01:00:04+00:00",
                "completed_at": "2026-08-27T01:20:00+00:00",
                "steps": {
                    "1_scraping": {"data": {"articles": 204}},
                    "3_enrichment": {"data": {"selected": 15, "enriched": 0}},
                    "7_publishing": {"data": {"submitted": 0}},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("INTEL_PIPELINE_DIR", str(pipeline_dir))
    backend_call = AsyncMock(
        return_value={
            "total": 17,
            "latest_item_at": "2026-08-23T00:00:00+00:00",
        }
    )
    tools, _ = _capture_tools(backend_call)

    result = await tools["intel_editorial_health"]()

    assert result["ok"] is False
    assert result["candidates_found"] == 204
    assert result["selected_for_enrichment"] == 15
    assert result["enriched"] == 0
    assert result["submitted_to_news_room"] == 0
    assert result["plan_b_required"] is True


@pytest.mark.asyncio
async def test_fact_gate_uses_mapped_notebook_and_independent_reviewer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    backend_call = AsyncMock(
        return_value={
            "item_id": "news_123",
            "title": "Verified public business update",
            "category": "business",
            "content": "A material public business claim with sufficient context.",
            "source_url": "https://example.go.id/update",
        }
    )
    query = AsyncMock(return_value="The notebook supports the material claim.")
    reviewer = AsyncMock(
        return_value={
            "verdict": "PASS",
            "notebooklm_verdict": "PASS",
            "checked_claims": 3,
            "findings": ["Material claims are supported."],
        }
    )
    monkeypatch.setattr(marketing, "_query_notebooklm", query)
    monkeypatch.setattr(marketing, "_run_independent_fact_reviewer", reviewer)
    tools, _ = _capture_tools(backend_call)

    result = await tools["newsroom_fact_gate"]("news_123")

    assert result["ok"] is True
    assert result["notebooklm_domain"] == "NB-3 Company"
    assert "fingerprint" not in result
    assert marketing._load_fact_gate("news_123")["fingerprint"]
    query.assert_awaited_once()
    reviewer.assert_awaited_once()


@pytest.mark.asyncio
async def test_fact_gate_blocks_pass_with_zero_checked_claims(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    backend_call = AsyncMock(
        return_value={
            "item_id": "news_tech",
            "title": "Public technology update",
            "category": "tech",
            "content": "A public technology claim that requires verification.",
            "source_url": "https://example.go.id/tech",
        }
    )
    monkeypatch.setattr(
        marketing,
        "_query_notebooklm",
        AsyncMock(return_value="NB-7 returned editorial evidence."),
    )
    monkeypatch.setattr(
        marketing,
        "_run_independent_fact_reviewer",
        AsyncMock(
            return_value={
                "verdict": "PASS",
                "notebooklm_verdict": "PASS",
                "checked_claims": 0,
                "findings": [],
            }
        ),
    )
    tools, _ = _capture_tools(backend_call)

    result = await tools["newsroom_fact_gate"]("news_tech")

    assert result["ok"] is False
    assert result["notebooklm_domain"] == "NB-7 Editorial"
    assert result["findings"] == [
        "Independent reviewer returned no usable findings."
    ]


@pytest.mark.asyncio
async def test_newsroom_rejects_dot_segment_item_id() -> None:
    tools, _ = _capture_tools(AsyncMock())

    with pytest.raises(ValueError, match="Invalid News Room item id"):
        await tools["newsroom_get_article"]("..")


@pytest.mark.asyncio
async def test_newsroom_publish_requires_confirmation_and_is_replay_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    article_payload = {
        "item_id": "news_123",
        "title": "A complete public article",
        "category": "business",
        "content": "Complete verified public editorial copy. " * 20,
        "source_url": "https://example.go.id/article",
    }
    capabilities = {
        "contract": marketing.NEWSROOM_CONTRACT,
        "ready": True,
        "capabilities": {
            name: "ready" for name in marketing.REQUIRED_NEWSROOM_CAPABILITIES
        },
    }
    publish_payload = {
            "success": True,
            "github_published": True,
            "title": "A complete public article",
            "published_url": "https://balizero.com/business/complete-article?draft=no#live",
            "published_at": "2026-08-27T01:00:00+00:00",
            "message": "Published",
        }
    backend_call = AsyncMock(
        side_effect=[capabilities, article_payload, publish_payload]
    )
    tools, _ = _capture_tools(backend_call)
    public_article = marketing._public_news_article(article_payload)
    marketing._write_json_atomic(
        marketing._fact_gate_path("news_123"),
        {
            "ok": True,
            "fingerprint": marketing._article_fingerprint(public_article),
        },
    )

    with pytest.raises(ValueError, match="explicitly confirm"):
        await tools["newsroom_publish"]("news_123", "publish-news-0001", "yes")

    result = await tools["newsroom_publish"](
        "news_123",
        "publish-news-0001",
        "SETUJU",
    )
    replay = await tools["newsroom_publish"](
        "news_123",
        "publish-news-0001",
        "SETUJU",
    )

    assert result == replay
    assert result == {
        "ok": True,
        "status": "queued_for_publication",
        "item_id": "news_123",
        "title": "A complete public article",
        "published_url": "https://balizero.com/business/complete-article",
        "published_at": "2026-08-27T01:00:00+00:00",
        "message": "Published",
        "position": "",
    }
    assert backend_call.await_count == 3
    backend_call.assert_any_await("/api/workspace-marketing/capabilities")
    backend_call.assert_any_await("/api/workspace-marketing/news/news_123")
    backend_call.assert_any_await(
        "/api/workspace-marketing/news/news_123/publish",
        method="POST",
        json={"confirmation": "DAMAR_CONFIRMED", "position": "latest"},
    )

    with pytest.raises(ValueError, match="different inputs"):
        await tools["newsroom_publish"](
            "news_456",
            "publish-news-0001",
            "SETUJU",
        )


@pytest.mark.asyncio
async def test_newsroom_publish_recovers_an_accepted_operation_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    item_id = "news_accepted"
    request_key = "publish-news-accepted-1"
    article_payload = {
        "item_id": item_id,
        "title": "A complete accepted public article",
        "category": "business",
        "content": "Complete verified public editorial copy. " * 20,
        "source_url": "https://example.go.id/article",
    }
    capabilities = {
        "contract": marketing.NEWSROOM_CONTRACT,
        "ready": True,
        "capabilities": {
            name: "ready" for name in marketing.REQUIRED_NEWSROOM_CAPABILITIES
        },
    }
    marketing._claim_operation(
        "newsroom-publish",
        request_key,
        {"item_id": item_id, "position": "latest"},
        {"item_id": item_id, "position": "latest"},
    )
    public_article = marketing._public_news_article(article_payload)
    marketing._write_json_atomic(
        marketing._fact_gate_path(item_id),
        {
            "ok": True,
            "fingerprint": marketing._article_fingerprint(public_article),
        },
    )
    backend_call = AsyncMock(
        side_effect=[
            capabilities,
            article_payload,
            {
                "success": True,
                "github_published": True,
                "title": article_payload["title"],
                "published_url": "https://balizero.com/business/accepted-article",
                "message": "Resumed",
            },
        ]
    )
    tools, _ = _capture_tools(backend_call)

    result = await tools["newsroom_publish"](
        item_id,
        request_key,
        "SETUJU",
    )

    assert result["ok"] is True
    assert backend_call.await_count == 3


@pytest.mark.asyncio
async def test_attaching_a_new_cover_invalidates_the_fact_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    gate_path = marketing._fact_gate_path("news_cover")
    marketing._write_json_atomic(gate_path, {"ok": True, "fingerprint": "old"})
    backend_call = AsyncMock(return_value={"success": True})
    tools, _ = _capture_tools(backend_call)

    result = await tools["newsroom_attach_cover"](
        "news_cover",
        "a" * 200,
        "cover.png",
    )

    assert result["ok"] is True
    assert not gate_path.exists()


@pytest.mark.asyncio
async def test_newsroom_publish_masks_backend_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    article_payload = {
        "item_id": "news_123",
        "title": "A complete public article",
        "category": "business",
        "content": "Complete verified public editorial copy. " * 20,
        "source_url": "https://example.go.id/article",
    }
    backend_call = AsyncMock(
        side_effect=[
            {
                "contract": marketing.NEWSROOM_CONTRACT,
                "ready": True,
                "capabilities": {
                    name: "ready"
                    for name in marketing.REQUIRED_NEWSROOM_CAPABILITIES
                },
            },
            article_payload,
            RuntimeError("client@example.com passport ABC123456 internal body"),
        ]
    )
    tools, _ = _capture_tools(backend_call)
    marketing._write_json_atomic(
        marketing._fact_gate_path("news_123"),
        {
            "ok": True,
            "fingerprint": marketing._article_fingerprint(
                marketing._public_news_article(article_payload)
            ),
        },
    )

    with pytest.raises(RuntimeError) as exc_info:
        await tools["newsroom_publish"](
            "news_123",
            "publish-news-fail-1",
            "SETUJU",
        )

    assert str(exc_info.value) == "News Room publication failed"
    operation = json.loads(
        marketing._operation_path(
            "newsroom-publish",
            "publish-news-fail-1",
        ).read_text(encoding="utf-8")
    )
    assert operation["result"] == {
        "ok": False,
        "status": "failed",
        "item_id": "news_123",
    }
    assert "client@example.com" not in json.dumps(operation)


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
    with pytest.raises(RuntimeError, match="not armed"):
        await tools["newsroom_update_article"](
            "news_1",
            "A complete public title",
            "Public copy. " * 30,
            "business",
            "A complete SEO title",
            "A complete public SEO description for the Bali Zero article.",
            "complete-public-title",
            "Editorial view of Jakarta business activity",
        )
    with pytest.raises(RuntimeError, match="not armed"):
        await tools["newsroom_attach_cover"]("news_1", "base64", "cover.png")
    with pytest.raises(RuntimeError, match="not armed"):
        await tools["newsroom_verify_live"]("news_1")


@pytest.mark.asyncio
async def test_live_verifier_checks_seo_alt_cover_and_persists_confirmation(
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    slug = "complete-article"
    article_url = f"https://balizero.com/business/{slug}"
    cover_path = "/static/news/complete-cover.png"
    status_payload = {
        "item_id": "news_123",
        "title": "A complete public article",
        "status": "publication_pending",
        "published_url": article_url,
        "position": "latest",
        "published_cover_path": cover_path,
        "seo_title": "Complete Bali Business Update",
        "seo_description": "A precise explanation of the Bali business update and what readers should verify.",
        "cover_image_alt": "Jakarta skyline illustrating the business update",
        "source_url": "https://example.go.id/business-update",
    }
    backend_call = AsyncMock(
        side_effect=[
            status_payload,
            {
                "success": True,
                "status": "published",
                "published_at": "2026-08-27T12:00:00+00:00",
            },
        ]
    )
    html_doc = f"""
      <html><head>
      <title>Complete Bali Business Update</title>
      <meta name="description" content="{status_payload['seo_description']}">
      <meta property="og:title" content="Complete Bali Business Update">
      <meta property="og:description" content="{status_payload['seo_description']}">
      <meta property="og:image" content="{cover_path}">
      <link rel="canonical" href="{article_url}">
      </head><body>{slug}<h1>A complete public article</h1>
      <img src="{cover_path}" alt="Jakarta skyline illustrating the business update">
      <a href="https://example.go.id/business-update?tracking=removed">Primary source</a>
      </body></html>
    """

    class Response:
        def __init__(
            self,
            *,
            status_code: int = 200,
            text: str = "",
            headers: dict[str, str] | None = None,
            payload: dict[str, Any] | None = None,
        ) -> None:
            self.status_code = status_code
            self.text = text
            self.headers = headers or {}
            self._payload = payload or {}

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        async def get(self, url: str, **_kwargs: Any) -> Response:
            if url == article_url:
                return Response(text=html_doc)
            if url == "https://balizero.com/news":
                return Response(
                    text=f'<a href="/business/{slug}">latest story</a>'
                )
            if url.endswith("complete-cover.png"):
                return Response(headers={"content-type": "image/png"})
            raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(marketing.httpx, "AsyncClient", FakeClient)
    tools, _ = _capture_tools(backend_call)

    result = await tools["newsroom_verify_live"]("news_123")

    assert result["ok"] is True
    assert result["status"] == "published"
    assert result["published_at"] == "2026-08-27T12:00:00+00:00"
    assert result["seo_title_live"] is True
    assert result["seo_description_live"] is True
    assert result["cover_alt_live"] is True
    assert result["source_link_live"] is True
    backend_call.assert_any_await(
        "/api/workspace-marketing/news/news_123/confirm-live",
        method="POST",
        json={"confirmation": "LIVE_VERIFIED"},
    )


@pytest.mark.asyncio
async def test_live_verifier_rejects_off_domain_metadata_and_unbound_alt(
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    slug = "complete-article"
    article_url = f"https://balizero.com/business/{slug}"
    cover_path = "/static/news/complete-cover.png"
    backend_call = AsyncMock(
        return_value={
            "item_id": "news_123",
            "title": "A complete public article",
            "status": "publication_pending",
            "published_url": article_url,
            "position": "latest",
            "published_cover_path": cover_path,
            "seo_title": "Complete Bali Business Update",
            "seo_description": "A precise explanation of the Bali business update.",
            "cover_image_alt": "Approved editorial cover",
            "source_url": "https://example.go.id/business-update",
        }
    )
    malicious = f"""
      <html><head>
      <title>Complete Bali Business Update</title>
      <meta name="description" content="A precise explanation of the Bali business update.">
      <meta property="og:title" content="WRONG TITLE">
      <meta property="og:description" content="A precise explanation of the Bali business update.">
      <meta property="og:image" content="https://evil.example{cover_path}">
      <link rel="canonical" href="https://evil.example/business/{slug}">
      </head><body><h1>A complete public article</h1>
      <div>Approved editorial cover</div>
      <img src="{cover_path}" alt="WRONG ALT">
      <a href="https://example.go.id/business-update">Primary source</a>
      </body></html>
    """

    class Response:
        status_code = 200
        headers: dict[str, str] = {}

        def __init__(self, text: str = "") -> None:
            self.text = text

    requested: list[str] = []

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        async def get(self, url: str, **_kwargs: Any) -> Response:
            requested.append(url)
            if url == article_url:
                return Response(malicious)
            if url == "https://balizero.com/news":
                return Response(f'<a href="/business/{slug}">story</a>')
            raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(marketing.httpx, "AsyncClient", FakeClient)
    tools, _ = _capture_tools(backend_call)

    result = await tools["newsroom_verify_live"]("news_123")

    assert result["ok"] is False
    assert result["seo_title_live"] is False
    assert result["canonical_live"] is False
    assert result["approved_cover_live"] is False
    assert result["cover_alt_live"] is False
    assert not any(url.startswith("https://evil.example") for url in requested)
    assert backend_call.await_count == 1


def test_homepage_position_proof_requires_exact_rendered_slot() -> None:
    document = """
      <section id="news">
        <a data-homepage-position="hero_main" href="/business/main-story">Main</a>
        <a data-homepage-position="hero_2" href="/business/second-story">Second</a>
      </section>
    """

    assert marketing._homepage_position_live(
        document,
        "hero_2",
        "https://balizero.com/business/second-story",
    )
    assert not marketing._homepage_position_live(
        document,
        "hero_main",
        "https://balizero.com/business/second-story",
    )


def test_publication_origin_rejects_nonstandard_ports_and_credentials() -> None:
    assert not marketing._is_balizero_public_url(
        "https://balizero.com:444/static/news/cover.png"
    )
    assert not marketing._is_balizero_public_url(
        "https://user@balizero.com/static/news/cover.png"
    )
    assert (
        marketing._normalized_public_url(
            "https://balizero.com:444/static/news/cover.png",
            "https://balizero.com",
        )
        == ""
    )


@pytest.mark.asyncio
async def test_live_verifier_never_fetches_nonstandard_publication_port(
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    backend_call = AsyncMock(
        return_value={
            "item_id": "news_123",
            "status": "publication_pending",
            "published_url": "https://balizero.com:444/business/story",
        }
    )
    client_created = False

    class ForbiddenClient:
        def __init__(self, **_kwargs: Any) -> None:
            nonlocal client_created
            client_created = True
            raise AssertionError("an invalid publication origin must never be fetched")

    monkeypatch.setattr(marketing.httpx, "AsyncClient", ForbiddenClient)
    tools, _ = _capture_tools(backend_call)

    result = await tools["newsroom_verify_live"]("news_123")

    assert result["ok"] is False
    assert client_created is False
    assert backend_call.await_count == 1


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
    assert captured[0] == ["health"]
    assert len(captured) == 2
    args = captured[1]
    assert args[args.index("--project") + 1] == marketing.FLOW_PROJECT_NAME
    assert args[args.index("--paygate-tier") + 1] == marketing.FLOW_PAYGATE_TIER
    assert "--dest" not in args


@pytest.mark.asyncio
async def test_flow_health_error_never_returns_raw_path_or_diagnostic(
    monkeypatch,
) -> None:
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
    failing_flow = AsyncMock(
        side_effect=[
            {"ok": True},
            RuntimeError("/Users/private/token"),
        ]
    )
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
    assert failing_flow.await_count == 2
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


def test_indonesian_grouped_currency_is_public_editorial_data() -> None:
    values = (
        "Modal disetor PT PMA naik ke Rp 2.500.000.000 per KBLI",
        "Biaya KITAS Rp 25000000 all-in",
        "Investment threshold IDR 10000000000",
        "PMK 44 Tahun 2026 berlaku 2026-09-01",
    )

    for text in values:
        assert marketing._public_team_input(text, field="topic", limit=500) == text
        assert marketing._clean_text(text) == text
    article = marketing._public_news_article(
        {
            "title": values[0],
            "content": values[1],
            "published_at": "2026-08-25",
        }
    )
    assert article["title"] == values[0]
    assert article["content"] == values[1]
    assert article["published_at"] == "2026-08-25"


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
    with pytest.raises(RuntimeError, match="not allowed"):
        workspace_flowkit._validate_args(
            [
                "generate-image",
                "--prompt",
                "Public editorial image",
                "--orientation",
                "SQUARE",
                "--project",
                workspace_flowkit.FLOW_PROJECT_NAME,
                "--paygate-tier",
                workspace_flowkit.FLOW_PAYGATE_TIER,
            ]
        )
    assert marketing.ALLOWED_ORIENTATIONS == {"PORTRAIT", "LANDSCAPE"}


@pytest.mark.asyncio
async def test_workspace_flowkit_cancellation_kills_process_group(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FakeProcess:
        pid = 7654
        returncode: int | None = None

        def __init__(self) -> None:
            self.started = asyncio.Event()

        async def communicate(self) -> tuple[bytes, bytes]:
            self.started.set()
            await asyncio.Event().wait()
            return b"", b""

        async def wait(self) -> int:
            self.returncode = -15
            return self.returncode

    python_path = tmp_path / "python"
    cli_path = tmp_path / "flowkit_cli.py"
    python_path.touch()
    cli_path.touch()
    process = FakeProcess()
    signals: list[tuple[int, int]] = []

    async def fake_create_subprocess_exec(*_args: str, **_kwargs: Any) -> FakeProcess:
        return process

    monkeypatch.setattr(workspace_flowkit, "PRO_HOSTNAME", "test-pro")
    monkeypatch.setattr(workspace_flowkit.socket, "gethostname", lambda: "test-pro")
    monkeypatch.setattr(workspace_flowkit, "FLOWKIT_PYTHON", python_path)
    monkeypatch.setattr(workspace_flowkit, "FLOWKIT_CLI", cli_path)
    monkeypatch.setattr(
        workspace_flowkit.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(
        workspace_flowkit.os,
        "killpg",
        lambda pid, sent_signal: signals.append((pid, sent_signal)),
    )

    task = asyncio.create_task(workspace_flowkit.run(["health"], timeout_s=600))
    await process.started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert signals == [(process.pid, workspace_flowkit.signal.SIGTERM)]


@pytest.mark.asyncio
async def test_cancelled_flow_operation_is_replayable_as_cancelled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    runner = AsyncMock(side_effect=[{"ok": True}, asyncio.CancelledError])
    monkeypatch.setattr(marketing, "_run_flowkit_cli", runner)
    tools, _ = _capture_tools(AsyncMock())

    with pytest.raises(asyncio.CancelledError):
        await tools["flow_generate_image"](
            "Public Bali Zero editorial image treatment",
            "flow-cancelled-01",
            "SETUJU",
        )

    replay = await tools["flow_generate_image"](
        "Public Bali Zero editorial image treatment",
        "flow-cancelled-01",
        "SETUJU",
    )

    assert replay == {"ok": False, "status": "cancelled"}
    assert runner.await_count == 2


@pytest.mark.asyncio
async def test_flow_outage_does_not_claim_idempotency_or_daily_quota(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKSPACE_MARKETING_WRITES_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_MARKETING_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKSPACE_MARKETING_FLOW_DAILY_LIMIT", "1")
    runner = AsyncMock(
        side_effect=[
            {"ok": False, "status": "unavailable", "error_kind": "flowkit_unavailable"},
            {"ok": True},
            {"ok": True, "media_id": "media-safe-1"},
        ]
    )
    monkeypatch.setattr(marketing, "_run_flowkit_cli", runner)
    tools, _ = _capture_tools(AsyncMock())

    outage = await tools["flow_generate_image"](
        "Public Bali Zero editorial image treatment",
        "flow-outage-0001",
        "SETUJU",
    )
    success = await tools["flow_generate_image"](
        "A second public Bali Zero editorial treatment",
        "flow-outage-0002",
        "SETUJU",
    )

    assert outage["ok"] is False
    assert outage["status"] == "unavailable"
    assert success["ok"] is True
    assert success["media_id"] == "media-safe-1"
    assert success["executed_on"] == "Pro"
    assert not marketing._operation_path("flow-image", "flow-outage-0001").exists()
    assert marketing._operation_path("flow-image", "flow-outage-0002").exists()


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
