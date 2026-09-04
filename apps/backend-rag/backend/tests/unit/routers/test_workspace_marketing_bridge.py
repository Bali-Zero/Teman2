"""Least-privilege tests for the ChatGPT Business News Room projection."""

from __future__ import annotations

import base64
import io
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from starlette.requests import Request

from backend.app import rag_proxy
from backend.app.routers import article_composer, intel, intel_scraper
from backend.middleware.hybrid_auth import HybridAuthMiddleware
from backend.services.integrations.github_publisher import github_publisher


def _request(key: str = "") -> Request:
    headers = []
    if key:
        headers.append((b"x-workspace-marketing-key", key.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/api/workspace-marketing/news/pending",
            "raw_path": b"/api/workspace-marketing/news/pending",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1),
            "server": ("test", 443),
        }
    )


def test_workspace_marketing_key_is_exact_and_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(intel.settings, "workspace_marketing_api_key", "dedicated-key")

    intel.require_workspace_marketing_key(_request("dedicated-key"))

    for candidate in (
        "",
        "wrong-key",
        "dedicated-key-extra",
        "DEDICATED-KEY",
        "generic-api-key",
    ):
        try:
            intel.require_workspace_marketing_key(_request(candidate))
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("invalid workspace marketing key was accepted")


def test_workspace_marketing_key_fails_closed_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(intel.settings, "workspace_marketing_api_key", None)

    try:
        intel.require_workspace_marketing_key(_request("any-key"))
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("unconfigured route key did not fail closed")


@pytest.mark.asyncio
async def test_pending_projection_is_bounded_and_drops_internal_fields(monkeypatch) -> None:
    item = {
        "id": "news_1",
        "title": "Public title",
        "content": "Public article body",
        "source_name": "Official source",
        "source": {"internal_path": "/Users/nuzantara/private"},
        "internal_path": "/Users/nuzantara/private",
        "enrichment": {"metadata": {"secret": "withheld"}},
    }

    def _strict_list_pending_items(
        *,
        intel_type,
        filter_type,
        sort_type,
        search,
        include_enrichment,
    ):
        assert intel_type == "news"
        assert filter_type is None
        assert sort_type is None
        assert search is None
        assert include_enrichment is False
        return {
            "items": [
                item,
                {**item, "id": "news_2", "status": "published"},
                {**item, "id": "news_3", "published_url": "https://balizero.com/news/3"},
                item,
            ],
        }

    monkeypatch.setattr(
        intel.staging_service,
        "list_pending_items",
        _strict_list_pending_items,
    )

    result = await intel.workspace_marketing_pending_news(limit=1)

    assert result["count"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "Public title"
    assert "content" not in result["items"][0]
    assert "internal_path" not in result["items"][0]
    assert "source" not in result["items"][0]
    assert "enrichment" not in result["items"][0]
    assert result["offset"] == 0
    assert result["next_offset"] == 1
    assert result["complete"] is False


@pytest.mark.asyncio
async def test_article_projection_allows_editorial_fields_only(monkeypatch) -> None:
    monkeypatch.setattr(
        intel.staging_service,
        "load_staging_item",
        lambda *_args: {
            "id": "news_1",
            "title": "Public title",
            "source_url": "https://example.go.id/article?access_token=private#section",
            "private_drive_url": "https://drive.google.com/private",
            "enrichment": {
                "headline": "Safe headline",
                "faq": [
                    {
                        "question": "Q",
                        "answer": "A",
                        "access_token": "withheld",
                        "internal_file_path": "/private",
                    },
                ],
                "thirty_second_brief": {
                    "what": "What happened",
                    "why_it_matters": "Why it matters",
                    "who": "Investors",
                    "risk_level": "medium",
                    "authorization": "Bearer withheld",
                },
                "bali_zero_take": {
                    "hidden_insight": "Insight",
                    "our_analysis": "Analysis",
                    "our_advice": "Advice",
                    "session_id": "withheld",
                },
                "next_steps": {
                    "expat": ["Check the rule"],
                    "investor": ["Review the filing"],
                    "share_link": "https://drive.google.com/private",
                },
                "metadata": {"secret": "withheld"},
                "api_key": "withheld",
                "passport_no": "withheld",
            },
        },
    )

    result = await intel.workspace_marketing_news_article("news_1")

    assert result["title"] == "Public title"
    assert result["enrichment"] == {
        "headline": "Safe headline",
        "thirty_second_brief": {
            "what": "What happened",
            "why_it_matters": "Why it matters",
            "who": "Investors",
            "risk_level": "medium",
        },
        "next_steps": {
            "expat": ["Check the rule"],
            "investor": ["Review the filing"],
        },
        "bali_zero_take": {
            "hidden_insight": "Insight",
            "our_analysis": "Analysis",
            "our_advice": "Advice",
        },
        "faq": [{"question": "Q", "answer": "A"}],
    }
    assert result["source_url"] == "https://example.go.id/article"
    assert "private_drive_url" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["approved", "published", "rejected", "archived"])
