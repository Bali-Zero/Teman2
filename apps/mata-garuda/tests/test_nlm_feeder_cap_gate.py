"""W15: nlm_feeder NB source-count cap gate.

Google NotebookLM silently rejects `source add` when a notebook reaches
~500-600 sources. Previously _nlm_add_url/_nlm_add_text wasted 60s on
rejected calls and logged unhelpful "case_not_resolved". W15 adds a
per-NB pre-check with 1h cache.
"""
from __future__ import annotations
import logging
from unittest.mock import patch, MagicMock

from mata_garuda.workers import nlm_feeder


def _reset_cache():
    nlm_feeder._NB_COUNT_CACHE.clear()


def test_nlm_at_cap_true_when_count_above_threshold():
    _reset_cache()
    with patch.object(nlm_feeder, "_nlm_notebook_source_count", return_value=600):
        assert nlm_feeder._nlm_at_cap("nb-id") is True


def test_nlm_at_cap_false_when_count_below_threshold():
    _reset_cache()
    with patch.object(nlm_feeder, "_nlm_notebook_source_count", return_value=215):
        assert nlm_feeder._nlm_at_cap("nb-id") is False


def test_nlm_at_cap_false_on_probe_failure():
    """If notebook-list probe fails, don't skip — let CLI try (graceful degrade)."""
    _reset_cache()
    with patch.object(nlm_feeder, "_nlm_notebook_source_count", return_value=None):
        assert nlm_feeder._nlm_at_cap("nb-id") is False


def test_add_url_skips_when_at_cap(caplog):
    _reset_cache()
    with patch.object(nlm_feeder, "_nlm_at_cap", return_value=True), \
         patch.object(nlm_feeder.subprocess, "run") as mock_run:
        caplog.set_level(logging.WARNING, logger="mata_garuda.workers")
        result = nlm_feeder._nlm_add_url("nb-cap", "https://example.com/x")
    assert result is False
    mock_run.assert_not_called()
    assert any("skip add (NB at cap)" in r.message for r in caplog.records)


def test_add_url_surfaces_stderr_on_rejection(caplog):
    _reset_cache()
    fake_rc = MagicMock(returncode=1, stderr="Error: Could not add url source", stdout="")
    with patch.object(nlm_feeder, "_nlm_at_cap", return_value=False), \
         patch.object(nlm_feeder.subprocess, "run", return_value=fake_rc):
        caplog.set_level(logging.WARNING, logger="mata_garuda.workers")
        result = nlm_feeder._nlm_add_url("nb-ok", "https://example.com/y")
    assert result is False
    assert any(
        "add_url rejected" in r.message and "Could not add url source" in r.message
        for r in caplog.records
    )


def test_add_url_success_still_returns_true():
    _reset_cache()
    fake_rc = MagicMock(returncode=0, stderr="", stdout="OK")
    with patch.object(nlm_feeder, "_nlm_at_cap", return_value=False), \
         patch.object(nlm_feeder.subprocess, "run", return_value=fake_rc):
        result = nlm_feeder._nlm_add_url("nb-ok", "https://example.com/z")
    assert result is True


def test_source_count_cache_hits_within_ttl():
    """Second call within TTL must not re-spawn subprocess."""
    _reset_cache()
    nlm_feeder._NB_COUNT_CACHE["nb-cached"] = (300, __import__("time").time())
    with patch.object(nlm_feeder.subprocess, "run") as mock_run:
        count = nlm_feeder._nlm_notebook_source_count("nb-cached")
    assert count == 300
    mock_run.assert_not_called()


def test_source_count_returns_none_on_subprocess_error():
    _reset_cache()
    fake_rc = MagicMock(returncode=1, stdout="", stderr="connection refused")
    with patch.object(nlm_feeder.subprocess, "run", return_value=fake_rc):
        count = nlm_feeder._nlm_notebook_source_count("nb-x")
    assert count is None


def test_source_cap_constant_matches_design():
    assert nlm_feeder.NLM_NOTEBOOK_SOURCE_CAP == 500
    assert nlm_feeder._NB_COUNT_TTL_S == 3600
