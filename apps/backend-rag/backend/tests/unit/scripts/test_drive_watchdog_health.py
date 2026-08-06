"""A corpus can pin a model the data can never express.

This file used to be `test_drive_watchdog_tiers.py`: 38 green assertions over
`classify_tier(60)`, `classify_tier(30)`, `classify_tier(14)`, `classify_tier(-1)`
and their boundaries. Every one of them passed, for two years, about a ladder
that could not fire truthfully — because it classified
`google_drive_tokens.expires_at` on a **day** scale, and that column is the
**one-hour access token**:

    google_drive_service.py:163   expires_at = now + expires_in (3600)
    google_drive_service.py:230   refresh when expires_at <= now + 5min

Measured on the live production table, 2026-08-06, both rows:

    SYSTEM      updated_at 2026-06-15 17:24:19   expires_at 18:24:18
    7dfe56b2…   updated_at 2026-08-06 11:11:20   expires_at 12:11:19

`expires_at - updated_at == 1h`, always. So `days_left` is 0 for a credential
refreshed one minute ago and negative for every idle row: TIER_30, TIER_14 and
TIER_7 were unreachable BY CONSTRUCTION, and the only two outcomes the ladder
could produce were "🚨 scade DOMANI" about a healthy credential and
"🔴 SCADUTO" about one nobody had used that day.

The corpus never noticed because it only ever fed a pure function numbers that
a human had invented. It tested that `classify_tier` implements the ladder —
faithfully — and never once that the ladder describes the table. Same shape as
W114: two copies of one assumption confirming each other is not evidence.

So the tests below do the thing the old ones structurally could not: they judge
the ROW SHAPES the table actually produces. The pure-function tests that remain
are anchored to those shapes, not to invented day counts.

    GUILT      — a row that cannot renew itself is a real, nameable failure
    GUILT      — no rows at all is a different failure with a different remedy
    INNOCENCE  — both live shapes (just-refreshed, idle-for-weeks) are SILENT
    INNOCENCE  — the SYSTEM row, unrefreshed on purpose since 2026-05-10, is
                 not an alarm
    LIMIT      — the declared blind spot is asserted, so nobody re-derives a
                 countdown from `updated_at` and calls it an expiry
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from scripts.drive_token_watchdog import (
    HEALTH_NO_REFRESH,
    HEALTH_NO_ROWS,
    HEALTH_OK,
    _age_text,
    classify_oauth_health,
    parse_expires_at,
    should_alert,
)

NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc)


def _row(user_id: str, *, has_refresh: bool = True, refreshed_ago: timedelta):
    """A row in the shape the fly side prints, with the 1h coupling the live
    table always shows: expires_at is updated_at + one hour, never more."""
    updated = NOW - refreshed_ago
    return {
        "user_id": user_id,
        "has_refresh": has_refresh,
        "updated_at": updated.strftime("%Y-%m-%d %H:%M:%S+00"),
        "expires_at": (updated + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S+00"),
    }


# ------------------------------------------------------------------- guilt
def test_a_row_that_cannot_renew_itself_is_the_real_failure():
    """`get_valid_token` returns None forever for a row with no refresh_token,
    and no amount of waiting fixes it. This is what a Drive P0 actually is."""
    health = classify_oauth_health(
        [_row("SYSTEM", has_refresh=False, refreshed_ago=timedelta(days=3))]
    )
    assert health.verdict == HEALTH_NO_REFRESH
    assert "SYSTEM" in health.message, "the message must name WHICH row is dead"
    assert "settings/integrations" in health.message, "and how to fix it"


def test_an_empty_table_is_a_different_failure_with_a_different_remedy():
    health = classify_oauth_health([])
    assert health.verdict == HEALTH_NO_ROWS
    assert health.verdict != HEALTH_NO_REFRESH, (
        "folding the two together would send one dedup key for two facts, and "
        "the gateway ladder would swallow the second"
    )


def test_one_broken_row_among_healthy_ones_still_speaks():
    """The table has more than one row and they fail independently — the old
    query read exactly one, `ORDER BY created_at DESC LIMIT 1`, so a dead
    SYSTEM row hid behind a healthy per-user row that happened to be newer."""
    health = classify_oauth_health(
        [
            _row("SYSTEM", has_refresh=False, refreshed_ago=timedelta(days=52)),
            _row("7dfe56b2", refreshed_ago=timedelta(minutes=1)),
        ]
    )
    assert health.verdict == HEALTH_NO_REFRESH
    assert "SYSTEM" in health.message
    assert "7dfe56b2" not in health.message, "the healthy row must not be accused"


# --------------------------------------------------------------- innocence
@pytest.mark.parametrize(
    "label,ago",
    [
        ("just refreshed", timedelta(minutes=1)),
        ("idle twelve days", timedelta(days=12)),
        ("idle since June", timedelta(days=52)),
    ],
)
def test_every_live_shape_with_a_refresh_token_is_silent(label, ago):
    """THE regression this file exists for.

    Under the old ladder: `just refreshed` → days_left 0 → "🚨 scade DOMANI",
    CRITICAL; both idle shapes → negative → "🔴 SCADUTO". Three false alarms,
    covering literally every state the table can be in.
    """
    health = classify_oauth_health([_row("SYSTEM", refreshed_ago=ago)])
    assert health.verdict == HEALTH_OK, f"{label} raised {health.verdict}"
    assert health.message == "", f"{label} produced an alert body: {health.message}"


def test_the_deliberately_unrefreshed_system_row_is_not_an_alarm():
    """`_refresh_token` early-returns for SYSTEM since 2026-05-10 — Drive runs
    on ServiceAccountDriveService and that row is left stale ON PURPOSE. Any
    staleness rule over `updated_at` would fire on it every six hours."""
    health = classify_oauth_health([_row("SYSTEM", refreshed_ago=timedelta(days=52))])
    assert health.verdict == HEALTH_OK


# ------------------------------------------------------------------- limit
def test_the_age_is_context_and_never_a_verdict():
    """The declared blind spot: `updated_at` age cannot separate "unused" from
    "refresh is failing". It appears in the detail line so a human reading the
    log has it, and nowhere else — a threshold on it would rebuild the same
    false positive one field to the left."""
    fresh = classify_oauth_health([_row("SYSTEM", refreshed_ago=timedelta(minutes=1))])
    stale = classify_oauth_health([_row("SYSTEM", refreshed_ago=timedelta(days=52))])

    assert fresh.verdict == stale.verdict == HEALTH_OK
    assert fresh.detail != stale.detail, "the age must still be VISIBLE in the log"
    assert fresh.message == stale.message == ""


def test_age_text_never_raises_on_junk():
    """It feeds a log line. A watchdog must not die describing itself."""
    assert _age_text(None) == "?"
    assert _age_text("") == "?"
    assert _age_text("not a timestamp") == "?"
    assert _age_text(12345) == "?"
    assert _age_text("2026-08-06 11:00:00+00", now_utc=NOW) == "1h fa"
    assert _age_text("2026-07-25 12:00:00+00", now_utc=NOW) == "12g fa"


# ---------------------------------------------------------------- ratchet
def test_should_alert_speaks_once_per_distinct_failure():
    assert should_alert(HEALTH_NO_REFRESH, None) is True, "first time ever"
    assert should_alert(HEALTH_NO_REFRESH, HEALTH_OK) is True, "newly broken"
    assert should_alert(HEALTH_NO_REFRESH, HEALTH_NO_REFRESH) is False, "repeat"
    assert should_alert(HEALTH_NO_REFRESH, HEALTH_NO_ROWS) is True, (
        "a CHANGED failure is different news with a different remedy"
    )


def test_should_alert_is_silent_on_recovery():
    """Recovery is not news, and — more importantly — an alert on it would be
    delivered through the same key as the failure and reset nothing."""
    assert should_alert(HEALTH_OK, HEALTH_NO_REFRESH) is False
    assert should_alert(HEALTH_OK, None) is False


# ---------------------------------------------------------------- parsing
def test_parse_expires_at_handles_both_wire_forms():
    """asyncpg stringifies with an offset; some paths hand back a naive value.
    Neither may be read as a local time."""
    assert parse_expires_at("2026-08-06 12:11:19+00:00").tzinfo is not None
    assert parse_expires_at("2026-08-06T12:11:19Z") == datetime(
        2026, 8, 6, 12, 11, 19, tzinfo=timezone.utc
    )
    assert parse_expires_at("2026-08-06 12:11:19") == datetime(
        2026, 8, 6, 12, 11, 19, tzinfo=timezone.utc
    )
