"""Unit tests for scripts/lint_symbiosis_promises.py."""
from __future__ import annotations

import contextlib
import io
import subprocess
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

    # ---- guilt + innocence twins with independently derived expectations ----

    CITE = "Test: `tests/test_x.py`"

    def _run(self, text: str) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._lint_text(text)
        return rc, buf.getvalue()

    def test_non_promise_line_produces_no_finding(self) -> None:
        rc, out = self._run("Plain prose about the weather.\nNothing lyrical here.\n")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("OK:"))

    def test_citation_ten_lines_after_is_accepted(self) -> None:
        # promise at line 1, citation at line 11 = ten lines after
        text = "This is durable.\n" + "filler\n" * 9 + self.CITE + "\n"
        self.assertEqual(text.splitlines()[10], self.CITE)
        self.assertEqual(self._run(text)[0], 0)

    def test_citation_eleven_lines_after_is_rejected(self) -> None:
        text = "This is durable.\n" + "filler\n" * 10 + self.CITE + "\n"
        self.assertEqual(text.splitlines()[11], self.CITE)
        self.assertEqual(self._run(text)[0], 1)

    def test_citation_on_the_same_line_is_accepted(self) -> None:
        rc, _ = self._run("This is durable. Test: `tests/test_x.py`\n")
        self.assertEqual(rc, 0)

    def test_citation_on_the_line_before_does_not_cover(self) -> None:
        rc, out = self._run(self.CITE + "\nThis is durable.\n")
        self.assertEqual(rc, 1)
        self.assertIn("L2:", out)

    def test_one_finding_per_line_even_if_several_patterns_match(self) -> None:
        rc, out = self._run("durable replay guaranteed\n")
        self.assertEqual(rc, 1)
        self.assertIn("1 unverified durability promise(s)", out)
        self.assertEqual(out.count("  L1:"), 1)

    def test_two_uncited_promises_are_both_reported_with_line_numbers(self) -> None:
        text = "intro\nThis is durable.\n" + "filler\n" * 11 + "We guarantee it.\n"
        rc, out = self._run(text)
        self.assertEqual(rc, 1)
        self.assertIn("2 unverified durability promise(s)", out)
        self.assertIn("  L2:", out)
        self.assertIn("  L14:", out)

    def test_claim_is_truncated_to_eighty_chars(self) -> None:
        claim = "durable " + "x" * 92  # 100 chars
        _, out = self._run(claim + "\n")
        self.assertIn(repr(claim[:80]), out)
        self.assertNotIn(claim[:81], out)

    def test_matched_pattern_is_named_in_report(self) -> None:
        _, out = self._run("We never lose data.\n")
        self.assertIn(r"(matched: /\bnever\s+lose\b/)", out)

    def test_cli_uses_argv_path_and_exit_code(self) -> None:
        script = Path(lint_promises.__file__)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "other.md"
            f.write_text("This is durable.\n")
            r = subprocess.run(
                [sys.executable, str(script), str(f)], capture_output=True, text=True
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("L1:", r.stdout)

    def test_cli_default_path_is_symbiosis_md_in_cwd(self) -> None:
        script = Path(lint_promises.__file__)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "SYMBIOSIS.md").write_text("This is durable.\n")
            r = subprocess.run(
                [sys.executable, str(script)], capture_output=True, text=True, cwd=d
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("SYMBIOSIS.md", r.stdout)
            (Path(d) / "SYMBIOSIS.md").write_text("Plain.\n")
            r = subprocess.run(
                [sys.executable, str(script)], capture_output=True, text=True, cwd=d
            )
            self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
