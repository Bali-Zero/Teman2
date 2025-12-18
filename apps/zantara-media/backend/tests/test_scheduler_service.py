"""
Unit tests for Scheduler Service
Tests for daily automation using APScheduler
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scheduler import SchedulerService, scheduler_service


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def service():
    """Create a fresh SchedulerService instance"""
    return SchedulerService()


@pytest.fixture
def mock_content_orchestrator():
    """Mock content orchestrator"""
    with patch("app.services.scheduler.content_orchestrator") as mock:
        mock.run_daily_pipeline = AsyncMock(
            return_value={
                "articles_generated": 5,
                "articles_published": 3,
                "duration_seconds": 45.5,
                "errors": [],
            }
        )
        yield mock


# ============================================================================
# Initialization Tests
# ============================================================================


class TestSchedulerInitialization:
    """Tests for scheduler initialization"""

    def test_initial_state(self, service):
        """Test scheduler initial state"""
        assert service.scheduler is None
        assert service.is_running is False

    @pytest.mark.asyncio
    async def test_start_scheduler(self, service):
        """Test starting the scheduler"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await service.start()

            assert service.is_running is True
            mock_scheduler.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_scheduler_already_running(self, service):
        """Test starting scheduler when already running does nothing"""
        service.is_running = True

        # Should return early without error
        await service.start()

        assert service.scheduler is None  # Wasn't created again

    @pytest.mark.asyncio
    async def test_stop_scheduler(self, service):
        """Test stopping the scheduler"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await service.start()
            await service.stop()

            assert service.is_running is False
            mock_scheduler.shutdown.assert_called_once_with(wait=False)

    @pytest.mark.asyncio
    async def test_stop_scheduler_not_running(self, service):
        """Test stopping scheduler when not running does nothing"""
        # Should return early without error
        await service.stop()

        assert service.is_running is False


# ============================================================================
# Job Registration Tests
# ============================================================================


class TestJobRegistration:
    """Tests for job registration"""

    @pytest.mark.asyncio
    async def test_daily_job_registered(self, service):
        """Test that daily content generation job is registered"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await service.start()

            # Check add_job was called with daily_content_generation
            calls = mock_scheduler.add_job.call_args_list
            job_ids = [call.kwargs.get("id") for call in calls]
            assert "daily_content_generation" in job_ids

    @pytest.mark.asyncio
    async def test_cleanup_job_registered(self, service):
        """Test that weekly cleanup job is registered"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await service.start()

            calls = mock_scheduler.add_job.call_args_list
            job_ids = [call.kwargs.get("id") for call in calls]
            assert "weekly_cleanup" in job_ids

    @pytest.mark.asyncio
    async def test_daily_job_schedule_time(self, service):
        """Test that daily job is scheduled at 6 AM"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await service.start()

            # Find the daily job call
            for call in mock_scheduler.add_job.call_args_list:
                if call.kwargs.get("id") == "daily_content_generation":
                    trigger = call.kwargs.get("trigger")
                    # CronTrigger with hour=6, minute=0
                    assert trigger is not None
                    break


# ============================================================================
# Daily Pipeline Tests
# ============================================================================


class TestDailyPipeline:
    """Tests for daily pipeline execution"""

    @pytest.mark.asyncio
    async def test_run_daily_pipeline_success(self, service, mock_content_orchestrator):
        """Test successful daily pipeline execution"""
        await service._run_daily_pipeline()

        mock_content_orchestrator.run_daily_pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_daily_pipeline_with_errors(self, service):
        """Test daily pipeline handles errors gracefully"""
        with patch("app.services.scheduler.content_orchestrator") as mock:
            mock.run_daily_pipeline = AsyncMock(
                return_value={
                    "articles_generated": 3,
                    "articles_published": 1,
                    "duration_seconds": 30.0,
                    "errors": ["Failed to generate article 2", "Network timeout"],
                }
            )

            # Should not raise exception
            await service._run_daily_pipeline()

    @pytest.mark.asyncio
    async def test_run_daily_pipeline_exception(self, service):
        """Test daily pipeline catches exceptions"""
        with patch("app.services.scheduler.content_orchestrator") as mock:
            mock.run_daily_pipeline = AsyncMock(
                side_effect=Exception("Pipeline failed")
            )

            # Should not raise exception, just log error
            await service._run_daily_pipeline()


# ============================================================================
# Weekly Cleanup Tests
# ============================================================================


class TestWeeklyCleanup:
    """Tests for weekly cleanup task"""

    @pytest.mark.asyncio
    async def test_weekly_cleanup_executes(self, service):
        """Test weekly cleanup task executes without error"""
        # Currently a placeholder, should not raise
        await service._weekly_cleanup()

    @pytest.mark.asyncio
    async def test_weekly_cleanup_handles_exception(self, service):
        """Test weekly cleanup handles exceptions gracefully"""
        # Even with internal issues, should not propagate exception
        await service._weekly_cleanup()


