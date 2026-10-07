import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_MOD_PATH = Path(os.environ.get(
    "HEALER_RUN_CHECKS_UNDER_TEST", Path(__file__).resolve().parents[1] / "healer_run_checks.py"
))
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


def test_summarize_registry_branch_table() -> None:
    rows = {
        "cure-missing-is-session": [{"id": "a"}],
        "cure-session": [{"id": "a", "cure": "session"}],
        "cure-owner": [{"id": "a", "cure": "owner"}],
        "mixed": [{"id": "a", "cure": "owner"}, {"id": "b", "cure": "session"}],
    }
    got = {row: checks.summarize_registry(json.dumps({"dead": dead})) for row, dead in rows.items()}
    assert got == {
        "cure-missing-is-session": (["a"], ["a"]),
        "cure-session": (["a"], ["a"]),
        "cure-owner": (["a"], []),
        "mixed": (["a", "b"], ["b"]),
    }


@pytest.mark.parametrize("raw", [
    "not-json", "null", "[]", "{}", '{"dead": {}}', '{"dead": [1]}',
    '{"dead": [{"id": "a", "cure": "Owner"}]}', '{"dead": [{"id": "a", "cure": null}]}',
    '{"dead": [{"id": "a", "cure": ["owner"]}]}', '{"dead": [{"id": "a", "cure": "pr"}]}',
])
def test_summarize_registry_rejects_malformed_or_undeclared_cure(raw: str) -> None:
    with pytest.raises(checks.ProbeReportError):
        checks.summarize_registry(raw)


def test_registry_findings_branch_table() -> None:
    rows = {
        "bucket-absent-is-none": {"dead": []},
        "named": {"dead": [], "findings": [{"id": "kbli"}, {"id": "launchd"}]},
        "id-missing": {"dead": [], "findings": [{}]},
    }
    got = {row: checks.registry_findings(json.dumps(data)) for row, data in rows.items()}
    assert got == {
        "bucket-absent-is-none": [],
        "named": ["kbli", "launchd"],
        "id-missing": ["(unknown)"],
    }


@pytest.mark.parametrize("raw", [
    "not-json", "[]", '{"findings": "kbli"}', '{"findings": [1]}', '{"findings": null}',
])
def test_registry_findings_rejects_a_malformed_bucket(raw: str) -> None:
    with pytest.raises(checks.ProbeReportError):
        checks.registry_findings(raw)


def test_registry_summary_cli_prints_findings_after_dead() -> None:
    raw = json.dumps({"dead": [{"id": "a", "cure": "owner"}], "findings": [{"id": "k"}]})
    out = subprocess.run(
        [sys.executable, str(_MOD_PATH), "registry-summary"],
        input=raw, capture_output=True, text=True, check=True,
    ).stdout
    assert out == "1\n0\na\n1\nk\n"


def test_summarize_home_fork_branch_table(tmp_path, monkeypatch) -> None:
    mine = tmp_path / "mine.sh"
    mine.write_text("x\n")
    readonly = tmp_path / "readonly.sh"
    readonly.write_text("x\n")
    readonly.chmod(0o444)
    rootish = tmp_path / "rootish.sh"
    rootish.write_text("x\n")
    (tmp_path / "home").mkdir()
    (tmp_path / "home/tilde.sh").write_text("x\n")
    (tmp_path / "home/tilde.sh").chmod(0o444)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    real_stat = Path.stat

    def stat(self, *a, **kw):
        result = real_stat(self, *a, **kw)
        if self.name == "rootish.sh":
            return os.stat_result((result.st_mode, result.st_ino, result.st_dev,
                                   result.st_nlink, 0, 0, result.st_size,
                                   0, 0, 0))
        return result

    monkeypatch.setattr(Path, "stat", stat)
    absent = "DIVERGED: scripts/x.sh is absent from this checkout — the CHECKOUT is the stale side"
    rows = {
        "writable-own-innocence": f"DIVERGED: {mine} != scripts/mine.sh — a fix is stranded",
        "not-writable-guilt": f"DIVERGED: {readonly} != scripts/readonly.sh — a fix is stranded",
        "uid0-writable-guilt": f"DIVERGED: {rootish} != scripts/rootish.sh — a fix is stranded",
        "origin-main-form-guilt": f"DIVERGED: {readonly} != origin/main:scripts/r.sh (absent from this checkout)",
        "no-repo-twin-guilt": f"NO-REPO-TWIN: {readonly} executes live but scripts/r.sh is not in the repo",
        "no-repo-twin-innocence": f"NO-REPO-TWIN: {mine} executes live but scripts/m.sh is not in the repo",
        "stat-error-innocence": f"DIVERGED: {tmp_path / 'gone.sh'} != scripts/gone.sh — a fix is stranded",
        "tilde-expanded-guilt": "DIVERGED: ~/tilde.sh != scripts/tilde.sh — a fix is stranded",
        "unrecognised-line-innocence": absent,
    }
    got = {}
    for row, line in rows.items():
        _paths, curable = checks.summarize_home_fork(json.dumps({"check_breaches": [line]}))
        got[row] = "session" if curable else "owner"
    assert got == {
        "writable-own-innocence": "session", "not-writable-guilt": "owner",
        "uid0-writable-guilt": "owner", "origin-main-form-guilt": "owner",
        "no-repo-twin-guilt": "owner", "no-repo-twin-innocence": "session",
        "stat-error-innocence": "session", "tilde-expanded-guilt": "owner",
        "unrecognised-line-innocence": "session",
    }
    assert checks.summarize_home_fork(json.dumps({"check_breaches": [absent]})) == ([absent[:80]], [absent[:80]])


@pytest.mark.parametrize("raw", ["not-json", "null", "[]", "{}", '{"check_breaches": "x"}', '{"check_breaches": [1]}'])
def test_summarize_home_fork_rejects_malformed_report(raw: str) -> None:
    with pytest.raises(checks.ProbeReportError):
        checks.summarize_home_fork(raw)
