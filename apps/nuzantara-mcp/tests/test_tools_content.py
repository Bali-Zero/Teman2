"""Unit tests for content tools."""

import pytest

from nuzantara_mcp.tools.content import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register content tools and capture them."""
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
async def test_compose_article_defaults(mock_mcp, mock_call, mock_call_safe) -> None:
    """compose_article should POST with default style and length."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"title": "Test", "body": "Content"}

    result = await tools["compose_article"](topic="New visa rules")
    assert result["title"] == "Test"
    mock_call.assert_called_once_with(
        "/api/article-composer/compose",
        method="POST",
        json={"topic": "New visa rules", "style": "informative", "target_length": "medium"},
    )


@pytest.mark.asyncio
async def test_compose_article_with_data(mock_mcp, mock_call, mock_call_safe) -> None:
    """compose_article should include data dict when provided."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"title": "Test"}

    await tools["compose_article"](
        topic="Tax update", style="alert", data={"regulation": "PMK 28/2025"}
    )
    payload = mock_call.call_args[1]["json"]
    assert payload["data"] == {"regulation": "PMK 28/2025"}
    assert payload["style"] == "alert"


@pytest.mark.asyncio
async def test_publish_article(mock_mcp, mock_call, mock_call_safe) -> None:
    """publish_article should POST to publish endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"url": "https://balizero.com/article/123"}

    result = await tools["publish_article"](article_id="abc-123")
    assert "url" in result
    mock_call.assert_called_once_with(
        "/api/article-composer/publish/abc-123", method="POST"
    )


@pytest.mark.asyncio
async def test_list_articles_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_articles should call /api/news with defaults."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"articles": []}

    await tools["list_articles"]()
    mock_call.assert_called_once_with(
        "/api/news", params={"limit": 20, "offset": 0}
    )


@pytest.mark.asyncio
async def test_list_articles_with_category(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_articles should include category filter."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"articles": []}

    await tools["list_articles"](category="visa")
    params = mock_call.call_args[1]["params"]
    assert params["category"] == "visa"


@pytest.mark.asyncio
async def test_get_article(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_article should fetch by ID."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"title": "Article", "body": "Full content"}

    result = await tools["get_article"](article_id="art-456")
    assert result["title"] == "Article"
    mock_call.assert_called_once_with("/api/news/art-456")


@pytest.mark.asyncio
async def test_subscribe_newsletter(mock_mcp, mock_call, mock_call_safe) -> None:
    """subscribe_newsletter should POST email."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"status": "subscribed"}

    await tools["subscribe_newsletter"](email="user@test.com", name="User")
    payload = mock_call.call_args[1]["json"]
    assert payload["email"] == "user@test.com"
    assert payload["name"] == "User"


@pytest.mark.asyncio
async def test_list_subscribers(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_subscribers should pass limit and offset."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"subscribers": []}

    await tools["list_subscribers"](limit=10, offset=5)
    mock_call.assert_called_once_with(
        "/api/newsletter/subscribers", params={"limit": 10, "offset": 5}
    )
