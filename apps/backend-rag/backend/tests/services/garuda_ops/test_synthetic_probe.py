"""Bite-proof for `garuda_ops.synthetic_probe`.

Two things under test: (1) the one stage that IS live today
(`EligibilityVerdictStage`) really runs the real engine and really fails if
the engine regresses; (2) the runner's honesty property — it must report
`all_succeeded=False` today, because stages 2-5 are genuinely blocked on
L1/L3/L4, and it must stop at the first non-success rather than attempting
stages whose preconditions were never met.
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.services.garuda_flow import pricing as pricing_module
from backend.services.garuda_flow.civil_clock import garuda_today
from backend.services.garuda_flow.freshness import FreshnessReport, FreshnessVerdict
from backend.services.garuda_ops.synthetic_probe import (
    DEFAULT_STAGES,
    EligibilityVerdictStage,
    ProbeStageStatus,
    run_probe,
)

_TODAY = garuda_today()

# `pricing.price_catalogue_freshness` gates on the REAL catalogue's
# `metadata.last_updated` stamp, measured against actual wall-clock `today`
# (SM-G05, fail-closed-by-design — see `pricing.py:price_for_case`). At the
# time this lane was built the catalogue was genuinely stale (111d vs a
# 90d max) — a real, independent finding reported in the PR, not a bug in
# this test. Monkeypatching this one function is the documented seam
# (`pricing.py`'s own docstring: "named ... so it can be monkeypatched
# independently") to make the STAGE's classification logic deterministic
# and future-proof against that catalogue's freshness changing underneath
# an unrelated test run.


def _force_fresh_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pricing_module,
        "price_catalogue_freshness",
        # `**_` absorbs `key`/`row`: `price_catalogue_freshness` grew per-row
        # attestation kwargs (owner decision 7, `verified_on`) after this helper
        # was written, and `price_for_case` now always calls it with `key=`/`row=`.
        # Matches the same absorption in
        # `backend/tests/services/garuda_flow/conftest.py`.
        lambda *, today, service=None, **_: FreshnessReport(
            source="price_catalogue",
            verdict=FreshnessVerdict.FRESH,
            stamp=today.isoformat(),
            age_days=0,
            max_age_days=90,
            detail="forced fresh for test determinism",
        ),
    )


@pytest.mark.asyncio
async def test_eligibility_stage_succeeds_when_catalogue_is_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_fresh_catalogue(monkeypatch)
    result = await EligibilityVerdictStage().run(today=_TODAY)
    assert result.status is ProbeStageStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_full_probe_today_is_honestly_incomplete_not_falsely_green(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bite: with today's DEFAULT_STAGES, `all_succeeded` MUST be False
    — a probe that reported success here while L1/L3/L4 don't exist would
    be exactly the 'esiste != armato' failure this lane exists to refuse."""
    _force_fresh_catalogue(monkeypatch)
    result = await run_probe(DEFAULT_STAGES, today=_TODAY)
    assert not result.all_succeeded
    first_blocked = result.first_non_success
    assert first_blocked is not None
    assert first_blocked.status is ProbeStageStatus.BLOCKED
    assert first_blocked.name == "persistence_policy"
    # Stage 1 ran and succeeded before the blocked one; later stages never
    # ran at all (the runner stops, per SYN-01's "one signed result binds
    # ALL stage outcomes").
    assert result.stage_results[0].status is ProbeStageStatus.SUCCEEDED
    assert len(result.stage_results) == 2


@pytest.mark.asyncio
async def test_full_probe_reports_price_unresolvable_as_failed_when_catalogue_is_stale() -> None:
    """Companion to the two tests above, run against REAL (unpatched)
    catalogue state: whatever that state is today, the probe must classify
    it correctly — SUCCEEDED if fresh, FAILED (not a silent pass, not an
    uncaught exception) if stale. Either outcome is a valid bite here; an
    exception escaping is not."""
    result = await EligibilityVerdictStage().run(today=_TODAY)
    assert result.status in (ProbeStageStatus.SUCCEEDED, ProbeStageStatus.FAILED)


@pytest.mark.asyncio
async def test_stage_reports_failed_when_the_synthetic_fixture_is_declined() -> None:
    """RED-if-broken: `EligibilityVerdictStage` must report FAILED (not
    SUCCEEDED, not an exception) if its known-ACCEPT fixture is ever
    declined by the engine — proving the stage actually inspects the
    outcome rather than treating any non-crashing call as success. We break
    it here by monkeypatching the fixture builder to an expired passport,
    which `eligibility.screen` must decline."""
    import backend.services.garuda_ops.synthetic_probe as probe_module

    def _expired_passport_fixture(today: date) -> tuple[date, date, date | None]:
        return today, date(today.year - 5, 1, 1), None

    original = probe_module._synthetic_entry_and_expiry
    probe_module._synthetic_entry_and_expiry = _expired_passport_fixture
    try:
        result = await EligibilityVerdictStage().run(today=_TODAY)
    finally:
        probe_module._synthetic_entry_and_expiry = original

    assert result.status is ProbeStageStatus.FAILED
    assert "declined" in result.detail
