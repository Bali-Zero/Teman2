"""
API Tests for oracle_database - Coverage 95% Target
Tests DatabaseManager methods

Coverage:
- __init__ method
- _init_engine method
- get_user_profile method
- store_query_analytics method
- store_feedback method
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestDatabaseManager:
    """Test DatabaseManager class"""

    def test_init(self):
        """Test DatabaseManager initialization"""
        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"
        manager = DatabaseManager(db_url)

        assert manager.database_url == db_url
        assert manager._engine is not None

    def test_init_engine_success(self):
        """Test _init_engine with successful initialization"""
        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"
        manager = DatabaseManager(db_url)

        assert manager._engine is not None

    def test_init_engine_failure(self):
        """Test _init_engine with initialization failure"""
        from backend.services.oracle_database import DatabaseManager

        with patch(
            "backend.services.oracle_database.create_engine",
            side_effect=Exception("Connection error"),
        ):
            with pytest.raises(Exception):
                DatabaseManager("invalid://url")

    @pytest.mark.asyncio
    async def test_get_user_profile_from_team_members(self):
        """Test get_user_profile loading from team_members"""
        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"

        with patch("backend.services.oracle_database.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=None)

            manager = DatabaseManager(db_url)

            # Mock team_members import by patching the import inside the method
            with patch(
                "data.team_members.TEAM_MEMBERS",
                [
                    {
                        "id": "test_user",
                        "email": "test@example.com",
                        "name": "Test User",
                        "role": "Member",
                        "preferred_language": "en",
                    }
                ],
            ):
                result = await manager.get_user_profile("test@example.com")

                assert result is not None
                assert result["email"] == "test@example.com"
                assert result["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_get_user_profile_from_database(self):
        """Test get_user_profile loading from PostgreSQL"""
        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"

        with patch("backend.services.oracle_database.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.mappings.return_value.fetchone.return_value = {
                "id": "db_user",
                "email": "db@example.com",
                "name": "DB User",
                "role": "Admin",
                "status": "active",
                "language_preference": "en",
                "meta_json": "{}",
                "role_level": "admin",
                "timezone": "UTC",
            }

            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=None)

            manager = DatabaseManager(db_url)

            # Mock team_members import to fail
            with patch("data.team_members.TEAM_MEMBERS", side_effect=ImportError()):
                result = await manager.get_user_profile("db@example.com")

                assert result is not None
                assert result["email"] == "db@example.com"

    @pytest.mark.asyncio
    async def test_get_user_profile_not_found(self):
        """Test get_user_profile when user not found"""
        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"

        with patch("backend.services.oracle_database.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.mappings.return_value.fetchone.return_value = None

            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=None)

            manager = DatabaseManager(db_url)

            with patch("data.team_members.TEAM_MEMBERS", []):
                result = await manager.get_user_profile("notfound@example.com")

                assert result is None

    @pytest.mark.asyncio
    async def test_get_user_profile_db_error(self):
        """Test get_user_profile with database error"""
        from sqlalchemy.exc import SQLAlchemyError

        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"

        with patch("backend.services.oracle_database.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = SQLAlchemyError("DB error")

            mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=None)

            manager = DatabaseManager(db_url)

            with patch("data.team_members.TEAM_MEMBERS", []):
                with pytest.raises(SQLAlchemyError):
                    await manager.get_user_profile("test@example.com")

    @pytest.mark.asyncio
    async def test_store_query_analytics_success(self):
        """Test store_query_analytics with successful storage"""
        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"

        with patch("backend.services.oracle_database.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = None
            mock_engine.return_value.begin.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=None)

            manager = DatabaseManager(db_url)

            analytics_data = {
                "user_id": "user123",
                "query_hash": "hash123",
                "query_text": "Test query",
                "response_text": "Test response",
                "language_preference": "en",
                "model_used": "gemini",
                "response_time_ms": 100,
                "document_count": 5,
                "session_id": "session123",
                "metadata": {"key": "value"},
            }

            await manager.store_query_analytics(analytics_data)

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_query_analytics_db_error(self):
        """Test store_query_analytics with database error"""
        from sqlalchemy.exc import SQLAlchemyError

        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"

        with patch("backend.services.oracle_database.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = SQLAlchemyError("DB error")

            mock_engine.return_value.begin.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=None)

            manager = DatabaseManager(db_url)

            analytics_data = {"user_id": "user123"}

            with pytest.raises(SQLAlchemyError):
                await manager.store_query_analytics(analytics_data)

    @pytest.mark.asyncio
    async def test_store_feedback_success(self):
        """Test store_feedback with successful storage"""
        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"

        with patch("backend.services.oracle_database.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = None
            mock_engine.return_value.begin.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=None)

            manager = DatabaseManager(db_url)

            feedback_data = {
                "user_id": "user123",
                "query_text": "Test query",
                "original_answer": "Original answer",
                "user_correction": "Corrected answer",
                "feedback_type": "correction",
                "model_used": "gemini",
                "response_time_ms": 100,
                "user_rating": 5,
                "session_id": "session123",
                "metadata": {"key": "value"},
            }

            await manager.store_feedback(feedback_data)

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_feedback_db_error(self):
        """Test store_feedback with database error"""
        from sqlalchemy.exc import SQLAlchemyError

        from backend.services.oracle_database import DatabaseManager

        db_url = "postgresql://test:test@localhost:5432/test"

        with patch("backend.services.oracle_database.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = SQLAlchemyError("DB error")

            mock_engine.return_value.begin.return_value.__enter__ = MagicMock(
                return_value=mock_conn
            )
            mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=None)

            manager = DatabaseManager(db_url)

            feedback_data = {"user_id": "user123"}

            with pytest.raises(SQLAlchemyError):
                await manager.store_feedback(feedback_data)
