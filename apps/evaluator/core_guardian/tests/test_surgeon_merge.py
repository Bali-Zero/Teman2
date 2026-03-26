"""Tests for Surgeon merge-bot path."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from surgeon import merge_to_main, write_last_json


class TestMergeToMain(unittest.TestCase):
    @patch("surgeon.subprocess.run")
    @patch("surgeon.PROJECT_ROOT", Path("/fake/root"))
    def test_merge_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = merge_to_main("cg/fix-abc123")
        self.assertIsNone(result)
        self.assertGreaterEqual(mock_run.call_count, 3)

    @patch("surgeon.subprocess.run")
    @patch("surgeon.PROJECT_ROOT", Path("/fake/root"))
    def test_merge_conflict_returns_error(self, mock_run: MagicMock) -> None:
        # First call (fetch) succeeds, second (checkout) succeeds, third (merge) fails
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),  # fetch
            MagicMock(returncode=0, stderr="", stdout="main"),  # symbolic-ref
            MagicMock(returncode=0, stderr=""),  # checkout main
            MagicMock(returncode=1, stderr="CONFLICT (content): merge conflict"),  # merge fails
            MagicMock(returncode=0, stderr=""),  # checkout back
        ]
        result = merge_to_main("cg/fix-abc123")
        self.assertIsNotNone(result)
        self.assertIn("CONFLICT", result)

    def test_write_last_json_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            state_dir = Path(d)
            write_last_json("test_job", "ok", state_dir=state_dir)
            f = state_dir / "test_job.last.json"
            self.assertTrue(f.exists())
            data = json.loads(f.read_text())
            self.assertEqual(data["status"], "ok")
            self.assertIn("ts", data)
            self.assertEqual(data["job"], "test_job")

    def test_write_last_json_failed_status(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            state_dir = Path(d)
            write_last_json("core_guardian", "failed", detail="merge failed: CONFLICT", state_dir=state_dir)
            f = state_dir / "core_guardian.last.json"
            data = json.loads(f.read_text())
            self.assertEqual(data["status"], "failed")
            self.assertIn("merge failed", data["detail"])


if __name__ == "__main__":
    unittest.main()
