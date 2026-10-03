"""Guilt + innocence corpus for the inert ``pro/local-ci`` status adapter."""
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parent.parent / "gh_status_adapter.py"
_spec = importlib.util.spec_from_file_location("gh_status_adapter_under_test", _MODULE)
adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adapter)

SHA = "0123456789abcdef0123456789abcdef01234567"


def _status(overall="PASS", run_id="lci-20260926T152929Z-25281807", checks=None, sha=SHA):
    body = {"run_id": run_id, "overall": overall, "candidate_sha": sha,
            "checks": checks if checks is not None else {
                "a": {"status": "PASS", "reason": "rc=0"},
                "b": {"status": "NOT_APPLICABLE", "reason": "domain untouched"}}}
    return body


def _write(tmp_path, body) -> Path:
    p = tmp_path / "status.json"
    p.write_text(json.dumps(body))
    return p


@pytest.fixture
def no_subprocess(monkeypatch):
    def boom(*a, **k):
        raise AssertionError(f"subprocess must not run in this phase: {a!r}")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.delenv("LOCALCI_ADAPTER_ARMED", raising=False)
    monkeypatch.delenv("LOCALCI_ADAPTER_PHASE", raising=False)


@pytest.mark.parametrize("overall,state", [
    ("PASS", "success"),
    ("FAIL", "failure"),
    ("ERROR", "failure"),
    ("BLOCKED", "error"),
    ("STALE", "error"),
    ("INTERRUPTED", "error"),
    ("SUBSET_PASS", "pending"),
    ("SOMETHING_NEW", "error"),
    ("pass", "error"),
    ("", "error"),
    (None, "error"),
    (7, "error"),
])
def test_mapping_table(overall, state):
    assert adapter.build_payload(_status(overall=overall))["state"] == state


def test_only_a_full_pass_is_ever_success():
    for overall in list(adapter.STATE_BY_OVERALL) + ["SUBSET_PASS", "UNKNOWN", None]:
        state = adapter.build_payload(_status(overall=overall))["state"]
        assert (state == "success") == (overall == "PASS"), overall


def test_subset_pass_is_pending_and_says_it_is_not_parity():
    payload = adapter.build_payload(_status(overall="SUBSET_PASS"))
    assert payload["state"] == "pending"
    assert payload["description"].startswith("SUBSET (not parity)")


def test_context_is_always_the_non_required_comparison_context():
    for overall in ("PASS", "FAIL", "SUBSET_PASS", None):
        assert adapter.build_payload(_status(overall=overall))["context"] == "pro/local-ci"


def test_description_carries_run_id_and_counts():
    checks = {"p1": {"status": "PASS"}, "p2": {"status": "PASS"}, "f": {"status": "FAIL"},
              "e": {"status": "ERROR"}, "n": {"status": "NOT_APPLICABLE"}, "x": "garbage"}
    desc = adapter.build_payload(_status(overall="FAIL", checks=checks))["description"]
    assert "lci-20260926T152929Z-25281807" in desc
    assert "PASS 2" in desc and "FAIL 2" in desc and "other 2" in desc


def test_description_never_exceeds_140_chars_even_for_absurd_input():
    huge = {f"c{i}": {"status": "PASS"} for i in range(5000)}
    for overall in ("PASS", "SUBSET_PASS", "INTERRUPTED", "X" * 500):
        desc = adapter.build_payload(_status(overall=overall, run_id="r" * 900, checks=huge))["description"]
        assert len(desc) <= 140, (overall, len(desc))
        assert "PASS 5000" in desc or len(desc) == 140


def test_missing_run_id_is_refused_not_invented():
    with pytest.raises(adapter.AdapterError):
        adapter.build_payload({"overall": "PASS", "candidate_sha": SHA, "checks": {}})


@pytest.mark.parametrize("sha", [None, "", "abc123", "Z" * 40, SHA.upper(), SHA + "0"])
def test_a_bad_sha_builds_no_url(sha):
    with pytest.raises(adapter.AdapterError):
        adapter.build_url("Bali-Zero/Teman2", sha)


@pytest.mark.parametrize("repo", ["", "nogslash", "a/b/c", "a b/c", "a/../b;rm"])
def test_a_bad_repo_builds_no_url(repo):
    with pytest.raises(adapter.AdapterError):
        adapter.build_url(repo, SHA)


def test_url_shape():
    assert adapter.build_url("Bali-Zero/Teman2", SHA) == f"repos/Bali-Zero/Teman2/statuses/{SHA}"


