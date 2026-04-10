"""
Critical path tests for dependencies.py — the module imported by ALL routers.

A broken import in this file crashes the entire application at startup
(incident 2026-02-16). These tests verify import integrity and
dependency injection behavior.
"""

from unittest.mock import MagicMock

import pytest

# --- Import Chain Tests (P0 Critical) ---


class TestImportChain:
    """Verify that the dependencies module and all its functions are importable.

    This is the most critical test — a broken import here means total app failure.
    """

    def test_dependencies_module_imports(self):
        """The dependencies module should import without errors."""
        from backend.app import dependencies

        assert dependencies is not None

    def test_all_dependency_functions_exist(self):
        """All known DI functions should be importable."""
        from backend.app.dependencies import (
            get_ai_client,
            get_cache,
            get_channel_router,
            get_current_portal_client,
            get_current_user,
            get_current_user_email,
            get_current_user_optional,
            get_database_pool,
            get_intelligent_router,
            get_memory_service,
            get_optional_database_pool,
            get_orchestrator,
            get_search_service,
            require_team_member,
        )

        # All should be callable
        for fn in [
            get_search_service,
            get_ai_client,
            get_intelligent_router,
            get_memory_service,
            get_database_pool,
            get_current_user,
            get_current_user_optional,
            get_current_user_email,
            require_team_member,
            get_cache,
            get_orchestrator,
            get_optional_database_pool,
            get_current_portal_client,
            get_channel_router,
        ]:
            assert callable(fn), f"{fn.__name__} is not callable"

    def test_typing_imports_present(self):
        """Critical: typing imports (Any, Annotated, etc.) must be present.

        The 2026-02-16 outage was caused by a missing 'Any' import in deps sub-modules.
        dependencies.py re-exports from deps/ sub-modules — verify typing in those.
        """
        import inspect

        from backend.app.deps import services, orchestrator

        svc_source = inspect.getsource(services)
        assert "from typing import" in svc_source, "deps/services.py missing typing import"
        assert "Any" in svc_source, "deps/services.py missing Any"

        orch_source = inspect.getsource(orchestrator)
        assert "Any" in orch_source, "deps/orchestrator.py missing Any"


# --- DI Function Behavior Tests ---


class TestServiceDependencies:
    """Test that DI functions correctly retrieve services from app.state."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock Request with populated app.state."""
        request = MagicMock()
        request.app.state.search_service = MagicMock()
        request.app.state.ai_client = MagicMock()
        request.app.state.intelligent_router = MagicMock()
        request.app.state.memory_service = MagicMock()
        request.app.state.db_pool = MagicMock()
        request.app.state.cache_service = MagicMock()
        request.app.state.channel_router = MagicMock()
        return request

    def test_get_search_service_success(self, mock_request):
        from backend.app.dependencies import get_search_service

        result = get_search_service(mock_request)
        assert result is mock_request.app.state.search_service

    def test_get_search_service_missing_raises_503(self):
        from fastapi import HTTPException

        from backend.app.dependencies import get_search_service

        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # Empty state

        with pytest.raises(HTTPException) as exc_info:
            get_search_service(request)
        assert exc_info.value.status_code == 503

    def test_get_ai_client_success(self, mock_request):
        from backend.app.dependencies import get_ai_client

        result = get_ai_client(mock_request)
        assert result is mock_request.app.state.ai_client

    def test_get_ai_client_missing_raises_503(self):
        from fastapi import HTTPException

        from backend.app.dependencies import get_ai_client

        request = MagicMock()
        request.app.state = MagicMock(spec=[])

        with pytest.raises(HTTPException) as exc_info:
            get_ai_client(request)
        assert exc_info.value.status_code == 503

    def test_get_database_pool_success(self, mock_request):
        from backend.app.dependencies import get_database_pool

        result = get_database_pool(mock_request)
        assert result is mock_request.app.state.db_pool

    def test_get_database_pool_missing_raises_503(self):
        from fastapi import HTTPException

        from backend.app.dependencies import get_database_pool

        request = MagicMock()
        request.app.state = MagicMock(spec=[])

        with pytest.raises(HTTPException) as exc_info:
            get_database_pool(request)
        assert exc_info.value.status_code == 503

    def test_get_optional_database_pool_returns_none(self):
        from backend.app.dependencies import get_optional_database_pool

        request = MagicMock()
        request.app.state = MagicMock(spec=[])

        result = get_optional_database_pool(request)
        assert result is None

    def test_get_cache_success(self, mock_request):
        from backend.app.dependencies import get_cache

        result = get_cache(mock_request)
        assert result is not None


