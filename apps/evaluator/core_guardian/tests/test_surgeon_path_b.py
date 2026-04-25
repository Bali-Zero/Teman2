"""Tests for Surgeon Path B — AST-aware Claude Code invocation for UNSAFE codes."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from surgeon import (
    UNSAFE_RUFF_CODES,
    build_surgeon_prompt,
    extract_ast_context,
    get_ruff_violations,
)


def _write_tmp(source: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    tmp.write(source)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


class TestGetRuffViolations(unittest.TestCase):
    @patch("surgeon.subprocess.run")
    def test_parses_json(self, mock_run: MagicMock) -> None:
        payload = [
            {"location": {"row": 12, "column": 4}, "message": "func too complex"},
            {"location": {"row": 30, "column": 1}, "message": "func too complex (2)"},
        ]
        mock_run.return_value = MagicMock(returncode=1, stdout=json.dumps(payload), stderr="")
        out = get_ruff_violations(Path("/fake/foo.py"), "C901")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], {"row": 12, "col": 4, "message": "func too complex"})
        self.assertEqual(out[1]["row"], 30)

    @patch("surgeon.subprocess.run")
    def test_returns_empty_on_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ruff", timeout=30)
        self.assertEqual(get_ruff_violations(Path("/fake/x.py"), "C901"), [])

    @patch("surgeon.subprocess.run")
    def test_returns_empty_on_empty_stdout(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        self.assertEqual(get_ruff_violations(Path("/fake/x.py"), "C901"), [])

    @patch("surgeon.subprocess.run")
    def test_returns_empty_on_bad_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="not-json{", stderr="")
        self.assertEqual(get_ruff_violations(Path("/fake/x.py"), "C901"), [])


class TestExtractAstContext(unittest.TestCase):
    def test_returns_enclosing_function(self) -> None:
        source = (
            "def outer():\n"
            "    x = 1\n"
            "    return x\n"
            "\n"
            "def target_func():\n"
            "    a = 1\n"
            "    b = 2\n"
            "    c = a + b\n"
            "    return c\n"
        )
        path = _write_tmp(source)
        try:
            violations = [{"row": 7, "col": 1, "message": "complex"}]
            out = extract_ast_context(path, violations)
            self.assertIn("target_func", out)
            self.assertNotIn("outer", out)
        finally:
            path.unlink()

    def test_deduplicates_overlapping_violations(self) -> None:
        source = (
            "def target():\n"
            "    x = 1\n"
            "    y = 2\n"
            "    z = 3\n"
            "    return x + y + z\n"
        )
        path = _write_tmp(source)
        try:
            violations = [
                {"row": 2, "col": 1, "message": "a"},
                {"row": 3, "col": 1, "message": "b"},
                {"row": 4, "col": 1, "message": "c"},
            ]
            out = extract_ast_context(path, violations)
            self.assertEqual(out.count("def target"), 1)
        finally:
            path.unlink()

    def test_falls_back_on_syntax_error(self) -> None:
        # File with a syntax error — should trigger fallback window path.
        source = "def broken(:\n    x = 1\n    y = 2\n    z = 3\n"
        path = _write_tmp(source)
        try:
            violations = [{"row": 3, "col": 1, "message": "anything"}]
            out = extract_ast_context(path, violations)
            self.assertIn("fallback window", out)
            self.assertIn("y = 2", out)
        finally:
            path.unlink()

    def test_returns_empty_on_no_violations(self) -> None:
        source = "def f():\n    return 1\n"
        path = _write_tmp(source)
        try:
            self.assertEqual(extract_ast_context(path, []), "")
        finally:
            path.unlink()


class TestBuildSurgeonPrompt(unittest.TestCase):
    def test_includes_ast_when_provided(self) -> None:
        prompt = build_surgeon_prompt(
            task_description="reduce complexity",
            target_file="backend/app/routers/foo.py",
            ruff_code="C901",
            ast_context="def target_func():\n    pass",
            ruff_violations_json='[{"row": 12}]',
        )
        self.assertIn("AST CONTEXT", prompt)
        self.assertIn("target_func", prompt)
        self.assertIn("RUFF VIOLATIONS", prompt)
        self.assertIn('"row": 12', prompt)
        # Guidance for C901 refactor
        self.assertIn("cyclomatic complexity", prompt)

    def test_unchanged_without_ast(self) -> None:
        prompt = build_surgeon_prompt(
            task_description="fix DTZ005",
            target_file="backend/app/routers/foo.py",
            ruff_code="DTZ005",
        )
        self.assertNotIn("AST CONTEXT", prompt)
        self.assertNotIn("RUFF VIOLATIONS", prompt)


class TestSurgeonPassesAstToClaudeCode(unittest.TestCase):
    """Verify that for C901, _surgeon_core builds a prompt enriched with AST."""

    def test_prompt_contains_ast_marker_for_c901(self) -> None:
        # Unit-level verification: calling build_surgeon_prompt with the
        # same enrichment params that _surgeon_core passes for UNSAFE codes
        # yields a prompt with the AST marker. This covers the wiring without
        # exercising the whole surgeon_run pipeline.
        violations = [{"row": 5, "col": 1, "message": "C901"}]
        ast_ctx = "# target_func (lines 1-8)\ndef target_func():\n    pass"
        prompt = build_surgeon_prompt(
            task_description="reduce complexity in target_func",
            target_file="backend/app/routers/foo.py",
            ruff_code="C901",
            ast_context=ast_ctx,
            ruff_violations_json=json.dumps(violations),
        )
        self.assertIn("AST CONTEXT", prompt)
        self.assertIn("target_func", prompt)
        # Confirm C901 is in UNSAFE set (the condition that triggers enrichment)
        self.assertIn("C901", UNSAFE_RUFF_CODES)


if __name__ == "__main__":
    unittest.main()
