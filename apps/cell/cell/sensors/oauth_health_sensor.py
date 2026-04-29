"""OAuthHealthSensor — Cell sensor for Google Drive OAuth token expiry.

Reads the watchdog state file written by `scripts/drive_token_watchdog.py`
(no extra DB / fly ssh round-trip from the Cell pulse loop). Maps the
last-classified tier to green/yellow/red per the P1-11 (zero-crash audit
2026-04-29) tier table:

    TIER                  days_left      Cell color
    --------------------  -------------  ------------
    TIER_OK               > 30           green
    TIER_30_DAYS          15..30         green   (heads-up only)
    TIER_14_DAYS          8..14          yellow  (warning)
    TIER_7_DAYS           2..7           red     (urgent — visible to organism)
    TIER_1_DAY            0..1           red
    TIER_EXPIRED          < 0            red

State file: ``~/.agent/decisions/state/drive_oauth_watchdog.state.json``
(written every ``drive_token_watchdog.py`` run on Air, every 6h).

If the state file is missing OR stale (no successful watchdog run within the
last 18h = 3× the cron interval), the sensor returns ``yellow`` with reason
``stale`` — the Cell can then surface "OAuth visibility lost" as distinct
from "OAuth definitely fine".

The sensor never makes network calls — it only inspects a local JSON file.
This keeps the Cell pulse loop fast and decoupled from Fly.io connectivity.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cell.sensors.oauth_health")

# Default state-file path; matches scripts/drive_token_watchdog.py.
_DEFAULT_STATE_PATH = os.path.expanduser(
    "~/.agent/decisions/state/drive_oauth_watchdog.state.json"
)

# Watchdog cron runs every 6h; treat last_check older than 18h as stale.
_DEFAULT_STALE_AFTER_HOURS = 18.0

# Tier → (cell_color, reason_label). Mirrors the watchdog tier names so the
# Cell pulse and the Telegram alerts agree on terminology.
_TIER_TO_COLOR: dict[str, tuple[str, str]] = {
    "ok": ("green", "token healthy (>30 days remaining)"),
    "info_30d": ("green", "30d heads-up window"),
    "warning_14d": ("yellow", "14d warning — re-auth this week"),
    "urgent_7d": ("red", "7d urgent — re-auth NOW"),
    "critical_1d": ("red", "1d critical — re-auth immediately"),
    "critical_expired": ("red", "OAuth EXPIRED — Drive polling broken"),
}


@dataclass
class OAuthHealthReading:
    """One sensor reading. ``status`` is green/yellow/red per Cell convention."""

    status: str  # "green", "yellow", "red", "unknown"
    tier: str = ""  # watchdog tier string (e.g. "warning_14d") or empty
    days_left: int | None = None  # extracted from state if present
    last_check_iso: str = ""  # last watchdog run ISO timestamp
    metadata: dict[str, Any] = field(default_factory=dict)


class OAuthHealthSensor:
    """Reads the drive_token_watchdog state file and classifies it.

    No network I/O. The watchdog is the sole owner of the actual check; this
    sensor is purely a *consumer* of the watchdog's classification.
    """

    def __init__(
        self,
        state_path: str = _DEFAULT_STATE_PATH,
        stale_after_hours: float = _DEFAULT_STALE_AFTER_HOURS,
    ) -> None:
        self._state_path = state_path
        self._stale_after_hours = stale_after_hours

    def read(self, now: datetime | None = None) -> OAuthHealthReading:
        """Read & classify. ``now`` is injectable for tests."""
        now = now or datetime.now(timezone.utc)

        if not os.path.exists(self._state_path):
            return OAuthHealthReading(
                status="unknown",
                metadata={
                    "reason": "watchdog state file not found",
                    "path": self._state_path,
                },
            )

        try:
            with open(self._state_path) as f:
                state = json.load(f)
        except Exception as e:
            logger.debug(f"OAuthHealthSensor: failed to read {self._state_path}: {e}")
            return OAuthHealthReading(
                status="unknown",
                metadata={"reason": f"state read error: {e}", "path": self._state_path},
            )

        tier = state.get("last_oauth_tier", "") or ""
        last_check_iso = state.get("last_oauth_check_iso", "") or ""
        days_left = state.get("last_oauth_days_left")  # optional

        # Staleness check — if the watchdog hasn't successfully run recently,
        # we don't trust the cached tier. Yellow ("visibility lost"), not red.
        if last_check_iso:
            try:
                last_check_dt = datetime.fromisoformat(last_check_iso)
                if last_check_dt.tzinfo is None:
                    last_check_dt = last_check_dt.replace(tzinfo=timezone.utc)
                age_hours = (now - last_check_dt).total_seconds() / 3600.0
                if age_hours > self._stale_after_hours:
                    return OAuthHealthReading(
                        status="yellow",
                        tier=tier,
                        days_left=days_left,
                        last_check_iso=last_check_iso,
                        metadata={
                            "reason": f"watchdog state stale ({age_hours:.1f}h old)",
                            "stale_after_hours": self._stale_after_hours,
                        },
                    )
            except Exception as e:
                logger.debug(
                    f"OAuthHealthSensor: failed to parse last_check_iso "
                    f"{last_check_iso!r}: {e}"
                )
                # Fall through to tier-based classification.

        if not tier:
            return OAuthHealthReading(
                status="unknown",
                last_check_iso=last_check_iso,
                metadata={"reason": "state file has no last_oauth_tier yet"},
            )

        color, reason = _TIER_TO_COLOR.get(
            tier, ("unknown", f"unknown tier: {tier}")
        )
        return OAuthHealthReading(
            status=color,
            tier=tier,
            days_left=days_left,
            last_check_iso=last_check_iso,
            metadata={"reason": reason},
        )
