"""Tests for Core Guardian V4 Decision Logger."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDecisionLogger(unittest.TestCase):
    """Test decision logging to DB and fallback to JSONL."""

    def setUp(self) -> None:
        # Reset module-level pool
        import decision_logger
        decision_logger._pool = None

    @patch.dict("os.environ", {"DATABASE_URL": ""})
    def test_fallback_when_no_db_url(self) -> None:
        """Should fall back to local JSONL when DATABASE_URL is empty."""
        import decision_logger

        with patch.object(decision_logger, "_fallback_log") as mock_fallback:
            decision_logger.log_decision_sync(
                "test-001", "test", "smoke_test", "test finding", "info", "none"
            )
            mock_fallback.assert_called_once()
            record = mock_fallback.call_args[0][0]
            self.assertEqual(record["run_id"], "test-001")
            self.assertEqual(record["component"], "test")

    @patch.dict("os.environ", {"DATABASE_URL": ""})
    def test_risk_score_fallback(self) -> None:
        """Risk score should also fall back to JSONL."""
        import decision_logger

        with patch.object(decision_logger, "_fallback_log") as mock_fallback:
            decision_logger.log_risk_score_sync(
                overall=42, rbac=30, api_contract=20, cache=10, dead_code=5
            )
            mock_fallback.assert_called_once()
            record = mock_fallback.call_args[0][0]
            self.assertEqual(record["overall"], 42)

    def test_fallback_log_writes_jsonl(self) -> None:
        """Fallback log should write valid JSONL."""
        import decision_logger
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            tmp_path = Path(f.name)

        try:
            with patch.object(decision_logger, "_FALLBACK_FILE", tmp_path):
                decision_logger._fallback_log({"test": "data", "num": 42})

            content = tmp_path.read_text().strip()
            parsed = json.loads(content)
            self.assertEqual(parsed["test"], "data")
            self.assertEqual(parsed["num"], 42)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_log_decision_sync_handles_exception(self) -> None:
        """Sync wrapper should not raise even if underlying async fails."""
        import decision_logger

        with patch.object(decision_logger, "_get_pool", side_effect=Exception("DB down")):
            with patch.object(decision_logger, "_fallback_log"):
                # Should not raise
                decision_logger.log_decision_sync(
                    "test-002", "test", "error_test", "db down", "error", "none"
                )


class TestDecisionLoggerQueries(unittest.TestCase):
    """Test query functions."""

    @patch.dict("os.environ", {"DATABASE_URL": ""})
    def test_get_recent_decisions_empty_without_db(self) -> None:
        """Should return empty list when DB not available."""
        import asyncio
        import decision_logger
        decision_logger._pool = None

        result = asyncio.run(decision_logger.get_recent_decisions(hours=24))
        self.assertEqual(result, [])

    @patch.dict("os.environ", {"DATABASE_URL": ""})
    def test_get_risk_trend_empty_without_db(self) -> None:
        """Should return empty list when DB not available."""
        import asyncio
        import decision_logger
        decision_logger._pool = None

        result = asyncio.run(decision_logger.get_risk_trend(days=7))
        self.assertEqual(result, [])

    @patch.dict("os.environ", {"DATABASE_URL": ""})
    def test_get_latest_risk_score_none_without_db(self) -> None:
        """Should return None when DB not available."""
        import asyncio
        import decision_logger
        decision_logger._pool = None

        result = asyncio.run(decision_logger.get_latest_risk_score())
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
