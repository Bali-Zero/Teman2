import importlib.util
import sys
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[1] / "healer_run_checks.py"
_spec = importlib.util.spec_from_file_location("healer_run_checks", _MOD_PATH)
checks = importlib.util.module_from_spec(_spec)
sys.modules["healer_run_checks"] = checks
_spec.loader.exec_module(checks)


def test_count_diverged_uses_current_status_schema() -> None:
    raw = '{"probes":[{"id":"a","status":"DIVERGED"},{"id":"b","status":"OK"}]}'

    assert checks.count_diverged_probes(raw) == 1


def test_count_diverged_keeps_legacy_verdict_schema() -> None:
    raw = '{"probes":[{"id":"a","verdict":"DIVERGED"},{"id":"b","verdict":"OK"}]}'

    assert checks.count_diverged_probes(raw) == 1


@pytest.mark.parametrize("raw", ["not-json", "null", "[]", "{}", '{"probes": {}}', '{"probes": []}'])
def test_count_diverged_invalid_report_raises(raw: str) -> None:
    with pytest.raises(checks.ProbeReportError):
        checks.count_diverged_probes(raw)


@pytest.mark.parametrize("raw", ["not-json", "null", "[]", "{}", '{"probes": {}}', '{"probes": []}'])
def test_count_diverged_main_invalid_report_returns_three(raw, monkeypatch, capsys) -> None:
    monkeypatch.setattr(checks, "_read_stdin", lambda: raw)

    assert checks.main(["x", "count-diverged"]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip()


def test_classify_session_tail_detects_weekly_limit() -> None:
    tail = "You've hit your weekly limit - resets Jul 12 at 9am (Asia/Makassar)"

    assert checks.classify_session_tail(tail) == "rate_or_quota_limit"


def test_classify_session_tail_detects_auth_required() -> None:
    tail = "401 token_revoked refresh_token_reused"

    assert checks.classify_session_tail(tail) == "auth_required"


def test_classify_session_tail_leaves_unknown_failures_generic() -> None:
    tail = "unexpected process crash"

    assert checks.classify_session_tail(tail) == "session_error"
