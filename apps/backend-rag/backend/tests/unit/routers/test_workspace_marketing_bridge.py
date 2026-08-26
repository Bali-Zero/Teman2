"""Least-privilege tests for the ChatGPT Business News Room projection."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app import rag_proxy
from backend.app.routers import intel, intel_scraper
from backend.middleware.hybrid_auth import HybridAuthMiddleware


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
    )


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
    with pytest.raises(HTTPException) as exc_info:
        await intel.workspace_marketing_publish_news(
            "news_1",
            intel.WorkspaceNewsPublishRequest(confirmation="DAMAR_CONFIRMED"),
        )
    assert exc_info.value.status_code == 409
    publisher.assert_not_awaited()


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


def test_http_publish_requires_fixed_damar_confirmation(monkeypatch) -> None:
    client = _middleware_client(monkeypatch)
    response = client.post(
        "/api/workspace-marketing/news/news_1/publish",
        json={"confirmation": "yes"},
        headers={"X-Workspace-Marketing-Key": "dedicated-key"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
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


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_http_publish_boundary_is_post_only(monkeypatch, method: str) -> None:
    client = _middleware_client(monkeypatch)
    response = getattr(client, method)(
        "/api/workspace-marketing/news/news_1/publish",
        headers={"X-Workspace-Marketing-Key": "dedicated-key"},
    )
    assert response.status_code == 405


def test_workspace_marketing_router_exposes_one_mutating_route() -> None:
    methods_by_path: dict[str, set[str]] = {}
    for route in intel.router.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/workspace-marketing/"):
            methods_by_path[path] = set(getattr(route, "methods", set()))

    assert methods_by_path == {
        "/api/workspace-marketing/news/pending": {"GET"},
        "/api/workspace-marketing/news/{item_id}": {"GET"},
        "/api/workspace-marketing/news/{item_id}/publish": {"POST"},
    }


def test_workspace_marketing_routes_reach_the_rag_process_in_split_production() -> None:
    assert rag_proxy.is_heavy_route("/api/workspace-marketing/news/pending") is True
    assert rag_proxy.is_heavy_route("/api/workspace-marketing/news/news_1") is True
    assert rag_proxy.is_heavy_route("/api/workspace-marketing/news/news_1/publish") is True
