"""Tests for `scripts/price_review_sentinel.py`.

Guilt/innocence pairs on the pure classifier, an anti-proxy test that the
sentinel watches the file the LIVE pricing service loads (not a filename typed
twice), a non-vacuity guard so these tests cannot pass against an empty
structure, and a gateway test with a fake `tg_notify.py`.

The non-vacuity guard is not ceremony: a sibling test shipped this month
filtered on a field name that does not exist in the real artifact, matched
nothing, compared nothing against everything, and passed. Any test that
asserts "no X violates Y" must first prove there were X's to check.
"""

from __future__ import annotations

import datetime as dt
import json
import stat
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import price_review_sentinel as prs  # noqa: E402

TODAY = dt.date(2026, 8, 31)


def _sheet(last_updated: str | None, entries: dict | None = None) -> dict:
    metadata: dict = {"currency": "IDR"}
    if last_updated is not None:
        metadata["last_updated"] = last_updated
    return {
        "metadata": metadata,
        "services": {"single_entry_visas": entries or {"X": {"price": 1_000_000}}},
    }


# ---------------------------------------------------------------------------
# Anti-proxy: the sentinel must watch what the live service loads
# ---------------------------------------------------------------------------


def test_sentinel_resolves_the_file_the_live_pricing_service_loads():
    """A sheet renamed to a 2027 edition must not leave this sentinel watching
    a dead file and reporting green. The filename comes from the service."""
    from importlib import import_module

    sys.path.insert(0, str(REPO / "apps" / "backend-rag"))
    service = import_module("backend.services.pricing.pricing_service")

    resolved = prs.resolve_price_sheet()
    assert resolved.name == service._PRICING_FILENAME
    assert resolved.is_file(), f"the live price sheet is not on disk at {resolved}"


def test_the_real_sheet_is_classifiable_and_not_empty():
    """Non-vacuity: the real artifact parses, and it really does carry a large
    body of priced entries, so the assertions below are about something."""
    sheet = json.loads(prs.resolve_price_sheet().read_text(encoding="utf-8"))
    priced = prs.iter_priced_entries(sheet)
    assert len(priced) >= 100, f"priced-entry count collapsed to {len(priced)}"

    verdict = prs.classify(sheet, today=TODAY, git_date=None)
    assert verdict.outcome != prs.OUTCOME_CANNOT_VERIFY, verdict.reason
    assert verdict.priced_entries == len(priced)


# ---------------------------------------------------------------------------
# The core claim: the attestation can prove OVERDUE, never FRESH
# ---------------------------------------------------------------------------


def test_guilt_a_change_after_the_review_date_is_unmaintained_not_fresh():
    """The measured live state on 2026-08-31: the field said 2026-05-06 while
    the file had changed on 2026-08-26. That must never read as a pass."""
    verdict = prs.classify(
        _sheet("2026-05-06"), today=TODAY, git_date=dt.date(2026, 8, 26)
    )
    assert verdict.outcome == prs.OUTCOME_UNMAINTAINED
    assert "2026-08-26" in verdict.reason


def test_guilt_a_recent_review_date_contradicted_by_a_change_is_still_not_ok():
    """The dangerous case: the date is INSIDE the interval, so a naive check
    would report OK — but the file moved after it was written."""
    verdict = prs.classify(
        _sheet("2026-08-20"), today=TODAY, git_date=dt.date(2026, 8, 28)
    )
    assert verdict.outcome == prs.OUTCOME_UNMAINTAINED


def test_guilt_verified_on_alone_can_expose_the_broken_attestation():
    """git is not the only trace: a per-entry stamp newer than the file-level
    date proves the same thing, with git unavailable."""
    entries = {"VOA": {"price": 1, "verified_on": "2026-08-25"}}
    verdict = prs.classify(_sheet("2026-05-06", entries), today=TODAY, git_date=None)
    assert verdict.outcome == prs.OUTCOME_UNMAINTAINED
    assert verdict.newest_verified_on == dt.date(2026, 8, 25)