def test_dry_run_writes_the_file_and_never_calls_subprocess(tmp_path, no_subprocess, capsys):
    status = _write(tmp_path, _status(overall="SUBSET_PASS"))
    out = tmp_path / "out"
    rc = adapter.main([str(status), "--out", str(out)])
    assert rc == 0
    record = json.loads((out / "adapter_dryrun.json").read_text())
    assert set(record) == {"payload", "url", "would_post"}
    assert record["would_post"] is False
    assert record["url"] == f"repos/Bali-Zero/Teman2/statuses/{SHA}"
    assert record["payload"]["state"] == "pending"
    assert json.loads(capsys.readouterr().out) == record


def test_explicit_dry_run_flag_is_the_same_as_the_default(tmp_path, no_subprocess):
    status = _write(tmp_path, _status())
    assert adapter.main([str(status), "--dry-run", "--out", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "adapter_dryrun.json").exists()


def test_out_defaults_to_the_status_directory(tmp_path, no_subprocess):
    status = _write(tmp_path, _status())
    assert adapter.main([str(status)]) == 0
    assert (tmp_path / "adapter_dryrun.json").exists()


def test_post_and_dry_run_together_are_rejected(tmp_path, no_subprocess):
    status = _write(tmp_path, _status())
    with pytest.raises(SystemExit) as exc:
        adapter.main([str(status), "--post", "--dry-run"])
    assert exc.value.code != 0


def test_post_without_arming_is_refused_and_touches_nothing(tmp_path, no_subprocess, capsys):
    status = _write(tmp_path, _status())
    rc = adapter.main([str(status), "--post", "--out", str(tmp_path / "o")])
    cap = capsys.readouterr()
    assert rc == adapter.EXIT_POST_REFUSED != 0
    assert "REFUSED" in cap.err and "LOCALCI_ADAPTER_ARMED=1" in cap.err
    assert '"gh"' in cap.out
    assert not (tmp_path / "o").exists()


def test_armed_but_not_live_is_still_refused(tmp_path, no_subprocess, monkeypatch, capsys):
    monkeypatch.setenv("LOCALCI_ADAPTER_ARMED", "1")
    status = _write(tmp_path, _status())
    rc = adapter.main([str(status), "--post"])
    assert rc == adapter.EXIT_POST_REFUSED
    assert "LOCALCI_ADAPTER_PHASE=live" in capsys.readouterr().err


def test_live_phase_without_arming_is_still_refused(tmp_path, no_subprocess, monkeypatch):
    monkeypatch.setenv("LOCALCI_ADAPTER_PHASE", "live")
    status = _write(tmp_path, _status())
    assert adapter.main([str(status), "--post"]) == adapter.EXIT_POST_REFUSED


def test_arming_without_the_post_flag_never_posts(tmp_path, no_subprocess, monkeypatch):
    monkeypatch.setenv("LOCALCI_ADAPTER_ARMED", "1")
    monkeypatch.setenv("LOCALCI_ADAPTER_PHASE", "live")
    status = _write(tmp_path, _status())
    assert adapter.main([str(status), "--out", str(tmp_path / "o")]) == 0


def test_only_all_three_conditions_reach_gh_and_it_is_gh_api(tmp_path, monkeypatch):
    calls = []

    def fake(argv, **kw):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setenv("LOCALCI_ADAPTER_ARMED", "1")
    monkeypatch.setenv("LOCALCI_ADAPTER_PHASE", "live")
    status = _write(tmp_path, _status(overall="SUBSET_PASS"))
    assert adapter.main([str(status), "--post"]) == 0
    assert len(calls) == 1
    argv = calls[0]
    assert argv[:2] == ["gh", "api"] and f"repos/Bali-Zero/Teman2/statuses/{SHA}" in argv
    assert "state=pending" in argv and "context=pro/local-ci" in argv


def test_a_broken_status_file_exits_2_and_writes_nothing(tmp_path, no_subprocess):
    for body in ("not json", "[1, 2]", json.dumps({"overall": "PASS"}),
                 json.dumps(_status(sha="deadbeef"))):
        p = tmp_path / "status.json"
        p.write_text(body)
        out = tmp_path / "out"
        assert adapter.main([str(p), "--out", str(out)]) == adapter.EXIT_BAD_INPUT
        assert not out.exists()
    assert adapter.main([str(tmp_path / "missing.json")]) == adapter.EXIT_BAD_INPUT


def test_no_http_client_is_imported():
    tree = ast.parse(_MODULE.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"requests", "urllib", "urllib3", "http", "httpx", "aiohttp"}
