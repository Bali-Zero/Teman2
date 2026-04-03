"""Unit tests for Intel tools."""

import pytest

from nuzantara_mcp.tools.intel import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register intel tools and capture them."""
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
async def test_submit_scraper_job_minimal(mock_mcp, mock_call, mock_call_safe) -> None:
    """submit_scraper_job with sources only."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"job_id": "scrape-1", "status": "queued"}

    result = await tools["submit_scraper_job"](sources=["kemenkumham", "pajak.go.id"])
    assert result["job_id"] == "scrape-1"
    mock_call.assert_called_once_with(
        "/api/intel/scraper/submit",
        method="POST",
        json={"sources": ["kemenkumham", "pajak.go.id"]},
    )


@pytest.mark.asyncio
async def test_submit_scraper_job_with_topic(mock_mcp, mock_call, mock_call_safe) -> None:
    """submit_scraper_job with topic filter."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"job_id": "scrape-2"}

    await tools["submit_scraper_job"](sources=["oss.go.id"], topic="KBLI changes")
    call_json = mock_call.call_args[1]["json"]
    assert call_json["topic"] == "KBLI changes"
    assert call_json["sources"] == ["oss.go.id"]


@pytest.mark.asyncio
async def test_submit_scraper_job_no_topic_omits(mock_mcp, mock_call, mock_call_safe) -> None:
    """submit_scraper_job without topic should not include it."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"job_id": "scrape-3"}

    await tools["submit_scraper_job"](sources=["test"])
    call_json = mock_call.call_args[1]["json"]
    assert "topic" not in call_json


@pytest.mark.asyncio
async def test_list_staging_items_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_staging_items with no filter defaults to 'all'."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"items": [{"title": "New regulation"}]}

    result = await tools["list_staging_items"]()
    assert len(result["items"]) == 1
    mock_call.assert_called_once_with(
        "/api/intel/staging/pending", params={"type": "all"}
    )


@pytest.mark.asyncio
async def test_list_staging_items_visa(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_staging_items with status=visa."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"items": []}

    await tools["list_staging_items"](status="visa")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["type"] == "visa"


@pytest.mark.asyncio
async def test_list_staging_items_news(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_staging_items with status=news."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"items": []}

    await tools["list_staging_items"](status="news")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["type"] == "news"


@pytest.mark.asyncio
async def test_list_staging_items_invalid_status_defaults_all(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_staging_items with unknown status should default to 'all'."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"items": []}

    await tools["list_staging_items"](status="unknown_type")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["type"] == "all"


@pytest.mark.asyncio
async def test_approve_staging_item_with_type_prefix(mock_mcp, mock_call, mock_call_safe) -> None:
    """approve_staging_item with type/id format should pass as-is."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"status": "approved"}

    result = await tools["approve_staging_item"](item_id="visa/item-123")
    assert result["status"] == "approved"
    mock_call.assert_called_once_with(
        "/api/intel/staging/approve/visa/item-123", method="POST"
    )


@pytest.mark.asyncio
async def test_approve_staging_item_without_type_adds_news(mock_mcp, mock_call, mock_call_safe) -> None:
    """approve_staging_item without type prefix should default to news/."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"status": "approved"}

    await tools["approve_staging_item"](item_id="item-456")
    mock_call.assert_called_once_with(
        "/api/intel/staging/approve/news/item-456", method="POST"
    )


@pytest.mark.asyncio
async def test_publish_intel(mock_mcp, mock_call, mock_call_safe) -> None:
    """publish_intel should POST with content_type and item_id in URL."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"published_url": "https://balizero.com/intel/123"}

    result = await tools["publish_intel"](content_type="regulation", item_id="item-789")
    assert "published_url" in result
    mock_call.assert_called_once_with(
        "/api/intel/staging/publish/regulation/item-789", method="POST"
    )


@pytest.mark.asyncio
async def test_get_intel_metrics(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_intel_metrics should call correct endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"total_scraped": 500, "approved": 350, "published": 200}

    result = await tools["get_intel_metrics"]()
    assert result["total_scraped"] == 500
    mock_call.assert_called_once_with("/api/intel/metrics")


@pytest.mark.asyncio
async def test_get_critical_alerts(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_critical_alerts should call correct endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "alerts": [{"severity": "critical", "impact": "KITAS holders"}]
    }

    result = await tools["get_critical_alerts"]()
    assert result["alerts"][0]["severity"] == "critical"
    mock_call.assert_called_once_with("/api/intel/critical")


@pytest.mark.asyncio
async def test_get_intel_trends_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_intel_trends with default period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"topics": [{"name": "visa", "count": 42}]}

    result = await tools["get_intel_trends"]()
    mock_call.assert_called_once_with(
        "/api/intel/trends", params={"period": "30d"}
    )


@pytest.mark.asyncio
async def test_get_intel_trends_custom_period(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_intel_trends with custom period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {}

    await tools["get_intel_trends"](period="90d")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["period"] == "90d"


@pytest.mark.asyncio
async def test_search_intel(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_intel should POST with query and limit."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"results": [{"title": "PP 28/2025"}]}

    result = await tools["search_intel"](query="new visa regulation", limit=5)
    assert result["results"][0]["title"] == "PP 28/2025"
    mock_call.assert_called_once_with(
        "/api/intel/search",
        method="POST",
        json={"query": "new visa regulation", "limit": 5},
    )


@pytest.mark.asyncio
async def test_search_intel_default_limit(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_intel default limit should be 10."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"results": []}

    await tools["search_intel"](query="test")
    call_json = mock_call.call_args[1]["json"]
    assert call_json["limit"] == 10


@pytest.mark.asyncio
async def test_submit_scraper_job_error(mock_mcp, mock_call, mock_call_safe) -> None:
    """Error propagation from _call."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.side_effect = Exception("Rate limited")

    with pytest.raises(Exception, match="Rate limited"):
        await tools["submit_scraper_job"](sources=["test"])
