import importlib.util
import sys
from pathlib import Path

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


def test_count_diverged_malformed_json_is_zero() -> None:
    assert checks.count_diverged_probes("not-json") == 0


def test_classify_session_tail_detects_weekly_limit() -> None:
    tail = "You've hit your weekly limit - resets Jul 12 at 9am (Asia/Makassar)"

    assert checks.classify_session_tail(tail) == "rate_or_quota_limit"


def test_classify_session_tail_detects_auth_required() -> None:
    tail = "401 token_revoked refresh_token_reused"

    assert checks.classify_session_tail(tail) == "auth_required"


def test_classify_session_tail_leaves_unknown_failures_generic() -> None:
    tail = "unexpected process crash"

    assert checks.classify_session_tail(tail) == "session_error"