def test_innocence_a_trace_within_the_grace_day_does_not_trip_unmaintained():
    """A commit at 00:22Z is the previous evening in WITA. One day of grace,
    and no more — otherwise every same-day review looks broken."""
    verdict = prs.classify(
        _sheet("2026-08-25"), today=TODAY, git_date=dt.date(2026, 8, 26)
    )
    assert verdict.outcome == prs.OUTCOME_OK


def test_guilt_two_days_past_the_review_date_does_trip():
    verdict = prs.classify(
        _sheet("2026-08-25"), today=TODAY, git_date=dt.date(2026, 8, 27)
    )
    assert verdict.outcome == prs.OUTCOME_UNMAINTAINED


# ---------------------------------------------------------------------------
# The interval itself
# ---------------------------------------------------------------------------


def test_guilt_past_the_ninety_day_interval_is_review_due():
    verdict = prs.classify(
        _sheet("2026-05-01"), today=TODAY, git_date=dt.date(2026, 5, 1)
    )
    assert verdict.outcome == prs.OUTCOME_REVIEW_DUE
    assert verdict.age_days == 122
    assert "90-day" in verdict.reason


def test_innocence_exactly_at_the_interval_is_not_yet_due():
    at_boundary = TODAY - dt.timedelta(days=prs.PRICE_REVIEW_INTERVAL_DAYS)
    verdict = prs.classify(
        _sheet(at_boundary.isoformat()), today=TODAY, git_date=at_boundary
    )
    assert verdict.outcome == prs.OUTCOME_APPROACHING
    assert verdict.age_days == 90


def test_one_day_past_the_interval_is_due():
    past = TODAY - dt.timedelta(days=prs.PRICE_REVIEW_INTERVAL_DAYS + 1)
    verdict = prs.classify(_sheet(past.isoformat()), today=TODAY, git_date=past)
    assert verdict.outcome == prs.OUTCOME_REVIEW_DUE


def test_innocence_a_fresh_sheet_is_ok():
    recent = TODAY - dt.timedelta(days=10)
    verdict = prs.classify(_sheet(recent.isoformat()), today=TODAY, git_date=recent)
    assert verdict.outcome == prs.OUTCOME_OK


def test_approaching_fires_inside_the_warn_window():
    approaching = TODAY - dt.timedelta(days=prs.PRICE_REVIEW_INTERVAL_DAYS - 3)
    verdict = prs.classify(
        _sheet(approaching.isoformat()), today=TODAY, git_date=approaching
    )
    assert verdict.outcome == prs.OUTCOME_APPROACHING
    assert "due in 3 day(s)" in verdict.reason


# ---------------------------------------------------------------------------
# Absence is UNKNOWN, never "today"
# ---------------------------------------------------------------------------


def test_a_missing_review_date_cannot_verify_rather_than_passing():
    verdict = prs.classify(_sheet(None), today=TODAY, git_date=None)
    assert verdict.outcome == prs.OUTCOME_CANNOT_VERIFY


def test_an_unparseable_review_date_cannot_verify():
    verdict = prs.classify(_sheet("soon"), today=TODAY, git_date=None)
    assert verdict.outcome == prs.OUTCOME_CANNOT_VERIFY


def test_parse_date_never_invents_a_value():
    for bad in (None, "", "nope", 20260506, "2026-13-45", {}):
        assert prs.parse_date(bad) is None
    assert prs.parse_date("2026-05-06") == dt.date(2026, 5, 6)
    assert prs.parse_date("2026-08-26T00:22:20Z") == dt.date(2026, 8, 26)


def test_entries_without_attestation_is_counted_and_reported():
    entries = {
        "A": {"price": 1, "verified_on": "2026-08-25"},
        "B": {"price": 2},
        "C": {"tier_range": "1-2"},
    }
    verdict = prs.classify(
        _sheet("2026-08-25", entries), today=TODAY, git_date=dt.date(2026, 8, 25)
    )
    assert verdict.priced_entries == 3
    assert verdict.entries_with_attestation == 1
    assert verdict.entries_without_attestation == 2
    assert "2 of 3 priced entries carry no verified_on" in prs.format_alert_text(verdict)


