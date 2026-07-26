"""E33 guarantee-scan kill switch — three-state resolution.

The scanner ships blocked-by-default, which is correct. What was NOT correct
is that a *missing* switch row and a *deliberately disabled* switch were
indistinguishable: both blocked, both logged the same "awaiting owner
approval", and the endpoint answered the same reason. That is the shape that
let the organ ship un-armed and stay invisible (superscar #2, esiste != armato).

Guilt: an absent row must be reported as UNPROVISIONED, distinctly.
Innocence: an explicitly disabled switch must still read as a recorded
decision, and near-miss values must never arm the scan.
"""

from __future__ import annotations

import pytest

from backend.services.crm.e33_guarantee_scanner import (
    ScanSwitchState,
    is_scan_enabled,
    resolve_scan_switch,
)


def _pool(row: dict[str, str] | None):
    """Minimal asyncpg-pool double returning ``row`` from ``fetchrow``."""

    class _Pool:
        def acquire(self):
            class _Cm:
                async def __aenter__(self_inner):
                    class _Conn:
                        async def fetchrow(self_conn, sql, *args):
                            assert "system_settings" in sql
                            assert args == ("e33_guarantee_scan_enabled",)
                            return row

                    return _Conn()

                async def __aexit__(self_inner, *exc):
                    return False

            return _Cm()

    return _Pool()


@pytest.mark.asyncio
async def test_absent_row_is_unprovisioned_not_disabled():
    """GUILT: no row at all is the un-armed state, and says so."""
    state = await resolve_scan_switch(_pool(None))

    assert state is ScanSwitchState.UNPROVISIONED
    assert state is not ScanSwitchState.DISABLED
    assert state.is_enabled is False


@pytest.mark.asyncio
async def test_explicit_false_is_disabled_not_unprovisioned():
    """INNOCENCE: a recorded 'false' is a decision, not a missing arming step."""
    state = await resolve_scan_switch(_pool({"value": "false"}))

    assert state is ScanSwitchState.DISABLED
    assert state is not ScanSwitchState.UNPROVISIONED
    assert state.is_enabled is False


@pytest.mark.asyncio
async def test_true_arms_the_scan():
    state = await resolve_scan_switch(_pool({"value": "true"}))

    assert state is ScanSwitchState.ENABLED
    assert state.is_enabled is True


@pytest.mark.parametrize("value", ["True", "TRUE", " true", "true ", "1", "yes", ""])
@pytest.mark.asyncio
async def test_near_miss_values_never_arm_the_scan(value: str):
    """Fail-closed: only the exact string 'true' enables — unchanged behaviour."""
    state = await resolve_scan_switch(_pool({"value": value}))

    assert state is ScanSwitchState.DISABLED
    assert state.is_enabled is False


@pytest.mark.parametrize(
    ("row", "expected"),
    [(None, False), ({"value": "false"}, False), ({"value": "true"}, True)],
)
@pytest.mark.asyncio
async def test_boolean_view_matches_resolved_state(row, expected):
    """`is_scan_enabled` stays a faithful thin view over the three-state resolver."""
    assert await is_scan_enabled(_pool(row)) is expected
    assert (await resolve_scan_switch(_pool(row))).is_enabled is expected
