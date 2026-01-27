
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

class TestBurnoutDetectorService:
    @pytest.fixture(autouse=True)
    async def setup_service(self):
        self.asyncpg_pool = MagicMock()
        self.burnout_detector_service = BurnoutDetectorService(self.asyncpg_pool)

    @pytest.mark.asyncio
    async def test_detect_burnout_signals(self, burnout_detector_service):
        # Assuming there are some entries in the team_work_sessions table for testing purposes
        with self.asyncpg_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO team_work_sessions (user_email, session_start, duration_minutes, conversations_count, activities_count)
                VALUES ($1, $2, $3, $4, $5),
                       ($1, $6, $7, $8, $9);
            """, "test@example.com", datetime.now(), 300, 10, 5,
                             "test@example.com", datetime.now() + timedelta(days=1), 200, 5, 5)

        results = await burnout_detector_service.detect_burnout_signals("test@example.com")

        assert len(results) == 1
        result = results[0]
        assert result["email"] == "test@example.com"
        assert result["warning_count"] > 0

    @pytest.mark.asyncio
    async def test_detect_burnout_signals_no_sessions(self, burnout_detector_service):
        results = await burnout_detector_service.detect_burnout_signals("nonexistent@example.com")

        assert len(results) == 0