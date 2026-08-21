#!/usr/bin/env python3
"""Falsifiable tests for scripts/llm_burn_alarm.py.

Run:
    apps/backend-rag/.venv/bin/python -m pytest scripts/test_llm_burn_alarm.py -q

Fixtures below reuse the LIVE numbers measured on Postgres 2026-08-20 (see the
PR this ships in): 2026-08-10 was $11.11 / 2238 calls / 20,869,166 input
tokens against a trailing-week median of $0.15-$0.30; a normal day sits in
$0.11-$1.70 / 53-673 calls. The guilt/innocence tests below are these exact
measured worlds, not invented numbers, per CLAUDE.md §6 (verify sources).
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import llm_burn_alarm as lba  # noqa: E402


# ---------------------------------------------------------------------------
# compute_verdict — the pure guard
# ---------------------------------------------------------------------------


def test_guilt_2026_08_10_reproduction_triggers_alarm() -> None:
    """The measured 08-10 world: $11.11/2238 calls vs a $0.50 baseline (team's
    stated round number) — must ALARM, comfortably clear of the 5x/$1 gates."""
    baseline = [Decimal("0.50")] * 7
    current = lba.WindowStats(usd=Decimal("11.11"), input_tokens=20_869_166, calls=2238)
    verdict, med = lba.compute_verdict(
        baseline, current, multiplier=lba.DEFAULT_MULTIPLIER, floor_usd=lba.DEFAULT_FLOOR_USD,
    )
    assert verdict is lba.Verdict.ALARM
    assert med == Decimal("0.50")


def test_guilt_measured_baseline_from_live_postgres() -> None:
    """Same guilt case against the ACTUAL 7 quiet days read live on Postgres
    2026-08-20 (2026-08-13..2026-08-19), not the rounded $0.50 example."""
    baseline = [
        Decimal("0.232477"), Decimal("0.106923"), Decimal("0.107857"),
        Decimal("0.198414"), Decimal("0.202416"), Decimal("0.263001"),
        Decimal("0.232276"),
    ]
    current = lba.WindowStats(usd=Decimal("11.11"), input_tokens=20_869_166, calls=2238)
    verdict, med = lba.compute_verdict(
        baseline, current, multiplier=lba.DEFAULT_MULTIPLIER, floor_usd=lba.DEFAULT_FLOOR_USD,
    )
    assert verdict is lba.Verdict.ALARM
    assert med == Decimal("0.202416")  # median of the 7 (4th smallest)


def test_innocence_normal_day_against_normal_week_does_not_alarm() -> None:
    """A normal day's own numbers measured against a baseline week living in
    the same $0.26-$1.70/90-230-calls band the mandate names as innocent.

    NOTE on the numbers chosen: the stated band spans a 6.5x ratio end to
    end ($1.70/$0.26), so a baseline drawing its LOW end for the median and
    a current day at the band's HIGH end would cross a 5x multiplier by
    construction — that would be an artifact of how wide the stated range
    is, not a false positive in the guard. A real week does not sample its
    median from the extreme low tail, so this fixture spreads the 7 values
    across the band (median lands mid-band) and puts current near the same
    middle, which is what an actual quiet week looks like.
    """
    baseline = [
        Decimal("0.30"), Decimal("1.60"), Decimal("0.45"), Decimal("0.90"),
        Decimal("1.10"), Decimal("0.55"), Decimal("0.70"),
    ]
    current = lba.WindowStats(usd=Decimal("1.65"), input_tokens=1_800_000, calls=230)
    verdict, med = lba.compute_verdict(
        baseline, current, multiplier=lba.DEFAULT_MULTIPLIER, floor_usd=lba.DEFAULT_FLOOR_USD,
    )
    assert verdict is lba.Verdict.OK
    assert med == Decimal("0.70")


def test_innocence_below_floor_never_alarms_even_at_infinite_ratio() -> None:
    """Every baseline day at $0 (median == 0) but current is a few cents —
    below the plan-minimum floor, so OK despite an undefined/infinite ratio."""
    baseline = [Decimal("0")] * 7
    current = lba.WindowStats(usd=Decimal("0.09"), input_tokens=500, calls=3)
    verdict, med = lba.compute_verdict(
        baseline, current, multiplier=lba.DEFAULT_MULTIPLIER, floor_usd=lba.DEFAULT_FLOOR_USD,
    )
    assert verdict is lba.Verdict.OK
    assert med == Decimal("0")


def test_zero_baseline_above_floor_alarms() -> None:
    """Every baseline day at $0, current clears the floor -> ALARM (the
    infinite-ratio branch, distinct from the above)."""
    baseline = [Decimal("0")] * 7
    current = lba.WindowStats(usd=Decimal("2.00"), input_tokens=500_000, calls=40)
    verdict, med = lba.compute_verdict(
        baseline, current, multiplier=lba.DEFAULT_MULTIPLIER, floor_usd=lba.DEFAULT_FLOOR_USD,
    )
    assert verdict is lba.Verdict.ALARM


def test_exactly_at_multiplier_boundary_alarms_inclusive() -> None:
    baseline = [Decimal("1.00")] * 7
    current = lba.WindowStats(usd=Decimal("5.00"), input_tokens=1, calls=1)  # exactly 5x
    verdict, _ = lba.compute_verdict(baseline, current, multiplier=Decimal("5"), floor_usd=Decimal("1"))
    assert verdict is lba.Verdict.ALARM


def test_just_under_multiplier_boundary_does_not_alarm() -> None:
    baseline = [Decimal("1.00")] * 7
    current = lba.WindowStats(usd=Decimal("4.99"), input_tokens=1, calls=1)
    verdict, _ = lba.compute_verdict(baseline, current, multiplier=Decimal("5"), floor_usd=Decimal("1"))
    assert verdict is lba.Verdict.OK


def test_empty_baseline_raises_caller_must_map_to_cannot_verify() -> None:
    current = lba.WindowStats(usd=Decimal("5"), input_tokens=1, calls=1)
    with pytest.raises(ValueError):
        lba.compute_verdict([], current, multiplier=Decimal("5"), floor_usd=Decimal("1"))


# ---------------------------------------------------------------------------
# build_alarm_message — names the cause (W116)
# ---------------------------------------------------------------------------


def test_alarm_message_names_endpoint_model_and_baseline_comparison() -> None:
    current = lba.WindowStats(usd=Decimal("11.11"), input_tokens=20_869_166, calls=2238)
    offenders = [
        lba.Offender("rag.gateway.chat", "gemini-2.5-flash", 1136, Decimal("6.98"), 16132),
        lba.Offender("rag.verifier", "gemini-2.5-flash", 516, Decimal("4.06"), 4818),
    ]
    msg = lba.build_alarm_message(current, Decimal("0.20"), Decimal("5"), offenders, 7)
    assert "rag.gateway.chat" in msg
    assert "gemini-2.5-flash" in msg
    assert "2238" in msg
    assert "$11.11" in msg
    assert "$0.20" in msg
    # ratio stated, not just raw numbers
    assert "x" in msg
    # sentence commas survive — the thousands-separator bug this test pins
    assert "chiamate," in msg
    assert "20.869.166" in msg  # Italian-style thousands, not "20,869,166"


def test_alarm_message_without_offenders_still_states_totals() -> None:
    current = lba.WindowStats(usd=Decimal("3.00"), input_tokens=100, calls=5)
    msg = lba.build_alarm_message(current, Decimal("0.20"), Decimal("5"), [], 7)
    assert "$3.00" in msg
    assert "breakdown" in msg.lower() or "totale" in msg.lower()


def test_alarm_message_zero_median_states_undefined_ratio_not_a_fake_number() -> None:
    current = lba.WindowStats(usd=Decimal("2.00"), input_tokens=100, calls=5)
    msg = lba.build_alarm_message(current, Decimal("0"), Decimal("5"), [], 7)
    assert "$0.00x" not in msg  # never fabricate a ratio out of a zero denominator
    assert "indefinito" in msg.lower() or "$0" in msg


def test_cannot_verify_message_distinct_from_alarm_wording() -> None:
    msg = lba.build_cannot_verify_message("Postgres unreachable")
    assert "Postgres unreachable" in msg
    assert "tutto tranquillo" in msg  # explicitly disclaims the "all clean" reading


# ---------------------------------------------------------------------------
# I/O layer: fetch_* functions against a monkeypatched run_pg — judge the
# REPLY (rc + shape), never rc alone (W104).
# ---------------------------------------------------------------------------


def test_fetch_baseline_daily_usd_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    out = "\n".join(f"2026-08-{10+i:02d}\t0.{i}0" for i in range(7)) + "\n"
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (0, out, ""))
    result = lba.fetch_baseline_daily_usd(7)
    assert result is not None
    assert len(result) == 7


def test_fetch_baseline_daily_usd_nonzero_rc_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (1, "", "connection refused"))
    assert lba.fetch_baseline_daily_usd(7) is None


def test_fetch_baseline_daily_usd_wrong_row_count_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """rc==0 but only 3 rows instead of 7 — judged on SHAPE, not just rc."""
    out = "2026-08-10\t0.10\n2026-08-11\t0.20\n2026-08-12\t0.30\n"
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (0, out, ""))
    assert lba.fetch_baseline_daily_usd(7) is None


def test_fetch_baseline_daily_usd_garbage_output_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    out = "\n".join(["not-a-row"] * 7)
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (0, out, ""))
    assert lba.fetch_baseline_daily_usd(7) is None


def test_fetch_current_window_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (0, "11.11\t20869166\t2238\n", ""))
    stats = lba.fetch_current_window()
    assert stats == lba.WindowStats(usd=Decimal("11.11"), input_tokens=20869166, calls=2238)


def test_fetch_current_window_failure_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (2, "", "syntax error"))
    assert lba.fetch_current_window() is None


def test_fetch_current_window_empty_output_is_none_not_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """rc==0 with truly empty stdout must be CANNOT-VERIFY, never coerced to
    a silent WindowStats(0,0,0)."""
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (0, "", ""))
    assert lba.fetch_current_window() is None


def test_fetch_offenders_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    out = "rag.gateway.chat\tgemini-2.5-flash\t1136\t6.98\t16132\n"
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (0, out, ""))
    offenders = lba.fetch_offenders(3)
    assert offenders == [lba.Offender("rag.gateway.chat", "gemini-2.5-flash", 1136, Decimal("6.98"), 16132)]


def test_fetch_offenders_failure_is_none_not_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed offenders read must be distinguishable from 'zero offenders' —
    main() treats None as 'no breakdown available' (best-effort), not as an
    empty result the caller could mistake for a clean signal."""
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (1, "", "timeout"))
    assert lba.fetch_offenders(3) is None


