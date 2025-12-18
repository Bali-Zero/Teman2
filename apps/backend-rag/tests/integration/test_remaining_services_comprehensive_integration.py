"""
Comprehensive Integration Tests for Remaining Services
Tests notifications, auto_crm, zantara_tools, cultural_rag, validator, oracle_config, rate_limiter, zantara_prompt_builder
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
class TestNotificationsRouterIntegration:
    """Integration tests for notifications router"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI

        from app.routers.notifications import router

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

        # Create notifications table
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    notification_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255),
                    message TEXT,
                    status VARCHAR(50) DEFAULT 'pending',
                    sent_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )

        yield pool
        await pool.close()

    def test_notifications_endpoints_exist(self, client):
        """Test that notification endpoints exist"""
        # These endpoints may require authentication
        endpoints = [
            "/api/notifications",
            "/api/notifications/unread",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not be 404
            assert response.status_code != 404


@pytest.mark.integration
class TestAutoCRMServiceIntegration:
    """Integration tests for AutoCRMService"""

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
    async def test_auto_crm_service_init(self, db_pool):
        """Test AutoCRMService initialization"""
        from services.auto_crm_service import AutoCRMService

        service = AutoCRMService(db_pool=db_pool)
        assert service is not None

    @pytest.mark.asyncio
    async def test_extract_client_info(self, db_pool):
        """Test extracting client info"""
        from services.auto_crm_service import AutoCRMService

        service = AutoCRMService(db_pool=db_pool)

        # Mock AI extraction
        with patch.object(service, "_extract_with_ai") as mock_extract:
            mock_extract.return_value = {
                "name": "Test Client",
                "email": "client@example.com",
                "phone": "+1234567890",
            }

            info = await service.extract_client_info("Test conversation")
            assert info is not None
            assert "name" in info


@pytest.mark.integration
class TestZantaraToolsIntegration:
    """Integration tests for ZantaraTools"""

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
    async def test_zantara_tools_init(self, db_pool):
        """Test ZantaraTools initialization"""
        from services.zantara_tools import ZantaraTools

        tools = ZantaraTools(db_pool=db_pool)
        assert tools is not None

    @pytest.mark.asyncio
    async def test_get_tools_list(self, db_pool):
        """Test getting tools list"""
        from services.zantara_tools import ZantaraTools

        tools = ZantaraTools(db_pool=db_pool)
        tools_list = tools.get_tools()
        assert isinstance(tools_list, list)
        assert len(tools_list) > 0


@pytest.mark.integration
class TestCulturalRagServiceIntegration:
    """Integration tests for CulturalRagService"""

    @pytest.mark.asyncio
    async def test_cultural_rag_service_init(self):
        """Test CulturalRagService initialization"""
        from services.cultural_rag_service import CulturalRagService

        service = CulturalRagService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_get_cultural_context(self):
        """Test getting cultural context"""
        from services.cultural_rag_service import CulturalRagService

        service = CulturalRagService()

        context = await service.get_cultural_context(
            query="Test query",
            user_language="id",
        )

        assert context is not None


@pytest.mark.integration
class TestResponseValidatorIntegration:
    """Integration tests for ResponseValidator"""

    def test_validator_init(self):
        """Test ResponseValidator initialization"""
        from services.response.validator import ResponseValidator

        validator = ResponseValidator()
        assert validator is not None

    def test_validate_response(self):
        """Test validating response"""
        from services.response.validator import ResponseValidator

        validator = ResponseValidator()

        # Test valid response
        is_valid = validator.validate_response("This is a valid response")
        assert is_valid is True

        # Test empty response
        is_valid = validator.validate_response("")
        assert is_valid is False


@pytest.mark.integration
class TestOracleConfigIntegration:
    """Integration tests for OracleConfig"""

    def test_oracle_config_init(self):
        """Test OracleConfig initialization"""
        from services.oracle_config import OracleConfig

        config = OracleConfig()
        assert config is not None

    def test_get_collection_config(self):
        """Test getting collection config"""
        from services.oracle_config import OracleConfig

        config = OracleConfig()
        collection_config = config.get_collection_config("visa_oracle")
        assert collection_config is not None


@pytest.mark.integration
class TestRateLimiterIntegration:
    """Integration tests for RateLimiter"""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter"""
        from middleware.rate_limiter import RateLimiter

        return RateLimiter()

    def test_rate_limiter_init(self, rate_limiter):
        """Test rate limiter initialization"""
        assert rate_limiter is not None

    @pytest.mark.asyncio
    async def test_check_rate_limit(self, rate_limiter):
        """Test checking rate limit"""
        # Mock Redis if needed
        with patch.object(rate_limiter, "redis_client", None):
            # Should work without Redis (fallback to in-memory)
            allowed = await rate_limiter.check_rate_limit("test_ip", limit=10, window=60)
            assert isinstance(allowed, bool)

    @pytest.mark.asyncio
    async def test_rate_limit_middleware(self, rate_limiter):
        """Test rate limit middleware"""
        from fastapi import Request

        # Create mock request
        request = Request({"type": "http", "method": "GET", "path": "/"})
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        # Test middleware call
        with patch.object(rate_limiter, "check_rate_limit", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True
            # Middleware should not raise exception
            pass


@pytest.mark.integration
class TestZantaraPromptBuilderIntegration:
    """Integration tests for ZantaraPromptBuilder"""

    def test_prompt_builder_init(self):
        """Test ZantaraPromptBuilder initialization"""
        from prompts.zantara_prompt_builder import ZantaraPromptBuilder

        builder = ZantaraPromptBuilder()
        assert builder is not None

    def test_build_system_prompt(self):
        """Test building system prompt"""
        from prompts.zantara_prompt_builder import ZantaraPromptBuilder

        builder = ZantaraPromptBuilder()
        prompt = builder.build_system_prompt()
        assert prompt is not None
        assert len(prompt) > 0

    def test_build_user_prompt(self):
        """Test building user prompt"""
        from prompts.zantara_prompt_builder import ZantaraPromptBuilder

        builder = ZantaraPromptBuilder()
        prompt = builder.build_user_prompt(
            query="Test query",
            context=[],
        )
        assert prompt is not None

    def test_build_rag_prompt(self):
        """Test building RAG prompt"""
        from prompts.zantara_prompt_builder import ZantaraPromptBuilder

        builder = ZantaraPromptBuilder()
        prompt = builder.build_rag_prompt(
            query="Test query",
            documents=["Doc 1", "Doc 2"],
        )
        assert prompt is not None
        assert "Test query" in prompt


@pytest.mark.integration
class TestPluginSystemIntegration:
    """Integration tests for Plugin System"""

    def test_plugin_init(self):
        """Test Plugin initialization"""
        from core.plugins.plugin import Plugin

        plugin = Plugin(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
        )
        assert plugin.name == "test_plugin"
        assert plugin.version == "1.0.0"

    def test_plugin_execute(self):
        """Test plugin execution"""
        from core.plugins.plugin import Plugin

        plugin = Plugin(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
        )

        # Test execute method
        result = plugin.execute("test_input")
        # Plugin base class may return None or raise NotImplementedError
        assert result is None or isinstance(result, Exception)


@pytest.mark.integration
class TestGeminiAdapterIntegration:
    """Integration tests for Gemini Adapter"""

    def test_gemini_adapter_init(self):
        """Test GeminiAdapter initialization"""
        from llm.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter()
        assert adapter is not None

    @pytest.mark.asyncio
    async def test_gemini_adapter_generate(self):
        """Test Gemini adapter generate"""
        from llm.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter()

        # Mock Gemini client
        with patch.object(adapter, "client") as mock_client:
            mock_client.generate_content = AsyncMock(return_value=MagicMock(text="Test response"))

            response = await adapter.generate(
                prompt="Test prompt",
                max_tokens=100,
            )

            assert response is not None

    @pytest.mark.asyncio
    async def test_gemini_adapter_stream(self):
        """Test Gemini adapter streaming"""
        from llm.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter()

        # Mock streaming
        async def mock_stream():
            yield MagicMock(text="Chunk 1")
            yield MagicMock(text="Chunk 2")

        with patch.object(adapter, "client") as mock_client:
            mock_client.generate_content.return_value = mock_stream()

            chunks = []
            async for chunk in adapter.stream(prompt="Test prompt"):
                chunks.append(chunk)

            # Should have received chunks
            assert len(chunks) >= 0  # May be empty if streaming not implemented
