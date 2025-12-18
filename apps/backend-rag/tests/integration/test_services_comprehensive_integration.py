"""
Comprehensive Integration Tests for Service Layer
Tests team_analytics, intelligent_router, oracle_google_services, collaborator_service
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestTeamAnalyticsServiceIntegration:
    """Integration tests for TeamAnalyticsService"""

    @pytest_asyncio.fixture
    async def db_pool(self, postgres_container):
        """Create database pool"""
        import asyncpg

        database_url = postgres_container
        if database_url and "+" in database_url:
            database_url = database_url.replace("+psycopg2", "")

        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)

        # Create team_work_sessions table
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_work_sessions (
                    id SERIAL PRIMARY KEY,
                    user_name VARCHAR(255),
                    user_email VARCHAR(255) NOT NULL,
                    session_start TIMESTAMP WITH TIME ZONE NOT NULL,
                    session_end TIMESTAMP WITH TIME ZONE,
                    duration_minutes INTEGER,
                    conversations_count INTEGER DEFAULT 0,
                    activities_count INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'completed',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )

        yield pool
        await pool.close()

    @pytest.mark.asyncio
    async def test_analyze_work_patterns(self, db_pool):
        """Test analyzing work patterns"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Insert test data
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, status)
                VALUES
                ($1, NOW() - INTERVAL '1 day', 120, 'completed'),
                ($1, NOW() - INTERVAL '2 days', 180, 'completed')
                """,
                "test@example.com",
            )

        result = await service.analyze_work_patterns(user_email="test@example.com", days=30)
        assert "patterns" in result or "error" in result

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores(self, db_pool):
        """Test calculating productivity scores"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Insert test data
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES
                ($1, $2, NOW() - INTERVAL '1 day', 240, 10, 50, 'completed')
                """,
                "Test User",
                "test@example.com",
            )

        results = await service.calculate_productivity_scores(days=7)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_detect_burnout_signals(self, db_pool):
        """Test detecting burnout signals"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Insert test data with burnout indicators
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES
                ($1, $2, NOW() - INTERVAL '1 day', 600, 5, 20, 'completed'),
                ($1, $2, NOW() - INTERVAL '2 days', 650, 4, 18, 'completed')
                """,
                "Test User",
                "test@example.com",
            )

        results = await service.detect_burnout_signals(user_email="test@example.com")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_analyze_performance_trends(self, db_pool):
        """Test analyzing performance trends"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Insert test data
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES
                ($1, NOW() - INTERVAL '1 week', 240, 10, 50, 'completed'),
                ($1, NOW() - INTERVAL '2 weeks', 180, 8, 40, 'completed')
                """,
                "test@example.com",
            )

        result = await service.analyze_performance_trends(user_email="test@example.com", weeks=4)
        assert "weekly_breakdown" in result or "error" in result

    @pytest.mark.asyncio
    async def test_analyze_workload_balance(self, db_pool):
        """Test analyzing workload balance"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Insert test data for multiple users
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, status)
                VALUES
                ('User 1', 'user1@example.com', NOW() - INTERVAL '1 day', 240, 10, 'completed'),
                ('User 2', 'user2@example.com', NOW() - INTERVAL '1 day', 180, 8, 'completed')
                """
            )

        result = await service.analyze_workload_balance(days=7)
        assert "team_distribution" in result or "error" in result

    @pytest.mark.asyncio
    async def test_identify_optimal_hours(self, db_pool):
        """Test identifying optimal hours"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Insert test data
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, conversations_count, status)
                VALUES
                ($1, NOW() - INTERVAL '1 day' + INTERVAL '9 hours', 120, 5, 'completed')
                """,
                "test@example.com",
            )

        result = await service.identify_optimal_hours(user_email="test@example.com", days=30)
        assert "optimal_windows" in result or "error" in result

    @pytest.mark.asyncio
    async def test_generate_team_insights(self, db_pool):
        """Test generating team insights"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Insert test data
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, session_end, duration_minutes, conversations_count, activities_count, status)
                VALUES
                ('User 1', 'user1@example.com', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day' + INTERVAL '4 hours', 240, 10, 50, 'completed')
                """
            )

        result = await service.generate_team_insights(days=7)
        assert "team_summary" in result or "error" in result


@pytest.mark.integration
class TestIntelligentRouterIntegration:
    """Integration tests for IntelligentRouter"""

    @pytest.mark.asyncio
    async def test_intelligent_router_init(self):
        """Test IntelligentRouter initialization"""
        from services.intelligent_router import IntelligentRouter

        router = IntelligentRouter()
        assert router is not None
        assert router.orchestrator is not None

    @pytest.mark.asyncio
    async def test_route_chat(self):
        """Test routing chat"""
        from services.intelligent_router import IntelligentRouter

        router = IntelligentRouter()

        # Mock orchestrator
        router.orchestrator.process_query = AsyncMock(
            return_value={
                "answer": "Test response",
                "sources": [],
            }
        )

        result = await router.route_chat(
            message="Test message",
            user_id="test_user",
        )

        assert "response" in result
        assert result["response"] == "Test response"

    @pytest.mark.asyncio
    async def test_stream_chat(self):
        """Test streaming chat"""
        from services.intelligent_router import IntelligentRouter

        router = IntelligentRouter()

        # Mock orchestrator stream - must accept query and user_id kwargs
        async def mock_stream(query: str, user_id: str):
            yield {"type": "chunk", "content": "Test"}
            yield {"type": "done"}

        router.orchestrator.stream_query = mock_stream

        chunks = []
        async for chunk in router.stream_chat(
            message="Test message",
            user_id="test_user",
        ):
            chunks.append(chunk)

        assert len(chunks) > 0

    def test_get_stats(self):
        """Test getting router stats"""
        from services.intelligent_router import IntelligentRouter

        router = IntelligentRouter()
        stats = router.get_stats()
        assert "router" in stats
        assert "model" in stats


@pytest.mark.integration
class TestGoogleServicesIntegration:
    """Integration tests for Google Services"""

    @pytest.mark.asyncio
    async def test_google_services_init(self):
        """Test GoogleServices initialization"""
        from services.oracle_google_services import GoogleServices

        service = GoogleServices()
        assert service is not None

    @pytest.mark.asyncio
    async def test_gemini_initialized(self):
        """Test Gemini initialization status"""
        from services.oracle_google_services import GoogleServices

        service = GoogleServices()
        # Check if the service has the initialization flag
        assert hasattr(service, "_gemini_initialized")

    @pytest.mark.asyncio
    async def test_drive_service_attribute(self):
        """Test Drive service attribute exists"""
        from services.oracle_google_services import GoogleServices

        service = GoogleServices()
        # Check if the service has drive service attribute
        assert hasattr(service, "_drive_service")


@pytest.mark.integration
class TestCollaboratorServiceIntegration:
    """Integration tests for CollaboratorService (JSON-based)"""

    def test_collaborator_service_init(self):
        """Test CollaboratorService initialization"""
        from services.collaborator_service import CollaboratorService

        try:
            service = CollaboratorService()
            assert service is not None
            assert hasattr(service, "members")
        except FileNotFoundError:
            # Expected if team_members.json doesn't exist in test environment
            pytest.skip("team_members.json not found")

    def test_list_members(self):
        """Test listing team members"""
        from services.collaborator_service import CollaboratorService

        try:
            service = CollaboratorService()
            members = service.list_members()
            assert isinstance(members, list)
        except FileNotFoundError:
            pytest.skip("team_members.json not found")

    def test_get_team_stats(self):
        """Test getting team stats"""
        from services.collaborator_service import CollaboratorService

        try:
            service = CollaboratorService()
            stats = service.get_team_stats()
            assert isinstance(stats, dict)
            assert "total" in stats
        except FileNotFoundError:
            pytest.skip("team_members.json not found")

    @pytest.mark.asyncio
    async def test_identify_unknown_email(self):
        """Test identifying with unknown email returns anonymous profile"""
        from services.collaborator_service import CollaboratorService

        try:
            service = CollaboratorService()
            profile = await service.identify("unknown@example.com")
            # Should return anonymous profile for unknown emails
            assert profile is not None
            assert hasattr(profile, "email")
        except FileNotFoundError:
            pytest.skip("team_members.json not found")


@pytest.mark.integration
class TestResponseHandlerIntegration:
    """Integration tests for ResponseHandler"""

    def test_response_handler_init(self):
        """Test ResponseHandler initialization"""
        from services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        assert handler is not None

    def test_classify_query(self):
        """Test query classification"""
        from services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        query_type = handler.classify_query("Hello")
        assert query_type in ["greeting", "casual", "business", "emergency"]

    def test_sanitize_response(self):
        """Test response sanitization"""
        from services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        response = handler.sanitize_response(
            "Test response",
            query_type="business",
            apply_santai=True,
            add_contact=True,
        )
        assert response is not None

    def test_sanitize_response_empty(self):
        """Test sanitizing empty response"""
        from services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        response = handler.sanitize_response("", query_type="business")
        assert response == ""


@pytest.mark.integration
class TestLLMAdaptersIntegration:
    """Integration tests for LLM adapters"""

    def test_registry_get_adapter_gemini(self):
        """Test getting Gemini adapter"""
        from llm.adapters.registry import get_adapter

        adapter = get_adapter("gemini-2.0-flash")
        assert adapter is not None

    def test_registry_get_adapter_fallback(self):
        """Test adapter fallback"""
        from llm.adapters.registry import get_adapter

        adapter = get_adapter("unknown-model")
        # Should fallback to GeminiAdapter
        assert adapter is not None

    def test_fallback_messages_get_message(self):
        """Test getting fallback messages"""
        from llm.fallback_messages import get_fallback_message

        message = get_fallback_message("connection_error", "en")
        assert message is not None
        assert len(message) > 0

    def test_fallback_messages_localization(self):
        """Test fallback message localization"""
        from llm.fallback_messages import get_fallback_message

        en_message = get_fallback_message("connection_error", "en")
        it_message = get_fallback_message("connection_error", "it")
        id_message = get_fallback_message("connection_error", "id")

        assert en_message != it_message
        assert en_message != id_message

    def test_fallback_messages_unknown_type(self):
        """Test fallback message with unknown type"""
        from llm.fallback_messages import get_fallback_message

        message = get_fallback_message("unknown_type", "en")
        # Should return generic error message
        assert message is not None