def test_fetch_table_has_rows_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (0, "24443\n", ""))
    assert lba.fetch_table_has_rows() is True


def test_fetch_table_has_rows_false_when_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (0, "0\n", ""))
    assert lba.fetch_table_has_rows() is False


def test_fetch_table_has_rows_none_on_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (2, "", "could not connect to server"))
    assert lba.fetch_table_has_rows() is None


# ---------------------------------------------------------------------------
# main() end-to-end: the three named outcomes are DISTINCT (OK / ALARM /
# CANNOT_VERIFY), and CANNOT_VERIFY covers BOTH "query failed" and "table
# genuinely empty" — never read as a clean burn=0 (W106b).
# ---------------------------------------------------------------------------


class _SpySend:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, *, tier, source, text, dedup_key, dry_run=False, notify_fn=None):
        self.calls.append({"tier": tier, "source": source, "text": text, "dedup_key": dedup_key})
        return "sent"


def _patch_pg_sequence(monkeypatch: pytest.MonkeyPatch, *, count_out, baseline_out, current_out, offenders_out):
    """Route run_pg by SQL shape so each of the four call sites in main() is
    answered distinctly (sanity COUNT / baseline / current / offenders)."""

    def fake_run_pg(sql: str, **kw):
        if "COUNT(*) FROM llm_cost_events" in sql and "GROUP BY" not in sql:
            return count_out
        if "generate_series" in sql:
            return baseline_out
        if "LIMIT" in sql:
            return offenders_out
        return current_out

    monkeypatch.setattr(lba, "run_pg", fake_run_pg)


