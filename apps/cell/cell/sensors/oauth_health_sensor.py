"""OAuthHealthSensor — Cell sensor for the Google Drive OAuth credential.

Reads the watchdog state file written by `scripts/drive_token_watchdog.py`
(no extra DB / fly ssh round-trip from the Cell pulse loop) and maps its
verdict to green/yellow/red:

    last_oauth_health   Cell color
    -----------------   ------------
    ok                  green
    no-token            red    (no credential exists at all)
    no-refresh          red    (cannot renew itself — re-auth required)

REPLACED 2026-08-06 — this sensor used to read `last_oauth_tier` and
`last_oauth_days_left` and paint a 30/14/7/1-**day** ladder. That ladder was
derived from `google_drive_tokens.expires_at`, which is the **one-hour access
token**, not a 90-day credential clock (measured: `expires_at - updated_at`
is exactly 1h on every row). So `days_left` was 0 for a token refreshed one
minute ago and negative for every idle row: this sensor would have painted
Drive permanently red off a healthy credential. See
`classify_oauth_health` in the watchdog for the full measurement.

The old keys are not merely ignored, they are deleted by the watchdog when it
writes — a state file from before today still contains them.

State file: ``~/.agent/decisions/state/drive_oauth_watchdog.state.json``
(written every ``drive_token_watchdog.py`` run, every 6h).

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

# Verdict → (cell_color, reason_label). Mirrors the watchdog's HEALTH_*
# constants so the Cell pulse and the Telegram alerts agree on terminology.
_HEALTH_TO_COLOR: dict[str, tuple[str, str]] = {
    "ok": ("green", "credential present and renewable"),
    "no-token": ("red", "no OAuth row in google_drive_tokens"),
    "no-refresh": ("red", "no refresh_token — cannot renew, re-auth required"),
}

# Values the watchdog wrote before 2026-08-06, off the wrong scale. A state
# file that still carries one is not evidence of anything: report unknown
# rather than repainting a stale day-ladder verdict as if it were current.
_RETIRED_TIER_VALUES = frozenset(
    {"info_30d", "warning_14d", "urgent_7d", "critical_1d", "critical_expired"}
)


@dataclass
class OAuthHealthReading:
    """One sensor reading. ``status`` is green/yellow/red per Cell convention."""

    status: str  # "green", "yellow", "red", "unknown"
    health: str = ""  # watchdog verdict ("ok"/"no-token"/"no-refresh") or empty
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

        health = state.get("last_oauth_health", "") or ""
        last_check_iso = state.get("last_oauth_check_iso", "") or ""

        # Staleness check — if the watchdog hasn't successfully run recently,
        # we don't trust the cached verdict. Yellow ("visibility lost"), not red.
        if last_check_iso:
            try:
                last_check_dt = datetime.fromisoformat(last_check_iso)
                if last_check_dt.tzinfo is None:
                    last_check_dt = last_check_dt.replace(tzinfo=timezone.utc)
                age_hours = (now - last_check_dt).total_seconds() / 3600.0
                if age_hours > self._stale_after_hours:
                    return OAuthHealthReading(
                        status="yellow",
                        health=health,
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
                # Fall through to verdict-based classification.

        if not health:
            # Includes every state file written before 2026-08-06: those carry
            # `last_oauth_tier` and no `last_oauth_health`, and the watchdog has
            # not run since the change. Unknown is the honest answer.
            legacy = state.get("last_oauth_tier")
            reason = "state file has no last_oauth_health yet"
            if legacy:
                reason = (
                    f"pre-2026-08-06 state (last_oauth_tier={legacy!r}) — that "
                    "ladder measured the 1h access token on a day scale; "
                    "ignored, waiting for the next watchdog run"
                )
            return OAuthHealthReading(
                status="unknown",
                last_check_iso=last_check_iso,
                metadata={"reason": reason},
            )

        if health in _RETIRED_TIER_VALUES:
            # A retired ladder value in the CURRENT key: the only way here is a
            # hand-edited or half-migrated state file. Never repaint it.
            return OAuthHealthReading(
                status="unknown",
                health=health,
                last_check_iso=last_check_iso,
                metadata={
                    "reason": f"retired day-ladder value in last_oauth_health: {health}"
                },
            )

        color, reason = _HEALTH_TO_COLOR.get(
            health, ("unknown", f"unknown verdict: {health}")
        )
        return OAuthHealthReading(
            status=color,
            health=health,
            last_check_iso=last_check_iso,
            metadata={"reason": reason},
        )
