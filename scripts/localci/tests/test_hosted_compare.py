"""Guilt + innocence corpus for the read-only hosted-vs-local comparator."""
from __future__ import annotations

import importlib.util
import json
import re
import types
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parent.parent / "hosted_compare.py"
_spec = importlib.util.spec_from_file_location("hosted_compare_under_test", _MODULE)
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)

SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER = "f" * 40
REPO, BRANCH = "o/r", "main"
ACTIONS = 15368


def _status(results: dict, ctx_status="ok", sha=SHA):
    return {"run_id": "gate-ground", "overall": "BLOCKED", "candidate_sha": sha,
            "contexts": {"status": ctx_status, "required": list(results), "results": results}}


def _local(verdict, mapping="executed", check="ctx.x"):
    return {"mapping": mapping, "check": check, "verdict": verdict}


def _run(name, conclusion="success", status="completed", app_id=ACTIONS, at="2026-10-06T07:00:00Z", head_sha=SHA):
    return {"name": name, "status": status, "conclusion": conclusion, "completed_at": at, "head_sha": head_sha,
            "app": {"id": app_id, "slug": "github-actions" if app_id == ACTIONS else f"app-{app_id}"}}


def _st(context, state):
    return {"context": context, "state": state, "updated_at": "2026-10-06T09:00:00Z"}


def _req(*names, app_id=ACTIONS):
    return [{"context": n, "app_id": app_id} for n in names]


def _klass(report, name):
    return next(r["class"] for r in report["rows"] if r["context"] == name)


def _one(local, runs, statuses=(), app_id=ACTIONS):
    return _klass(hc.compare(_status({"a": _local(local)}), _req("a", app_id=app_id), list(runs), list(statuses)), "a")


def test_both_green_and_both_red_agree():
    rep = hc.compare(_status({"a": _local("OK"), "b": _local("FAIL")}), _req("a", "b"), [_run("a"), _run("b", "failure")], [])
    assert (_klass(rep, "a"), _klass(rep, "b")) == ("AGREE", "AGREE")
    assert rep["counts"]["AGREE"] == 2 and hc.exit_code(rep) == 0


def test_local_green_over_a_hosted_red_is_a_false_green_and_exits_1():
    rep = hc.compare(_status({"a": _local("OK")}), _req("a"), [_run("a", "failure")], [])
    assert _klass(rep, "a") == "FALSE_GREEN" and hc.exit_code(rep) == 1


def test_every_hosted_red_conclusion_is_red():
    for concl in ("failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"):
        assert _one("OK", [_run("a", concl)]) == "FALSE_GREEN", concl


def test_local_red_over_a_hosted_green_is_a_false_red_and_does_not_fail_the_run():
    rep = hc.compare(_status({"a": _local("FAIL")}), _req("a"), [_run("a")], [])
    assert _klass(rep, "a") == "FALSE_RED" and hc.exit_code(rep) == 0


def test_blocked_uncovered_and_unknown_local_verdicts_are_blind_never_green():
    for verdict in ("BLOCKED", "UNCOVERED", "ERROR", "QUEUED", "PASS", None):
        assert _one(verdict, [_run("a")]) == "LOCAL_BLIND", verdict


def test_a_contexts_file_that_is_not_ok_blinds_every_local_verdict():
    rep = hc.compare(_status({"a": _local("OK")}, ctx_status="missing"), _req("a"), [_run("a", "failure")], [])
    assert _klass(rep, "a") == "LOCAL_BLIND"


def test_hosted_skipped_satisfies_the_gate():
    assert _one("OK", [_run("a", "skipped")]) == "AGREE"


def test_a_pending_or_absent_hosted_verdict_is_incomplete_and_exits_3():
    for runs in ([_run("a", None, status="in_progress")], [], [_run("a"), _run("a", None, status="queued")], [_run("a", "a-new-conclusion")]):
        rep = hc.compare(_status({"a": _local("OK")}), _req("a"), runs, [])
        assert _klass(rep, "a") == "HOSTED_PENDING" and hc.exit_code(rep) == 3, runs


