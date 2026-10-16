"""B31: the label read-back and the pre-flip census. GitHub is faked; nothing here writes to it."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from .fixture_repo import runner  # noqa: F401 — puts scripts/localci on sys.path like its siblings
from localci import label_census as lc  # noqa: E402
from localci import label_intent as _li  # noqa: E402

mg = lc.mg
PUSH, BEFORE, AFTER = "2026-10-14T10:00:00Z", "2026-10-14T09:00:00Z", "2026-10-14T11:00:00Z"
ROLES = {"boss": "admin", "maint": "maintain", "writer": "write"}


def pr(n, *, label=True, actor=("User", "boss"), at=AFTER, auto=True, draft=False, queue=False, head=None):
    ev = [{"__typename": "LabeledEvent", "createdAt": at, "label": {"name": mg.ARM_LABEL}, "actor": {"__typename": actor[0], "login": actor[1]}}] if label else []
    return {"number": n, "title": f"pr {n}", "isDraft": draft, "headRefOid": head or f"{n:040x}", "isInMergeQueue": queue,
            "autoMergeRequest": {"enabledAt": "x"} if auto else None, "labels": {"nodes": [{"name": mg.ARM_LABEL}] if label else []},
            "timelineItems": {"nodes": ev}}


@pytest.fixture(autouse=True)
def github(monkeypatch):
    def get(path):
        if (m := re.fullmatch(r"repos/[^/]+/[^/]+/collaborators/([^/]+)/permission", path)):
            return {"role_name": ROLES.get(m[1], "read")}
        if re.fullmatch(r"repos/[^/]+/[^/]+/commits/[0-9a-f]{40}/check-suites\?per_page=100", path):
            return {"total_count": 1, "check_suites": [{"created_at": PUSH}]}
        raise AssertionError(f"unexpected read {path}")
    monkeypatch.setattr(mg.hc, "gh_get", get)


def test_a_label_by_a_privileged_user_after_the_push_is_valid():
    assert mg.label_arm("o/r", pr(1)) == (None, "boss")
    assert mg.label_arm("o/r", pr(2, actor=("User", "maint")))[0] is None


@pytest.mark.parametrize("kw, why", [
    ({"label": False}, "absent"),
    ({"actor": ("User", "writer")}, "not admin or maintain"),
    ({"actor": ("Bot", "github-actions")}, "not applied last by a user account"),
    ({"at": BEFORE}, "predates the head"),
])
def test_the_census_names_every_armed_pr_without_a_valid_label_and_why(kw, why):
    rows = lc.census("o/r", [pr(7, **kw)])
    assert [r["pr"] for r in rows] == [7] and why in rows[0]["reason"]


def test_the_census_leaves_out_what_is_valid_unarmed_or_draft():
    rows = lc.census("o/r", [pr(1), pr(2, label=False, auto=False), pr(3, label=False, draft=True), pr(4, queue=True), pr(5, label=False, queue=True),
                             pr(6, at=BEFORE, auto=False), pr(8, label=False)])
    assert {r["pr"]: r["armed_by"] for r in rows} == {5: "queue", 6: "label", 8: "auto-merge"}


def test_the_census_reads_every_page(monkeypatch):
    pages = [{"pageInfo": {"hasNextPage": True, "endCursor": "c1"}, "nodes": [pr(1, label=False)]},
             {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [pr(2, label=False)]}]
    seen = []
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: seen.append(v.get("after")) or {"repository": {"pullRequests": pages[len(seen) - 1]}})
    assert [p["number"] for p in lc.open_prs("o/r")] == [1, 2] and seen == [None, "c1"]


def test_the_first_page_carries_no_cursor_key(monkeypatch):
    """GitHub answers a literal "None" cursor with INVALID_CURSOR_ARGUMENTS: the first request must not name `after` at all."""
    keys = []
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: keys.append(sorted(v)) or {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": False}, "nodes": []}}})
    lc.open_prs("o/r")
    assert keys == [["name", "owner"]]


@pytest.mark.parametrize("repo_doc", [{}, {"repository": None}])
def test_a_response_without_a_repository_is_a_graphql_error_not_a_crash(monkeypatch, repo_doc):
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: repo_doc)
    with pytest.raises(mg.GraphQLError):
        lc.open_prs("o/r")
    with pytest.raises(mg.GraphQLError):
        lc.verify("o/r", 1)


def test_a_page_without_nodes_or_page_info_is_an_empty_last_page(monkeypatch):
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: {"repository": {"pullRequests": {"nodes": None}}})
    assert lc.open_prs("o/r") == []


def test_census_of_an_empty_list_reads_nothing(monkeypatch):
    monkeypatch.setattr(mg, "gh_graphql", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not read")))
    assert lc.census("o/r", []) == []


def test_census_tolerates_missing_or_malformed_label_data():
    bare = pr(3, label=False)
    del bare["labels"]
    nodes_none = pr(4, label=False)
    nodes_none["labels"] = {"nodes": None}
    junk = pr(5, label=True)
    junk["labels"] = {"nodes": [None, "x", {"name": mg.ARM_LABEL}]}
    notitle = pr(6, label=False)
    notitle["title"] = None
    rows = lc.census("o/r", [bare, nodes_none, junk, notitle])
    assert {r["pr"]: r["label"] for r in rows} == {3: False, 4: False, 6: False} and [r["title"] for r in rows if r["pr"] == 6] == [""]


def _graphql(monkeypatch, node):
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: {"repository": {"pullRequest": node, "pullRequests": {"pageInfo": {"hasNextPage": False}, "nodes": [node] if node else []}}})


def test_verify_exit_codes_valid_invalid_unreadable(monkeypatch, capsys):
    _graphql(monkeypatch, pr(1))
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 0 and "LABEL_OK pr=1 actor=boss" in capsys.readouterr().out
    _graphql(monkeypatch, pr(1, at=BEFORE))
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 1 and "LABEL_INVALID pr=1" in capsys.readouterr().out
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: (_ for _ in ()).throw(mg.GraphQLError("502")))
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 2 and "LABEL_UNREADABLE" in capsys.readouterr().err


def _suites(monkeypatch, fn, only="check-suites"):
    real = mg.hc.gh_get
    monkeypatch.setattr(mg.hc, "gh_get", lambda path: fn(path) if only in path else real(path))


@pytest.mark.parametrize("how", ["raises", "incomplete", "no-timestamp"])
def test_verify_check_suites_unreadable_is_unknown_not_invalid(monkeypatch, capsys, how):
    """B31 L6: a transient read failure on a VALID label must be rc 2 (the helper retries), never rc 1 (the helper would remove the label)."""
    _graphql(monkeypatch, pr(1))
    def fn(path):
        if how == "raises":
            raise RuntimeError("502")
        return {"total_count": 2, "check_suites": [{"created_at": PUSH}]} if how == "incomplete" else {"total_count": 1, "check_suites": [{"created_at": None}]}
    _suites(monkeypatch, fn)
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 2 and "LABEL_UNREADABLE" in capsys.readouterr().err


def test_verify_unreadable_head_or_event_time_is_unknown(monkeypatch, capsys):
    _graphql(monkeypatch, pr(1, head="not-a-sha"))
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 2 and "LABEL_UNREADABLE" in capsys.readouterr().err


def test_verify_permission_read_failure_is_unknown(monkeypatch, capsys):
    _graphql(monkeypatch, pr(1))
    def boom(path):
        raise RuntimeError("502")
    _suites(monkeypatch, boom, only="/permission")
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 2


@pytest.mark.parametrize("kw", [{"label": False}, {"actor": ("User", "writer")}, {"actor": ("Bot", "github-actions")}, {"at": BEFORE}])
def test_verify_a_judged_invalid_label_stays_rc_1(monkeypatch, capsys, kw):
    _graphql(monkeypatch, pr(1, **kw))
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 1 and "LABEL_INVALID" in capsys.readouterr().out


def test_a_read_failure_inside_the_census_is_exit_2_not_a_clean_list(monkeypatch, capsys):
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: (_ for _ in ()).throw(mg.GraphQLError("502")))
    assert lc.main(["census", "--repo", "o/r"]) == 2 and "LABEL_UNREADABLE" in capsys.readouterr().err


def test_census_lists_a_queue_only_armed_pr_without_a_valid_label():
    rows = lc.census("o/r", [pr(5, label=False, auto=False, queue=True)])
    assert [(r["pr"], r["armed_by"]) for r in rows] == [(5, "queue")]


def test_verify_a_missing_pull_request_is_an_error_not_a_verdict(monkeypatch):
    _graphql(monkeypatch, None)
    with pytest.raises(mg.GraphQLError):
        lc.verify("o/r", 3)


def test_open_prs_refuses_a_page_that_is_not_a_page_and_skips_non_nodes(monkeypatch):
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: {"repository": {"pullRequests": None}})
    with pytest.raises(mg.GraphQLError):
        lc.open_prs("o/r")
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": False}, "nodes": [None, "x", pr(4, label=False)]}}})
    assert [n["number"] for n in lc.open_prs("o/r")] == [4]


def test_census_row_carries_the_label_flag_and_a_bounded_title():
    long = pr(6, at=BEFORE, auto=False)
    long["title"] = "t" * 200
    rows = lc.census("o/r", [long, pr(8, label=False)])
    by = {r["pr"]: r for r in rows}
    assert by[6]["label"] is True and by[8]["label"] is False and len(by[6]["title"]) == 70


def test_verify_quiet_writes_the_invalid_line_to_stderr(monkeypatch, capsys):
    _graphql(monkeypatch, pr(1, at=BEFORE))
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1", "--quiet"]) == 1
    out = capsys.readouterr()
    assert out.out == "" and "LABEL_INVALID" in out.err


def test_the_poller_outlives_the_helpers_deadline_with_margin():
    """B31 L5: the helper's wall-clock deadline plus the arm must end before the poller kills it (its subprocess timeout)."""
    root = Path(__file__).resolve().parents[3]
    cfg = subprocess.run(["bash", str(root / "scripts/signal_merge_intent.sh"), "7"], capture_output=True, text=True, timeout=30,
                         env={"PATH": "/usr/bin:/bin", "SIGNAL_INTENT_SHOW_CONFIG": "1"}).stdout
    deadline = int(re.search(r"deadline=(\d+)", cfg)[1])
    poller = (root / "apps/bali-intel-scraper/scripts/post_publish_poller.py").read_text()
    timeout = int(re.search(r"\[str\(intent\), number\],[^\n]*timeout=(\d+)", poller)[1])
    assert deadline <= 45 and timeout >= deadline + 15, (timeout, deadline)


