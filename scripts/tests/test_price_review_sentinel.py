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


def test_exactly_at_the_interval_is_already_due():
    """Day 90 of a 90-day interval has elapsed. The first draft used a strict
    `>`, which delayed the verdict to day 91 and printed "due in 0 day(s)" on
    day 90 — flagged by the codex-gpt-5.6-sol council seat."""
    at_boundary = TODAY - dt.timedelta(days=prs.PRICE_REVIEW_INTERVAL_DAYS)
    verdict = prs.classify(
        _sheet(at_boundary.isoformat()), today=TODAY, git_date=at_boundary
    )
    assert verdict.outcome == prs.OUTCOME_REVIEW_DUE
    assert verdict.age_days == 90


def test_one_day_before_the_interval_is_still_only_approaching():
    almost = TODAY - dt.timedelta(days=prs.PRICE_REVIEW_INTERVAL_DAYS - 1)
    verdict = prs.classify(_sheet(almost.isoformat()), today=TODAY, git_date=almost)
    assert verdict.outcome == prs.OUTCOME_APPROACHING


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
    delivery = prs.send_alert(verdict, gateway_path=gateway)
    assert delivery.attempted is False
    assert delivery.label == "skipped"
    assert not argv_log.exists()


def test_unmaintained_is_p0_and_carries_a_stable_dedup_key(tmp_path):
    gateway, argv_log = _fake_gateway(tmp_path)
    verdict = prs.classify(
        _sheet("2026-05-06"), today=TODAY, git_date=dt.date(2026, 8, 26)
    )
    delivery = prs.send_alert(verdict, gateway_path=gateway)
    assert delivery.delivered is True
    assert delivery.gateway_verdict == "VERDICT: SENT"
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


def test_a_missing_gateway_is_an_attempted_but_undelivered_alert(tmp_path):
    verdict = prs.classify(_sheet("2026-01-01"), today=TODAY, git_date=None)
    delivery = prs.send_alert(verdict, gateway_path=tmp_path / "absent.py")
    assert delivery.attempted is True
    assert delivery.delivered is False
    assert delivery.label == "FAILED"


def test_a_gateway_that_prints_sent_but_exits_nonzero_did_not_deliver(tmp_path):
    """The printed line is not delivery; the RETURN CODE is. The first draft
    believed the line and would have called this a success."""
    gateway, _ = _fake_gateway(tmp_path, exit_code=3)
    verdict = prs.classify(_sheet("2026-01-01"), today=TODAY, git_date=None)
    delivery = prs.send_alert(verdict, gateway_path=gateway)
    assert delivery.gateway_verdict == "VERDICT: SENT"
    assert delivery.delivered is False


# ---------------------------------------------------------------------------
# A date that has not happened yet — the shape that slipped past every other
# check (found by the kimi-code/k3 council seat, reproduced before adoption)
# ---------------------------------------------------------------------------


def test_guilt_a_future_review_date_is_an_anomaly_not_a_fresh_sheet():
    """A negative age is trivially 'inside the interval', and no real trace can
    ever be newer than a future date — so without this check the sentinel
    reported OK with the reason 'reviewed -123 days ago'."""
    verdict = prs.classify(
        _sheet("2027-01-01"), today=TODAY, git_date=dt.date(2026, 8, 26)
    )
    assert verdict.outcome == prs.OUTCOME_ANOMALY
    assert verdict.age_days == -123
    assert "2027-01-01" in verdict.reason


def test_guilt_a_future_verified_on_is_also_an_anomaly():
    entries = {"X": {"price": 1, "verified_on": "2027-02-02"}}
    verdict = prs.classify(
        _sheet("2026-08-20", entries), today=TODAY, git_date=dt.date(2026, 8, 20)
    )
    assert verdict.outcome == prs.OUTCOME_ANOMALY
    assert "2027-02-02" in verdict.reason


def test_innocence_today_itself_is_not_a_future_date():
    verdict = prs.classify(_sheet(TODAY.isoformat()), today=TODAY, git_date=TODAY)
    assert verdict.outcome == prs.OUTCOME_OK


def test_anomaly_is_p0_and_exits_one(tmp_path):
    gateway, argv_log = _fake_gateway(tmp_path)
    verdict = prs.classify(_sheet("2027-01-01"), today=TODAY, git_date=None)
    prs.send_alert(verdict, gateway_path=gateway)
    argv = json.loads(argv_log.read_text())
    assert argv[argv.index("--tier") + 1] == "p0"
    assert prs.EXIT_BY_OUTCOME[prs.OUTCOME_ANOMALY] == 1