def test_a_red_anywhere_on_the_commit_is_red_whatever_the_order_or_the_timestamps():
    red_then_green = [_run("a", "failure", at="2026-10-06T03:30:00-05:00"), _run("a", "success", at="2026-10-06T08:00:00Z")]
    assert _one("OK", red_then_green) == "FALSE_GREEN" and _one("OK", red_then_green[::-1]) == "FALSE_GREEN"
    assert _one("OK", [_run("a", "success"), _run("a", "failure", at=None)]) == "FALSE_GREEN"
    assert _one("OK", [_run("a", "failure"), _run("a", "skipped", at="2026-10-06T23:00:00Z")]) == "FALSE_GREEN"


def test_a_same_named_commit_status_must_pass_too():
    assert _one("OK", [_run("a", "success")], [_st("a", "failure")], app_id=None) == "FALSE_GREEN"
    assert _one("OK", [_run("a", "success")], [_st("a", "error")], app_id=None) == "FALSE_GREEN"
    assert _one("OK", [_run("a", "success")], [_st("a", "pending")], app_id=None) == "HOSTED_PENDING"
    assert _one("OK", [], [_st("a", "success")], app_id=None) == "AGREE"


def test_a_pinned_context_is_satisfied_only_by_its_own_app():
    assert _one("OK", [_run("a", "failure"), _run("a", "success", app_id=999)]) == "FALSE_GREEN"
    assert _one("OK", [_run("a", "success", app_id=999)]) == "HOSTED_PENDING"
    assert _one("OK", [], [_st("a", "success")]) == "HOSTED_PENDING"
    assert _one("OK", [_run("a", "success"), _run("a", "failure", app_id=999)]) == "FALSE_GREEN"
    assert _one("OK", [_run("a", "success", app_id=999)], app_id=None) == "AGREE"


def test_drift_between_live_required_names_and_the_local_plan_exits_1():
    rep = hc.compare(_status({"a": _local("OK"), "gone": _local("OK")}), _req("a", "new"), [_run("a"), _run("new")], [])
    assert rep["drift"] == {"missing_locally": ["new"], "stale_locally": ["gone"]}
    assert _klass(rep, "new") == "LOCAL_BLIND" and hc.exit_code(rep) == 1


def test_contexts_without_a_pinned_source_app_are_listed():
    req = _req("a") + _req("b", app_id=None) + _req("c", app_id=-1) + _req("d", app_id=True)
    rep = hc.compare(_status({n: _local("OK") for n in "abcd"}), req, [_run(n) for n in "abcd"], [])
    assert rep["unpinned_source"] == ["b", "c", "d"]


@pytest.mark.parametrize("required", [[], None, [{}], [{"context": ""}], ["a"], _req("a", "a")])
def test_a_malformed_required_set_is_refused_never_skipped(required):
    with pytest.raises(hc.CompareError):
        hc.compare(_status({"a": _local("OK")}), required, [_run("a")], [])


def test_hosted_lists_that_are_not_lists_of_objects_are_refused():
    for runs, sts in ((None, []), ([_run("a")], None), (["x"], []), ([_run("a")], [1])):
        with pytest.raises(hc.CompareError):
            hc.compare(_status({"a": _local("OK")}), _req("a"), runs, sts)


def _fixture(tmp_path, results, **over):
    (tmp_path / "status.json").write_text(json.dumps(_status(results)))
    doc = {"repo": REPO, "branch": BRANCH, "sha": SHA, "required_checks": _req(*results, app_id=None),
           "check_runs": [_run(n) for n in results], "statuses": [], **over}
    (tmp_path / "fx.json").write_text(json.dumps(doc))
    return [str(tmp_path / "status.json"), "--repo", REPO, "--fixtures", str(tmp_path / "fx.json")]


def test_main_replays_a_bound_fixture_offline_and_writes_the_report(tmp_path, capsys):
    rc = hc.main(_fixture(tmp_path, {"a": _local("BLOCKED", "blocked", None)}))
    out = json.loads((tmp_path / "hosted_compare.json").read_text())
    assert rc == 0 and out["counts"]["LOCAL_BLIND"] == 1 and out["agreement"] == "0/1" and out["source"] == "fixtures"
    assert "LOCAL_BLIND" in capsys.readouterr().out


@pytest.mark.parametrize("over", [{"sha": OTHER}, {"repo": "o/other"}, {"branch": "dev"}, {"sha": None},
                                  {"check_runs": [_run("a", head_sha=OTHER)]}, {"required_checks": []}, {"required_checks": [{}]}])