async def test_article_detail_hides_non_pending_states(monkeypatch, status: str) -> None:
    monkeypatch.setattr(
        intel.staging_service,
        "load_staging_item",
        lambda *_args: {"id": "news_1", "status": status, "title": "Not pending"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await intel.workspace_marketing_news_article("news_1")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_article_detail_uses_real_item_id_validator(monkeypatch) -> None:
    monkeypatch.setattr(
        intel.staging_service,
        "load_staging_item",
        lambda *_args: pytest.fail("malformed id reached the staging service"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await intel.workspace_marketing_news_article("bad..id")

    assert exc_info.value.status_code == 404


def _ready_news_item() -> dict[str, object]:
    return {
        "id": "news_1",
        "status": "pending",
        "title": "A complete public article",
        "content": "Public editorial copy. " * 20,
        "category": "business",
        "source_url": "https://example.go.id/article",
        "cover_image": "covers/news_1.png",
    }


@pytest.mark.asyncio
async def test_capabilities_fail_closed_when_github_publisher_is_unconfigured(
    monkeypatch,
) -> None:
    monkeypatch.setattr(github_publisher, "token", None)
    monkeypatch.setattr(github_publisher, "owner", "Bali-Zero")
    monkeypatch.setattr(github_publisher, "repo", "Teman2")
    monkeypatch.setattr(intel.os, "access", lambda *_args: True)

    result = await intel.workspace_marketing_capabilities()

    assert result["ready"] is False
    assert result["capabilities"]["list_pending"] == "ready"
    assert result["capabilities"]["update_article"] == "unavailable"
    assert result["capabilities"]["publish"] == "unavailable"
    assert result["prerequisites"]["github_publisher_configured"] is False


@pytest.mark.asyncio
async def test_workspace_publish_uses_named_actor_and_existing_cover_only(
    monkeypatch,
) -> None:
    publish = AsyncMock(
        return_value={
            "success": True,
            "github_published": True,
            "title": "A complete public article",
            "published_url": "https://balizero.com/business/complete-article",
            "published_at": "2026-08-27T01:00:00+00:00",
            "message": "Published",
        }
    )
    monkeypatch.setattr(intel.staging_service, "load_staging_item", lambda *_: _ready_news_item())
    monkeypatch.setattr(
        intel.staging_service,
        "compare_and_set_status",
        lambda *_args, **_kwargs: (True, _ready_news_item()),
    )
    monkeypatch.setattr(intel_scraper, "publish_staging_item_internal", publish)

    result = await intel.workspace_marketing_publish_news(
        "news_1",
        intel.WorkspaceNewsPublishRequest(confirmation="DAMAR_CONFIRMED"),
    )

    assert result["success"] is True
    assert result["published_url"].startswith("https://balizero.com/")
    publish.assert_awaited_once_with(
        "news",
        "news_1",
        actor="workspace-agent:damar",
        allow_generated_cover=False,
        position="latest",
    )


@pytest.mark.asyncio
async def test_workspace_publish_recovers_expired_lease_with_same_operation(
    monkeypatch,
) -> None:
    stale = {
        **_ready_news_item(),
        "status": "publishing",
        "publish_position": "latest",
        "publication_operation_id": "news_1",
        "publication_lease_until": "2026-08-26T00:00:00+00:00",
    }
    publish = AsyncMock(
        return_value={
            "success": True,
            "github_published": True,
            "title": stale["title"],
            "published_url": "https://balizero.com/business/complete-article",
            "message": "Publication request resumed",
        }
    )
    cas = MagicMock(return_value=(True, stale))
    monkeypatch.setattr(intel.staging_service, "load_staging_item", lambda *_: stale)
    monkeypatch.setattr(intel.staging_service, "compare_and_set_status", cas)
    monkeypatch.setattr(intel_scraper, "publish_staging_item_internal", publish)

    result = await intel.workspace_marketing_publish_news(
        "news_1",
        intel.WorkspaceNewsPublishRequest(confirmation="DAMAR_CONFIRMED"),
    )

    assert result["success"] is True
    assert cas.call_args.kwargs["expected"] == {"publishing"}
    assert cas.call_args.kwargs["expected_values"] == {
        "publication_lease_until": "2026-08-26T00:00:00+00:00"
    }
    assert cas.call_args.kwargs["updates"]["publication_operation_id"] == "news_1"
    publish.assert_awaited_once()


def test_expired_lease_can_be_acquired_by_only_one_recovery(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(intel.staging_service, "news_staging_dir", tmp_path)
    old_lease = "2026-08-26T00:00:00+00:00"
    (tmp_path / "news_lease.json").write_text(
        json.dumps(
            {
                **_ready_news_item(),
                "status": "publishing",
                "publication_lease_until": old_lease,
            }
        ),
        encoding="utf-8",
    )

    first, _ = intel.staging_service.compare_and_set_status(
        "news",
        "news_lease",
        expected={"publishing"},
        new_status="publishing",
        updates={"publication_lease_until": "2026-08-27T01:10:00+00:00"},
        expected_values={"publication_lease_until": old_lease},
    )
    second, current = intel.staging_service.compare_and_set_status(
        "news",
        "news_lease",
        expected={"publishing"},
        new_status="publishing",
        updates={"publication_lease_until": "2026-08-27T01:20:00+00:00"},
        expected_values={"publication_lease_until": old_lease},
    )

    assert first is True
    assert second is False
    assert current["publication_lease_until"] == "2026-08-27T01:10:00+00:00"


@pytest.mark.asyncio
async def test_workspace_update_saves_complete_editorial_package(monkeypatch) -> None:
    item = _ready_news_item()
    save = Mock()
    monkeypatch.setattr(intel.staging_service, "load_staging_item", lambda *_: item)
    monkeypatch.setattr(intel.staging_service, "save_staging_item", save)
    monkeypatch.setattr(github_publisher, "token", "test-token")
    monkeypatch.setattr(github_publisher, "owner", "test-owner")
    monkeypatch.setattr(github_publisher, "repo", "test-repo")
    monkeypatch.setattr(
        github_publisher,
        "check_file_exists",
        AsyncMock(return_value=False),
    )
    body = intel.WorkspaceNewsUpdateRequest(
        title="Indonesia updates a material business rule",
        content="Verified public editorial copy. " * 20,
        category="business",
        seo_title="Indonesia Business Rule Update Explained",
        seo_description=(
            "What changed, who is affected, and what businesses in Indonesia should verify now."
        ),
        slug="indonesia-business-rule-update",
        cover_image_alt="Jakarta business district at sunrise after a regulatory update",
    )

    result = await intel.workspace_marketing_update_news("news_1", body)

    assert result["success"] is True
    assert item["slug"] == "indonesia-business-rule-update"
    save.assert_called_once_with("news", "news_1", item)


@pytest.mark.asyncio
async def test_workspace_update_rejects_existing_public_slug(monkeypatch) -> None:
    monkeypatch.setattr(
        intel.staging_service, "load_staging_item", lambda *_: _ready_news_item()
    )
    monkeypatch.setattr(github_publisher, "token", "test-token")
    monkeypatch.setattr(github_publisher, "owner", "test-owner")
    monkeypatch.setattr(github_publisher, "repo", "test-repo")
    monkeypatch.setattr(
        github_publisher,
        "check_file_exists",
        AsyncMock(return_value=True),
    )
    body = intel.WorkspaceNewsUpdateRequest(
        title="Indonesia updates a material business rule",
        content="Verified public editorial copy. " * 20,
        category="business",
        seo_title="Indonesia Business Rule Update Explained",
        seo_description=(
            "What changed, who is affected, and what businesses in Indonesia should verify now."
        ),
        slug="existing-public-article",
        cover_image_alt="Jakarta business district at sunrise after a regulatory update",
    )

    with pytest.raises(HTTPException) as exc_info:
        await intel.workspace_marketing_update_news("news_1", body)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_workspace_cover_accepts_only_real_image_bytes(monkeypatch) -> None:
    upload = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(intel, "upload_cover_image", upload)
    monkeypatch.setattr(
        intel.staging_service,
        "load_staging_item",
        lambda *_: _ready_news_item(),
    )
    image_buffer = io.BytesIO()
    Image.effect_noise((1200, 630), 100).convert("RGB").save(image_buffer, format="PNG")
    valid_png = base64.b64encode(image_buffer.getvalue()).decode()

    result = await intel.workspace_marketing_attach_cover(
        "news_1",
        intel.WorkspaceNewsCoverRequest(
            cover_image_base64=valid_png,
            cover_image_filename="editorial-cover.png",
        ),
    )

    assert result == {"success": True, "item_id": "news_1"}
    upload.assert_awaited_once()

    invalid = base64.b64encode(b"not an image" * 500).decode()
    with pytest.raises(HTTPException) as exc_info:
        await intel.workspace_marketing_attach_cover(
            "news_1",
            intel.WorkspaceNewsCoverRequest(
                cover_image_base64=invalid,
                cover_image_filename="fake.png",
            ),
        )
    assert exc_info.value.status_code == 422

    corrupted_png = base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + (b"not-real-pixel-data" * 400)
    ).decode()
    with pytest.raises(HTTPException) as exc_info:
        await intel.workspace_marketing_attach_cover(
            "news_1",
            intel.WorkspaceNewsCoverRequest(
                cover_image_base64=corrupted_png,
                cover_image_filename="corrupt.png",
            ),
        )
    assert exc_info.value.status_code == 422

    monkeypatch.setattr(
        intel.staging_service,
        "load_staging_item",
        lambda *_: {**_ready_news_item(), "status": "published"},
    )
    with pytest.raises(HTTPException) as exc_info:
        await intel.workspace_marketing_attach_cover(
            "news_1",
            intel.WorkspaceNewsCoverRequest(
                cover_image_base64=valid_png,
                cover_image_filename="editorial-cover.png",
            ),
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_failed_github_publish_remains_pending_and_retryable(
    tmp_path,
    monkeypatch,
) -> None:
    item = _ready_news_item()
    item["cover_image"] = "cover.png"
    # A decodable image: the cover is re-encoded as JPEG at publish time, so a
    # bare PNG header would be refused as unreadable before GitHub is reached.
    cover_png = io.BytesIO()
    Image.new("RGB", (1200, 630), color="navy").save(cover_png, format="PNG")
    (tmp_path / "cover.png").write_bytes(cover_png.getvalue())
    staging_path = tmp_path / "news_1.json"
    staging_path.write_text(json.dumps(item), encoding="utf-8")
    monkeypatch.setattr(intel_scraper.staging_service, "load_staging_item", lambda *_: item)
    monkeypatch.setattr(intel_scraper.staging_service, "get_staging_dir", lambda *_: tmp_path)
    monkeypatch.setattr(
        intel_scraper.staging_service,
        "save_staging_item",
        lambda _type, _item_id, payload: staging_path.write_text(
            json.dumps(payload), encoding="utf-8"
        ),
    )
    monkeypatch.setattr(
        intel_scraper,
        "ingest_intel_to_qdrant",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(intel_scraper, "invalidate_cache", AsyncMock())
    monkeypatch.setattr(intel_scraper, "intel_user_actions_total", MagicMock())
    monkeypatch.setattr(intel_scraper.settings, "balizero_website_url", "https://balizero.com")
    monkeypatch.setitem(
        sys.modules,
        "claude_validator",
        SimpleNamespace(ClaudeValidator=SimpleNamespace(add_published_article=lambda **_: None)),
    )
    monkeypatch.setattr(
        article_composer,
        "publish_article_internal",
        AsyncMock(
            return_value=article_composer.PublishResponse(
                success=False,
                message="GitHub write failed",
                error="GitHub write failed",
            )
        ),
    )

    result = await intel_scraper.publish_staging_item_internal(
        "news",
        "news_1",
        actor="workspace-agent:damar",
        allow_generated_cover=False,
    )

    persisted = json.loads(staging_path.read_text(encoding="utf-8"))
    assert result["success"] is False
    assert result["published_url"] is None
    assert persisted["status"] == "pending"
    assert "published_at" not in persisted
    assert "published_url" not in persisted
    assert persisted["last_publication_failed_at"]


@pytest.mark.asyncio
async def test_workspace_publish_blocks_incomplete_or_already_published_items(
    monkeypatch,
) -> None:
    publisher = AsyncMock()
    monkeypatch.setattr(intel_scraper, "publish_staging_item_internal", publisher)
    incomplete = _ready_news_item()
    incomplete.pop("cover_image")
    monkeypatch.setattr(intel.staging_service, "load_staging_item", lambda *_: incomplete)

    with pytest.raises(HTTPException) as exc_info:
        await intel.workspace_marketing_publish_news(
            "news_1",
            intel.WorkspaceNewsPublishRequest(confirmation="DAMAR_CONFIRMED"),
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["missing"] == ["cover_image"]

    published = _ready_news_item()
    published["status"] = "published"
    published["published_url"] = "https://balizero.com/business/already-live"
    monkeypatch.setattr(intel.staging_service, "load_staging_item", lambda *_: published)
    replay = await intel.workspace_marketing_publish_news(
        "news_1",
        intel.WorkspaceNewsPublishRequest(confirmation="DAMAR_CONFIRMED"),
    )
    assert replay["idempotent"] is True
    assert replay["status"] == "published"
    publisher.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_live_is_atomic_and_idempotent(monkeypatch) -> None:
    pending_live = {
        **_ready_news_item(),
        "status": "publication_pending",
        "published_url": "https://balizero.com/business/complete-article",
    }
    monkeypatch.setattr(
        intel.staging_service, "load_staging_item", lambda *_: pending_live
    )
    compare = Mock(return_value=(True, {**pending_live, "status": "published"}))
    monkeypatch.setattr(intel.staging_service, "compare_and_set_status", compare)

    result = await intel.workspace_marketing_confirm_live(
        "news_1",
        intel.WorkspacePublicationConfirmedRequest(confirmation="LIVE_VERIFIED"),
    )

    assert result["success"] is True
    assert result["status"] == "published"
    assert result["idempotent"] is False
    assert compare.call_args.kwargs["expected"] == {"publication_pending"}
    assert compare.call_args.kwargs["new_status"] == "published"

    monkeypatch.setattr(
        intel.staging_service,
        "load_staging_item",
        lambda *_: {**pending_live, "status": "published", "published_at": "now"},
    )
    replay = await intel.workspace_marketing_confirm_live(
        "news_1",
        intel.WorkspacePublicationConfirmedRequest(confirmation="LIVE_VERIFIED"),
    )
    assert replay["idempotent"] is True
    assert replay["published_at"] == "now"


def _middleware_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(intel.settings, "workspace_marketing_api_key", "dedicated-key")
    monkeypatch.setattr(
        intel.staging_service,
        "list_pending_items",
        lambda **_kwargs: {"items": [{"id": "news_1", "status": "pending"}]},
    )
    monkeypatch.setattr(
        intel.staging_service,
        "load_staging_item",
        lambda *_args: _ready_news_item(),
    )
    monkeypatch.setattr(
        intel_scraper,
        "publish_staging_item_internal",
        AsyncMock(
            return_value={
                "success": True,
                "github_published": True,
                "title": "A complete public article",
                "published_url": "https://balizero.com/business/complete-article",
                "published_at": "2026-08-27T01:00:00+00:00",
                "message": "Published",
            }
        ),
    )
    monkeypatch.setattr(
        intel.staging_service,
        "compare_and_set_status",
        lambda *_args, **_kwargs: (True, _ready_news_item()),
    )
    app = FastAPI()
    app.include_router(intel.router)
    app.add_middleware(HybridAuthMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def test_http_boundary_requires_exact_dedicated_key(monkeypatch) -> None:
    client = _middleware_client(monkeypatch)
    path = "/api/workspace-marketing/news/pending"

    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Workspace-Marketing-Key": "wrong"}).status_code == 401
    response = client.get(
        path,
        headers={"X-Workspace-Marketing-Key": "dedicated-key"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "count": 1,
        "total": 1,
        "offset": 0,
        "next_offset": None,
        "complete": True,
        "latest_item_at": None,
        "items": [{"id": "news_1", "status": "pending"}],
    }

    publish_path = "/api/workspace-marketing/news/news_1/publish"
    publish_body = {"confirmation": "DAMAR_CONFIRMED"}
    assert client.post(publish_path, json=publish_body).status_code == 401
    assert (
        client.post(
            publish_path,
            json=publish_body,
            headers={"X-Workspace-Marketing-Key": "wrong"},
        ).status_code
        == 401
    )
    published = client.post(
        publish_path,
        json=publish_body,
        headers={"X-Workspace-Marketing-Key": "dedicated-key"},
    )
    assert published.status_code == 200
    assert published.json()["published_url"].startswith("https://balizero.com/")


def test_all_bridge_routes_reach_their_dedicated_route_auth(monkeypatch) -> None:
    client = _middleware_client(monkeypatch)
    headers = {"X-Workspace-Marketing-Key": "dedicated-key"}

    assert client.get("/api/workspace-marketing/capabilities", headers=headers).status_code == 200
    assert (
        client.get(
            "/api/workspace-marketing/news/news_1/publication-status",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/workspace-marketing/news/news_1/editorial",
            headers=headers,
            json={},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/workspace-marketing/news/news_1/confirm-live",
            headers=headers,
            json={},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/workspace-marketing/news/news_1/cover",
            headers=headers,
            json={},
        ).status_code
        == 422
    )


def test_http_publish_requires_fixed_damar_confirmation(monkeypatch) -> None:
    client = _middleware_client(monkeypatch)
    response = client.post(
        "/api/workspace-marketing/news/news_1/publish",
        json={"confirmation": "yes"},
        headers={"X-Workspace-Marketing-Key": "dedicated-key"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
@pytest.mark.parametrize(
    "path",
    [
        "/api/workspace-marketing/news/pending",
        "/api/workspace-marketing/news/news_1",
    ],
)
def test_http_read_boundary_is_get_only(monkeypatch, method: str, path: str) -> None:
    client = _middleware_client(monkeypatch)
    response = getattr(client, method)(
        path,
        headers={"X-Workspace-Marketing-Key": "dedicated-key"},
    )
    assert response.status_code == 405


def test_http_pending_route_rejects_put_instead_of_matching_item_id(monkeypatch) -> None:
    client = _middleware_client(monkeypatch)
    response = client.put(
        "/api/workspace-marketing/news/pending",
        headers={"X-Workspace-Marketing-Key": "dedicated-key"},
    )
    assert response.status_code == 405


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_http_publish_boundary_is_post_only(monkeypatch, method: str) -> None:
    client = _middleware_client(monkeypatch)
    response = getattr(client, method)(
        "/api/workspace-marketing/news/news_1/publish",
        headers={"X-Workspace-Marketing-Key": "dedicated-key"},
    )
    assert response.status_code == 405


def test_workspace_marketing_router_exposes_exact_editorial_routes() -> None:
    methods_by_path: dict[str, set[str]] = {}
    for route in intel.router.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/workspace-marketing/"):
            methods_by_path[path] = set(getattr(route, "methods", set()))

    assert methods_by_path == {
        "/api/workspace-marketing/capabilities": {"GET"},
        "/api/workspace-marketing/news/pending": {"GET"},
        "/api/workspace-marketing/news/{item_id}": {"GET"},
        "/api/workspace-marketing/news/{item_id}/editorial": {"PUT"},
        "/api/workspace-marketing/news/{item_id}/cover": {"POST"},
        "/api/workspace-marketing/news/{item_id}/publish": {"POST"},
        "/api/workspace-marketing/news/{item_id}/publication-status": {"GET"},
        "/api/workspace-marketing/news/{item_id}/confirm-live": {"POST"},
    }


def test_workspace_marketing_routes_reach_the_rag_process_in_split_production() -> None:
    assert rag_proxy.is_heavy_route("/api/workspace-marketing/news/pending") is True
    assert rag_proxy.is_heavy_route("/api/workspace-marketing/news/news_1") is True
    assert rag_proxy.is_heavy_route("/api/workspace-marketing/news/news_1/publish") is True