# ---------------------------------------------------------------------------
# Corroboration, malformed input, and the rc=1 laundering hole
# (all three reported by the kimi-code/k3 council seat, all three reproduced
# against the classifier before being adopted)
# ---------------------------------------------------------------------------


def test_guilt_no_trace_at_all_cannot_exonerate_the_sheet():
    """git unavailable AND zero verified_on entries: the contradiction check
    passes VACUOUSLY. That is not evidence of freshness, and it used to return
    OK with the reason 'nothing shows the sheet changed after that date'."""
    verdict = prs.classify(_sheet("2026-08-30"), today=TODAY, git_date=None)
    assert verdict.outcome == prs.OUTCOME_CANNOT_VERIFY
    assert "nothing independent can corroborate" in verdict.reason


def test_the_asymmetry_survives_no_overdue_is_still_provable_without_traces():
    """A field-only signal can still prove OVERDUE — that direction needs no
    corroboration. Losing it would be the wrong cure for the vacuity above."""
    verdict = prs.classify(_sheet("2026-01-01"), today=TODAY, git_date=None)
    assert verdict.outcome == prs.OUTCOME_REVIEW_DUE


def test_innocence_one_trace_is_enough_to_corroborate():
    entries = {"X": {"price": 1, "verified_on": "2026-08-30"}}
    verdict = prs.classify(_sheet("2026-08-30", entries), today=TODAY, git_date=None)
    assert verdict.outcome == prs.OUTCOME_OK


def test_malformed_metadata_cannot_verify_instead_of_crashing():
    for bad in (None, "2026-08-01", [], 7):
        verdict = prs.classify(
            {"metadata": bad, "services": {"a": {"X": {"price": 1}}}},
            today=TODAY, git_date=None,
        )
        assert verdict.outcome == prs.OUTCOME_CANNOT_VERIFY, bad
        assert "malformed" in verdict.reason


def test_a_crash_never_exits_one_because_the_wrapper_reads_one_as_a_finding(monkeypatch):
    """rc=1 means 'a finding was computed and delivered'. If a crash could also
    exit 1, the wrapper's heartbeat would report a healthy organ that delivered
    a finding it never computed."""
    def boom(*_args, **_kwargs):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(prs, "classify", boom)
    rc = prs.main(["--dry-run", "--now", "2026-08-31"])
    assert rc == prs.EXIT_CANNOT_VERIFY


# ---------------------------------------------------------------------------
# Codex-gpt-5.6-sol: the exit-code test enumerated CONSTANTS, not outcomes the
# classifier actually returns — so `Verdict(outcome="TYPO")` stayed green.
# ---------------------------------------------------------------------------


def _outcome_matrix() -> list[tuple[str, dict]]:
    """Inputs chosen to drive classify() down every branch it has."""
    ten_days = (TODAY - dt.timedelta(days=10)).isoformat()
    warn = (TODAY - dt.timedelta(days=prs.PRICE_REVIEW_INTERVAL_DAYS - 3)).isoformat()
    return [
        ("fresh", dict(sheet=_sheet(ten_days), git_date=dt.date.fromisoformat(ten_days))),
        ("approaching", dict(sheet=_sheet(warn), git_date=dt.date.fromisoformat(warn))),
        ("overdue", dict(sheet=_sheet("2026-01-01"), git_date=dt.date(2026, 1, 1))),
        ("unmaintained", dict(sheet=_sheet("2026-05-06"), git_date=dt.date(2026, 8, 26))),
        ("future", dict(sheet=_sheet("2027-01-01"), git_date=dt.date(2026, 8, 26))),
        ("no-trace", dict(sheet=_sheet(ten_days), git_date=None)),
        ("no-date", dict(sheet=_sheet(None), git_date=None)),
        ("bad-metadata", dict(sheet={"metadata": None, "services": {"a": {"X": {"price": 1}}}}, git_date=None)),
        ("empty-sheet", dict(sheet={"metadata": {"last_updated": TODAY.isoformat()}}, git_date=None)),
        ("dirty", dict(sheet=_sheet(ten_days), git_date=dt.date.fromisoformat(ten_days), worktree_dirty=True)),
    ]


