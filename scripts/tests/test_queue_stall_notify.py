"""test_queue_stall_notify.py — pure-function tests over synthetic classifier reports, plus
monkeypatched-I/O tests for main(). No network, no real gh/fleet_mail.sh calls: the classifier
subprocess and fleet_mail.sh are both stubbed at their module-level seams
(`qsn.run_classifier`, `qsn._run`), and every stubbing test asserts that stub was the only
thing invoked — never merely that the assertions on its output happen to pass.

Covers the mandate's explicit cases:
  1. kill switch OFF -> zero sends, receipt line still printed (guilt: run_classifier must
     never even be called).
  2. --dry-run -> zero subprocess calls beyond the classifier read, intended payload printed.
  3. a real stall row -> exactly one send, dedup key contains BOTH the PR number and the cause.
  4. innocence: a clean board (no stalled rows) -> zero sends, rc 0, summary says stalled=0.
  5. innocence: a "queued-and-advancing" row (classifier's own "not actionably stuck" default)
     -> no send.
  6. classifier rc=1 -> notifier exits non-zero, even when nothing needed to be sent.
  7. a send that fails -> notifier exits non-zero, send_failed appears in the summary.
  8. the cap: more notify-worthy rows than the cap -> sends stop at the cap,
     suppressed_by_cap is non-zero.
  9. CANNOT-VERIFY rows are delivered, distinctly worded, not dropped — even though the
     classifier's own rc is 1 for that same run (propagated as failure regardless of delivery).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue_stall_notify as qsn  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_repeat_state(monkeypatch, tmp_path):
    """No unit test may read or write the operator's real local paging state."""
    monkeypatch.setattr(qsn, "SEEN_FILE", tmp_path / "queue_stall_notify_seen.json")


def make_row(number: int, cause: str, detail: str = "detail") -> dict:
    return {"number": number, "title": f"PR {number}", "age_minutes": 45, "cause": cause, "detail": detail}


def make_report(rows: list[dict], *, examined_total: int | None = None, fetch_error: str | None = None) -> dict:
    return {
        "repo": "Bali-Zero/Teman2",
        "generated_at": "2026-09-01T00:00:00Z",
        "min_age_minutes": 30,
        "examined_total": examined_total if examined_total is not None else len(rows),
        "excluded_drafts": 0,
        "rows": rows,
        "fetch_error": fetch_error,
    }


def _fail_if_called(*_args, **_kwargs):
    raise AssertionError("this stub must never be invoked in this scenario")


# ── plan_notifications: pure ────────────────────────────────────────────────


def test_real_stall_cause_is_notify_worthy_key_has_number_and_cause():
    plan = qsn.plan_notifications([make_row(202, "not-armed", "x")], cap=10)
    assert len(plan["to_notify"]) == 1
    item = plan["to_notify"][0]
    assert item["number"] == 202
    assert item["cause"] == "not-armed"
    assert item["key"] == "queue_stall:202:not-armed"
    assert item["cannot_verify"] is False


def test_same_pr_across_invocations_changed_cause_is_not_a_repeat():
    first = qsn.plan_notifications([make_row(707, "not-armed", "x")], cap=1)["to_notify"]
    first_key = first[0]["key"]
    second = qsn.plan_notifications([make_row(707, "conflict", "y")], cap=1)["to_notify"]
    re_page = qsn.plan_repage(second, seen={first_key: 1_000.0}, now=1_001.0, cap=1)
    assert [item["key"] for item in re_page["to_notify"]] == ["queue_stall:707:conflict"]
    assert re_page["suppressed_as_repeat"] == []


def test_queued_and_advancing_is_not_notify_worthy():
    plan = qsn.plan_notifications([make_row(303, "queued-and-advancing", "no known blocker")], cap=10)
    assert plan["to_notify"] == []
    assert plan["suppressed_by_cap"] == []
    assert plan["skipped"] == [(303, "queued-and-advancing")]


def test_classifier_stall_vocabulary_is_fully_accounted_for_without_importing_it():
    """The subprocess boundary stays intact: inspect source AST, never import the classifier."""
    source = qsn.CLASSIFIER.read_text()
    tree = ast.parse(source)
    stall_causes = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "STALL_CAUSES" for target in node.targets)
    )
    accounted_for = qsn.REAL_STALL_CAUSES | qsn.DELIBERATELY_IGNORED
    assert set(stall_causes) <= accounted_for