def test_the_script_runs_as_a_program():
    """The entry guard: run as a script, with no gh to read from, the verdict is unreadable (rc 2) and loud, not a silent 0."""
    root = Path(__file__).resolve().parents[3]
    run = subprocess.run([sys.executable, str(root / "scripts/localci/label_census.py"), "verify", "--repo", "o/r", "--pr", "1"],
                         capture_output=True, text=True, timeout=60, env={"PATH": "/nonexistent"})
    assert run.returncode == 2 and "LABEL_UNREADABLE" in run.stderr


def test_census_exit_code_and_json(monkeypatch, capsys):
    _graphql(monkeypatch, pr(9, label=False))
    assert lc.main(["census", "--repo", "o/r", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)[0]["pr"] == 9
    _graphql(monkeypatch, pr(9))
    assert lc.main(["census", "--repo", "o/r"]) == 0


def test_census_prints_each_row_and_the_total(monkeypatch, capsys):
    _graphql(monkeypatch, pr(9, label=False))
    assert lc.main(["census", "--repo", "o/r"]) == 1
    out = capsys.readouterr().out
    assert "#9 [auto-merge] label" in out and "CENSUS 1 armed PR(s)" in out


def test_no_caller_swallows_the_helpers_exit():
    """B31 L2: `signal_merge_intent.sh ... || true` is how 31 of 49 PRs lost their label unseen (a discarded status is pinned by the docs_guardian behaviour tests)."""
    root = Path(__file__).resolve().parents[3]
    swallowed = []
    for path in [*(root / "scripts").glob("*.sh"), *(root / "scripts" / "ci").glob("*.sh"), *(root / "scripts").glob("*.py"), *(root / "apps" / "bali-intel-scraper" / "scripts").glob("*.py")]:
        for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if "signal_merge_intent.sh" in line and not line.lstrip().startswith("#") and re.search(r"\|\|\s*(true|:)\b", line):
                swallowed.append(f"{path.relative_to(root)}:{i}")
    assert not swallowed, swallowed


def _run_docs_guardian_tail(tmp_path, helper_rc, script=None, broken=0, pr_url="https://github.com/o/r/pull/12", helper=True, gh_rc=0):
    """Run docs_guardian.sh from its auto-merge block to the end with a fake helper, a fake git and a recording notify."""
    root = Path(__file__).resolve().parents[3]
    text = (script or root / "scripts/docs_guardian.sh").read_text()
    tail = text[text.index("# Enable auto-merge only if"):]
    (tmp_path / "scripts").mkdir()
    hp = tmp_path / "scripts/signal_merge_intent.sh"
    hp.write_text(f"#!/bin/sh\necho \"$@\" >> helper.log\necho 'SIGNAL_INTENT_FAIL fake' >&2\nexit {helper_rc}\n")
    hp.chmod(0o755 if helper else 0o644)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/gh").write_text(f"#!/bin/sh\necho \"$@\" >> gh.log\nexit {gh_rc}\n")
    (tmp_path / "bin/gh").chmod(0o755)
    (tmp_path / "bin/git").write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / "bin/git").chmod(0o755)
    harness = tmp_path / "h.sh"
    harness.write_text(f"set -euo pipefail\nBROKEN={broken}; PR_URL={pr_url}; L1_COMMITTED=0; L25_COMMITTED=0; L25_SUMMARY=''; ORPHANS=0; PR_BODY_FILE=''\n"
                       "notify() { printf '%s|%s\\n' \"$1\" \"$2\" >> notified; }\n" + tail)
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "HOME": str(tmp_path)}
    run = subprocess.run(["bash", str(harness)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    notified = (tmp_path / "notified").read_text() if (tmp_path / "notified").exists() else ""
    return run, notified


def test_docs_guardian_fails_loud_when_the_helper_fails(tmp_path):
    """B31 L2: a failed intent is stderr ERROR, a notification naming the PR, and exit 1 — each one pinned."""
    run, notified = _run_docs_guardian_tail(tmp_path, 2)
    assert run.returncode == 1
    assert "ERROR: signal_merge_intent failed on PR #12" in run.stderr
    assert "MERGE INTENT FAILED on PR #12" in notified


def test_docs_guardian_is_quiet_when_the_helper_succeeds(tmp_path):
    run, notified = _run_docs_guardian_tail(tmp_path, 0)
    assert run.returncode == 0
    assert "MERGE INTENT FAILED" not in notified and "ERROR" not in run.stderr


def _called(tmp_path, name):
    f = tmp_path / name
    return f.read_text() if f.exists() else ""


@pytest.mark.parametrize("kw", [{"broken": 1}, {"pr_url": ""}, {"pr_url": "https://example.com/o/r/pull/12"}, {"pr_url": "https://github.com/o/r/pull/x"}])
def test_docs_guardian_arms_only_a_clean_run_with_a_pull_request_url(tmp_path, kw):
    """B31 prime: each operand of the arm gate (no broken links, a URL, a github pull URL) holds the helper back on its own."""
    run, notified = _run_docs_guardian_tail(tmp_path, 0, **kw)
    assert run.returncode == 0 and _called(tmp_path, "helper.log") == "" and _called(tmp_path, "gh.log") == ""


def test_docs_guardian_passes_the_pull_number_to_the_helper(tmp_path):
    run, _ = _run_docs_guardian_tail(tmp_path, 0)
    assert _called(tmp_path, "helper.log").split() == ["12"] and _called(tmp_path, "gh.log") == ""


def test_docs_guardian_without_the_helper_falls_back_to_a_bare_arm_that_cannot_fail_the_run(tmp_path):
    run, notified = _run_docs_guardian_tail(tmp_path, 0, helper=False, gh_rc=1)
    assert run.returncode == 0 and _called(tmp_path, "helper.log") == ""
    assert _called(tmp_path, "gh.log").split() == ["pr", "merge", "12", "--auto"] and "MERGE INTENT FAILED" not in notified


def _poller():
    import importlib.util
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("b31_post_publish_poller", root / "apps/bali-intel-scraper/scripts/post_publish_poller.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("rc, stdout, labelled, alerts", [
    (0, "SIGNAL_INTENT pr=1 label=applied queue=absent arm=skipped\n", True, 0),
    (2, "SIGNAL_INTENT pr=1 label=failed queue=absent arm=skipped\n", False, 1),   # B31: exit 2 also prints arm=skipped; it is NOT a labelled PR
    (2, "SIGNAL_INTENT pr=1 label=failed queue=present arm=armed\n", False, 1),
    (3, "", False, 0),
    (0, "SIGNAL_INTENT pr=1 label=applied queue=present arm=armed\n", False, 0),   # exit 0 without arm=skipped is not "labelled (no merge queue)"
])
def test_the_poller_logs_labelled_only_for_exit_0_and_alerts_on_exit_2(monkeypatch, rc, stdout, labelled, alerts):
    """B31 C4: `returncode == 0 and "arm=skipped"` — a helper that failed the label still says arm=skipped on stdout."""
    mod = _poller()
    logs, sent = [], []
    monkeypatch.setattr(mod, "log", logs.append)
    monkeypatch.setattr(mod, "send_telegram_alert", lambda *a, **k: sent.append(k.get("dedup_key", "")))
    monkeypatch.setattr(mod, "_pr_state", lambda n: None)
    monkeypatch.setattr(mod, "_log_gh_failure", lambda *a, **k: None)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], rc, stdout, "boom"))
    got = mod._arm_pr("https://github.com/o/r/pull/1", "article")
    assert got is labelled
    assert any("labelled merge-intent" in line for line in logs) is labelled
    assert len([d for d in sent if "unlabelled" in d]) == alerts


def test_the_signal_merge_intent_shell_suite_passes():
    """B31 L1: the guilt/innocence table of the helper (valid left alone, stale refreshed, bounded retry, read-back, exit 2) lives in shell."""
    root = Path(__file__).resolve().parents[3]
    run = subprocess.run(["bash", str(root / "scripts/tests/test_signal_merge_intent.sh")], capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout[-1500:] + run.stderr[-500:]


def test_a_command_that_outlives_its_timeout_is_rc_124_not_a_hang(monkeypatch):
    monkeypatch.setattr(_li, "CMD_TIMEOUT", 1)
    rc, out = _li._run(["sleep", "5"])
    assert rc == 124 and "timed out" in out

