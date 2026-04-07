"""Tests for Core Guardian V4 Risk Scorer."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from risk_scorer import (
    compute_risk_score,
    get_threshold_action,
    write_deploy_block,
    clear_deploy_block,
    THRESHOLD_AUTO_FIX,
    THRESHOLD_AUTO_FIX_ALERT,
    THRESHOLD_BLOCK_DEPLOY,
)


class TestComputeRiskScore(unittest.TestCase):
    """Test risk score computation."""

    def test_all_clean_returns_zero(self) -> None:
        result = compute_risk_score({"rbac": 0, "api_contract": 0, "cache": 0, "dead_code": 0})
        self.assertEqual(result["overall"], 0)
        self.assertEqual(result["rbac"], 0)
        self.assertEqual(result["api_contract"], 0)
        self.assertEqual(result["cache"], 0)
        self.assertEqual(result["dead_code"], 0)

    def test_rbac_dominates(self) -> None:
        """RBAC has 40% weight and 15pts per error — 5 errors should push score high."""
        result = compute_risk_score({"rbac": 5, "api_contract": 0, "cache": 0, "dead_code": 0})
        self.assertEqual(result["rbac"], 75)  # 5 * 15 = 75
        self.assertEqual(result["overall"], 30)  # 75 * 0.40 = 30

    def test_api_contract_contribution(self) -> None:
        result = compute_risk_score({"rbac": 0, "api_contract": 8, "cache": 0, "dead_code": 0})
        self.assertEqual(result["api_contract"], 80)  # 8 * 10 = 80
        self.assertEqual(result["overall"], 24)  # 80 * 0.30 = 24

    def test_cache_contribution(self) -> None:
        result = compute_risk_score({"rbac": 0, "api_contract": 0, "cache": 12, "dead_code": 0})
        self.assertEqual(result["cache"], 60)  # 12 * 5 = 60
        self.assertEqual(result["overall"], 12)  # 60 * 0.20 = 12

    def test_dead_code_contribution(self) -> None:
        result = compute_risk_score({"rbac": 0, "api_contract": 0, "cache": 0, "dead_code": 20})
        self.assertEqual(result["dead_code"], 60)  # 20 * 3 = 60
        self.assertEqual(result["overall"], 6)  # 60 * 0.10 = 6

    def test_capped_at_100(self) -> None:
        """Individual scores should cap at 100."""
        result = compute_risk_score({"rbac": 100, "api_contract": 100, "cache": 100, "dead_code": 100})
        self.assertEqual(result["rbac"], 100)
        self.assertEqual(result["api_contract"], 100)
        self.assertEqual(result["cache"], 100)
        self.assertEqual(result["dead_code"], 100)
        self.assertEqual(result["overall"], 100)

    def test_overall_capped_at_100(self) -> None:
        """Overall should not exceed 100."""
        result = compute_risk_score({"rbac": 50, "api_contract": 50, "cache": 50, "dead_code": 50})
        self.assertLessEqual(result["overall"], 100)

    def test_missing_keys_default_to_zero(self) -> None:
        """Missing audit keys should default to 0."""
        result = compute_risk_score({"rbac": 3})
        self.assertEqual(result["rbac"], 45)  # 3 * 15
        self.assertEqual(result["api_contract"], 0)
        self.assertEqual(result["cache"], 0)
        self.assertEqual(result["dead_code"], 0)

    def test_combined_realistic_scenario(self) -> None:
        """Realistic scenario: 2 RBAC errors, 3 ghost endpoints, 10 cache, 15 dead code."""
        result = compute_risk_score({"rbac": 2, "api_contract": 3, "cache": 10, "dead_code": 15})
        self.assertEqual(result["rbac"], 30)       # 2*15
        self.assertEqual(result["api_contract"], 30) # 3*10
        self.assertEqual(result["cache"], 50)       # 10*5
        self.assertEqual(result["dead_code"], 45)   # 15*3
        # Overall: 30*0.4 + 30*0.3 + 50*0.2 + 45*0.1 = 12+9+10+4.5 = 35.5 → 36
        self.assertEqual(result["overall"], 36)


class TestThresholds(unittest.TestCase):
    """Test threshold actions."""

    def test_below_60_no_action(self) -> None:
        self.assertEqual(get_threshold_action(0), "none")
        self.assertEqual(get_threshold_action(59), "none")

    def test_60_auto_fix(self) -> None:
        self.assertEqual(get_threshold_action(60), "auto_fix")
        self.assertEqual(get_threshold_action(79), "auto_fix")

    def test_80_auto_fix_alert(self) -> None:
        self.assertEqual(get_threshold_action(80), "auto_fix_alert")
        self.assertEqual(get_threshold_action(94), "auto_fix_alert")

    def test_95_block_deploy(self) -> None:
        self.assertEqual(get_threshold_action(95), "block_deploy")
        self.assertEqual(get_threshold_action(100), "block_deploy")


class TestDeployBlock(unittest.TestCase):
    """Test deploy block sentinel file."""

    def test_write_and_clear_deploy_block(self) -> None:
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp())
        sentinel = tmp_dir / "deploy_blocked.json"

        with patch("risk_scorer.DEPLOY_BLOCKED_FILE", sentinel):
            write_deploy_block(96, {"rbac": 100, "api_contract": 90})
            self.assertTrue(sentinel.exists())

            data = json.loads(sentinel.read_text())
            self.assertEqual(data["risk_score"], 96)
            self.assertIn("exceeds threshold", data["reason"])

            clear_deploy_block()
            self.assertFalse(sentinel.exists())

        # Cleanup
        tmp_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