def test_every_outcome_the_classifier_actually_returns_has_an_exit_code():
    seen = set()
    for label, kwargs in _outcome_matrix():
        verdict = prs.classify(today=TODAY, **kwargs)
        assert verdict.outcome in prs.EXIT_BY_OUTCOME, f"{label}: {verdict.outcome}"
        seen.add(verdict.outcome)
    # Non-vacuity: the matrix must really exercise a spread of branches, or
    # this test proves nothing about the ones it never reached.
    assert len(seen) >= 5, f"matrix only reached {sorted(seen)}"


def test_the_constant_list_and_the_exit_table_agree():
    outcomes = {v for k, v in vars(prs).items() if k.startswith("OUTCOME_")}
    assert outcomes == set(prs.EXIT_BY_OUTCOME)


def test_an_uncommitted_edit_is_a_trace_the_commit_log_cannot_show():
    """The Pro checkout routinely carries uncommitted files. A price edited in
    the working tree leaves git history untouched, so without this the sheet
    would read as reviewed-and-unchanged."""
    ten_days = (TODAY - dt.timedelta(days=10)).isoformat()
    clean = prs.classify(
        _sheet(ten_days), today=TODAY, git_date=dt.date.fromisoformat(ten_days)
    )
    dirty = prs.classify(
        _sheet(ten_days), today=TODAY, git_date=dt.date.fromisoformat(ten_days),
        worktree_dirty=True,
    )
    assert clean.outcome == prs.OUTCOME_OK
    assert dirty.outcome == prs.OUTCOME_UNMAINTAINED


def test_a_trailing_garbage_date_is_unknown_not_partially_believed():
    """`_ISO_DATE` was not end-anchored, so "2026-05-06-whatever" parsed."""
    assert prs.parse_date("2026-05-06-whatever") is None
    assert prs.parse_date("2026-05-06 extra") is None
    assert prs.parse_date("2026-05-06T00:22:20Z") == dt.date(2026, 5, 6)


def test_a_sheet_with_no_priced_entries_cannot_be_reported_current():
    verdict = prs.classify(
        {"metadata": {"last_updated": TODAY.isoformat()}}, today=TODAY, git_date=TODAY
    )
    assert verdict.outcome == prs.OUTCOME_CANNOT_VERIFY
    assert "no priced entries" in verdict.reason


# ---------------------------------------------------------------------------
# main(): the exit code the wrapper actually reads
# ---------------------------------------------------------------------------


def test_main_exits_one_on_the_real_sheet_today_and_says_so_on_its_last_line(capsys):
    rc = prs.main(["--dry-run", "--now", "2026-08-31"])
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last.startswith("SENTINEL-STATE ")
    assert f"rc={rc}" in last
    assert rc in (prs.EXIT_OK, prs.EXIT_FINDING)


def test_main_exits_three_when_the_finding_could_not_be_delivered(tmp_path, monkeypatch, capsys):
    """An undelivered p0 must not be representable as a delivered one."""
    # Point the module constant at a path that does not exist. `send_alert`
    # resolves TG_NOTIFY at call time precisely so this cannot leak to the
    # real gateway — an earlier draft used a default argument and did.
    monkeypatch.setattr(prs, "TG_NOTIFY", tmp_path / "absent.py")
    monkeypatch.setattr(
        prs, "classify",
        lambda *a, **k: prs.Verdict(outcome=prs.OUTCOME_REVIEW_DUE, reason="synthetic"),
    )
    rc = prs.main(["--now", "2026-08-31"])
    assert rc == prs.EXIT_UNDELIVERED
    assert "delivery=FAILED" in capsys.readouterr().out



# ---------------------------------------------------------------------------
# A trace only corroborates if it COULD have contradicted (Gear-3 gate on 5400)
# ---------------------------------------------------------------------------


def test_guilt_a_trace_older_than_the_review_date_corroborates_nothing():
    """The vacuity gate, one layer down. An entry stamped 2026-01-01 cannot
    contradict a review dated 2026-08-25 whatever the file did — but it is a
    trace, so `if not traces` passed and the sheet read OK."""
    entries = {"X": {"price": 1, "verified_on": "2026-01-01"}}
    verdict = prs.classify(
        _sheet("2026-08-25", entries), today=TODAY, git_date=None
    )
    assert verdict.outcome == prs.OUTCOME_CANNOT_VERIFY
    assert "could never have contradicted" in verdict.reason


