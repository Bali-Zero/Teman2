"""The council-reserve observer accepts only a full pass of at least 3 tests."""

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "observe_council_reserve_seat.py"
_spec = importlib.util.spec_from_file_location("observe_council_reserve_seat", _PATH)
obs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(obs)


def test_accepts_full_pass():
    assert obs.summary_ok("3 passed, 990 deselected in 0.5s")
    assert obs.summary_ok("======= 5 passed in 1.20s =======")


def test_rejects_reduced_count():
    assert not obs.summary_ok("2 passed, 990 deselected in 0.5s")


def test_rejects_failed_skipped_error_and_missing():
    assert not obs.summary_ok("1 failed, 3 passed in 0.5s")
    assert not obs.summary_ok("3 passed, 1 skipped in 0.5s")
    assert not obs.summary_ok("3 passed, 1 error in 0.5s")
    assert not obs.summary_ok("3 passed, 1 warning in 0.5s")
    assert not obs.summary_ok("")
    assert not obs.summary_ok(None)


def test_observer_takes_no_arguments_marker():
    assert "# bites-observable" in _PATH.read_text()
