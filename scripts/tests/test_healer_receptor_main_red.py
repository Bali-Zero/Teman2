"""Guilt + innocence for healer_receptor_main_red.py (receptor 8).

Fixture = the shape measured on 2026-09-09: main HEAD is a docs-only merge where
`Backend Static (Python)` is `skipped`, the same context is `failure` on the
commit two back (pip-audit httpx2 CVE), everything else green. A HEAD-only
reader says GREEN there; this receptor must say RED, escalate HIGH once, dedupe
on the next tick, resolve when a newer sha turns green, and NEVER rerun.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[1] / "healer_receptor_main_red.py"
_spec = importlib.util.spec_from_file_location("healer_receptor_main_red", _MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
sys.modules["healer_receptor_main_red"] = mod
_spec.loader.exec_module(mod)

HEAD, MID, OLD = "a" * 40, "b" * 40, "c" * 40
STATIC, TESTS, E2E = "Backend Static (Python)", "Backend Tests (Python)", "E2E Tests (Playwright)"
JOB_URL = "https://github.com/o/r/actions/runs/111/job/222"      # the aggregator job
STATIC_URL = "https://github.com/o/r/actions/runs/111/job/333"   # the root-cause job


def _run(name, conclusion, url="", status="completed", completed="2026-09-09T01:00:00Z"):
    return {"name": name, "conclusion": conclusion, "status": status,
            "html_url": url, "completed_at": completed}


def fixture(static_on_head="skipped", static_on_mid="failure", head_in_progress=False):
    head_runs = [_run(STATIC, static_on_head, STATIC_URL), _run(TESTS, "skipped"), _run(E2E, "success")]
    if head_in_progress:
        head_runs.append(_run(E2E, None, status="in_progress"))
    return {
        "repos/{owner}/{repo}/branches/main/protection/required_status_checks":
            {"contexts": [STATIC, TESTS, E2E]},
        "repos/{owner}/{repo}/rules/branches/main": [],
        "repos/{owner}/{repo}/commits?sha=main&per_page=20":
            [{"sha": HEAD}, {"sha": MID}, {"sha": OLD}],
        f"repos/{{owner}}/{{repo}}/commits/{HEAD}/check-runs?per_page=100": {"check_runs": head_runs},
        f"repos/{{owner}}/{{repo}}/commits/{MID}/check-runs?per_page=100": {"check_runs": [
            _run(STATIC, static_on_mid, STATIC_URL), _run(TESTS, "failure", JOB_URL),
            # an older SKIPPED run of the same context on the same sha must not mask the verdict
            _run(STATIC, "skipped", completed="2026-09-08T00:00:00Z")]},
        f"repos/{{owner}}/{{repo}}/commits/{OLD}/check-runs?per_page=100": {"check_runs": [
            _run(STATIC, "success"), _run(TESTS, "success"), _run(E2E, "success")]},
        # the required context (job 222) is an AGGREGATOR; the root cause is the
        # sibling job 333 (not required) which finished first
        "repos/{owner}/{repo}/actions/runs/111/jobs?per_page=100": {"jobs": [
            {"id": 222, "name": TESTS, "conclusion": "failure", "completed_at": "2026-09-09T01:01:00Z",
             "steps": [{"name": "Assert every upstream job succeeded", "conclusion": "failure"}]},
            {"id": 333, "name": STATIC, "conclusion": "failure", "completed_at": "2026-09-09T00:57:00Z",
             "steps": [{"name": "Install", "conclusion": "success"},
                       {"name": "pip-audit", "conclusion": "failure"}]},
            {"id": 444, "name": "MCP Server Tests", "conclusion": "success", "completed_at": "2026-09-09T00:58:00Z",
             "steps": []}]},
        "repos/{owner}/{repo}/actions/jobs/333/logs":
            "2026-09-09T00:57:25.5Z \x1b[36;1mFound 3 known vulnerabilities\x1b[0m\n"
            "2026-09-09T00:57:25.6Z httpx2 2.10.0  CVE-2026-84382 2.12.0\n"
            "2026-09-09T00:57:25.7Z ##[error]Process completed with exit code 1.\n",
    }


class FakeGh:
    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, path):
        self.calls.append(path)
        if path not in self.table:
            raise mod.GhError(f"unmapped {path}")
        return self.table[path]


def _go(gh, tmp_path, **kw):
    kw.setdefault("state_path", tmp_path / "state.json")
    kw.setdefault("escalations", tmp_path / "esc.jsonl")
    kw.setdefault("writer", "testhost")
    kw.setdefault("now", 1_000.0)
    return mod.run(gh=gh, **kw)


def _lines(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


# ---------------- guilt ----------------
def test_red_two_commits_back_is_red_and_escalates_high(tmp_path):
    gh = FakeGh(fixture())
    rc, rep = _go(gh, tmp_path)
    assert rc == 1
    assert rep["red"] == sorted([STATIC, TESTS])
    assert rep["states"][STATIC] == {**rep["states"][STATIC], "state": "red", "sha": MID, "depth": 1}
    assert rep["states"][E2E]["state"] == "green"
    lines = _lines(tmp_path / "esc.jsonl")
    static = [l for l in lines if l["context"] == STATIC][0]
    assert static["priority"] == "HIGH" and static["status"] == "pending"
    assert static["job"] == "main-required-red:backend-static-python"
    assert static["failed_steps"] == ["pip-audit"]
    assert [j["name"] for j in static["failed_jobs"]] == [TESTS, STATIC]
    assert "CVE-2026-84382" in static["log_tail"] and "\x1b" not in static["log_tail"]
    tests = [l for l in lines if l["context"] == TESTS][0]
    assert tests["failed_steps"] == ["Assert every upstream job succeeded"]
    assert tests["log_job"] == STATIC and "pip-audit" in tests["error_summary"]
    assert "CVE-2026-84382" in tests["log_tail"]  # aggregator line carries the ROOT log
    assert static["cure_lane"]["owner"] == "session"
    assert static["cure_lane"]["branch"].endswith("/infra/main-red-backend-static-python")
    assert rep["board"]["escalated"] == [f"{STATIC}@{MID}", f"{TESTS}@{MID}"]
    # ts is numeric like every other board writer: read_all_escalations() sorts on it.
    assert all(isinstance(l["ts"], float) for l in lines)


def test_same_red_second_tick_is_deduped(tmp_path):
    gh = FakeGh(fixture())
    _go(gh, tmp_path)
    rc, rep = _go(gh, tmp_path, now=2_000.0)
    assert rc == 1 and rep["board"]["escalated"] == []
    assert len([l for l in _lines(tmp_path / "esc.jsonl") if l["status"] == "pending"]) == 2


def test_new_sha_still_red_escalates_again_and_green_resolves(tmp_path):
    gh = FakeGh(fixture())
    _go(gh, tmp_path)
    cured = fixture(static_on_head="success")
    cured[f"repos/{{owner}}/{{repo}}/commits/{HEAD}/check-runs?per_page=100"]["check_runs"][1] = \
        _run(TESTS, "success")
    rc, rep = _go(FakeGh(cured), tmp_path, now=3_000.0)
    assert rc == 0 and sorted(rep["board"]["resolved"]) == sorted([STATIC, TESTS])
    resolved = [l for l in _lines(tmp_path / "esc.jsonl") if l["status"] == "resolved"]
    assert {l["job"] for l in resolved} == {"main-required-red:backend-static-python",
                                            "main-required-red:backend-tests-python"}
    assert all(isinstance(l["ts"], float) and isinstance(l["resolved_at"], float) for l in resolved)
    # The mixed board (pending + resolved) must sort: this is the TypeError the string ts caused.
    sorted(_lines(tmp_path / "esc.jsonl"), key=lambda e: e.get("ts", 0), reverse=True)
    assert json.loads((tmp_path / "state.json").read_text())["open"] == {}


def test_blind_when_protection_unreadable(tmp_path):
    t = fixture()
    del t["repos/{owner}/{repo}/branches/main/protection/required_status_checks"]
    rc, rep = _go(FakeGh(t), tmp_path)
    assert rc == 2 and rep["blind"]
    assert not (tmp_path / "esc.jsonl").exists()


# ---------------- innocence ----------------
def test_all_green_is_green_and_writes_nothing(tmp_path):
    t = fixture(static_on_head="success", static_on_mid="success")
    t[f"repos/{{owner}}/{{repo}}/commits/{HEAD}/check-runs?per_page=100"]["check_runs"][1] = \
        _run(TESTS, "success")
    rc, rep = _go(FakeGh(t), tmp_path)
    assert rc == 0 and rep["red"] == []
    assert not (tmp_path / "esc.jsonl").exists()


def test_green_on_head_beats_older_red(tmp_path):
    t = fixture(static_on_head="success")
    t[f"repos/{{owner}}/{{repo}}/commits/{HEAD}/check-runs?per_page=100"]["check_runs"][1] = \
        _run(TESTS, "success")
    rc, rep = _go(FakeGh(t), tmp_path)
    assert rc == 0 and rep["states"][STATIC]["depth"] == 0


def test_non_required_failure_is_ignored(tmp_path):
    t = fixture(static_on_head="success", static_on_mid="success")
    runs = t[f"repos/{{owner}}/{{repo}}/commits/{HEAD}/check-runs?per_page=100"]["check_runs"]
    runs[1] = _run(TESTS, "success")
    runs.append(_run("npm audit (advisory)", "failure"))
    rc, rep = _go(FakeGh(t), tmp_path)
    assert rc == 0 and "npm audit (advisory)" not in rep["states"]


def test_in_progress_on_head_is_pending_not_red(tmp_path):
    t = fixture(static_on_head="success", static_on_mid="success", head_in_progress=True)
    t[f"repos/{{owner}}/{{repo}}/commits/{HEAD}/check-runs?per_page=100"]["check_runs"][1] = \
        _run(TESTS, "success")
    rc, rep = _go(FakeGh(t), tmp_path)
    assert rc == 0 and rep["states"][E2E]["state"] == "pending"


def test_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setenv(mod.KILL_SWITCH_ENV, "1")
    gh = FakeGh(fixture())
    rc, rep = _go(gh, tmp_path)
    assert rc == 0 and rep["disabled"] and gh.calls == []


def test_no_escalate_senses_without_touching_board_or_state(tmp_path):
    rc, rep = _go(FakeGh(fixture()), tmp_path, escalate=False)
    assert rc == 1 and rep["red"]
    assert not (tmp_path / "esc.jsonl").exists() and not (tmp_path / "state.json").exists()


def test_never_reruns():
    tree = ast.parse(_MOD_PATH.read_text(encoding="utf-8"))
    tree.body = tree.body[1:]  # drop the module docstring, which NAMES the forbidden call
    code = ast.unparse(tree)
    assert not re.search(r"run\s+rerun|rerun-failed|actions/runs/\S*/rerun", code)
    gh = FakeGh(fixture())
    mod.run(gh=gh, escalate=False)
    assert not any("rerun" in c for c in gh.calls)
