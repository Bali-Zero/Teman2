"""
Unit tests for Handlers Router
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.handlers import extract_handlers_from_router, list_all_handlers, search_handlers


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    with patch("app.core.config.settings") as mock:
        mock.database_url = "postgresql://user:pass@localhost:5432/db"
        yield mock


@pytest.fixture
def mock_router_module():
    """Mock router module"""
    module = MagicMock()
    route = MagicMock()
    route.name = "test_handler"
    route.path = "/api/test"
    route.methods = {"GET", "POST"}
    route.endpoint = MagicMock(__doc__="Test handler")
    module.router.routes = [route]
    return module


# ============================================================================
# Tests for extract_handlers_from_router
# ============================================================================


def test_extract_handlers_from_router(mock_router_module):
    """Test extracting handlers from router module"""
    # Set __name__ on mock module
    mock_router_module.__name__ = "test_module"

    handlers = extract_handlers_from_router(mock_router_module)

    assert len(handlers) == 1
    assert handlers[0]["name"] == "test_handler"
    assert handlers[0]["path"] == "/api/test"
    assert "GET" in handlers[0]["methods"]
    assert handlers[0]["module"] == "test_module"


def test_extract_handlers_from_router_no_router():
    """Test extracting handlers from module without router"""
    module = MagicMock()
    del module.router

    handlers = extract_handlers_from_router(module)
    assert handlers == []


# ============================================================================
# Tests for list_all_handlers
# ============================================================================


@pytest.mark.asyncio
async def test_list_all_handlers_success():
    """Test listing all handlers"""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # Ignore Pydantic warnings
        with patch("app.routers.handlers.extract_handlers_from_router", return_value=[]):
            # Mock Configuration to avoid environment validation
            with patch("app.routers.oracle_universal.Configuration") as mock_config_cls:
                mock_config_instance = MagicMock()
                mock_config_cls.return_value = mock_config_instance

                result = await list_all_handlers()

                assert "total_handlers" in result
                assert "categories" in result
            assert "handlers" in result
            assert isinstance(result["total_handlers"], int)


# ============================================================================
# Tests for search_handlers
# ============================================================================


@pytest.mark.asyncio
async def test_search_handlers_by_name():
    """Test searching handlers by name"""
    mock_handlers = [
        {"name": "test_handler", "path": "/api/test", "description": "Test handler"},
        {"name": "other_handler", "path": "/api/other", "description": "Other"},
    ]

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"handlers": mock_handlers}
        ):
            result = await search_handlers("test")

            assert isinstance(result, dict)
            assert "query" in result
            assert "matches" in result
            assert "handlers" in result
            assert len(result["handlers"]) > 0
            assert any("test" in h["name"].lower() for h in result["handlers"])


@pytest.mark.asyncio
async def test_search_handlers_no_results():
    """Test searching handlers with no results"""
    mock_handlers = [
        {"name": "test_handler", "path": "/api/test", "description": "Test"},
    ]

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"handlers": mock_handlers}
        ):
            result = await search_handlers("xyz123nonexistent")

            assert isinstance(result, dict)
            assert result["matches"] == 0
            assert len(result["handlers"]) == 0


@pytest.mark.asyncio
async def test_search_handlers_by_path():
    """Test searching handlers by path"""
    mock_handlers = [
        {"name": "handler1", "path": "/api/clients", "description": "Client management"},
        {"name": "handler2", "path": "/api/agents", "description": "Agent tools"},
    ]

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"handlers": mock_handlers}
        ):
            result = await search_handlers("clients")

            assert result["matches"] == 1
            assert result["handlers"][0]["path"] == "/api/clients"


@pytest.mark.asyncio
async def test_search_handlers_by_description():
    """Test searching handlers by description"""
    mock_handlers = [
        {"name": "handler1", "path": "/api/test", "description": "Upload documents"},
        {"name": "handler2", "path": "/api/other", "description": "List items"},
    ]

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"handlers": mock_handlers}
        ):
            result = await search_handlers("upload")

            assert result["matches"] == 1
            assert "upload" in result["handlers"][0]["description"].lower()


# ============================================================================
# Tests for get_handlers_by_category
# ============================================================================


@pytest.mark.asyncio
async def test_get_handlers_by_category_success():
    """Test getting handlers by category"""
    from app.routers.handlers import get_handlers_by_category

    mock_categories = {
        "agents": {
            "count": 2,
            "handlers": [
                {
                    "name": "create_agent",
                    "path": "/api/agents/create",
                    "description": "Create agent",
                },
                {"name": "list_agents", "path": "/api/agents/list", "description": "List agents"},
            ],
        }
    }

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"categories": mock_categories}
        ):
            result = await get_handlers_by_category("agents")

            assert result["count"] == 2
            assert len(result["handlers"]) == 2
            assert result["handlers"][0]["name"] == "create_agent"


@pytest.mark.asyncio
async def test_get_handlers_by_category_not_found():
    """Test getting handlers for non-existent category"""
    from fastapi import HTTPException

    from app.routers.handlers import get_handlers_by_category

    mock_categories = {"agents": {"count": 1, "handlers": []}}

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"categories": mock_categories}
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_handlers_by_category("nonexistent")

            assert exc_info.value.status_code == 404
            assert "nonexistent" in str(exc_info.value.detail)


# ============================================================================
# Additional edge cases for extract_handlers_from_router
# ============================================================================


def test_extract_handlers_no_endpoint():
    """Test extracting handlers from route without endpoint"""
    module = MagicMock()
    route = MagicMock()
    del route.endpoint  # Remove endpoint attribute
    module.router.routes = [route]

    handlers = extract_handlers_from_router(module)
    assert handlers == []


def test_extract_handlers_no_methods():
    """Test extracting handlers from route without methods"""
    module = MagicMock()
    module.__name__ = "test_module"
    route = MagicMock()
    route.name = "test"
    route.path = "/test"
    del route.methods  # Remove methods attribute
    route.endpoint = MagicMock(__doc__="Test")
    module.router.routes = [route]

    handlers = extract_handlers_from_router(module)
    assert len(handlers) == 1
    assert handlers[0]["methods"] == []


def test_extract_handlers_none_docstring():
    """Test extracting handlers with None docstring"""
    module = MagicMock()
    module.__name__ = "test_module"
    route = MagicMock()
    route.name = "test"
    route.path = "/test"
    route.methods = {"GET"}
    route.endpoint = MagicMock(__doc__=None)
    module.router.routes = [route]

    handlers = extract_handlers_from_router(module)
    assert len(handlers) == 1
    assert handlers[0]["description"] == ""


# ============================================================================
# Additional Edge Cases for search_handlers
# ============================================================================


@pytest.mark.asyncio
async def test_search_handlers_case_insensitive():
    """Test searching handlers is case-insensitive"""
    mock_handlers = [
        {"name": "TestHandler", "path": "/api/test", "description": "Test handler"},
        {"name": "OTHER_HANDLER", "path": "/api/other", "description": "Other handler"},
    ]

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"handlers": mock_handlers}
        ):
            result_lower = await search_handlers("test")
            result_upper = await search_handlers("TEST")
            result_mixed = await search_handlers("TeSt")

            assert result_lower["matches"] == result_upper["matches"]
            assert result_upper["matches"] == result_mixed["matches"]


@pytest.mark.asyncio
async def test_search_handlers_partial_match():
    """Test searching handlers with partial matches"""
    mock_handlers = [
        {"name": "create_client", "path": "/api/clients/create", "description": "Create client"},
        {"name": "update_client", "path": "/api/clients/update", "description": "Update client"},
        {"name": "delete_client", "path": "/api/clients/delete", "description": "Delete client"},
    ]

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"handlers": mock_handlers}
        ):
            result = await search_handlers("client")

            assert result["matches"] == 3
            assert all(
                "client" in h["name"].lower() or "client" in h["path"].lower()
                for h in result["handlers"]
            )


@pytest.mark.asyncio
async def test_search_handlers_special_characters():
    """Test searching handlers with special characters"""
    mock_handlers = [
        {"name": "test_handler", "path": "/api/test", "description": "Test handler"},
    ]

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"handlers": mock_handlers}
        ):
            # Special characters should be handled gracefully
            result = await search_handlers("test@#$%")

            # Should still find matches if the base word matches
            assert isinstance(result, dict)
            assert "matches" in result


@pytest.mark.asyncio
async def test_search_handlers_empty_query():
    """Test searching handlers with empty query"""
    mock_handlers = [
        {"name": "handler1", "path": "/api/test1", "description": "Handler 1"},
        {"name": "handler2", "path": "/api/test2", "description": "Handler 2"},
    ]

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"handlers": mock_handlers}
        ):
            result = await search_handlers("")

            # Empty query should match all or return empty
            assert isinstance(result, dict)
            assert "matches" in result


@pytest.mark.asyncio
async def test_search_handlers_multiple_matches():
    """Test searching handlers returns multiple matches"""
    mock_handlers = [
        {"name": "create_user", "path": "/api/users/create", "description": "Create user"},
        {"name": "create_client", "path": "/api/clients/create", "description": "Create client"},
        {"name": "update_user", "path": "/api/users/update", "description": "Update user"},
    ]

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"handlers": mock_handlers}
        ):
            result = await search_handlers("create")

            assert result["matches"] == 2
            assert len(result["handlers"]) == 2
            assert all("create" in h["name"].lower() for h in result["handlers"])


# ============================================================================
# Additional Edge Cases for get_handlers_by_category
# ============================================================================


@pytest.mark.asyncio
async def test_get_handlers_by_category_empty_category():
    """Test getting handlers for category with no handlers"""
    from app.routers.handlers import get_handlers_by_category

    mock_categories = {
        "empty_category": {"count": 0, "handlers": []},
    }

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"categories": mock_categories}
        ):
            result = await get_handlers_by_category("empty_category")

            assert result["count"] == 0
            assert len(result["handlers"]) == 0


@pytest.mark.asyncio
async def test_get_handlers_by_category_case_sensitive():
    """Test that category names are case-sensitive"""
    from fastapi import HTTPException

    from app.routers.handlers import get_handlers_by_category

    mock_categories = {
        "agents": {"count": 1, "handlers": [{"name": "test", "path": "/test"}]},
    }

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"categories": mock_categories}
        ):
            # Should work with exact case
            result = await get_handlers_by_category("agents")
            assert result["count"] == 1

            # Should fail with different case
            with pytest.raises(HTTPException) as exc_info:
                await get_handlers_by_category("Agents")

            assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_handlers_by_category_special_characters():
    """Test getting handlers for category with special characters"""

    from app.routers.handlers import get_handlers_by_category

    mock_categories = {
        "test-category": {"count": 1, "handlers": [{"name": "test", "path": "/test"}]},
    }

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch(
            "app.routers.handlers.list_all_handlers", return_value={"categories": mock_categories}
        ):
            result = await get_handlers_by_category("test-category")

            assert result["count"] == 1


# ============================================================================
# Additional Edge Cases for list_all_handlers
# ============================================================================


@pytest.mark.asyncio
async def test_list_all_handlers_empty_modules():
    """Test listing handlers when modules return empty handlers"""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch("app.routers.handlers.extract_handlers_from_router", return_value=[]):
            with patch("app.routers.oracle_universal.Configuration") as mock_config_cls:
                mock_config_instance = MagicMock()
                mock_config_cls.return_value = mock_config_instance

                result = await list_all_handlers()

                assert result["total_handlers"] == 0
                assert isinstance(result["categories"], dict)


@pytest.mark.asyncio
async def test_list_all_handlers_duplicate_modules():
    """Test listing handlers handles duplicate modules gracefully"""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        # The router already has oracle_universal twice in modules list
        with patch("app.routers.handlers.extract_handlers_from_router", return_value=[]):
            with patch("app.routers.oracle_universal.Configuration") as mock_config_cls:
                mock_config_instance = MagicMock()
                mock_config_cls.return_value = mock_config_instance

                result = await list_all_handlers()

                # Should handle duplicates without error
                assert isinstance(result, dict)
                assert "total_handlers" in result


@pytest.mark.asyncio
async def test_list_all_handlers_response_structure():
    """Test that list_all_handlers returns correct structure"""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with patch("app.routers.handlers.extract_handlers_from_router", return_value=[]):
            with patch("app.routers.oracle_universal.Configuration") as mock_config_cls:
                mock_config_instance = MagicMock()
                mock_config_cls.return_value = mock_config_instance

                result = await list_all_handlers()

                assert "total_handlers" in result
                assert "categories" in result
                assert "handlers" in result
                assert "last_updated" in result
                assert isinstance(result["total_handlers"], int)
                assert isinstance(result["categories"], dict)
                assert isinstance(result["handlers"], list)