class TestAuthDependencies:
    """Test authentication dependency functions."""

    def test_require_team_member_allows_admin(self):
        from backend.app.dependencies import require_team_member

        user = {"email": "admin@balizero.com", "role": "admin"}
        result = require_team_member(user)
        assert result == user

    def test_require_team_member_allows_agent(self):
        from backend.app.dependencies import require_team_member

        user = {"email": "agent@balizero.com", "role": "agent"}
        result = require_team_member(user)
        assert result == user

    def test_require_team_member_rejects_client(self):
        from fastapi import HTTPException

        from backend.app.dependencies import require_team_member

        user = {"email": "client@example.com", "role": "client"}
        with pytest.raises(HTTPException) as exc_info:
            require_team_member(user)
        assert exc_info.value.status_code == 403

    def test_get_current_user_email(self):
        from backend.app.dependencies import get_current_user_email

        user = {"email": "test@balizero.com", "role": "admin"}
        result = get_current_user_email(user)
        assert result == "test@balizero.com"


# --- Import Chain Guard: ALL deps/ sub-modules (P0 Critical) ---


class TestAllDepsTypingGuards:
    """Guard against rogue AI agents silently removing 'Any' from typing imports.

    Feb 2026 outage: missing Any in deps sub-module crashed prod at startup.
    dependencies.py is imported by 77+ routers — one missing import = total failure.
    """

    def test_all_deps_modules_have_typing_any(self):
        """ALL deps/ sub-modules must retain `from typing import ... Any`.

        Policy: Rogue AI agents (Gemini, Windsurf, Cursor) silently remove
        unused-looking imports. Feb 2026 outage: missing Any crashed prod.
        This test covers ALL 7 modules, not just services+orchestrator.
        """
        import inspect

        from backend.app.deps import (
            auth,
            crm_access,
            database,
            orchestrator,
            owner,
            permissions,
            services,
        )

        for module in [auth, database, services, orchestrator, owner, permissions, crm_access]:
            source = inspect.getsource(module)
            assert "Any" in source, (
                f"{module.__name__} missing 'Any' — rogue AI removal detected. "
                f"Restore: from typing import Any"
            )

    def test_dependencies_getattr_exposes_orchestrator(self):
        """dependencies.__getattr__ must expose _agentic_rag_orchestrator.

        health.py accesses this directly. Removing __getattr__ breaks health endpoint.
        """
        from backend.app import dependencies

        val = getattr(dependencies, "_agentic_rag_orchestrator", "MISSING")
        assert val != "MISSING", "__getattr__ not forwarding _agentic_rag_orchestrator"

    def test_dependencies_reexports_all_expected_functions(self):
        """Verify dependencies.py re-exports all DI functions used by 77+ routers.

        If a new deps/ function is added but not re-exported,
        routers importing from dependencies.py will break at import time.
        """
        from backend.app import dependencies

        expected = [
            # From deps/auth.py
            "get_current_user",
            "get_current_user_optional",
            "get_current_user_email",
            "require_team_member",
            "security",
            "get_current_portal_client",
            # From deps/database.py
            "get_database_pool",
            "get_database",
            "get_db",
            "get_optional_database_pool",
            # From deps/services.py
            "get_search_service",
            "get_ai_client",
            "get_intelligent_router",
            "get_memory_service",
            "get_cache",
            "get_channel_router",
            # From deps/orchestrator.py
            "get_orchestrator",
            # From deps/owner.py
            "require_owner",
            "OWNER_EMAILS",
        ]
        for name in expected:
            assert hasattr(dependencies, name), f"dependencies.py missing re-export: {name}"