def test_a_fixture_for_another_repo_branch_or_commit_is_refused(tmp_path, over):
    assert hc.main(_fixture(tmp_path, {"a": _local("OK")}, **over)) == 2
    assert not (tmp_path / "hosted_compare.json").exists()


def test_main_refuses_a_status_without_a_full_sha_or_a_bad_repo(tmp_path):
    argv = _fixture(tmp_path, {"a": _local("OK")})
    (tmp_path / "status.json").write_text(json.dumps(_status({"a": _local("OK")}, sha="abc123")))
    assert hc.main(argv) == 2
    (tmp_path / "status.json").write_text(json.dumps(_status({"a": _local("OK")})))
    assert hc.main([str(tmp_path / "status.json"), "--repo", "not a repo"]) == 2
    assert hc.main([str(tmp_path / "missing.json")]) == 2


def _fake_gh(monkeypatch, pages: dict):
    """Replace subprocess.run in the module: record every argv, answer from `pages` keyed by API path."""
    calls: list = []

    def run(argv, **_kw):
        calls.append(argv)
        body = pages.get(argv[-1])
        return types.SimpleNamespace(returncode=0 if body is not None else 1, stdout=json.dumps(body) if body is not None else "", stderr="HTTP 404")

    monkeypatch.setattr(hc.subprocess, "run", run)
    return calls


def _live_pages(runs_p1, statuses_pages):
    base = f"repos/{REPO}/commits/{SHA}"
    pages = {f"repos/{REPO}/branches/{BRANCH}/protection/required_status_checks": {"checks": _req("a", app_id=None)},
             f"{base}/check-runs?per_page=100&page=1": {"total_count": len(runs_p1), "check_runs": runs_p1}}
    for i, batch in enumerate(statuses_pages, start=1):
        pages[f"{base}/status?per_page=100&page={i}"] = {"state": "x", "statuses": batch}
    return pages


def test_the_live_path_issues_only_bare_gets(tmp_path, monkeypatch):
    (tmp_path / "status.json").write_text(json.dumps(_status({"a": _local("OK")})))
    calls = _fake_gh(monkeypatch, _live_pages([_run("a")], [[]]))
    assert hc.main([str(tmp_path / "status.json"), "--repo", REPO]) == 0
    assert len(calls) == 3
    for argv in calls:
        assert argv[:2] == ["gh", "api"] and len(argv) == 3, argv
        assert re.fullmatch(r"repos/o/r/(branches|commits)/[A-Za-z0-9_./?=&-]+", argv[2]), argv
    assert json.loads((tmp_path / "hosted_compare.json").read_text())["source"] == "live"


def test_a_red_status_on_the_second_page_is_read(tmp_path, monkeypatch):
    (tmp_path / "status.json").write_text(json.dumps(_status({"a": _local("OK")})))
    filler = [_st(f"other-{i}", "success") for i in range(100)]
    _fake_gh(monkeypatch, _live_pages([_run("a")], [filler, [_st("a", "failure")]]))
    assert hc.main([str(tmp_path / "status.json"), "--repo", REPO]) == 1
    assert json.loads((tmp_path / "hosted_compare.json").read_text())["counts"]["FALSE_GREEN"] == 1


def test_a_failed_or_truncated_live_read_is_refused(tmp_path, monkeypatch):
    (tmp_path / "status.json").write_text(json.dumps(_status({"a": _local("OK")})))
    filler = [_st(f"other-{i}", "success") for i in range(100)]
    _fake_gh(monkeypatch, _live_pages([_run("a")], [filler]))            # page 2 of statuses is a 404
    assert hc.main([str(tmp_path / "status.json"), "--repo", REPO]) == 2
    monkeypatch.setattr(hc, "MAX_PAGES", 1)
    _fake_gh(monkeypatch, _live_pages([_run("a")], [filler, []]))        # more pages than the cap allows
    assert hc.main([str(tmp_path / "status.json"), "--repo", REPO]) == 2
    assert not (tmp_path / "hosted_compare.json").exists()


# ------------------------------------------------------------------ coverage travels with the verdict (B3)
E2E_NOTE = "the six repository secrets are empty here"


def _cov(verdict, coverage, note=None, **kw):
    return {**_local(verdict, **kw), "coverage": coverage, **({"coverage_note": note} if note else {})}


