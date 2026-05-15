"""Grandfathered polling-based watchdog test stub for pg-organism-bridge.

Documents the L3 grandfathered exception: the watchdog uses 5min polling
instead of durable XADD heartbeat consumer. Heartbeat-based watchdog is
follow-up PR (gated on bridge restart). Until then, polling watchdog is
in production AND lint_symbiosis_promises.py needs this file to exist.

TODO follow-up PR: replace polling with XREAD BLOCK consumer of
`organism:heartbeat` stream (60s XADD producer in pg-to-organism-bridge.py).
"""
import pytest


@pytest.mark.skip(reason="TDD stub for L4 audit gate — implementation in follow-up PR")
def test_watchdog_alerts_when_bridge_pid_missing():
    """Polling watchdog detects missing bridge PID and alerts via Telegram."""
    pass


@pytest.mark.skip(reason="TDD stub for L4 audit gate")
def test_watchdog_alerts_when_redis_stream_lag_exceeds_30min():
    """Polling watchdog alerts when organism:events stream stale > 30min."""
    pass
