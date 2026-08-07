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
    GUILT      — a row FROZEN for 3+ days is reported: refresh is lazy-on-use,
                 so `updated_at` advancing is a consumer succeeding, and when
                 7dfe56b2's refresh token was revoked the column simply stopped
                 moving for twelve days while GARUDA logged `invalid_grant`
                 nightly. A revoked token still has `refresh_token IS NOT
                 NULL`, so the P0 cannot see it; the freeze can.
    INNOCENCE  — a recently-refreshed row is SILENT, at every age inside the
                 window — that is the false CRITICAL this file exists for
    INNOCENCE  — the SYSTEM row, frozen on purpose since 2026-05-10, is never
                 called stale
    INNOCENCE  — an unreadable timestamp is not staleness
    PRECEDENCE — a dead credential outranks a frozen one, or a real outage
                 goes out at digest tier
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from scripts.drive_token_watchdog import (
    HEALTH_NO_REFRESH,
    HEALTH_NO_ROWS,
    HEALTH_OK,
    HEALTH_STALE_REFRESH,
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
        ("refreshed yesterday", timedelta(days=1)),
        ("just inside the window", timedelta(days=2, hours=23)),
    ],
)
def test_a_recently_refreshed_row_is_silent(label, ago):
    """THE regression this file exists for.

    Under the old ladder every one of these is an alarm: `just refreshed` →
    days_left 0 → "🚨 scade DOMANI" CRITICAL, and the other two → negative →
    "🔴 SCADUTO". Three false alarms over a credential that is working.
    """
    health = classify_oauth_health([_row("7dfe56b2", refreshed_ago=ago)], now_utc=NOW)
    assert health.verdict == HEALTH_OK, f"{label} raised {health.verdict}"
    assert health.message == "", f"{label} produced an alert body: {health.message}"


def test_the_deliberately_unrefreshed_system_row_is_not_stale():
    """`_refresh_token` early-returns for SYSTEM since 2026-05-10 — Drive runs
    on ServiceAccountDriveService and that row is left frozen ON PURPOSE
    (2026-06-15 and counting). The staleness rule must exclude it by ENTITY,
    or it fires every six hours forever about the intended state."""
    health = classify_oauth_health(
        [_row("SYSTEM", refreshed_ago=timedelta(days=52))], now_utc=NOW
    )
    assert health.verdict == HEALTH_OK


# --------------------------------------------------------------- staleness
def test_a_frozen_row_is_reported():
    """The signal that would have caught the real outage.

    Refresh is lazy-on-use, so `updated_at` advancing is a consumer
    succeeding. Row 7dfe56b2 froze at 2026-07-25 19:02 when its refresh token
    was revoked and stayed frozen twelve days while GARUDA collected
    `invalid_grant` nightly. A revoked token still has `refresh_token IS NOT
    NULL`, so the P0 above is blind to it — the freeze is not.
    """
    health = classify_oauth_health(
        [_row("7dfe56b2", refreshed_ago=timedelta(days=12))], now_utc=NOW
    )
    assert health.verdict == HEALTH_STALE_REFRESH
    assert "7dfe56b2" in health.message
    assert "invalid_grant" in health.message, (
        "the note must point at where the PROOF is — this verdict alone cannot "
        "tell a revoked credential from an unused one"
    )


def test_the_boundary_is_the_stated_threshold():
    """Just inside is silent, just outside speaks. Pinned because the value is
    derived from something real — three missed runs of a daily consumer — and
    a future edit that drifts it should have to say so here."""
    from scripts.drive_token_watchdog import STALE_REFRESH_DAYS

    inside = timedelta(days=STALE_REFRESH_DAYS, hours=-1)
    outside = timedelta(days=STALE_REFRESH_DAYS, hours=1)
    assert (
        classify_oauth_health([_row("u", refreshed_ago=inside)], now_utc=NOW).verdict
        == HEALTH_OK
    )
    assert (
        classify_oauth_health([_row("u", refreshed_ago=outside)], now_utc=NOW).verdict
        == HEALTH_STALE_REFRESH
    )


def test_an_unreadable_timestamp_is_not_staleness():
    """"I could not read it" is not "it is old". Treating an unparseable
    `updated_at` as stale would put a recurring digest note on a healthy row,
    which is the false-positive family this whole change exists to end."""
    row = _row("u", refreshed_ago=timedelta(minutes=1))
    row["updated_at"] = "not a timestamp"
    health = classify_oauth_health([row], now_utc=NOW)
    assert health.verdict == HEALTH_OK
    assert "?" in health.detail, "the unreadable field must still be VISIBLE"


def test_a_dead_credential_outranks_a_stale_one():
    """Precedence: a row that can never renew is actionable now; a frozen one
    is a hint. If both are true of the same table the message must be the P0,
    or a real outage goes out at digest tier."""
    health = classify_oauth_health(
        [_row("u", has_refresh=False, refreshed_ago=timedelta(days=12))], now_utc=NOW
    )
    assert health.verdict == HEALTH_NO_REFRESH


# ------------------------------------------------------------------- limit
def test_the_age_is_always_visible_in_the_detail_line():
    """Whatever the verdict, a human reading the log gets the ages — the
    verdict is a summary, and this organ has already been wrong once about
    what a column means."""
    fresh = classify_oauth_health(
        [_row("u", refreshed_ago=timedelta(minutes=1))], now_utc=NOW
    )
    stale = classify_oauth_health(
        [_row("u", refreshed_ago=timedelta(days=12))], now_utc=NOW
    )
    assert fresh.detail != stale.detail
    assert "12g" in stale.detail, stale.detail
    assert fresh.message == ""


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
