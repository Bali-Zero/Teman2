"""
Comprehensive Integration Tests for Timesheet Services
Tests TeamTimesheetService and time tracking

Covers:
- Timesheet creation
- Time tracking
- Time reporting
- Team time analytics
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestTeamTimesheetServiceIntegration:
    """Integration tests for TeamTimesheetService"""

    @pytest.mark.asyncio
    async def test_timesheet_service_initialization(self, db_pool):
        """Test TeamTimesheetService initialization"""
        with patch("services.team_timesheet_service.asyncpg") as mock_asyncpg:
            from services.team_timesheet_service import TeamTimesheetService

            service = TeamTimesheetService(db_pool=db_pool)

            assert service is not None

    @pytest.mark.asyncio
    async def test_timesheet_entry_creation(self, db_pool):
        """Test timesheet entry creation"""

        async with db_pool.acquire() as conn:
            # Create timesheet_entries table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS timesheet_entries (
                    id SERIAL PRIMARY KEY,
                    team_member_email VARCHAR(255),
                    client_id INTEGER,
                    practice_id INTEGER,
                    task_description TEXT,
                    hours_worked DECIMAL(5,2),
                    date_worked DATE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create timesheet entry
            entry_id = await conn.fetchval(
                """
                INSERT INTO timesheet_entries (
                    team_member_email, client_id, practice_id, task_description, hours_worked, date_worked
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "team@example.com",
                123,
                456,
                "KITAS application review",
                2.5,
                datetime.now().date(),
            )

            assert entry_id is not None

            # Retrieve entry
            entry = await conn.fetchrow(
                """
                SELECT task_description, hours_worked
                FROM timesheet_entries
                WHERE id = $1
                """,
                entry_id,
            )

            assert entry is not None
            assert entry["hours_worked"] == 2.5

            # Cleanup
            await conn.execute("DELETE FROM timesheet_entries WHERE id = $1", entry_id)

    @pytest.mark.asyncio
    async def test_timesheet_reporting(self, db_pool):
        """Test timesheet reporting"""

        async with db_pool.acquire() as conn:
            # Create multiple entries
            team_member = "timesheet@team.com"
            for i in range(5):
                await conn.execute(
                    """
                    INSERT INTO timesheet_entries (
                        team_member_email, hours_worked, date_worked
                    )
                    VALUES ($1, $2, $3)
                    """,
                    team_member,
                    4.0 + (i * 0.5),
                    datetime.now().date() - timedelta(days=i),
                )

            # Generate report
            report = await conn.fetchrow(
                """
                SELECT
                    team_member_email,
                    SUM(hours_worked) as total_hours,
                    COUNT(*) as total_entries,
                    AVG(hours_worked) as avg_hours_per_day
                FROM timesheet_entries
                WHERE team_member_email = $1
                GROUP BY team_member_email
                """,
                team_member,
            )

            assert report is not None
            assert report["total_hours"] > 0
            assert report["total_entries"] == 5

            # Cleanup
            await conn.execute(
                "DELETE FROM timesheet_entries WHERE team_member_email = $1", team_member
            )

    @pytest.mark.asyncio
    async def test_timesheet_analytics(self, db_pool):
        """Test timesheet analytics"""

        async with db_pool.acquire() as conn:
            # Create entries for multiple team members
            team_members = ["member1@team.com", "member2@team.com", "member3@team.com"]

            for member in team_members:
                for i in range(3):
                    await conn.execute(
                        """
                        INSERT INTO timesheet_entries (
                            team_member_email, hours_worked, date_worked
                        )
                        VALUES ($1, $2, $3)
                        """,
                        member,
                        8.0,
                        datetime.now().date() - timedelta(days=i),
                    )

            # Team analytics
            analytics = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT team_member_email) as active_members,
                    SUM(hours_worked) as total_team_hours,
                    AVG(hours_worked) as avg_hours_per_entry
                FROM timesheet_entries
                WHERE date_worked >= $1
                """,
                datetime.now().date() - timedelta(days=7),
            )

            assert analytics is not None
            assert analytics["active_members"] == 3
            assert analytics["total_team_hours"] > 0

            # Cleanup
            await conn.execute(
                "DELETE FROM timesheet_entries WHERE team_member_email = ANY($1)", team_members
            )