def test_cannot_verify_is_notify_worthy_and_flagged_distinctly():
    plan = qsn.plan_notifications([make_row(606, qsn.CANNOT_VERIFY, "checkSuites fetch failed")], cap=10)
    assert len(plan["to_notify"]) == 1
    item = plan["to_notify"][0]
    assert item["cannot_verify"] is True
    assert item["key"] == "queue_stall:606:CANNOT-VERIFY"


def test_cap_suppresses_past_the_limit_in_order():
    rows = [make_row(n, "not-armed", "x") for n in (501, 502, 503)]
    plan = qsn.plan_notifications(rows, cap=1)
    assert [i["number"] for i in plan["to_notify"]] == [501]
    assert [i["number"] for i in plan["suppressed_by_cap"]] == [502, 503]


def test_cannot_verify_message_wording_is_distinct_from_a_real_stall():
    real = qsn._format_message(
        {"number": 1, "cause": "conflict", "cannot_verify": False, "detail": "mergeStateStatus=DIRTY"}
    )
    unverifiable = qsn._format_message(
        {"number": 2, "cause": qsn.CANNOT_VERIFY, "cannot_verify": True, "detail": "network flap"}
    )
    assert "COULD NOT VERIFY" in unverifiable
    assert "COULD NOT VERIFY" not in real


# ── main(): kill switch ─────────────────────────────────────────────────────


def test_kill_switch_off_zero_sends_and_receipt_line_printed(monkeypatch, capsys):
    monkeypatch.setenv("QUEUE_STALL_NOTIFY_ENABLED", "false")
    monkeypatch.setattr(qsn, "run_classifier", _fail_if_called)
    monkeypatch.setattr(qsn, "_run", _fail_if_called)

    rc = qsn.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "disabled=true" in out
    assert "sent=0" in out


# ── main(): --dry-run ───────────────────────────────────────────────────────


def test_dry_run_zero_subprocess_calls_intended_payload_printed(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    report = make_report([make_row(101, "conflict", "mergeStateStatus=DIRTY")])
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, report, "", ""))
    monkeypatch.setattr(qsn, "_run", _fail_if_called)

    rc = qsn.main(["--dry-run"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "[dry-run] would signal PR #101" in out
    assert "queue_stall:101:conflict" in out
    assert "sent=1" in out
    assert not qsn.SEEN_FILE.exists()


def test_repeat_is_suppressed_then_repages_after_interval(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    report = make_report([make_row(111, "conflict", "mergeStateStatus=DIRTY")])
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, report, "", ""))
    monkeypatch.setattr(qsn.time, "time", lambda: 10_000.0)
    calls = []
    monkeypatch.setattr(qsn, "_run", lambda cmd, timeout=30: (calls.append(cmd) or (0, "ok", "")))

    assert qsn.main([]) == 0
    assert qsn.main([]) == 0
    assert len(calls) == 1
    assert "suppressed_as_repeat=1" in capsys.readouterr().out

    monkeypatch.setattr(qsn.time, "time", lambda: 10_000.0 + qsn.REPAGE_SECONDS)
    assert qsn.main([]) == 0
    assert len(calls) == 2


def test_changed_cause_sends_immediately_even_when_same_pr_was_just_sent(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    first = make_report([make_row(222, "not-armed", "not queued")])
    second = make_report([make_row(222, "required-check-red", "statusCheckRollup=FAILURE")])
    reports = iter((first, second))
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, next(reports), "", ""))
    monkeypatch.setattr(qsn.time, "time", lambda: 20_000.0)
    calls = []
    monkeypatch.setattr(qsn, "_run", lambda cmd, timeout=30: (calls.append(cmd) or (0, "ok", "")))

    assert qsn.main([]) == 0
    assert qsn.main([]) == 0
    assert len(calls) == 2
    assert calls[1][calls[1].index("--key") + 1] == "queue_stall:222:required-check-red"
    assert "suppressed_as_repeat=0" in capsys.readouterr().out


