"""
Comprehensive Integration Tests for Router Endpoints
Tests identity, legal_ingest, agentic_rag, productivity, root_endpoints
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestRootEndpointsIntegration:
    """Integration tests for root endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI

        from app.routers.root_endpoints import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()

    def test_csrf_token_endpoint(self, client):
        """Test CSRF token endpoint"""
        response = client.get("/api/csrf-token")
        assert response.status_code == 200
        data = response.json()
        assert "csrfToken" in data
        assert "sessionId" in data
        assert "X-CSRF-Token" in response.headers
        assert "X-Session-Id" in response.headers

    def test_dashboard_stats_endpoint(self, client):
        """Test dashboard stats endpoint"""
        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active_agents" in data
        assert "system_health" in data


@pytest.mark.integration
class TestIdentityRouterIntegration:
    """Integration tests for identity router"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI

        from app.modules.identity.router import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @pytest.fixture
    async def db_pool(self, postgres_container):
        """Create database pool"""
        import asyncpg

        database_url = postgres_container
        if database_url and "+" in database_url:
            database_url = database_url.replace("+psycopg2", "")

        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        yield pool
        await pool.close()

    @pytest.mark.asyncio
    async def test_login_success(self, client, db_pool):
        """Test successful login"""
        # Create test user
        async with db_pool.acquire() as conn:
            from app.modules.identity.service import IdentityService

            service = IdentityService()
            pin_hash = service.get_password_hash("1234")

            await conn.execute(
                """
                INSERT INTO team_members (full_name, email, pin_hash, role, department, active)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (email) DO UPDATE SET
                    pin_hash = EXCLUDED.pin_hash,
                    active = EXCLUDED.active
                """,
                "Test User",
                "test@example.com",
                pin_hash,
                "admin",
                "tech",
                True,
            )

        # Test login
        response = client.post(
            "/team/login",
            json={"email": "test@example.com", "pin": "1234"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data
        assert "sessionId" in data
        assert "user" in data

    def test_login_invalid_pin_format(self, client):
        """Test login with invalid PIN format"""
        response = client.post(
            "/team/login",
            json={"email": "test@example.com", "pin": "abc"},
        )
        assert response.status_code == 400

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        response = client.post(
            "/team/login",
            json={"email": "nonexistent@example.com", "pin": "1234"},
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestLegalIngestRouterIntegration:
    """Integration tests for legal ingestion router"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI

        from app.routers.legal_ingest import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_ingest_legal_document_file_not_found(self, client):
        """Test legal ingestion with non-existent file"""
        response = client.post(
            "/api/legal/ingest",
            json={"file_path": "/nonexistent/file.pdf"},
        )
        assert response.status_code == 404

    def test_ingest_legal_document_invalid_tier(self, client):
        """Test legal ingestion with invalid tier"""
        # Create a temporary file for testing
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test legal document content")
            temp_path = f.name

        try:
            response = client.post(
                "/api/legal/ingest",
                json={"file_path": temp_path, "tier": "INVALID"},
            )
            assert response.status_code == 400
        finally:
            os.unlink(temp_path)

    def test_get_collection_stats(self, client):
        """Test getting collection stats"""
        response = client.get("/api/legal/collections/stats?collection_name=legal_unified")
        assert response.status_code == 200


@pytest.mark.integration
class TestAgenticRagRouterIntegration:
    """Integration tests for agentic RAG router"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI

        from app.routers.agentic_rag import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_query_agentic_rag(self, client):
        """Test agentic RAG query endpoint"""
        # Mock orchestrator
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 0.5,
                    "route_used": "simple",
                }
            )
            mock_get.return_value = mock_orchestrator

            response = client.post(
                "/api/agentic-rag/query",
                json={"query": "Test query", "user_id": "test_user"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "sources" in data


@pytest.mark.integration
class TestProductivityRouterIntegration:
    """Integration tests for productivity router"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI

        from app.routers.productivity import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_productivity_endpoints_exist(self, client):
        """Test that productivity endpoints exist"""
        # Test various endpoints
        endpoints = [
            "/api/productivity/gmail/unread",
            "/api/productivity/calendar/events",
        ]

        for endpoint in endpoints:
            # These may require authentication, so we just check they exist
            response = client.get(endpoint)
            # Should not be 404
            assert response.status_code != 404


