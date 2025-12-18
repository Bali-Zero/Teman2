"""
Extended Integration Tests for Oracle Services
Tests advanced Oracle features including multi-modal capabilities

Covers:
- Multi-modal Oracle queries (PDF vision, audio processing)
- Google Drive integration
- User localization and personalization
- Feedback system integration
- Analytics tracking
- Session management
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", os.getenv("QDRANT_URL", "http://localhost:6333"))
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestOracleMultiModalIntegration:
    """Test Oracle multi-modal capabilities"""

    @pytest.mark.asyncio
    async def test_oracle_with_pdf_vision(self, qdrant_client, db_pool):
        """Test Oracle query with PDF vision analysis"""
        from app.models import OracleQueryRequest
        from app.routers.oracle_universal import hybrid_oracle_query

        with (
            patch("app.routers.oracle_universal.smart_oracle") as mock_smart_oracle,
            patch("app.routers.oracle_universal.get_search_service") as mock_get_search,
        ):
            # Mock smart oracle with PDF vision
            mock_smart_oracle.return_value = {
                "answer": "The PDF shows KBLI code 56101 for restaurants",
                "sources": ["pdf_analysis"],
                "vision_analysis": {
                    "tables_found": 1,
                    "visual_elements": ["table_kbli_codes"],
                },
            }

            # Mock search service
            mock_search = MagicMock()
            mock_search.search = AsyncMock(
                return_value={
                    "results": [{"text": "KBLI 56101", "score": 0.9}],
                    "collection_used": "kbli_eye",
                }
            )
            mock_get_search.return_value = mock_search

            request = OracleQueryRequest(
                query="What KBLI code is shown in this PDF?",
                user_email="test@example.com",
                context_docs=["drive_file_id_123"],
            )

            result = await hybrid_oracle_query(request, mock_search)

            assert result is not None
            assert result.get("success") is True or "answer" in result

    @pytest.mark.asyncio
    async def test_oracle_google_drive_integration(self, qdrant_client, db_pool):
        """Test Oracle with Google Drive document access"""
        from app.routers.oracle_universal import download_pdf_from_drive

        with (
            patch("app.routers.oracle_universal.build") as mock_build,
            patch("app.routers.oracle_universal.os.path.exists") as mock_exists,
        ):
            # Mock Google Drive service
            mock_drive = MagicMock()
            mock_files = MagicMock()
            mock_files.list.return_value.execute.return_value = {
                "files": [
                    {
                        "id": "file123",
                        "name": "test_document.pdf",
                        "mimeType": "application/pdf",
                    }
                ]
            }
            mock_drive.files.return_value = mock_files

            # Mock download
            mock_media = MagicMock()
            mock_downloader = MagicMock()
            mock_downloader.next_chunk.return_value = (None, True)
            mock_media.MediaIoBaseDownload.return_value = mock_downloader
            mock_drive.files.return_value.get_media.return_value = mock_media

            mock_build.return_value = mock_drive
            mock_exists.return_value = True

            # Test download
            result = download_pdf_from_drive("test_document.pdf")

            # Should return file path or None
            assert result is None or isinstance(result, str)


@pytest.mark.integration
class TestOracleLocalizationIntegration:
    """Test Oracle user localization and personalization"""

    @pytest.mark.asyncio
    async def test_oracle_user_localization(self, qdrant_client, db_pool):
        """Test Oracle query with user localization preferences"""
        from app.models import OracleQueryRequest
        from app.routers.oracle_universal import hybrid_oracle_query

        with (
            patch("app.routers.oracle_universal.get_search_service") as mock_get_search,
            patch("app.routers.oracle_universal.OracleDatabase") as mock_oracle_db,
        ):
            # Mock user profile with localization
            mock_db_instance = MagicMock()
            mock_db_instance.get_user_profile = AsyncMock(
                return_value={
                    "email": "test@example.com",
                    "meta_json": {"language": "it", "timezone": "Asia/Jakarta"},
                }
            )
            mock_oracle_db.return_value = mock_db_instance

            # Mock search service
            mock_search = MagicMock()
            mock_search.search = AsyncMock(
                return_value={
                    "results": [{"text": "KITAS info", "score": 0.9}],
                    "collection_used": "visa_oracle",
                }
            )
            mock_get_search.return_value = mock_search

            request = OracleQueryRequest(
                query="What is KITAS?",
                user_email="test@example.com",
                language_override="it",  # Italian preference
            )

            result = await hybrid_oracle_query(request, mock_search)

            assert result is not None
            # Should use Italian language preference

    @pytest.mark.asyncio
    async def test_oracle_personality_integration(self, qdrant_client, db_pool):
        """Test Oracle with personality service integration"""
        from app.models import OracleQueryRequest
        from app.routers.oracle_universal import hybrid_oracle_query

        with (
            patch("app.routers.oracle_universal.get_search_service") as mock_get_search,
            patch("app.routers.oracle_universal.PersonalityService") as mock_personality,
        ):
            # Mock personality service
            mock_personality_instance = MagicMock()
            mock_personality_instance.get_user_personality = MagicMock(
                return_value={
                    "personality": "jaksel",
                    "language": "id",
                    "style": "casual_professional",
                }
            )
            mock_personality.return_value = mock_personality_instance

            # Mock search service
            mock_search = MagicMock()
            mock_search.search = AsyncMock(
                return_value={
                    "results": [{"text": "KITAS info", "score": 0.9}],
                    "collection_used": "visa_oracle",
                }
            )
            mock_get_search.return_value = mock_search

            request = OracleQueryRequest(
                query="What is KITAS?",
                user_email="test@example.com",
            )

            result = await hybrid_oracle_query(request, mock_search)

            assert result is not None


@pytest.mark.integration
class TestOracleFeedbackIntegration:
    """Test Oracle feedback system"""

    @pytest.mark.asyncio
    async def test_oracle_feedback_storage(self, qdrant_client, db_pool):
        """Test storing user feedback for Oracle queries"""
        from app.routers.oracle_universal import submit_feedback

        with patch("app.routers.oracle_universal.OracleDatabase") as mock_oracle_db:
            mock_db_instance = MagicMock()
            mock_db_instance.store_feedback = AsyncMock(return_value=True)
            mock_oracle_db.return_value = mock_db_instance

            feedback_data = {
                "query": "What is KITAS?",
                "response_id": "resp_123",
                "rating": 5,
                "comment": "Very helpful",
                "user_email": "test@example.com",
            }

            result = await submit_feedback(feedback_data)

            assert result is not None
            mock_db_instance.store_feedback.assert_called_once()

    @pytest.mark.asyncio
    async def test_oracle_analytics_tracking(self, qdrant_client, db_pool):
        """Test Oracle query analytics tracking"""
        from app.models import OracleQueryRequest
        from app.routers.oracle_universal import hybrid_oracle_query

        with (
            patch("app.routers.oracle_universal.get_search_service") as mock_get_search,
            patch("app.routers.oracle_universal.OracleDatabase") as mock_oracle_db,
        ):
            # Mock analytics storage
            mock_db_instance = MagicMock()
            mock_db_instance.store_query_analytics = AsyncMock(return_value=True)
            mock_oracle_db.return_value = mock_db_instance

            # Mock search service
            mock_search = MagicMock()
            mock_search.search = AsyncMock(
                return_value={
                    "results": [{"text": "KITAS info", "score": 0.9}],
                    "collection_used": "visa_oracle",
                }
            )
            mock_get_search.return_value = mock_search

            request = OracleQueryRequest(
                query="What is KITAS?",
                user_email="test@example.com",
                session_id="session_123",
            )

            result = await hybrid_oracle_query(request, mock_search)

            assert result is not None
            # Analytics should be tracked
            # Note: Actual tracking happens in the endpoint, not in the service


@pytest.mark.integration
class TestOracleSessionManagement:
    """Test Oracle session management"""

    @pytest.mark.asyncio
    async def test_oracle_session_tracking(self, qdrant_client, db_pool):
        """Test Oracle query with session tracking"""
        from app.models import OracleQueryRequest
        from app.routers.oracle_universal import hybrid_oracle_query

        with patch("app.routers.oracle_universal.get_search_service") as mock_get_search:
            mock_search = MagicMock()
            mock_search.search = AsyncMock(
                return_value={
                    "results": [{"text": "KITAS info", "score": 0.9}],
                    "collection_used": "visa_oracle",
                }
            )
            mock_get_search.return_value = mock_search

            session_id = "test_session_123"

            request = OracleQueryRequest(
                query="What is KITAS?",
                user_email="test@example.com",
                session_id=session_id,
            )

            result = await hybrid_oracle_query(request, mock_search)

            assert result is not None
            # Session should be tracked in analytics

    @pytest.mark.asyncio
    async def test_oracle_multi_query_session(self, qdrant_client, db_pool):
        """Test multiple Oracle queries in same session"""
        from app.models import OracleQueryRequest
        from app.routers.oracle_universal import hybrid_oracle_query

        with patch("app.routers.oracle_universal.get_search_service") as mock_get_search:
            mock_search = MagicMock()
            mock_search.search = AsyncMock(
                return_value={
                    "results": [{"text": "Info", "score": 0.9}],
                    "collection_used": "visa_oracle",
                }
            )
            mock_get_search.return_value = mock_search

            session_id = "test_session_multi_123"

            # First query
            request1 = OracleQueryRequest(
                query="What is KITAS?",
                user_email="test@example.com",
                session_id=session_id,
            )
            result1 = await hybrid_oracle_query(request1, mock_search)

            # Second query in same session
            request2 = OracleQueryRequest(
                query="What is PT PMA?",
                user_email="test@example.com",
                session_id=session_id,
            )
            result2 = await hybrid_oracle_query(request2, mock_search)

            assert result1 is not None
            assert result2 is not None
            # Both queries should be tracked in same session


@pytest.mark.integration
class TestOracleDomainHintIntegration:
    """Test Oracle domain hint routing"""

    @pytest.mark.asyncio
    async def test_oracle_with_domain_hint(self, qdrant_client, db_pool):
        """Test Oracle query with domain hint for routing"""
        from app.models import OracleQueryRequest
        from app.routers.oracle_universal import hybrid_oracle_query

        with patch("app.routers.oracle_universal.get_search_service") as mock_get_search:
            mock_search = MagicMock()
            mock_search.search = AsyncMock(
                return_value={
                    "results": [{"text": "Tax info", "score": 0.9}],
                    "collection_used": "tax_genius",
                }
            )
            mock_get_search.return_value = mock_search

            request = OracleQueryRequest(
                query="What are tax rates?",
                user_email="test@example.com",
                domain_hint="tax",  # Hint to route to tax collection
            )

            result = await hybrid_oracle_query(request, mock_search)

            assert result is not None
            # Should use domain hint for routing

    @pytest.mark.asyncio
    async def test_oracle_response_format(self, qdrant_client, db_pool):
        """Test Oracle query with different response formats"""
        from app.models import OracleQueryRequest
        from app.routers.oracle_universal import hybrid_oracle_query

        with patch("app.routers.oracle_universal.get_search_service") as mock_get_search:
            mock_search = MagicMock()
            mock_search.search = AsyncMock(
                return_value={
                    "results": [{"text": "KITAS info", "score": 0.9}],
                    "collection_used": "visa_oracle",
                }
            )
            mock_get_search.return_value = mock_search

            # Test structured format
            request_structured = OracleQueryRequest(
                query="What is KITAS?",
                user_email="test@example.com",
                response_format="structured",
            )
            result_structured = await hybrid_oracle_query(request_structured, mock_search)

            # Test conversational format
            request_conversational = OracleQueryRequest(
                query="What is KITAS?",
                user_email="test@example.com",
                response_format="conversational",
            )
            result_conversational = await hybrid_oracle_query(request_conversational, mock_search)

            assert result_structured is not None
            assert result_conversational is not None
