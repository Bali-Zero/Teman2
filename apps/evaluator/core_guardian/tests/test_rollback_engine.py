"""Tests for Core Guardian V4 Rollback Engine."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRollbackEngine(unittest.TestCase):
    """Test rollback engine snapshot and revert operations."""

    def _make_engine(self, state: dict | None = None):
        """Create a RollbackEngine with mocked state file."""
        with patch("rollback_engine.safe_load_json", return_value=state):
            from rollback_engine import RollbackEngine
            engine = RollbackEngine()
        return engine

    @patch("rollback_engine.subprocess.run")
    @patch("rollback_engine.PROJECT_ROOT", Path("/fake/project"))
    def test_create_snapshot_creates_tag(self, mock_run: MagicMock) -> None:
        """Should create a git tag at HEAD."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        engine = self._make_engine()

        tag = engine.create_pre_fix_snapshot("cg/fix-DTZ005-abc123")

        self.assertEqual(tag, "pre-fix/cg/fix-DTZ005-abc123")
        # Should call git tag (delete old + create new)
        tag_calls = [c for c in mock_run.call_args_list if "tag" in str(c)]
        self.assertGreaterEqual(len(tag_calls), 1)

    @patch("rollback_engine.subprocess.run")
    @patch("rollback_engine.PROJECT_ROOT", Path("/fake/project"))
    def test_create_snapshot_returns_none_on_failure(self, mock_run: MagicMock) -> None:
        """Should return None if git tag fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="error: tag exists")
        engine = self._make_engine()

        # Override second call to fail
        mock_run.side_effect = [
            MagicMock(returncode=0),  # delete old tag
            MagicMock(returncode=1, stderr="failed"),  # create new tag
        ]
        tag = engine.create_pre_fix_snapshot("cg/fix-test")
        self.assertIsNone(tag)

    @patch("rollback_engine.send_telegram_alert")
    @patch("rollback_engine.atomic_write_json")
    @patch("rollback_engine.subprocess.run")
    @patch("rollback_engine.PROJECT_ROOT", Path("/fake/project"))
    def test_rollback_to_snapshot_resets_hard(
        self, mock_run: MagicMock, mock_write: MagicMock, mock_tg: MagicMock
    ) -> None:
        """Should git reset --hard to tag and delete branch."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        engine = self._make_engine({"consecutive_rollbacks": 0, "total_rollbacks": 0, "disabled": False})

        result = engine.rollback_to_snapshot("pre-fix/cg/fix-test", "cg/fix-test")

        self.assertTrue(result)
        # Verify git reset --hard was called
        reset_calls = [c for c in mock_run.call_args_list if "reset" in str(c)]
        self.assertEqual(len(reset_calls), 1)
        self.assertIn("--hard", str(reset_calls[0]))

    @patch("rollback_engine.send_telegram_alert")
    @patch("rollback_engine.atomic_write_json")
    @patch("rollback_engine.subprocess.run")
    @patch("rollback_engine.PROJECT_ROOT", Path("/fake/project"))
    def test_rollback_breaker_fires_after_3(
        self, mock_run: MagicMock, mock_write: MagicMock, mock_tg: MagicMock
    ) -> None:
        """3 consecutive rollbacks should activate the circuit breaker."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        engine = self._make_engine({"consecutive_rollbacks": 2, "total_rollbacks": 5, "disabled": False})

        # This is the 3rd rollback
        engine.rollback_to_snapshot("pre-fix/test", "test-branch")

        self.assertTrue(engine._state["disabled"])
        # Telegram should be called with self-disable message
        mock_tg.assert_called()
        alert_msg = mock_tg.call_args[0][0]
        self.assertIn("SELF-DISABLED", alert_msg)

    def test_check_rollback_breaker_when_disabled(self) -> None:
        """Should return reason string when disabled."""
        engine = self._make_engine({"consecutive_rollbacks": 3, "total_rollbacks": 3, "disabled": True})
        result = engine.check_rollback_breaker()
        self.assertIsNotNone(result)
        self.assertIn("Self-disabled", result)

    def test_check_rollback_breaker_when_ok(self) -> None:
        """Should return None when not disabled."""
        engine = self._make_engine({"consecutive_rollbacks": 1, "total_rollbacks": 5, "disabled": False})
        result = engine.check_rollback_breaker()
        self.assertIsNone(result)

    @patch("rollback_engine.atomic_write_json")
    def test_record_success_resets_counter(self, mock_write: MagicMock) -> None:
        """Successful fix should reset consecutive rollback counter."""
        engine = self._make_engine({"consecutive_rollbacks": 2, "total_rollbacks": 5, "disabled": False})
        engine.record_success()
        self.assertEqual(engine._state["consecutive_rollbacks"], 0)

    @patch("rollback_engine.atomic_write_json")
    def test_reset_breaker(self, mock_write: MagicMock) -> None:
        """Manual breaker reset should clear disabled state."""
        engine = self._make_engine({"consecutive_rollbacks": 3, "total_rollbacks": 3, "disabled": True})
        engine.reset_breaker()
        self.assertFalse(engine._state["disabled"])
        self.assertEqual(engine._state["consecutive_rollbacks"], 0)


if __name__ == "__main__":
    unittest.main()