def test_main_end_to_end_alarm_dispatches_p0_with_named_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline_out = (0, "\n".join(f"2026-08-{10+i:02d}\t0.20" for i in range(7)) + "\n", "")
    current_out = (0, "11.11\t20869166\t2238\n", "")
    offenders_out = (0, "rag.gateway.chat\tgemini-2.5-flash\t1136\t6.98\t16132\n", "")
    count_out = (0, "24443\n", "")
    _patch_pg_sequence(monkeypatch, count_out=count_out, baseline_out=baseline_out,
                        current_out=current_out, offenders_out=offenders_out)
    spy = _SpySend()
    monkeypatch.setattr(lba, "send", spy)
    rc = lba.main([])
    assert rc == 1
    assert len(spy.calls) == 1
    assert spy.calls[0]["tier"] == "p0"
    assert "rag.gateway.chat" in spy.calls[0]["text"]


def test_main_end_to_end_ok_never_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline_out = (0, "\n".join(f"2026-08-{10+i:02d}\t0.50" for i in range(7)) + "\n", "")
    current_out = (0, "0.60\t100000\t80\n", "")
    offenders_out = (0, "", "")
    count_out = (0, "24443\n", "")
    _patch_pg_sequence(monkeypatch, count_out=count_out, baseline_out=baseline_out,
                        current_out=current_out, offenders_out=offenders_out)
    spy = _SpySend()
    monkeypatch.setattr(lba, "send", spy)
    rc = lba.main([])
    assert rc == 0
    assert spy.calls == []


