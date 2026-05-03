"""Tests for Watchdog -> Surgeon auto-dispatch."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import watchdog as wd


class TestAutoDispatchSurgeon(unittest.TestCase):
    @patch("watchdog.subprocess.Popen")
    @patch("watchdog.subprocess.run")
    @patch("watchdog.BACKEND_DIR", Path("/fake/backend"))
    @patch("watchdog.VENV_PYTHON", Path("/fake/python"))
    def test_dispatch_calls_popen_for_safe_code(
        self, mock_run: MagicMock, mock_popen: MagicMock
    ) -> None:
        # ruff returns a violation for ANN001
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps([
                {"filename": "backend/app/foo.py", "row": 5, "col": 1,
                 "code": "ANN001", "message": "missing type annotation"}
            ])
        )
        wd.auto_dispatch_surgeon(regressions=["backend/app/foo.py"])
        # Popen should be called to launch surgeon
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn("ANN001", args)

    @patch("watchdog.subprocess.Popen")
    @patch("watchdog.subprocess.run")
    def test_empty_regressions_falls_back_to_candidates(
        self, mock_run: MagicMock, mock_popen: MagicMock
    ) -> None:
        # Empty regressions -> _get_safe_ruff_candidates() is called instead
        # Return empty violations -> no Popen
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        wd.auto_dispatch_surgeon(regressions=[])
        mock_run.assert_called_once()  # _get_safe_ruff_candidates ran
        mock_popen.assert_not_called()

    @patch("watchdog.subprocess.Popen")
    @patch("watchdog.subprocess.run")
    @patch("watchdog.BACKEND_DIR", Path("/fake/backend"))
    def test_unsafe_code_not_dispatched(
        self, mock_run: MagicMock, mock_popen: MagicMock
    ) -> None:
        # ruff returns BLE001 (unsafe code -- not in SAFE_RUFF_CODES_FOR_DISPATCH)
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps([
                {"filename": "backend/app/bar.py", "row": 5, "col": 1,
                 "code": "BLE001", "message": "blind exception"}
            ])
        )
        wd.auto_dispatch_surgeon(regressions=["backend/app/bar.py"])
        mock_popen.assert_not_called()

    @patch("watchdog.subprocess.Popen")
    @patch("watchdog.subprocess.run")
    @patch("watchdog.BACKEND_DIR", Path("/fake/backend"))
    def test_max_two_files(
        self, mock_run: MagicMock, mock_popen: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps([
                {"filename": "f.py", "row": 1, "col": 1,
                 "code": "ANN001", "message": "missing annotation"}
            ])
        )
        wd.auto_dispatch_surgeon(
            regressions=["backend/app/a.py", "backend/app/b.py", "backend/app/c.py"]
        )
        # Max 2 files -> max 2 Popen calls
        self.assertLessEqual(mock_popen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