@pytest.mark.integration
class TestDependenciesIntegration:
    """Integration tests for dependency injection"""

    @pytest.fixture
    def app(self):
        """Create test app"""
        from fastapi import FastAPI

        app = FastAPI()
        return app

    def test_get_search_service_available(self, app):
        """Test getting search service when available"""
        from fastapi import Request

        from app.dependencies import get_search_service
        from services.search_service import SearchService

        # Set up app state
        app.state.search_service = SearchService()

        # Create mock request
        request = Request({"type": "http", "method": "GET", "path": "/"})
        request.app = app

        service = get_search_service(request)
        assert service is not None

    def test_get_search_service_unavailable(self, app):
        """Test getting search service when unavailable"""
        from fastapi import Request

        from app.dependencies import get_search_service

        # Don't set up app state
        request = Request({"type": "http", "method": "GET", "path": "/"})
        request.app = app

        with pytest.raises(Exception):  # Should raise HTTPException
            get_search_service(request)

    def test_get_ai_client_available(self, app):
        """Test getting AI client when available"""
        from fastapi import Request
        from llm.zantara_ai_client import ZantaraAIClient

        from app.dependencies import get_ai_client

        app.state.ai_client = ZantaraAIClient()

        request = Request({"type": "http", "method": "GET", "path": "/"})
        request.app = app

        client = get_ai_client(request)
        assert client is not None

    def test_get_database_pool_available(self, app, db_pool):
        """Test getting database pool when available"""
        from fastapi import Request

        from app.dependencies import get_database_pool

        app.state.db_pool = db_pool

        request = Request({"type": "http", "method": "GET", "path": "/"})
        request.app = app

        pool = get_database_pool(request)
        assert pool is not None

    def test_get_current_user_valid_token(self, app):
        """Test getting current user with valid token"""
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt

        from app.core.config import settings
        from app.dependencies import get_current_user

        # Create valid token
        token = jwt.encode(
            {"sub": "test@example.com", "user_id": "test_user", "role": "user"},
            settings.jwt_secret_key,
            algorithm="HS256",
        )

        # Create mock request with credentials
        request = Request({"type": "http", "method": "GET", "path": "/"})
        request.app = app

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = get_current_user(credentials)
        assert user["email"] == "test@example.com"

    def test_get_current_user_invalid_token(self, app):
        """Test getting current user with invalid token"""
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials

        from app.dependencies import get_current_user

        request = Request({"type": "http", "method": "GET", "path": "/"})
        request.app = app

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")
        with pytest.raises(Exception):  # Should raise HTTPException
            get_current_user(credentials)

    def test_get_cache(self, app):
        """Test getting cache service"""
        from core.cache import CacheService
        from fastapi import Request

        from app.dependencies import get_cache

        app.state.cache_service = CacheService()

        request = Request({"type": "http", "method": "GET", "path": "/"})
        request.app = app

        cache = get_cache(request)
        assert cache is not None


@pytest.mark.integration
class TestServiceHealthIntegration:
    """Integration tests for service health registry"""

    def test_service_registry_init(self):
        """Test service registry initialization"""
        from app.core.service_health import ServiceRegistry

        registry = ServiceRegistry()
        assert registry is not None
        assert len(registry._services) == 0

    def test_register_service(self):
        """Test registering a service"""
        from app.core.service_health import ServiceRegistry, ServiceStatus

        registry = ServiceRegistry()
        registry.register("test_service", ServiceStatus.HEALTHY)

        service = registry.get_service("test_service")
        assert service is not None
        assert service.status == ServiceStatus.HEALTHY

    def test_register_critical_service(self):
        """Test registering a critical service"""
        from app.core.service_health import ServiceRegistry, ServiceStatus

        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)

        service = registry.get_service("search")
        assert service.is_critical is True

    def test_get_critical_failures(self):
        """Test getting critical failures"""
        from app.core.service_health import ServiceRegistry, ServiceStatus

        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Connection failed")
        registry.register("ai", ServiceStatus.HEALTHY)

        failures = registry.get_critical_failures()
        assert len(failures) == 1
        assert failures[0].name == "search"

    def test_has_critical_failures(self):
        """Test checking for critical failures"""
        from app.core.service_health import ServiceRegistry, ServiceStatus

        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE)

        assert registry.has_critical_failures() is True

    def test_get_status(self):
        """Test getting status report"""
        from app.core.service_health import ServiceRegistry, ServiceStatus

        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("cache", ServiceStatus.DEGRADED)

        status = registry.get_status()
        assert "overall" in status
        assert "services" in status
        assert len(status["services"]) == 2

    def test_format_failures_message(self):
        """Test formatting failures message"""
        from app.core.service_health import ServiceRegistry, ServiceStatus

        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Connection failed")

        message = registry.format_failures_message()
        assert "search" in message
        assert "Connection failed" in message