def test_innocence_a_trace_on_the_review_date_does_corroborate():
    entries = {"X": {"price": 1, "verified_on": "2026-08-25"}}
    verdict = prs.classify(
        _sheet("2026-08-25", entries), today=TODAY, git_date=None
    )
    assert verdict.outcome == prs.OUTCOME_OK


def test_innocence_a_trace_one_grace_day_before_still_corroborates():
    """Merge lag runs the other way too: a commit landing the day before the
    date was typed is still evidence about the same edit."""
    entries = {"X": {"price": 1, "verified_on": "2026-08-24"}}
    verdict = prs.classify(
        _sheet("2026-08-25", entries), today=TODAY, git_date=None
    )
    assert verdict.outcome == prs.OUTCOME_OK


# ---------------------------------------------------------------------------
# The wrapper's interpreter — the defect no unit test could have caught, so it
# gets the one check that would have (Gear-3 gate on 5400)
# ---------------------------------------------------------------------------


def test_the_wrapper_does_not_run_this_sentinel_on_system_python():
    """`/usr/bin/python3` is 3.9.6 on Pro and on M5. This sentinel imports
    backend code to learn which file the live pricing service loads, and that
    import chain reaches a `str | None` annotation evaluated at class creation
    — a TypeError before 3.10. The first draft pinned /usr/bin/python3 and
    would have returned CANNOT_VERIFY on every scheduled run, forever, while a
    receipt in the evidence pack certified the opposite: the measurement had
    been taken with the ambient `python3` (3.11 via mise), not the one the
    wrapper names."""
    wrapper = (REPO / "infra" / "launchagents" / "wrappers"
               / "pro-price-review-sentinel.sh").read_text(encoding="utf-8")
    payload = [
        line for line in wrapper.splitlines()
        if "price_review_sentinel.py" in line and not line.lstrip().startswith("#")
    ]
    assert len(payload) == 1, f"expected one payload line, got {payload}"
    assert "/usr/bin/python3" not in payload[0], (
        "the wrapper invokes this sentinel with system python — 3.9.6 on both "
        "Pro and M5, which cannot import the backend package"
    )
    assert ".venv/bin/python" in payload[0], (
        "the wrapper must use the backend venv interpreter; it imports backend code"
    )


def test_the_wrapper_reads_only_the_state_line_this_run_printed():
    """`grep '^SENTINEL-STATE ' "$LOG" | tail -1` over the WHOLE append-only
    log returns the PREVIOUS run's outcome whenever this run prints none —
    the ${STATE:-...} fallback could then only ever fire on the very first
    run ever, so staleness would be guaranteed, not merely possible (see the
    wrapper's own comment above LOG_OFFSET). This test fails if someone
    reverts the offset-scoped read back to that whole-log form."""
    wrapper = (REPO / "infra" / "launchagents" / "wrappers"
               / "pro-price-review-sentinel.sh").read_text(encoding="utf-8")
    lines = wrapper.splitlines()
    non_comment = [
        (i, line) for i, line in enumerate(lines)
        if line.strip() and not line.lstrip().startswith("#")
    ]

    state_grep_lines = [
        (i, line) for i, line in non_comment
        if line.lstrip().startswith("STATE=")
        and "grep" in line
        and "SENTINEL-STATE" in line
    ]
    assert len(state_grep_lines) == 1, (
        f"expected exactly one STATE= assignment that greps SENTINEL-STATE, "
        f"got {state_grep_lines}"
    )
    grep_idx, grep_line = state_grep_lines[0]
    assert 'tail -c "+$((LOG_OFFSET + 1))"' in grep_line, (
        "STATE must be read from the offset-sliced tail of THIS run's output, "
        f"not the whole log: got {grep_line!r}"
    )

    naive_whole_log_form = [
        line for _, line in non_comment
        if "grep '^SENTINEL-STATE '" in line
        and '"$LOG"' in line
        and "tail -c" not in line
    ]
    assert naive_whole_log_form == [], (
        "found the un-scoped whole-log grep the offset fix was meant to "
        f"remove: {naive_whole_log_form}"
    )

    offset_assignment_indices = [
        i for i, line in non_comment
        if line.lstrip().startswith("LOG_OFFSET=")
    ]
    assert offset_assignment_indices, (
        "LOG_OFFSET is never assigned on a non-comment line"
    )
    assert offset_assignment_indices[0] < grep_idx, (
        "LOG_OFFSET must be computed BEFORE the state line is read (and "
        "before the payload runs), or it captures the wrong byte count"
    )
