"""Hardening — operational resilience for War Room 2.0 (Sprint 12).

Reference: docs/war-room-2.0-design.md §11, §14.

Modules:
- failover_detector: decides when Air should take over Trend-Hunter
- missed_runs_alerter: Telegram notifications for war_room_missed_runs
- token_watchdog: alerts 7gg before IG/LinkedIn long-lived token expiry
- quota_monitor: watches war_room_costs for soft-cap breach + daily spike
"""

from backend.services.hardening.failover_detector import (
    FailoverDetector,
    FailoverState,
    PeerState,
)
from backend.services.hardening.missed_runs_alerter import (
    MissedRunsAlerter,
    MissedRunsAlertResult,
)
from backend.services.hardening.quota_monitor import (
    QuotaMonitor,
    QuotaMonitorResult,
    QuotaReport,
)
from backend.services.hardening.token_watchdog import (
    TokenExpiryReport,
    TokenWatchdog,
    TokenWatchdogResult,
)

__all__ = [
    "FailoverDetector",
    "FailoverState",
    "MissedRunsAlertResult",
    "MissedRunsAlerter",
    "PeerState",
    "QuotaMonitor",
    "QuotaMonitorResult",
    "QuotaReport",
    "TokenExpiryReport",
    "TokenWatchdog",
    "TokenWatchdogResult",
]
