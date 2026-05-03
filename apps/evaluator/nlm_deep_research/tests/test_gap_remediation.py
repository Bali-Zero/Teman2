"""Tests for ARCH-5 Gap Remediation Loop (gap_scanner.run_remediation)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Make the project importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from apps.evaluator.nlm_deep_research.gap_scanner import (
    COVERAGE_MATRIX_FILE,
    MAX_REMEDIATIONS_PER_RUN,
    _add_source_to_notebook,
    _classify_freshness,
    _run_gemini_search,
    run_remediation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MATRIX = {
    "immigration": {
        "label": "Immigration & Visa",
        "coverage": {
            "KITAS requirements and process 2025": "GAP",
            "KITAP eligibility and conversion from KITAS": "STALE",
            "B211A visa digital nomad Indonesia": "FRESH",
        },
        "health_pct": 33.3,
        "gap_pct": 33.3,
    },
    "tax": {
        "label": "Tax & Fiscal",
        "coverage": {
            "PPh 21 rates and calculation for expats": "GAP",
            "CoreTax system migration 2025": "STALE",
            "PPN (VAT) 11% registration and reporting": "AGING",
        },
        "health_pct": 0.0,
        "gap_pct": 33.3,
    },
}


# ---------------------------------------------------------------------------
# Unit tests: _run_gemini_search
# ---------------------------------------------------------------------------


class TestRunGeminiSearch:
    def test_returns_content_on_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Immigration regulation update 2025...", stderr=""
            )
            result = _run_gemini_search("KITAS requirements 2025")
        assert result is not None
        assert "Immigration" in result

    def test_returns_none_on_no_result_marker(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="NO_RESULT", stderr="")
            result = _run_gemini_search("obscure topic")
        assert result is None

    def test_returns_none_on_nonzero_exit(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            result = _run_gemini_search("something")
        assert result is None

    def test_returns_none_if_gemini_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _run_gemini_search("something")
        assert result is None

    def test_returns_none_on_timeout(self):
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gemini", 120)):
            result = _run_gemini_search("something")
        assert result is None

    def test_returns_none_on_empty_output(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = _run_gemini_search("something")
        assert result is None


# ---------------------------------------------------------------------------
# Unit tests: _add_source_to_notebook
# ---------------------------------------------------------------------------


class TestAddSourceToNotebook:
    def test_returns_true_on_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            result = _add_source_to_notebook("nb-123", "Test Title", "Test content")
        assert result is True

    def test_returns_false_on_nonzero_exit(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="failed")
            result = _add_source_to_notebook("nb-123", "Test Title", "Test content")
        assert result is False

    def test_returns_false_on_timeout(self):
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("nlm", 60)):
            result = _add_source_to_notebook("nb-123", "Title", "Content")
        assert result is False

    def test_passes_correct_args_to_nlm(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            _add_source_to_notebook("nb-abc", "My Title", "My content here")
        call_args = mock_run.call_args[0][0]
        assert "nlm" in call_args
        assert "source" in call_args
        assert "add" in call_args
        assert "nb-abc" in call_args
        assert "--text" in call_args
        assert "My content here" in call_args
        assert "--title" in call_args
        assert "My Title" in call_args


# ---------------------------------------------------------------------------
# Unit tests: run_remediation
# ---------------------------------------------------------------------------


class TestRunRemediation:
    def test_dry_run_returns_counts_without_side_effects(self, tmp_path):
        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps(SAMPLE_MATRIX))

        with patch(
            "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
            matrix_file,
        ):
            result = run_remediation(dry_run=True)

        assert result["status"] in ("ok", "partial")
        assert result["dry_run"] is True
        # 2 GAP topics total: immigration/KITAS + tax/PPh21
        assert result["gap_topics_found"] == 2
        # 2 STALE topics: immigration/KITAP + tax/CoreTax
        assert result["stale_topics_found"] == 2
        # Dry run counts them as "added"
        assert result["sources_added"] == MAX_REMEDIATIONS_PER_RUN

    def test_skipped_if_no_coverage_matrix(self, tmp_path):
        missing_file = tmp_path / "nonexistent.json"
        with patch(
            "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
            missing_file,
        ):
            result = run_remediation(dry_run=False)

        assert result["status"] == "skipped"
        assert result["sources_added"] == 0

    def test_processes_gap_before_stale(self, tmp_path):
        """GAP topics must be processed before STALE topics."""
        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps(SAMPLE_MATRIX))

        processed_topics: list[str] = []

        def fake_gemini(query: str) -> str | None:
            return f"Content for: {query}"

        def fake_add(nb_id: str, title: str, content: str, **kwargs) -> bool:
            processed_topics.append(title)
            return True

        with (
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
                matrix_file,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._run_gemini_search",
                side_effect=fake_gemini,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._add_source_to_notebook",
                side_effect=fake_add,
            ),
            patch("apps.evaluator.nlm_deep_research.gap_scanner._send_telegram"),
            patch("time.sleep"),
        ):
            result = run_remediation(dry_run=False)

        # First processed items should contain GAP-classified topics
        # (immigration/KITAS and tax/PPh21 are GAP, come before STALE)
        assert result["sources_added"] == MAX_REMEDIATIONS_PER_RUN
        # All processed titles should exist
        assert len(processed_topics) == MAX_REMEDIATIONS_PER_RUN

    def test_respects_max_remediations_per_run(self, tmp_path):
        """Never processes more than MAX_REMEDIATIONS_PER_RUN targets."""
        # Use real domain keys so DOMAIN_TOPICS lookup finds the notebook_id
        big_matrix: dict[str, Any] = {}
        real_domains = ["immigration", "tax", "company", "property", "operations"]
        for domain in real_domains:
            big_matrix[domain] = {
                "label": domain.title(),
                "coverage": {f"Topic A for {domain}": "GAP", f"Topic B for {domain}": "GAP"},
            }

        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps(big_matrix))

        add_calls = 0

        def fake_gemini(query: str) -> str | None:
            return "Some content"

        def fake_add(nb_id: str, title: str, content: str, **kwargs) -> bool:
            nonlocal add_calls
            add_calls += 1
            return True

        with (
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
                matrix_file,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._run_gemini_search",
                side_effect=fake_gemini,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._add_source_to_notebook",
                side_effect=fake_add,
            ),
            patch("apps.evaluator.nlm_deep_research.gap_scanner._send_telegram"),
            patch("time.sleep"),
        ):
            result = run_remediation(dry_run=False)

        assert add_calls == MAX_REMEDIATIONS_PER_RUN
        assert result["sources_added"] == MAX_REMEDIATIONS_PER_RUN

    def test_handles_gemini_failure_gracefully(self, tmp_path):
        """If Gemini returns nothing, record error but continue with next topic."""
        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps(SAMPLE_MATRIX))

        with (
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
                matrix_file,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._run_gemini_search",
                return_value=None,
            ),
            patch("time.sleep"),
        ):
            result = run_remediation(dry_run=False)

        assert result["sources_added"] == 0
        assert result["search_failed"] == MAX_REMEDIATIONS_PER_RUN
        assert result["status"] == "partial"

    def test_marks_remediated_topics_as_fresh_in_matrix(self, tmp_path):
        """After adding a source, the topic should be marked FRESH in the matrix."""
        single_topic_matrix = {
            "immigration": {
                "label": "Immigration & Visa",
                "coverage": {"KITAS requirements and process 2025": "GAP"},
                "health_pct": 0.0,
            }
        }
        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps(single_topic_matrix))

        with (
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
                matrix_file,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._run_gemini_search",
                return_value="Updated KITAS information 2025...",
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._add_source_to_notebook",
                return_value=True,
            ),
            patch("apps.evaluator.nlm_deep_research.gap_scanner._send_telegram"),
            patch("time.sleep"),
        ):
            result = run_remediation(dry_run=False)

        assert result["sources_added"] == 1

        # Verify matrix was updated on disk
        updated_matrix = json.loads(matrix_file.read_text())
        assert updated_matrix["immigration"]["coverage"]["KITAS requirements and process 2025"] == "FRESH"

    def test_sends_telegram_when_sources_added(self, tmp_path):
        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps({"immigration": {
            "label": "Immigration",
            "coverage": {"KITAS topic": "GAP"},
        }}))

        with (
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
                matrix_file,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._run_gemini_search",
                return_value="Some content",
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._add_source_to_notebook",
                return_value=True,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._send_telegram"
            ) as mock_tg,
            patch("time.sleep"),
        ):
            run_remediation(dry_run=False)

        mock_tg.assert_called_once()
        call_text = mock_tg.call_args[0][0]
        assert "Remediation" in call_text
        assert "Fonti aggiunte" in call_text

    def test_no_telegram_when_nothing_added(self, tmp_path):
        """If no sources were added, no Telegram notification."""
        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps(SAMPLE_MATRIX))

        with (
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
                matrix_file,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._run_gemini_search",
                return_value=None,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._send_telegram"
            ) as mock_tg,
            patch("time.sleep"),
        ):
            run_remediation(dry_run=False)

        mock_tg.assert_not_called()

    def test_empty_matrix_returns_ok_with_zero_counts(self, tmp_path):
        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps({}))

        with patch(
            "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
            matrix_file,
        ):
            result = run_remediation(dry_run=False)

        assert result["gap_topics_found"] == 0
        assert result["stale_topics_found"] == 0
        assert result["sources_added"] == 0
        assert result["status"] == "ok"

    def test_source_add_failure_recorded_in_errors(self, tmp_path):
        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps({"immigration": {
            "label": "Immigration",
            "coverage": {"KITAS topic": "GAP"},
        }}))

        with (
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner.COVERAGE_MATRIX_FILE",
                matrix_file,
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._run_gemini_search",
                return_value="Content found",
            ),
            patch(
                "apps.evaluator.nlm_deep_research.gap_scanner._add_source_to_notebook",
                return_value=False,
            ),
            patch("time.sleep"),
        ):
            result = run_remediation(dry_run=False)

        assert result["sources_added"] == 0
        assert len(result["errors"]) == 1
        assert "source add failed" in result["errors"][0]


# ---------------------------------------------------------------------------
# CLI integration: --remediate flag
# ---------------------------------------------------------------------------


class TestRemediationCLI:
    def test_remediate_flag_calls_run_remediation(self, tmp_path):
        """Ensure --remediate CLI flag routes to run_remediation()."""
        import apps.evaluator.nlm_deep_research.gap_scanner as gs

        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps({}))

        with (
            patch.object(gs, "COVERAGE_MATRIX_FILE", matrix_file),
            patch("sys.argv", ["gap_scanner", "--remediate"]),
            patch("sys.exit") as mock_exit,
        ):
            gs.main()

        # Should exit 0 (empty matrix = ok)
        mock_exit.assert_called_once_with(0)