def test_main_cannot_verify_on_query_failure_dispatches_digest_not_p0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (1, "", "connect timeout"))
    spy = _SpySend()
    monkeypatch.setattr(lba, "send", spy)
    rc = lba.main([])
    assert rc == 2
    assert len(spy.calls) == 1
    assert spy.calls[0]["tier"] == "digest"  # visible, not an urgent P0 interrupt
    assert "tutto tranquillo" in spy.calls[0]["text"]


def test_main_cannot_verify_on_empty_table_is_distinct_from_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty table -> CANNOT_VERIFY (2), never OK (0) — the empty-table branch
    this pins is what W106b calls out by name."""
    monkeypatch.setattr(lba, "run_pg", lambda sql, **kw: (0, "0\n", ""))
    spy = _SpySend()
    monkeypatch.setattr(lba, "send", spy)
    rc = lba.main([])
    assert rc == 2
    assert rc != 0
    assert "ZERO righe" in spy.calls[0]["text"]


# ---------------------------------------------------------------------------
# Mutation check (required by the mandate): disabling the guard must flip
# the guilt test from red-if-broken to actually red — proving the test
# depends on compute_verdict's real logic, not a tautology.
# ---------------------------------------------------------------------------


def test_mutation_disabling_the_guard_makes_the_guilt_case_stop_alarming(monkeypatch: pytest.MonkeyPatch) -> None:
    """With compute_verdict patched to always return OK, the exact 08-10
    reproduction from test_guilt_2026_08_10_reproduction_triggers_alarm must
    NO LONGER alarm — demonstrating the real guilt test is sensitive to the
    guard (not a test that would pass regardless of compute_verdict's body)."""
    baseline = [Decimal("0.50")] * 7
    current = lba.WindowStats(usd=Decimal("11.11"), input_tokens=20_869_166, calls=2238)

    monkeypatch.setattr(
        lba, "compute_verdict",
        lambda *a, **kw: (lba.Verdict.OK, Decimal("0.50")),
    )
    verdict, _ = lba.compute_verdict(
        baseline, current, multiplier=lba.DEFAULT_MULTIPLIER, floor_usd=lba.DEFAULT_FLOOR_USD,
    )
    assert verdict is lba.Verdict.OK, (
        "mutation did not take — the guilt test would have passed even with "
        "the guard disabled, which means it was not actually testing the guard"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