def test_a_partial_agree_keeps_its_class_but_its_row_says_partial_and_it_is_counted_apart(tmp_path, capsys):
    # guilt: before B3 a partial AGREE read exactly like a full one, in the row, the counts and the printed table
    args = _fixture(tmp_path, {"E2E": _cov("OK", "partial", E2E_NOTE), "b": _cov("OK", "full")})
    assert hc.main(args) == 0
    out = json.loads((tmp_path / "hosted_compare.json").read_text())
    row = next(r for r in out["rows"] if r["context"] == "E2E")
    assert (row["class"], row["coverage"], row["coverage_note"]) == ("AGREE", "partial", E2E_NOTE)
    assert out["agreement"] == "2/2" and out["agreement_full"] == "1/2"
    assert out["coverage"] == {"compared_full": 1, "compared_partial": ["E2E"], "compared_unrecorded": [], "compared_skip_agreed": []}
    printed = capsys.readouterr().out
    assert re.search(r"^AGREE +GREEN\(1\) +GREEN +any +partial +E2E ", printed, re.M)
    assert "agreement_full=1/2 compared_full=1 compared_partial=1 ['E2E']" in printed


def test_every_full_context_counts_as_full_and_agreement_full_is_the_agreement():
    rep = hc.compare(_status({"a": _cov("OK", "full"), "b": _cov("FAIL", "full")}), _req("a", "b"), [_run("a"), _run("b", "failure")], [])
    assert rep["coverage"] == {"compared_full": 2, "compared_partial": [], "compared_unrecorded": [], "compared_skip_agreed": []} and rep["agreement_full"] == rep["agreement"] == "2/2"
    assert [r["coverage"] for r in rep["rows"]] == ["full", "full"]


@pytest.mark.parametrize("coverage", [None, "", "FULL", "complete", 1, ["full"]])
def test_a_result_that_records_no_readable_coverage_is_unrecorded_never_full(coverage):
    res = _local("OK") if coverage is None else _cov("OK", coverage)
    rep = hc.compare(_status({"a": res}), _req("a"), [_run("a")], [])
    assert rep["rows"][0]["class"] == "AGREE" and rep["rows"][0]["coverage"] == "unrecorded"
    assert rep["coverage"] == {"compared_full": 0, "compared_partial": [], "compared_unrecorded": ["a"], "compared_skip_agreed": []} and rep["agreement_full"] == "0/1"


def test_a_partial_context_still_reports_its_false_green_and_fails_the_run():
    rep = hc.compare(_status({"E2E": _cov("OK", "partial", E2E_NOTE)}), _req("E2E"), [_run("E2E", "failure")], [])
    assert _klass(rep, "E2E") == "FALSE_GREEN" and hc.exit_code(rep) == 1 and rep["coverage"]["compared_partial"] == ["E2E"]


def test_a_blind_partial_context_is_not_counted_as_compared_at_all():
    rep = hc.compare(_status({"E2E": _cov("ERROR", "partial", E2E_NOTE)}), _req("E2E"), [_run("E2E")], [])
    assert _klass(rep, "E2E") == "LOCAL_BLIND" and rep["coverage"] == {"compared_full": 0, "compared_partial": [], "compared_unrecorded": [], "compared_skip_agreed": []}


# ------------------------------------------------------------------ a host out of disk is no verdict (B3)
@pytest.mark.parametrize("hosted", ["success", "failure"])
@pytest.mark.parametrize("verdict,code", [("ERROR", "host_disk_full"), ("BLOCKED", "host_disk_below_floor 9.8GB<12GB")])
def test_a_context_the_host_could_not_judge_is_blind_never_false_red_and_never_agree(hosted, verdict, code):
    # guilt: before B3 the same run read FAIL here, and FALSE_RED beside a hosted green (Backend Tests, B2 final head)
    res = {**_cov(verdict, "full"), "no_verdict": code}
    rep = hc.compare(_status({"a": res}), _req("a"), [_run("a", hosted)], [])
    assert _klass(rep, "a") == "LOCAL_BLIND" and rep["rows"][0]["local_detail"] == f"{verdict} (executed) {code}"
    assert rep["counts"]["FALSE_RED"] == 0 and rep["coverage"]["compared_full"] == 0
