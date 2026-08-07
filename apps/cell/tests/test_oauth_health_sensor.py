"""Tests for OAuthHealthSensor — the Cell's view of the Drive credential.

The sensor consumes the JSON state file written by
`scripts/drive_token_watchdog.py`. We don't run the watchdog here; we write
fixture state files and assert the sensor classifies them correctly.

REWRITTEN 2026-08-06. This corpus used to assert a 30/14/7/1-**day** ladder —
`last_oauth_tier` + `last_oauth_days_left` — mirroring the watchdog's. Both
sides were derived from `google_drive_tokens.expires_at`, which is the
**one-hour access token**, not a 90-day credential clock (measured live:
`expires_at - updated_at == 1h` on every row). So `days_left` was 0 for a
credential refreshed a minute ago and negative for every idle row, and this
sensor would have painted Drive permanently red off a healthy credential.

The old tests could not catch it: they wrote `last_oauth_days_left=60` by hand
and checked the colour that follows from 60. No row in that table has ever
produced a 60. A fixture invented to match the model confirms the model.

    GUILT      — a credential that cannot renew itself is red
    INNOCENCE  — a healthy verdict is green, and staleness still wins over it
    MIGRATION  — a state file from before the change is UNKNOWN, never
                 repainted: its stored verdict was measured on the wrong scale
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cell.sensors.oauth_health_sensor import OAuthHealthSensor

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def _write_state(tmp_path: Path, **kwargs) -> str:
    """Write a watchdog-style state file and return its path."""
    p = tmp_path / "drive_oauth_watchdog.state.json"
    p.write_text(json.dumps(kwargs))
    return str(p)


class TestOAuthHealthSensor:
    def test_missing_state_file_is_unknown(self, tmp_path: Path) -> None:
        sensor = OAuthHealthSensor(state_path=str(tmp_path / "does_not_exist.json"))
        reading = sensor.read()
        assert reading.status == "unknown"
        assert "not found" in reading.metadata["reason"]

    def test_corrupt_state_file_is_unknown(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.json"
        p.write_text("not valid json {{{")
        sensor = OAuthHealthSensor(state_path=str(p))
        reading = sensor.read()
        assert reading.status == "unknown"

    # --------------------------------------------------------------- guilt
    def test_no_refresh_token_is_red(self, tmp_path: Path) -> None:
        """The one genuine Drive P0: the credential can no longer renew itself
        and only a human at the consent screen can fix it."""
        path = _write_state(
            tmp_path,
            last_oauth_health="no-refresh",
            last_oauth_check_iso=NOW.isoformat(),
        )
        reading = OAuthHealthSensor(state_path=path).read(now=NOW)
        assert reading.status == "red"
        assert reading.health == "no-refresh"
        assert "re-auth" in reading.metadata["reason"]

    def test_no_token_row_at_all_is_red(self, tmp_path: Path) -> None:
        path = _write_state(
            tmp_path,
            last_oauth_health="no-token",
            last_oauth_check_iso=NOW.isoformat(),
        )
        reading = OAuthHealthSensor(state_path=path).read(now=NOW)
        assert reading.status == "red"
        assert reading.health == "no-token"

    def test_a_frozen_refresh_is_yellow_not_red(self, tmp_path: Path) -> None:
        """The watchdog's third verdict. Yellow because the table cannot tell
        a revoked credential from an unused one — red would claim more than is
        known, and unknown (the default for an unmapped verdict) would throw
        the signal away entirely. Added with the verdict, not after it: an
        unmapped verdict here is a consumer the producer forgot."""
        path = _write_state(
            tmp_path,
            last_oauth_health="stale-refresh",
            last_oauth_check_iso=NOW.isoformat(),
        )
        reading = OAuthHealthSensor(state_path=path).read(now=NOW)
        assert reading.status == "yellow"
        assert reading.health == "stale-refresh"

    # ----------------------------------------------------------- innocence
    def test_healthy_verdict_is_green(self, tmp_path: Path) -> None:
        path = _write_state(
            tmp_path,
            last_oauth_health="ok",
            last_oauth_check_iso=(NOW - timedelta(hours=6)).isoformat(),
        )
        reading = OAuthHealthSensor(state_path=path).read(now=NOW)
        assert reading.status == "green"
        assert reading.health == "ok"

    def test_stale_state_is_yellow_even_when_the_verdict_is_ok(
        self, tmp_path: Path
    ) -> None:
        """Watchdog last ran 25h ago — past the 18h threshold. Visibility lost
        is distinct from "definitely fine", and it must outrank a cached ok."""
        path = _write_state(
            tmp_path,
            last_oauth_health="ok",
            last_oauth_check_iso=(NOW - timedelta(hours=25)).isoformat(),
        )
        reading = OAuthHealthSensor(state_path=path).read(now=NOW)
        assert reading.status == "yellow"
        assert "stale" in reading.metadata["reason"]

    def test_unknown_verdict_value_returns_unknown(self, tmp_path: Path) -> None:
        path = _write_state(
            tmp_path,
            last_oauth_health="some_future_verdict",
            last_oauth_check_iso=NOW.isoformat(),
        )
        reading = OAuthHealthSensor(state_path=path).read(now=NOW)
        assert reading.status == "unknown"

    # ----------------------------------------------------------- migration
    def test_a_pre_change_state_file_is_unknown_not_red(self, tmp_path: Path) -> None:
        """THE regression that would have shipped.

        Every machine has a state file written by the old watchdog, and the
        live one on Pro reads `critical_expired` / `-12` — recorded off the
        one-hour access token of a row nobody had used in twelve days. Mapped
        through the old table that is a permanent red Drive light. It is not
        evidence of anything: report unknown until the watchdog speaks again.
        """
        path = _write_state(
            tmp_path,
            last_oauth_tier="critical_expired",
            last_oauth_days_left=-12,
            last_oauth_check_iso=NOW.isoformat(),
        )
        reading = OAuthHealthSensor(state_path=path).read(now=NOW)
        assert reading.status == "unknown", (
            "a pre-2026-08-06 verdict was repainted as if it were current"
        )
        assert "critical_expired" in reading.metadata["reason"], (
            "the reason must name what it found, or this looks like a plain "
            "missing-key case and nobody learns why the light went grey"
        )

    def test_a_retired_ladder_value_in_the_current_key_is_never_repainted(
        self, tmp_path: Path
    ) -> None:
        """Belt and braces for a half-migrated or hand-edited file: the old
        vocabulary must not resolve to a colour through the new key either."""
        path = _write_state(
            tmp_path,
            last_oauth_health="critical_expired",
            last_oauth_check_iso=NOW.isoformat(),
        )
        reading = OAuthHealthSensor(state_path=path).read(now=NOW)
        assert reading.status == "unknown"
        assert "retired" in reading.metadata["reason"]

    def test_state_with_no_verdict_yet_is_unknown(self, tmp_path: Path) -> None:
        path = _write_state(tmp_path, last_oauth_check_iso=NOW.isoformat())
        reading = OAuthHealthSensor(state_path=path).read(now=NOW)
        assert reading.status == "unknown"
