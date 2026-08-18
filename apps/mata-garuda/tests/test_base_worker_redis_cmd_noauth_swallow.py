"""
Regression tests for the W89/W104 NOAUTH-swallow family in base_worker.redis_cmd
— the one SSOT that nerve.py and check_redis_split_brain.py both cite as
"already carries REDISCLI_AUTH" but that never got their own NOAUTH-in-stdout
detection (they each reimplemented it independently instead).

Background: redis-cli returns an auth-failure reply ("NOAUTH Authentication
required.", "WRONGPASS ...", "NOPERM ...") on STDOUT at exit 0 — never a
nonzero returncode. Every downstream caller of redis_cmd() (stream_tools,
task_tools, intel_publisher, wr2_bridge_publisher, kita_feed_generator,
public_channel_publisher, intel_scraper_bridge, run_nlm_feeder_stream, ...)
checks `result.startswith("[ERROR]")` to detect failure. Without this fix,
an auth failure on a host missing GARUDA_REDIS_PASSWORD (measured live on
Mini: com.matagaruda.intel-bridge.daily/normalizer.hourly/sentinel.daily
plists carry no such key) is silently treated as a successful reply —
intel_publisher.publish_to_redis() would return "NOAUTH Authentication
required." as if it were a real XADD entry ID.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from mata_garuda.workers import base_worker


def _completed(stdout: str, returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = ""
    return result


@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_noauth_reply_at_exit_0_is_surfaced_as_error(mock_run):
    mock_run.return_value = _completed("NOAUTH Authentication required.")
    out = base_worker.redis_cmd("XADD", "garuda:raw", "*", "k", "v")
    assert out.startswith("[ERROR]")
    assert "NOAUTH" in out


@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_wrongpass_reply_at_exit_0_is_surfaced_as_error(mock_run):
    mock_run.return_value = _completed("WRONGPASS invalid username-password pair")
    out = base_worker.redis_cmd("PING")
    assert out.startswith("[ERROR]")
    assert "WRONGPASS" in out


@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_noperm_reply_at_exit_0_is_surfaced_as_error(mock_run):
    mock_run.return_value = _completed("NOPERM this user has no permissions")
    out = base_worker.redis_cmd("XADD", "garuda:raw", "*", "k", "v")
    assert out.startswith("[ERROR]")
    assert "NOPERM" in out


@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_healthy_xadd_reply_passes_through_unflagged(mock_run):
    """Innocence: a genuine stream-id reply must NOT be treated as an error."""
    mock_run.return_value = _completed("1755000000000-0")
    out = base_worker.redis_cmd("XADD", "garuda:raw", "*", "k", "v")
    assert out == "1755000000000-0"
    assert not out.startswith("[ERROR]")


@patch("mata_garuda.workers.base_worker.subprocess.run")
def test_healthy_pong_reply_passes_through_unflagged(mock_run):
    mock_run.return_value = _completed("PONG")
    out = base_worker.redis_cmd("PING")
    assert out == "PONG"
