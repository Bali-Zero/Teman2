"""Tests for multimodal_pipeline._download_with_retry — readiness retry
for non-polling artifact downloads (mind-map/report vs audio/infographic).

Guilt: mind-map/report retry through transient not-ready failures and
succeed, or exhaust attempts and report failure.
Innocence: audio/infographic (NO_PROGRESS_SUPPORTED) and dry_run pass
through unretried — a first failure there is a real error, not a
readiness gap.
"""
from __future__ import annotations

from unittest.mock import patch

from apps.evaluator.nlm_deep_research.multimodal_pipeline import (
    DOWNLOAD_RETRY_ATTEMPTS,
    _download_with_retry,
)


class TestDownloadWithRetryGuilt:
    """Non-polling types (mind-map/report) retry on readiness failure."""

    @patch("apps.evaluator.nlm_deep_research.multimodal_pipeline.time.sleep")
    @patch("apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download")
    def test_succeeds_after_two_failures(self, mock_download, mock_sleep):
        mock_download.side_effect = [
            (False, "not ready"),
            (False, "not ready"),
            (True, "/tmp/out.json"),
        ]

        ok, msg = _download_with_retry("mind-map", "nb3-id", "/tmp/out.json")

        assert (ok, msg) == (True, "/tmp/out.json")
        assert mock_download.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("apps.evaluator.nlm_deep_research.multimodal_pipeline.time.sleep")
    @patch("apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download")
    def test_exhausts_all_attempts_then_fails(self, mock_download, mock_sleep):
        mock_download.return_value = (False, "still not ready")

        ok, msg = _download_with_retry("report", "nb-id", "/tmp/out.md")

        assert ok is False
        assert msg == "still not ready"
        assert mock_download.call_count == DOWNLOAD_RETRY_ATTEMPTS
        # one fewer sleep than attempts — no sleep after the final failure
        assert mock_sleep.call_count == DOWNLOAD_RETRY_ATTEMPTS - 1


class TestDownloadWithRetryInnocence:
    """Polling types and dry_run pass through unretried."""

    @patch("apps.evaluator.nlm_deep_research.multimodal_pipeline.time.sleep")
    @patch("apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download")
    def test_audio_failure_is_not_retried(self, mock_download, mock_sleep):
        mock_download.return_value = (False, "real error")

        ok, msg = _download_with_retry("audio", "nb2-id", "/tmp/out.m4a")

        assert (ok, msg) == (False, "real error")
        assert mock_download.call_count == 1
        mock_sleep.assert_not_called()

    @patch("apps.evaluator.nlm_deep_research.multimodal_pipeline.time.sleep")
    @patch("apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download")
    def test_dry_run_mind_map_is_single_passthrough(self, mock_download, mock_sleep):
        mock_download.return_value = (True, "dry_run")

        ok, msg = _download_with_retry(
            "mind-map", "nb3-id", "/tmp/out.json", dry_run=True
        )

        assert (ok, msg) == (True, "dry_run")
        assert mock_download.call_count == 1
        mock_sleep.assert_not_called()
