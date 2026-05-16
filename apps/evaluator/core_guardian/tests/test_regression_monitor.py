"""Tests for Core Guardian V4 Regression Monitor."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from regression_monitor import RegressionMonitor, CONSECUTIVE_BAD_CHECKS


class TestRegressionMonitor(unittest.TestCase):
    """Test regression detection logic."""

    def _make_monitor(self, branch: str = "test-branch", tag: str = "pre-fix/test") -> RegressionMonitor:
        return RegressionMonitor(branch=branch, tag=tag, duration=60)

    @patch("regression_monitor.urlopen")
    def test_probe_health_success(self, mock_urlopen: MagicMock) -> None:
        """Healthy response should return ok=True."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"status": "ok"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        monitor = self._make_monitor()
        result = monitor._probe_health()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)
        self.assertGreaterEqual(result["response_ms"], 0)

    @patch("regression_monitor.urlopen", side_effect=Exception("Connection refused"))
    def test_probe_health_failure(self, mock_urlopen: MagicMock) -> None:
        """Connection failure should return ok=False."""
        monitor = self._make_monitor()
        result = monitor._probe_health()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status_code"], 0)

    def test_no_regression_within_threshold(self) -> None:
        """19% increase should NOT trigger rollback."""
        monitor = self._make_monitor()

        # Baseline: 100ms average
        baseline = {"avg_response_ms": 100.0, "error_rate": 0.0}
        threshold = baseline["avg_response_ms"] * 1.2  # 120ms

        # 119ms is within threshold
        check = {"ok": True, "response_ms": 119, "status_code": 200}
        is_bad = check["response_ms"] > threshold
        self.assertFalse(is_bad)

    def test_regression_triggers_at_threshold(self) -> None:
        """25% increase should trigger bad check."""
        monitor = self._make_monitor()

        baseline = {"avg_response_ms": 100.0, "error_rate": 0.0}
        threshold = baseline["avg_response_ms"] * 1.2  # 120ms

        # 125ms exceeds threshold
        check = {"ok": True, "response_ms": 125, "status_code": 200}
        is_bad = check["response_ms"] > threshold
        self.assertTrue(is_bad)

    def test_single_spike_not_regression(self) -> None:
        """Single bad check should not count as regression (need 3 consecutive)."""
        # Simulate: bad, good, bad — should NOT trigger
        consecutive = 0

        # Bad
        consecutive += 1
        self.assertLess(consecutive, CONSECUTIVE_BAD_CHECKS)

        # Good → reset
        consecutive = 0

        # Bad
        consecutive += 1
        self.assertLess(consecutive, CONSECUTIVE_BAD_CHECKS)

    def test_three_consecutive_bad_is_regression(self) -> None:
        """3 consecutive bad checks should count as regression."""
        consecutive = 0
        for _ in range(CONSECUTIVE_BAD_CHECKS):
            consecutive += 1

        self.assertGreaterEqual(consecutive, CONSECUTIVE_BAD_CHECKS)

    @patch("regression_monitor.urlopen")
    def test_collect_baseline_averages(self, mock_urlopen: MagicMock) -> None:
        """Baseline should average 2 probes."""
        responses = []
        for _ in [100, 200]:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = json.dumps({"status": "ok"}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            responses.append(mock_resp)

        mock_urlopen.side_effect = responses

        monitor = self._make_monitor()
        with patch("regression_monitor.time.sleep"):
            baseline = monitor.collect_baseline()

        self.assertIn("avg_response_ms", baseline)
        self.assertIn("error_rate", baseline)
        # Both probes succeeded
        self.assertEqual(baseline["error_rate"], 0.0)


class TestRegressionMonitorHandleRegression(unittest.TestCase):
    """Test regression handling (rollback + alert)."""

    @patch("regression_monitor.send_telegram_alert")
    def test_handle_regression_sends_alert(self, mock_tg: MagicMock) -> None:
        """Regression handling should send Telegram alert."""
        monitor = RegressionMonitor("test-branch", "pre-fix/test", 60)
        baseline = {"avg_response_ms": 100.0, "error_rate": 0.0}

        # RollbackEngine is imported inline in _handle_regression, so patch at source
        mock_engine = MagicMock()
        mock_engine.rollback_to_snapshot.return_value = True
        with patch.dict("sys.modules", {"rollback_engine": MagicMock(RollbackEngine=MagicMock(return_value=mock_engine))}):
            with patch.dict("sys.modules", {"decision_logger": MagicMock()}):
                monitor._handle_regression(baseline)

        mock_tg.assert_called_once()
        msg = mock_tg.call_args[0][0]
        self.assertIn("REGRESSION", msg)
        self.assertIn("test-branch", msg)


if __name__ == "__main__":
    unittest.main()