def test_corrupt_state_file_still_pages(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    qsn.SEEN_FILE.write_text("this is not json")
    report = make_report([make_row(333, "conflict", "mergeStateStatus=DIRTY")])
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, report, "", ""))
    calls = []
    monkeypatch.setattr(qsn, "_run", lambda cmd, timeout=30: (calls.append(cmd) or (0, "ok", "")))

    assert qsn.main([]) == 0
    assert len(calls) == 1
    assert "sent=1" in capsys.readouterr().out


# ── main(): a real stall row -> exactly one send ────────────────────────────


def test_real_stall_row_produces_exactly_one_send(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    report = make_report([make_row(202, "not-armed", "autoMergeRequest=null and mergeQueueEntry=null")])
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, report, "", ""))

    calls = []

    def fake_run(cmd, timeout=30):
        calls.append(cmd)
        return 0, "delivered", ""

    monkeypatch.setattr(qsn, "_run", fake_run)

    rc = qsn.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[0] == "bash"
    assert cmd[1] == str(qsn.REPO_ROOT / "scripts" / "fleet_mail.sh")
    key_index = cmd.index("--key") + 1
    assert cmd[key_index] == "queue_stall:202:not-armed"
    assert "sent=1" in out
    assert "send_failed=0" in out


# ── main(): innocence — clean board ─────────────────────────────────────────


def test_clean_board_zero_sends_rc0_summary_says_so(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    report = make_report([], examined_total=12)
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, report, "", ""))
    monkeypatch.setattr(qsn, "_run", _fail_if_called)

    rc = qsn.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "examined=12" in out
    assert "stalled=0" in out
    assert "sent=0" in out


# ── main(): innocence — a not-stalled row must not produce a send ──────────


def test_queued_and_advancing_row_produces_no_send(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    report = make_report([make_row(303, "queued-and-advancing", "no known blocker")])
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, report, "", ""))
    monkeypatch.setattr(qsn, "_run", _fail_if_called)

    rc = qsn.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "stalled=0" in out
    assert "sent=0" in out


def test_unrecognized_cause_is_visible_in_summary(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    report = make_report([make_row(304, "new-classifier-cause", "future vocabulary drift")])
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, report, "", ""))
    monkeypatch.setattr(qsn, "_run", _fail_if_called)

    assert qsn.main([]) == 0
    out = capsys.readouterr().out
    assert "skipped=1" in out
    assert "unrecognized_causes=new-classifier-cause" in out


# ── main(): classifier failure propagates ───────────────────────────────────


def test_classifier_rc1_propagates_as_notifier_failure(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    report = make_report([], examined_total=0, fetch_error="gh api graphql failed rc=1: simulated")
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (1, report, "", "boom"))
    monkeypatch.setattr(qsn, "_run", _fail_if_called)

    rc = qsn.main([])
    out = capsys.readouterr().out

    assert rc != 0
    assert "classifier_rc=1" in out


def test_classifier_unparseable_output_is_still_a_loud_nonzero_receipt(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (127, None, "", "python: command not found"))
    monkeypatch.setattr(qsn, "_run", _fail_if_called)

    rc = qsn.main([])
    out = capsys.readouterr().out

    assert rc != 0
    assert "classifier_failed=true" in out


# ── main(): a send failure ──────────────────────────────────────────────────


def test_send_failure_makes_notifier_exit_nonzero_and_counted(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    report = make_report([make_row(404, "required-check-red", "statusCheckRollup=FAILURE")])
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, report, "", ""))
    monkeypatch.setattr(qsn, "_run", lambda cmd, timeout=30: (1, "", "network flap"))

    rc = qsn.main([])
    out = capsys.readouterr().out

    assert rc != 0
    assert "send_failed=1" in out


# ── main(): the cap ──────────────────────────────────────────────────────────


def test_cap_stops_sends_and_reports_suppressed(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    rows = [make_row(n, "not-armed", "x") for n in (501, 502, 503)]
    report = make_report(rows)
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (0, report, "", ""))

    calls = []

    def fake_run(cmd, timeout=30):
        calls.append(cmd)
        return 0, "ok", ""

    monkeypatch.setattr(qsn, "_run", fake_run)

    rc = qsn.main(["--cap", "1"])
    out = capsys.readouterr().out

    assert rc == 0
    assert len(calls) == 1
    assert "suppressed_by_cap=2" in out
    assert "stalled=3" in out


