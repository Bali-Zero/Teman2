"""
Tests for base_worker.redis_cmd retry-on-timeout behavior (2026-07-08).

Context: intel-bridge was observed at 292/292 (100%) publish failures on
Mini, all failing with "redis-cli timeout after 10s" while Mini's load
average was 25-38 (vs a 1.3-1.7 baseline) — a single-shot 10s timeout with
zero retry turns a transient host-scheduling spike into a hard failure.
redis_cmd() now retries TimeoutExpired (not other errors) with a short
fixed backoff between attempts, controlled by a new `retries` kwarg that
defaults to 2 (3 total attempts) and is fully backward compatible (every
existing caller passes only positional *args + `timeout=` keyword).
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from mata_garuda.workers import base_worker


def _completed(stdout: str = "OK", returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = ""
    return result


@patch("mata_garuda.workers.base_worker.time.sleep", return_value=None)
@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_redis_cmd_succeeds_first_try_no_retry_needed(mock_run, mock_sleep):
    mock_run.return_value = _completed("PONG")
    out = base_worker.redis_cmd("PING")
    assert out == "PONG"
    assert mock_run.call_count == 1
    assert mock_sleep.call_count == 0


@patch("mata_garuda.workers.base_worker.time.sleep", return_value=None)
@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_redis_cmd_retries_on_timeout_then_succeeds(mock_run, mock_sleep):
    mock_run.side_effect = [
        subprocess.TimeoutExpired(cmd="redis-cli", timeout=10),
        _completed("OK"),
    ]
    out = base_worker.redis_cmd("XADD", "stream", "*", "field", "value")
    assert out == "OK"
    assert mock_run.call_count == 2
    assert mock_sleep.call_count == 1


@patch("mata_garuda.workers.base_worker.time.sleep", return_value=None)
@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_redis_cmd_exhausts_retries_and_reports_attempts(mock_run, mock_sleep):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="redis-cli", timeout=10)
    out = base_worker.redis_cmd("XADD", "stream", "*", "field", "value")
    assert out == "[ERROR] redis-cli timeout after 10s (3 attempts)"
    assert mock_run.call_count == 3
    assert mock_sleep.call_count == 2


@patch("mata_garuda.workers.base_worker.time.sleep", return_value=None)
@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_redis_cmd_retries_zero_preserves_single_shot_behavior(mock_run, mock_sleep):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="redis-cli", timeout=5)
    out = base_worker.redis_cmd("PING", timeout=5, retries=0)
    assert out == "[ERROR] redis-cli timeout after 5s (1 attempts)"
    assert mock_run.call_count == 1
    assert mock_sleep.call_count == 0


@patch("mata_garuda.workers.base_worker.time.sleep", return_value=None)
@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_redis_cmd_does_not_retry_non_timeout_errors(mock_run, mock_sleep):
    mock_run.return_value = _completed(returncode=1)
    mock_run.return_value.stderr = "WRONGTYPE Operation against a key"
    out = base_worker.redis_cmd("XADD", "stream", "*")
    assert out == "[ERROR] redis-cli: WRONGTYPE Operation against a key"
    assert mock_run.call_count == 1
    assert mock_sleep.call_count == 0


@patch("mata_garuda.workers.base_worker.subprocess.run", side_effect=FileNotFoundError())
def test_redis_cmd_file_not_found_no_retry(mock_run):
    out = base_worker.redis_cmd("PING")
    assert out == "[ERROR] redis-cli not found"
    assert mock_run.call_count == 1
