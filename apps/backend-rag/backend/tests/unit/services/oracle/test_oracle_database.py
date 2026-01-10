"""
Unit tests for DatabaseManager (Oracle Database)
Target: 100% coverage
Composer: 4
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.oracle.oracle_database import DatabaseManager


@pytest.fixture
def database_manager():
    """Create database manager instance"""
    with patch("backend.services.oracle.oracle_database.create_engine"):
        return DatabaseManager(database_url="postgresql://test:test@localhost/testdb")


class TestDatabaseManager:
    """Tests for DatabaseManager"""

    def test_init(self):
        """Test initialization"""
        with patch("backend.services.oracle.oracle_database.create_engine") as mock_engine:
            manager = DatabaseManager(database_url="postgresql://test:test@localhost/testdb")
            assert manager.database_url == "postgresql://test:test@localhost/testdb"

    def test_init_placeholder_url(self):
        """Test initialization with placeholder URL"""
        with patch("backend.services.oracle.oracle_database.create_engine") as mock_engine:
            manager = DatabaseManager(database_url="postgresql://user:pass@localhost/db")
            # Should skip engine initialization
            mock_engine.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_profile_from_team_members(self, database_manager):
        """Test getting user profile from team_members"""
        with patch(
            "backend.data.team_members.TEAM_MEMBERS",
            [{"email": "test@example.com", "name": "Test", "role": "Dev", "id": "123"}],
        ):
            profile = await database_manager.get_user_profile("test@example.com")
            assert profile is not None
            assert profile["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_profile_from_db(self, database_manager):
        """Test getting user profile from database"""
        mock_result = MagicMock()
        mock_result.mappings.return_value.fetchone.return_value = {
            "id": "123",
            "email": "test@example.com",
            "name": "Test User",
        }

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        database_manager._engine = mock_engine

        profile = await database_manager.get_user_profile("test@example.com")
        assert profile is not None

    @pytest.mark.asyncio
    async def test_store_feedback(self, database_manager):
        """Test storing feedback"""
        mock_conn = MagicMock()
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        mock_conn.execute = MagicMock()

        database_manager._engine = mock_engine

        # store_feedback returns None (void)
        await database_manager.store_feedback(
            {
                "user_id": "test@example.com",
                "user_rating": 5,
                "query_text": "test",
                "original_answer": "answer",
            }
        )

        # Verify execute was called
        mock_conn.execute.assert_called_once()
