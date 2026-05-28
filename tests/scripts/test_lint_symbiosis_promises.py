"""Unit tests for scripts/lint_symbiosis_promises.py."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import lint_symbiosis_promises as lint_promises


class TestLintSymbiosisPromises(unittest.TestCase):
    def _lint_text(self, text: str) -> int:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(text)
            path = Path(f.name)
        try:
            return lint_promises.lint(path)
        finally:
            path.unlink()

    def test_accepts_promise_followed_by_test_citation(self) -> None:
        result = self._lint_text(
            "Replay is durable for registered channels.\n"
            "Test: `apps/backend-rag/backend/tests/services/events/test_event_bus_replay.py`\n"
        )

        self.assertEqual(result, 0)

    def test_previous_citation_does_not_cover_later_uncited_promise(self) -> None:
        result = self._lint_text(
            "Replay is durable for registered channels.\n"
            "Test: `apps/backend-rag/backend/tests/services/events/test_event_bus_replay.py`\n"
            "\n"
            "A disconnected worker will always recover all pending messages.\n"
        )

        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
