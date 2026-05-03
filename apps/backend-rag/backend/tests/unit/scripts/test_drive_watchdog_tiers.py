"""Tests for the tiered alert system in scripts/drive_token_watchdog.py.

Covers:
    - classify_tier() at each boundary (60, 30, 14, 7, 1, 0, -1 days)
    - should_alert() idempotency (no spam, escalation, de-escalation)
    - render_alert_text() formatting
    - parse_expires_at() / compute_days_left() roundtrip

The watchdog itself is not invoked here — only the pure functions. The
fly-ssh + Telegram I/O paths are integration-tested elsewhere (manual
QA on Air during deploy).

P1-11 reference: docs/audits/2026-04-29-zero-crash-audit/02_opus_analysis.md
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from scripts.drive_token_watchdog import (
    TIER_14_DAYS,
    TIER_1_DAY,
    TIER_30_DAYS,
    TIER_7_DAYS,
    TIER_EXPIRED,
    TIER_OK,
    TIER_SEVERITY,
    classify_tier,
    compute_days_left,
    parse_expires_at,
    render_alert_text,
    should_alert,
)


# ---------------------------------------------------------------------------
# classify_tier — tier-by-tier
# ---------------------------------------------------------------------------

class TestClassifyTier:
    """Each tier fires at the documented boundary."""

    def test_60_days_returns_ok(self) -> None:
        alert = classify_tier(60)
        assert alert.tier == TIER_OK
        assert alert.severity_label == "OK"
        assert alert.message_template == ""  # no message when OK

    def test_31_days_returns_ok(self) -> None:
        # Just above 30-day threshold — still OK
        assert classify_tier(31).tier == TIER_OK

    def test_30_days_returns_info(self) -> None:
        alert = classify_tier(30)
        assert alert.tier == TIER_30_DAYS
        assert alert.severity_label == "INFO"
        assert "🔵" in alert.emoji or alert.emoji == "🔵"

    def test_15_days_returns_info(self) -> None:
        # Within 30-day window, above 14-day → still info
        assert classify_tier(15).tier == TIER_30_DAYS

    def test_14_days_returns_warning(self) -> None:
        alert = classify_tier(14)
        assert alert.tier == TIER_14_DAYS
        assert alert.severity_label == "WARNING"

    def test_8_days_returns_warning(self) -> None:
        # Above 7-day threshold, within 14 → still warning
        assert classify_tier(8).tier == TIER_14_DAYS

    def test_7_days_returns_urgent(self) -> None:
        alert = classify_tier(7)
        assert alert.tier == TIER_7_DAYS
        assert alert.severity_label == "URGENT"

    def test_2_days_returns_urgent(self) -> None:
        # Above 1-day, within 7 → still urgent
        assert classify_tier(2).tier == TIER_7_DAYS

    def test_1_day_returns_critical(self) -> None:
        alert = classify_tier(1)
        assert alert.tier == TIER_1_DAY
        assert alert.severity_label == "CRITICAL"

    def test_0_days_returns_critical_1d(self) -> None:
        # Edge: 0 days = expires today. Treated as critical_1d (still positive).
        assert classify_tier(0).tier == TIER_1_DAY

    def test_negative_1_returns_expired(self) -> None:
        alert = classify_tier(-1)
        assert alert.tier == TIER_EXPIRED
        assert "EXPIRED" in alert.severity_label

    def test_negative_30_returns_expired(self) -> None:
        # Long-expired token still classified as expired (no separate tier).
        assert classify_tier(-30).tier == TIER_EXPIRED


# ---------------------------------------------------------------------------
# render_alert_text — formatting
# ---------------------------------------------------------------------------

class TestRenderAlertText:
    def test_render_30_day_message_includes_days(self) -> None:
        text = render_alert_text(classify_tier(25))
        assert "25" in text
        assert "Drive OAuth" in text

    def test_render_expired_message_uses_abs_days(self) -> None:
        # -3 days → message says "3 giorni fa"
        text = render_alert_text(classify_tier(-3))
        assert "3 giorni fa" in text
        assert "SCADUTO" in text

    def test_render_1_day_message_says_domani(self) -> None:
        text = render_alert_text(classify_tier(1))
        assert "DOMANI" in text


# ---------------------------------------------------------------------------
# should_alert — idempotency
# ---------------------------------------------------------------------------

class TestShouldAlert:
    """The state-file logic that prevents Telegram spam."""

    def test_first_time_30_day_alerts(self) -> None:
        # Cron runs first time, token at 28 days → alert.
        assert should_alert(TIER_30_DAYS, last_tier=None) is True

    def test_first_time_after_ok_alerts(self) -> None:
        # Last run was OK, now crossed into 30d window → alert.
        assert should_alert(TIER_30_DAYS, last_tier=TIER_OK) is True

    def test_same_tier_does_not_re_alert(self) -> None:
        # Cron runs again, still in 30-day window → silent.
        assert should_alert(TIER_30_DAYS, last_tier=TIER_30_DAYS) is False

    def test_escalation_30_to_14_alerts(self) -> None:
        # Token aged: was in info window, now in warning → alert.
        assert should_alert(TIER_14_DAYS, last_tier=TIER_30_DAYS) is True

    def test_escalation_14_to_7_alerts(self) -> None:
        assert should_alert(TIER_7_DAYS, last_tier=TIER_14_DAYS) is True

    def test_escalation_7_to_1_alerts(self) -> None:
        assert should_alert(TIER_1_DAY, last_tier=TIER_7_DAYS) is True

    def test_escalation_1_to_expired_alerts(self) -> None:
        assert should_alert(TIER_EXPIRED, last_tier=TIER_1_DAY) is True

    def test_de_escalation_after_reauth_silent(self) -> None:
        # User re-authed: was at urgent_7d, now back to OK → no alert.
        assert should_alert(TIER_OK, last_tier=TIER_7_DAYS) is False

    def test_de_escalation_to_lower_tier_silent(self) -> None:
        # Was warning (14d), but token got refreshed and now we're at info (30d).
        # Don't alert — the user already saw the warning, and this is improvement.
        assert should_alert(TIER_30_DAYS, last_tier=TIER_14_DAYS) is False

    def test_ok_to_ok_silent(self) -> None:
        assert should_alert(TIER_OK, last_tier=TIER_OK) is False

    def test_severity_table_is_strictly_monotonic(self) -> None:
        """Sanity: tiers ordered correctly from least to most urgent."""
        order = [TIER_OK, TIER_30_DAYS, TIER_14_DAYS, TIER_7_DAYS, TIER_1_DAY, TIER_EXPIRED]
        sev = [TIER_SEVERITY[t] for t in order]
        assert sev == sorted(sev), "TIER_SEVERITY must be monotonic"
        assert len(set(sev)) == len(sev), "TIER_SEVERITY must be unique"


# ---------------------------------------------------------------------------
# parse_expires_at + compute_days_left — date math
# ---------------------------------------------------------------------------

class TestDateMath:
    def test_parse_iso_with_tz(self) -> None:
        dt = parse_expires_at("2026-08-01T12:00:00+00:00")
        assert dt.tzinfo is not None
        assert dt.year == 2026 and dt.month == 8

    def test_parse_iso_with_z_suffix(self) -> None:
        dt = parse_expires_at("2026-08-01T12:00:00Z")
        assert dt.tzinfo is not None

    def test_parse_naive_assumed_utc(self) -> None:
        dt = parse_expires_at("2026-08-01 12:00:00")
        assert dt.tzinfo is timezone.utc

    def test_compute_days_left_future(self) -> None:
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        # 30 days later
        expires = now + timedelta(days=30)
        assert compute_days_left(expires, now) == 30

    def test_compute_days_left_past(self) -> None:
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        # 5 days ago
        expires = now - timedelta(days=5)
        assert compute_days_left(expires, now) == -5


# ---------------------------------------------------------------------------
# End-to-end tier-driven alert simulation (mocked timestamps)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "days,expected_tier",
    [
        (60, TIER_OK),
        (30, TIER_30_DAYS),
        (14, TIER_14_DAYS),
        (7, TIER_7_DAYS),
        (1, TIER_1_DAY),
        (0, TIER_1_DAY),
        (-1, TIER_EXPIRED),
    ],
    ids=["60d_ok", "30d_info", "14d_warn", "7d_urgent", "1d_crit", "0d_crit", "expired"],
)
def test_tier_table_at_thresholds(days: int, expected_tier: str) -> None:
    """Each documented threshold maps to the documented tier."""
    assert classify_tier(days).tier == expected_tier