# ---------------------------------------------------------------------------
# Exit-code contract
# ---------------------------------------------------------------------------


def test_every_outcome_has_a_deliberate_exit_code():
    outcomes = {
        value for name, value in vars(prs).items()
        if name.startswith("OUTCOME_")
    }
    assert outcomes == set(prs.EXIT_BY_OUTCOME), (
        "an outcome exists with no exit code mapped — it would silently fall "
        "through to CANNOT_VERIFY"
    )
    assert prs.EXIT_BY_OUTCOME[prs.OUTCOME_OK] == 0
    assert prs.EXIT_BY_OUTCOME[prs.OUTCOME_APPROACHING] == 0
    assert prs.EXIT_BY_OUTCOME[prs.OUTCOME_REVIEW_DUE] == 1
    assert prs.EXIT_BY_OUTCOME[prs.OUTCOME_UNMAINTAINED] == 1
    assert prs.EXIT_BY_OUTCOME[prs.OUTCOME_CANNOT_VERIFY] == 2


# ---------------------------------------------------------------------------
# Gateway (fake tg_notify.py — the W107 fake-world pattern)
# ---------------------------------------------------------------------------


def _fake_gateway(tmp_path: Path, exit_code: int = 0) -> tuple[Path, Path]:
    argv_log = tmp_path / "argv.json"
    gateway = tmp_path / "tg_notify.py"
    gateway.write_text(
        "import json, sys\n"
        f"json.dump(sys.argv[1:], open({str(argv_log)!r}, 'w'))\n"
        "sys.stderr.write('VERDICT: SENT\\n')\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    gateway.chmod(gateway.stat().st_mode | stat.S_IEXEC)
    return gateway, argv_log


def test_ok_sends_nothing(tmp_path):
    gateway, argv_log = _fake_gateway(tmp_path)
    verdict = prs.Verdict(outcome=prs.OUTCOME_OK, reason="fine")
    assert prs.send_alert(verdict, gateway_path=gateway) is None
    assert not argv_log.exists()


def test_unmaintained_is_p0_and_carries_a_stable_dedup_key(tmp_path):
    gateway, argv_log = _fake_gateway(tmp_path)
    verdict = prs.classify(
        _sheet("2026-05-06"), today=TODAY, git_date=dt.date(2026, 8, 26)
    )
    assert prs.send_alert(verdict, gateway_path=gateway) == "VERDICT: SENT"
    argv = json.loads(argv_log.read_text())
    assert argv[argv.index("--tier") + 1] == "p0"
    assert argv[argv.index("--source") + 1] == "price-review-sentinel"
    assert argv[argv.index("--dedup-key") + 1] == (
        "price-review:ATTESTATION_UNMAINTAINED:2026-05-06"
    )


def test_approaching_is_digest_not_p0(tmp_path):
    gateway, argv_log = _fake_gateway(tmp_path)
    approaching = TODAY - dt.timedelta(days=prs.PRICE_REVIEW_INTERVAL_DAYS - 3)
    verdict = prs.classify(
        _sheet(approaching.isoformat()), today=TODAY, git_date=approaching
    )
    prs.send_alert(verdict, gateway_path=gateway)
    argv = json.loads(argv_log.read_text())
    assert argv[argv.index("--tier") + 1] == "digest"


def test_a_missing_gateway_never_raises(tmp_path):
    verdict = prs.classify(_sheet("2026-01-01"), today=TODAY, git_date=None)
    assert prs.send_alert(verdict, gateway_path=tmp_path / "absent.py") is None


def test_a_failing_gateway_never_raises(tmp_path):
    gateway, _ = _fake_gateway(tmp_path, exit_code=3)
    verdict = prs.classify(_sheet("2026-01-01"), today=TODAY, git_date=None)
    assert prs.send_alert(verdict, gateway_path=gateway) == "VERDICT: SENT"
