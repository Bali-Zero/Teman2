"""The council-reserve observer accepts only a full pass of exactly the 2 pinned tests."""

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "observe_council_reserve_seat.py"
_spec = importlib.util.spec_from_file_location("observe_council_reserve_seat", _PATH)
obs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(obs)


def test_accepts_full_pass():
    assert obs.summary_ok("2 passed in 0.5s")
    assert obs.summary_ok("======= 2 passed in 1.20s =======")


def test_rejects_reduced_or_inflated_count_and_deselection():
    assert not obs.summary_ok("1 passed in 0.5s")
    assert not obs.summary_ok("3 passed in 0.5s")
    assert not obs.summary_ok("2 passed, 990 deselected in 0.5s")


def test_rejects_failed_skipped_error_and_missing():
    assert not obs.summary_ok("1 failed, 3 passed in 0.5s")
    assert not obs.summary_ok("2 passed, 1 skipped in 0.5s")
    assert not obs.summary_ok("2 passed, 1 error in 0.5s")
    assert not obs.summary_ok("2 passed, 1 warning in 0.5s")
    assert not obs.summary_ok("")
    assert not obs.summary_ok(None)


def test_explicit_node_ids_name_both_gemini_tests():
    assert len(obs.NODE_IDS) == obs.EXPECTED_TESTS == 2
    assert any(n.endswith("test_gemini4_argon_high_counts_toward_quorum_only_with_substitution_note") for n in obs.NODE_IDS)
    assert any(n.endswith("test_retired_gemini_3_1_pro_no_longer_counts_toward_quorum") for n in obs.NODE_IDS)


def test_main_ignores_arguments_and_runs_only_the_pinned_node_ids(monkeypatch, capsys):
    seen = {}

    class _Done:
        returncode = 0
        stdout = "2 passed in 0.1s"
        stderr = ""

    def _fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return _Done()

    monkeypatch.setattr(obs.subprocess, "run", _fake_run)
    monkeypatch.setattr(obs.sys, "argv", ["observe", "--evil", "rm -rf /"])
    assert obs.main() == 0
    assert "--evil" not in seen["cmd"] and "rm -rf /" not in seen["cmd"]
    assert tuple(seen["cmd"][3:5]) == obs.NODE_IDS
    assert "-k" not in seen["cmd"]
    assert "allowlist semantics hold" in capsys.readouterr().out


def test_main_fails_closed_when_the_run_is_reduced(monkeypatch):
    class _Done:
        returncode = 0
        stdout = "1 passed in 0.1s"
        stderr = ""

    monkeypatch.setattr(obs.subprocess, "run", lambda cmd, **kw: _Done())
    assert obs.main() != 0