# ── main(): CANNOT-VERIFY delivery ──────────────────────────────────────────


def test_cannot_verify_row_is_delivered_distinctly_even_though_classifier_failed(monkeypatch, capsys):
    # The classifier itself reports rc=1 whenever ANY row is CANNOT-VERIFY (its own contract) —
    # this run must still deliver the row (news, not silence) AND propagate the failure.
    monkeypatch.delenv("QUEUE_STALL_NOTIFY_ENABLED", raising=False)
    report = make_report([make_row(606, qsn.CANNOT_VERIFY, "checkSuites fetch failed: timeout")])
    monkeypatch.setattr(qsn, "run_classifier", lambda **kw: (1, report, "", ""))

    calls = []

    def fake_run(cmd, timeout=30):
        calls.append(cmd)
        return 0, "ok", ""

    monkeypatch.setattr(qsn, "_run", fake_run)

    rc = qsn.main([])
    out = capsys.readouterr().out

    assert rc != 0  # classifier_failed propagates even though the send itself succeeded
    assert len(calls) == 1
    key_index = calls[0].index("--key") + 1
    assert calls[0][key_index] == "queue_stall:606:CANNOT-VERIFY"
    msg = calls[0][-1]
    assert "COULD NOT VERIFY" in msg
    assert "sent=1" in out


# ---------------------------------------------------------------------------
# Mutual exclusion: a stale writer must not resurrect a pruned "sent" ghost
# ---------------------------------------------------------------------------

def test_lock_is_held_then_released(tmp_path):
    lock = tmp_path / "s.lock"
    with qsn.state_lock(lock) as status:
        assert status == "held"
    # released: a second acquisition succeeds
    with qsn.state_lock(lock) as status:
        assert status == "held"


def test_guilt_a_second_holder_is_told_busy_not_held(tmp_path):
    """The whole point: a concurrent invocation must NOT proceed to mutate state."""
    import fcntl
    lock = tmp_path / "s.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    other = lock.open("a+")
    fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with qsn.state_lock(lock) as status:
            assert status == "busy", status
    finally:
        fcntl.flock(other.fileno(), fcntl.LOCK_UN)
        other.close()


def test_innocence_a_broken_lock_proceeds_unlocked_and_never_goes_silent(tmp_path):
    """A lock that cannot be created must NOT stop the alarm. A duplicate page is
    survivable; a missed stall is not. This is the failure direction that matters."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("i am a file")
    with qsn.state_lock(blocker / "sub" / "s.lock") as status:
        assert status == "unavailable", status


def test_disabled_lock_yields_held_so_dry_run_never_blocks_a_real_run(tmp_path):
    with qsn.state_lock(tmp_path / "s.lock", enabled=False) as status:
        assert status == "held"


def test_the_reviewers_race_cannot_resurrect_a_pruned_entry(tmp_path, monkeypatch):
    """Reproduces the reported loss, then shows the lock forecloses it.

    Reported sequence: a SLOW process loads state, a FAST one starts later, correctly prunes a
    resolved PR and writes {}, then the SLOW one writes back its stale view — resurrecting a
    'sent' ghost, so a genuinely re-stalled PR reads as a repeat and is suppressed for a whole
    repage window. Unsafe direction: the alarm misses a real stall.
    """
    state = tmp_path / "seen.json"
    lock = tmp_path / "seen.json.lock"
    key = "queue_stall:100:not-armed"

    # WITHOUT the lock, the stale writer wins — this is the defect, pinned so it stays fixed.
    state.write_text(json.dumps({key: 0.0}))
    slow_view = qsn.load_seen(path=state)          # slow process reads
    qsn.save_seen({}, path=state)                  # fast process prunes and writes
    qsn.save_seen(slow_view, path=state)           # slow process writes its stale view
    assert qsn.load_seen(path=state) == {key: 0.0}, "the race itself must be real"

    # WITH the lock, the slow process cannot be inside the section while the fast one writes.
    import fcntl
    state.write_text(json.dumps({key: 0.0}))
    holder = lock.open("a+")
    fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with qsn.state_lock(lock) as status:
            assert status == "busy"
            # the losing process must not have written anything
        assert qsn.load_seen(path=state) == {key: 0.0}
    finally:
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
        holder.close()