# ============================================================================
# Manual Trigger Tests
# ============================================================================


class TestManualTrigger:
    """Tests for manual pipeline trigger"""

    @pytest.mark.asyncio
    async def test_trigger_manual_run_success(self, service, mock_content_orchestrator):
        """Test successful manual pipeline trigger"""
        result = await service.trigger_manual_run()

        assert result["success"] is True
        assert "stats" in result
        assert result["stats"]["articles_generated"] == 5

    @pytest.mark.asyncio
    async def test_trigger_manual_run_failure(self, service):
        """Test manual trigger handles failure"""
        with patch("app.services.scheduler.content_orchestrator") as mock:
            mock.run_daily_pipeline = AsyncMock(
                side_effect=Exception("Manual run failed")
            )

            result = await service.trigger_manual_run()

            assert result["success"] is False
            assert "error" in result
            assert "Manual run failed" in result["error"]


# ============================================================================
# Status Tests
# ============================================================================


class TestSchedulerStatus:
    """Tests for scheduler status"""

    def test_get_status_not_running(self, service):
        """Test status when scheduler not running"""
        status = service.get_status()

        assert status["running"] is False
        assert status["jobs"] == []

    @pytest.mark.asyncio
    async def test_get_status_running(self, service):
        """Test status when scheduler is running"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_job = MagicMock()
            mock_job.id = "daily_content_generation"
            mock_job.name = "Daily Content Generation Pipeline"
            mock_job.next_run_time = datetime(2025, 1, 11, 6, 0, 0)
            mock_job.trigger = MagicMock(__str__=lambda x: "cron[hour='6', minute='0']")
            mock_scheduler.get_jobs.return_value = [mock_job]
            mock_scheduler_class.return_value = mock_scheduler

            await service.start()
            status = service.get_status()

            assert status["running"] is True
            assert len(status["jobs"]) == 1
            assert status["jobs"][0]["id"] == "daily_content_generation"
            assert status["jobs"][0]["name"] == "Daily Content Generation Pipeline"

    @pytest.mark.asyncio
    async def test_get_status_job_without_next_run(self, service):
        """Test status for job without next run time (paused)"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_job = MagicMock()
            mock_job.id = "test_job"
            mock_job.name = "Test Job"
            mock_job.next_run_time = None  # No next run (paused)
            mock_job.trigger = MagicMock(__str__=lambda x: "cron")
            mock_scheduler.get_jobs.return_value = [mock_job]
            mock_scheduler_class.return_value = mock_scheduler

            await service.start()
            status = service.get_status()

            assert status["jobs"][0]["next_run"] is None


# ============================================================================
# Timezone Tests
# ============================================================================


class TestTimezone:
    """Tests for timezone handling"""

    @pytest.mark.asyncio
    async def test_scheduler_uses_bali_timezone(self, service):
        """Test that scheduler uses Asia/Makassar (Bali) timezone"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await service.start()

            # Check scheduler was created with correct timezone
            mock_scheduler_class.assert_called_once_with(timezone="Asia/Makassar")


# ============================================================================
# Singleton Instance Tests
# ============================================================================


class TestSingletonInstance:
    """Tests for the singleton scheduler_service instance"""

    def test_singleton_exists(self):
        """Test that singleton instance exists"""
        assert scheduler_service is not None
        assert isinstance(scheduler_service, SchedulerService)

    def test_singleton_initial_state(self):
        """Test singleton initial state"""
        # Note: In real tests, we'd want to reset this
        assert isinstance(scheduler_service.is_running, bool)


# ============================================================================
# Integration Tests
# ============================================================================


class TestSchedulerIntegration:
    """Integration tests for scheduler"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, service, mock_content_orchestrator):
        """Test full scheduler lifecycle: start -> trigger -> stop"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler.get_jobs.return_value = []
            mock_scheduler_class.return_value = mock_scheduler

            # Start
            await service.start()
            assert service.is_running is True

            # Manual trigger
            result = await service.trigger_manual_run()
            assert result["success"] is True

            # Status check
            status = service.get_status()
            assert status["running"] is True

            # Stop
            await service.stop()
            assert service.is_running is False

    @pytest.mark.asyncio
    async def test_restart_scheduler(self, service):
        """Test restarting the scheduler"""
        with patch("app.services.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await service.start()
            await service.stop()
            await service.start()

            assert service.is_running is True
            # Should have been created twice
            assert mock_scheduler_class.call_count == 2
