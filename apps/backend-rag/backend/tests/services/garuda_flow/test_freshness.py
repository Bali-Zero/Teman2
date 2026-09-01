"""Tests for the truth-freshness authority (G-FRESHNESS-FAIL-CLOSED, `freshness.py`).

Every guard here is proven to bite: each mechanism test below exercises BOTH
sides of the boundary it names (the literal red a broken guard would produce
IS the STALE-when-it-should-be-FRESH / FRESH-when-it-should-be-STALE case;
the literal green is the correct verdict on each side).

This file deliberately does NOT assert the real catalogue's, the real
nationality list's, or the real rule bundle's CURRENT freshness state
relative to the real wall clock — such an assertion passes today and goes
red the day someone re-stamps the file, training people to edit the test
instead of the data. `freshness_report.py` is the read-only diagnostic for
"what is the real state right now"; this file tests the MECHANISM with
injected/synthetic stamps and dates only.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.services.garuda_flow import freshness
from backend.services.garuda_flow.constants import RULES_VERIFIED_ON
from backend.services.garuda_flow.nationality_eligibility import RETRIEVED_ON

_SOURCE = "test_source"
_MAX_AGE = 90
_STAMP_DATE = date(2026, 1, 1)
_STAMP_STR = _STAMP_DATE.isoformat()


def _check(*, stamp: object, today: date, max_age_days: int = _MAX_AGE) -> freshness.FreshnessReport:
    return freshness.check_freshness(
        source=_SOURCE,
        stamp_accessor=lambda: stamp,
        max_age_days=max_age_days,
        today=today,
    )


class TestBoundary:
    """`today - stamp > max_age_days` — strict greater-than.

    A source re-verified on day 0 stays FRESH through the entire window and
    only goes STALE the day after — never on the boundary day itself.
    """

    def test_age_exactly_at_the_window_is_fresh(self) -> None:
        today = date(2026, 4, 1)  # exactly 90 days after 2026-01-01
        assert (today - _STAMP_DATE).days == _MAX_AGE
        report = _check(stamp=_STAMP_STR, today=today)
        assert report.verdict is freshness.FreshnessVerdict.FRESH
        assert not report.stale
        assert report.age_days == _MAX_AGE

    def test_one_day_past_the_window_is_stale(self) -> None:
        today = date(2026, 4, 2)  # 91 days after 2026-01-01
        assert (today - _STAMP_DATE).days == _MAX_AGE + 1
        report = _check(stamp=_STAMP_STR, today=today)
        assert report.verdict is freshness.FreshnessVerdict.STALE
        assert report.stale
        assert report.age_days == _MAX_AGE + 1

    def test_one_day_before_the_window_boundary_is_fresh(self) -> None:
        today = date(2026, 3, 31)  # 89 days after 2026-01-01
        report = _check(stamp=_STAMP_STR, today=today)
        assert not report.stale

    def test_verified_today_is_fresh(self) -> None:
        report = _check(stamp=_STAMP_STR, today=_STAMP_DATE)
        assert not report.stale
        assert report.age_days == 0


class TestFailClosedOnAbsenceAndGarbage:
    """Missing, malformed, or exception-raising stamps must ALL read STALE —
    "I could not tell" must never read as "fine"."""

    def test_missing_stamp_is_stale(self) -> None:
        report = _check(stamp=None, today=date(2026, 1, 2))
        assert report.stale
        assert report.age_days is None
        assert "missing" in report.detail

    def test_non_string_stamp_is_stale(self) -> None:
        report = _check(stamp=20260101, today=date(2026, 1, 2))
        assert report.stale
        assert report.age_days is None

    def test_malformed_iso_string_is_stale(self) -> None:
        report = _check(stamp="not-a-date", today=date(2026, 1, 2))
        assert report.stale
        assert report.age_days is None

    def test_wrong_format_date_string_is_stale(self) -> None:
        report = _check(stamp="01/01/2026", today=date(2026, 1, 2))
        assert report.stale

    def test_accessor_that_raises_is_stale_not_propagated(self) -> None:
        def _boom() -> object:
            raise RuntimeError("catalogue unreadable")

        report = freshness.check_freshness(
            source=_SOURCE,
            stamp_accessor=_boom,
            max_age_days=_MAX_AGE,
            today=date(2026, 1, 2),
        )
        assert report.stale
        assert report.stamp is None
        assert "RuntimeError" in report.detail

    def test_a_future_stamp_reads_as_fresh_not_as_an_error(self) -> None:
        """Design decision (see freshness.py module docstring): a stamp
        dated after ``today`` cannot happen in real production traffic
        (`civil_clock.garuda_today()` only advances), but does happen
        routinely in this engine's own test fixtures that fix a historical
        ``today``. The plain arithmetic comparison is used as-is rather than
        inventing a third state for it."""
        today = date(2025, 6, 1)
        report = _check(stamp=_STAMP_STR, today=today)
        assert (today - _STAMP_DATE).days < 0
        assert not report.stale


class TestRegistryWiring:
    """The two convenience readers wire to the REAL module constants — but
    the ``today`` used here is synthetic and chosen relative to those fixed
    constants, never the real wall clock, so this never asserts "the real
    current state".

    ``conftest.py``'s autouse fixture pins both readers to a canned FRESH
    report for every other file's engine tests (so a real stamp aging past
    its window can't flip an unrelated ACCEPT/DECLINE assertion elsewhere
    out from under it) — that fixture also applies here since this file
    lives in the same package, so every test below starts with
    ``monkeypatch.undo()`` to reach the REAL functions this class exists to
    test.
    """

    def test_nationality_eligibility_freshness_reads_the_real_stamp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        stamp_date = date.fromisoformat(RETRIEVED_ON)
        fresh = freshness.nationality_eligibility_freshness(today=stamp_date)
        assert fresh.stamp == RETRIEVED_ON
        assert fresh.max_age_days == freshness.MAX_AGE_DAYS["nationality_eligibility"]
        assert not fresh.stale

    def test_nationality_eligibility_freshness_goes_stale_past_its_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        from datetime import timedelta

        stamp_date = date.fromisoformat(RETRIEVED_ON)
        window = freshness.MAX_AGE_DAYS["nationality_eligibility"]
        stale = freshness.nationality_eligibility_freshness(
            today=stamp_date + timedelta(days=window + 1)
        )
        assert stale.stale

    def test_rule_constants_freshness_reads_the_real_stamp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        stamp_date = date.fromisoformat(RULES_VERIFIED_ON)
        fresh = freshness.rule_constants_freshness(today=stamp_date)
        assert fresh.stamp == RULES_VERIFIED_ON
        assert fresh.max_age_days == freshness.MAX_AGE_DAYS["rule_constants"]
        assert not fresh.stale

    def test_rule_constants_freshness_goes_stale_past_its_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        from datetime import timedelta

        stamp_date = date.fromisoformat(RULES_VERIFIED_ON)
        window = freshness.MAX_AGE_DAYS["rule_constants"]
        stale = freshness.rule_constants_freshness(today=stamp_date + timedelta(days=window + 1))
        assert stale.stale


def _repo_root() -> Path:
    """Find the worktree root without depending on pytest's current directory
    (same pattern as `test_preview_adapter_parity.py::_repo_root`)."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    raise AssertionError("repository root: no parent containing .git")


def test_freshness_windows_match_the_frozen_contract() -> None:
    """`freshness.MAX_AGE_DAYS` is the single source of truth in Python;
    `contracts/openapi.yaml`'s `x-truth-freshness-max-age-days` mirrors it.
    This pins the two together so they cannot silently drift in either
    direction — the contract is read here, never touched."""
    yaml = pytest.importorskip("yaml")
    contract_path = _repo_root() / "products/garuda-voa/contracts/openapi.yaml"
    assert contract_path.is_file(), f"contract missing: {contract_path}"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    contract_windows = contract["x-truth-freshness-max-age-days"]

    assert contract_windows == freshness.MAX_AGE_DAYS, (
        "freshness.MAX_AGE_DAYS has drifted from "
        "contracts/openapi.yaml's x-truth-freshness-max-age-days — the contract is "
        "frozen (orchestrator-only); fix the Python side to match it, never the "
        "other way around from this lane."
    )
