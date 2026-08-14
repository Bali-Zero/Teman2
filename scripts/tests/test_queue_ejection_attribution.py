"""Tests for scripts/queue_ejection_attribution.py — Merge-OS v3 agy-F3 disposition.

Module is imported via importlib.util.spec_from_file_location (not a package import),
mirroring scripts/tests/test_queue_baseline_probe.py.

NO network anywhere in this file. Every `gh` invocation is intercepted at the real
subprocess boundary the module crosses — `monkeypatch.setattr(qea.subprocess, "run",
fake_run)` (W114: fake at the boundary the real code crosses).

Scenarios required by the mandate:
  1. guilt — total API denial: errors[] populated, main() exit non-zero, record still written.
  2. guilt — unmapped ("ignoto") removal reason: UNKNOWN bucket, visible error, never dropped.
  3. guilt — batch multi-PR: each PR attributed to its OWN author/branch, never to the
     merge_group service actor (github-actions[bot]) — the whole point of agy-F3's fix.
  4. innocence — a day with zero queue episodes still produces a valid, zeroed record with
     exit 0.
Plus pure-function unit tests for classify_author, classify_removal_reason, and
pair_queue_episodes (guilt+innocence per scar family #3 where the function classifies).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

MODULE_PATH = Path(__file__).resolve().parent.parent / "queue_ejection_attribution.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("queue_ejection_attribution", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


qea = _load_module()


def _proc(cmd: list[str], rc: int, out: str, err: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(cmd, rc, out, err)


def _mk_run(run_id: int, head_branch: str, conclusion: str = "failure", created_at: str = "2026-08-12T09:05:00Z") -> dict:
    return {"id": run_id, "head_branch": head_branch, "conclusion": conclusion, "created_at": created_at}


def _timeline_number(cmd: list[str]) -> int:
    for i, tok in enumerate(cmd):
        if tok == "-F" and cmd[i + 1].startswith("number="):
            return int(cmd[i + 1].split("=", 1)[1])
    raise AssertionError(f"no number= in cmd: {cmd}")


def _added(created_at: str) -> dict:
    return {"__typename": "AddedToMergeQueueEvent", "createdAt": created_at}


def _removed(created_at: str, reason: str, sha: str | None) -> dict:
    return {
        "__typename": "RemovedFromMergeQueueEvent",
        "createdAt": created_at,
        "reason": reason,
        "beforeCommit": ({"oid": sha} if sha else None),
    }


def _timeline_payload(author_login: str, head_ref_name: str, nodes: list[dict], has_next: bool = False) -> dict:
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "author": {"login": author_login},
                    "headRefName": head_ref_name,
                    "timelineItems": {
                        "pageInfo": {"hasNextPage": has_next, "endCursor": None},
                        "nodes": nodes,
                    },
                }
            }
        }
    }


def _make_fake_gh(
    repo: str,
    mg_runs: list[dict],
    merged_numbers: list[int],
    timelines_by_pr: dict[int, dict],
    jobs_by_run_id: dict[int, list[dict]] | None = None,
    mg_reported_total: int | None = None,
):
    jobs_by_run_id = jobs_by_run_id or {}
    mg_reported_total = len(mg_runs) if mg_reported_total is None else mg_reported_total

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        assert cmd[0] == "gh", f"unexpected non-gh call: {cmd}"
        if cmd[1] == "api" and len(cmd) > 2 and cmd[2] == f"repos/{repo}/actions/runs":
            return _proc(cmd, 0, json.dumps({"total_count": mg_reported_total, "workflow_runs": mg_runs}))
        if cmd[1] == "api" and len(cmd) > 2 and cmd[2].endswith("/jobs"):
            run_id = int(cmd[2].split("/")[-2])
            return _proc(cmd, 0, json.dumps({"jobs": jobs_by_run_id.get(run_id, [])}))
        if cmd[1] == "pr" and cmd[2] == "list":
            return _proc(cmd, 0, json.dumps([{"number": n} for n in merged_numbers]))
        if cmd[1] == "api" and len(cmd) > 2 and cmd[2] == "graphql":
            number = _timeline_number(cmd)
            payload = timelines_by_pr.get(number)
            if payload is None:
                raise AssertionError(f"no timeline fixture for pr={number}")
            return _proc(cmd, 0, json.dumps(payload))
        raise AssertionError(f"unexpected gh invocation in fixture: {cmd}")

    return fake_run


def _fail_everything(cmd, **kwargs):  # noqa: ANN001, ANN003
    assert cmd[0] == "gh"
    return _proc(cmd, 1, "", "HTTP 403: API rate limit exceeded for installation")


# ---------------------------------------------------------------------------
# 1. Guilt — total API denial.
# ---------------------------------------------------------------------------


def test_api_denial_produces_record_with_errors_never_silent(monkeypatch):
    day = date(2026, 8, 12)
    monkeypatch.setattr(qea.subprocess, "run", _fail_everything)

    record = qea.build_record(qea.DEFAULT_REPO, day)

    assert record["errors"] != []
    assert all(isinstance(e, str) and e.strip() for e in record["errors"])
    assert record["episodes"] == []
    assert record["ejections"]["total"] == 0


def test_api_denial_end_to_end_via_main_nonzero_exit_but_record_on_disk(tmp_path, monkeypatch):
    day = date(2026, 8, 12)
    monkeypatch.setattr(qea.subprocess, "run", _fail_everything)

    out_dir = tmp_path / "ejections"
    rc = qea.main(["--repo", qea.DEFAULT_REPO, "--date", day.isoformat(), "--out-dir", str(out_dir)])

    assert rc == 1
    record_path = out_dir / f"{day.isoformat()}.json"
    assert record_path.exists(), "the record must be written even when everything failed"
    on_disk = json.loads(record_path.read_text())
    assert on_disk["errors"] != []


# ---------------------------------------------------------------------------
# 2. Guilt — unmapped ("ignoto") removal reason.
# ---------------------------------------------------------------------------


def test_unmapped_reason_lands_in_unknown_with_visible_error(monkeypatch):
    day = date(2026, 8, 12)
    sha = "a" * 40
    mg_runs = [_mk_run(1, f"gh-readonly-queue/main/pr-500-{sha}", conclusion="failure")]
    timelines = {
        500: _timeline_payload(
            "someone",
            "fix/x",
            [_added("2026-08-12T10:00:00Z"), _removed("2026-08-12T10:05:00Z", "some_new_reason_github_invented", sha)],
        )
    }
    fake = _make_fake_gh(qea.DEFAULT_REPO, mg_runs, [], timelines)
    monkeypatch.setattr(qea.subprocess, "run", fake)

    record = qea.build_record(qea.DEFAULT_REPO, day)

    assert record["ejections"]["by_class"]["UNKNOWN"] == 1
    assert record["ejections"]["total"] == 1
    assert len(record["episodes"]) == 1
    assert record["episodes"][0]["reason_class"] == "UNKNOWN"
    assert record["episodes"][0]["reason_raw"] == "some_new_reason_github_invented"
    assert any("unmapped removal reason" in e and "some_new_reason_github_invented" in e for e in record["errors"])


# ---------------------------------------------------------------------------
# 3. Guilt — batch multi-PR, each attributed to its OWN author, never the bot actor.
# ---------------------------------------------------------------------------


def test_batch_multi_pr_attributes_to_own_author_never_the_merge_queue_bot(monkeypatch):
    day = date(2026, 8, 12)
    sha_a = "a" * 40
    sha_b = "b" * 40
    mg_runs = [
        _mk_run(1, f"gh-readonly-queue/main/pr-100-{sha_a}", conclusion="failure"),
        _mk_run(2, f"gh-readonly-queue/main/pr-200-{sha_b}", conclusion="failure"),
    ]
    timelines = {
        100: _timeline_payload(
            "human-dev",
            "fix/typo",
            [_added("2026-08-12T09:00:00Z"), _removed("2026-08-12T09:10:00Z", "manual", sha_a)],
        ),
        200: _timeline_payload(
            "Balizero1987",
            "agent/air-m5/ops/thing",
            [_added("2026-08-12T11:00:00Z"), _removed("2026-08-12T11:10:00Z", "merge_conflict", sha_b)],
        ),
    }
    fake = _make_fake_gh(qea.DEFAULT_REPO, mg_runs, [], timelines)
    monkeypatch.setattr(qea.subprocess, "run", fake)

    record = qea.build_record(qea.DEFAULT_REPO, day)

    by_pr = {e["pr_number"]: e for e in record["episodes"]}
    assert by_pr[100]["author_class"] == "human"
    assert by_pr[100]["reason_class"] == "MANUAL"
    assert by_pr[200]["author_class"] == "agent"  # branch prefix wins, never "bot"
    assert by_pr[200]["reason_class"] == "CONFLICT"
    assert record["ejections"]["by_author_class"]["bot"] == 0
    assert record["ejections"]["by_author_class"]["human"] == 1
    assert record["ejections"]["by_author_class"]["agent"] == 1
    assert record["ejections"]["total"] == 2


def test_failed_checks_infra_vs_code_split_via_run_correlation(monkeypatch):
    day = date(2026, 8, 12)
    sha_infra = "c" * 40
    sha_code = "d" * 40
    mg_runs = [
        _mk_run(11, f"gh-readonly-queue/main/pr-300-{sha_infra}", conclusion="failure"),
        _mk_run(22, f"gh-readonly-queue/main/pr-400-{sha_code}", conclusion="failure"),
    ]
    timelines = {
        300: _timeline_payload(
            "dev1",
            "fix/a",
            [_added("2026-08-12T09:00:00Z"), _removed("2026-08-12T09:10:00Z", "failed_checks", sha_infra)],
        ),
        400: _timeline_payload(
            "dev2",
            "fix/b",
            [_added("2026-08-12T09:00:00Z"), _removed("2026-08-12T09:10:00Z", "failed_checks", sha_code)],
        ),
    }
    jobs_by_run_id = {
        11: [{"name": "Set up job", "conclusion": "failure"}],
        22: [{"name": "Backend Tests (Python)", "conclusion": "failure"}],
    }
    fake = _make_fake_gh(qea.DEFAULT_REPO, mg_runs, [], timelines, jobs_by_run_id=jobs_by_run_id)
    monkeypatch.setattr(qea.subprocess, "run", fake)

    record = qea.build_record(qea.DEFAULT_REPO, day)

    by_pr = {e["pr_number"]: e for e in record["episodes"]}
    assert by_pr[300]["reason_class"] == "INFRA"
    assert by_pr[400]["reason_class"] == "CODE"
    assert record["ejections"]["by_class"] == {
        "CODE": 1, "INFRA": 1, "CONFLICT": 0, "HEAD_MOVED": 0, "MANUAL": 0, "UNKNOWN": 0,
    }


def test_failed_checks_with_no_correlated_run_defaults_to_code_and_logs_gap(monkeypatch):
    day = date(2026, 8, 12)
    sha = "e" * 40
    # No merge_group run at all matches this (pr, sha) — correlation gap.
    timelines = {
        700: _timeline_payload(
            "dev3",
            "fix/c",
            [_added("2026-08-12T09:00:00Z"), _removed("2026-08-12T09:10:00Z", "failed_checks", sha)],
        )
    }
    fake = _make_fake_gh(qea.DEFAULT_REPO, [], [700], timelines)
    monkeypatch.setattr(qea.subprocess, "run", fake)

    record = qea.build_record(qea.DEFAULT_REPO, day)

    assert record["episodes"][0]["reason_class"] == "CODE"
    assert any("no matching failing merge_group run found" in e for e in record["errors"])


def test_merged_reason_is_not_an_ejection(monkeypatch):
    day = date(2026, 8, 12)
    sha = "f" * 40
    timelines = {
        800: _timeline_payload(
            "dev4",
            "fix/d",
            [_added("2026-08-12T09:00:00Z"), _removed("2026-08-12T09:10:00Z", "merged", sha)],
        )
    }
    fake = _make_fake_gh(qea.DEFAULT_REPO, [], [800], timelines)
    monkeypatch.setattr(qea.subprocess, "run", fake)

    record = qea.build_record(qea.DEFAULT_REPO, day)

    assert record["episodes"] == []
    assert record["successful_dequeues"] == 1
    assert record["ejections"]["total"] == 0


def test_reentry_episodes_are_distinct_even_with_same_author_and_sha(monkeypatch):
    day = date(2026, 8, 12)
    sha = "1" * 40
    timelines = {
        900: _timeline_payload(
            "dev5",
            "fix/e",
            [
                _added("2026-08-12T09:00:00Z"),
                _removed("2026-08-12T09:10:00Z", "manual", sha),
                _added("2026-08-12T10:00:00Z"),
                _removed("2026-08-12T10:10:00Z", "manual", sha),
            ],
        )
    }
    fake = _make_fake_gh(qea.DEFAULT_REPO, [], [900], timelines)
    monkeypatch.setattr(qea.subprocess, "run", fake)

    record = qea.build_record(qea.DEFAULT_REPO, day)

    assert len(record["episodes"]) == 2
    assert record["episodes"][0]["enqueued_at"] == "2026-08-12T09:00:00Z"
    assert record["episodes"][1]["enqueued_at"] == "2026-08-12T10:00:00Z"
    assert record["ejections"]["by_class"]["MANUAL"] == 2


def test_dangling_added_with_no_removed_lands_in_episodes_unresolved(monkeypatch):
    day = date(2026, 8, 12)
    timelines = {
        950: _timeline_payload("dev6", "fix/f", [_added("2026-08-12T09:00:00Z")]),
    }
    fake = _make_fake_gh(qea.DEFAULT_REPO, [], [950], timelines)
    monkeypatch.setattr(qea.subprocess, "run", fake)

    record = qea.build_record(qea.DEFAULT_REPO, day)

    assert record["episodes"] == []
    assert record["episodes_unresolved"] == [{"pr_number": 950, "enqueued_at": "2026-08-12T09:00:00Z"}]


# ---------------------------------------------------------------------------
# 4. Innocence — zero-episode day.
# ---------------------------------------------------------------------------


def test_empty_day_record_carries_full_schema_with_zeros(monkeypatch):
    day = date(2026, 8, 12)
    fake = _make_fake_gh(qea.DEFAULT_REPO, [], [], {})
    monkeypatch.setattr(qea.subprocess, "run", fake)

    record = qea.build_record(qea.DEFAULT_REPO, day)

    assert record["errors"] == []
    assert record["episodes"] == []
    assert record["episodes_unresolved"] == []
    assert record["successful_dequeues"] == 0
    assert record["ejections"] == {
        "by_class": {"CODE": 0, "INFRA": 0, "CONFLICT": 0, "HEAD_MOVED": 0, "MANUAL": 0, "UNKNOWN": 0},
        "by_author_class": {"human": 0, "agent": 0, "bot": 0, "unknown": 0},
        "total": 0,
    }
    assert record["discovery"]["candidate_prs_total"] == 0
    assert record["discovery"]["merge_group_run_collection"] == {
        "reported_total": 0, "fetched": 0, "complete": True,
    }


def test_empty_day_end_to_end_via_main_writes_file_and_exits_zero(tmp_path, monkeypatch):
    day = date(2026, 8, 12)
    fake = _make_fake_gh(qea.DEFAULT_REPO, [], [], {})
    monkeypatch.setattr(qea.subprocess, "run", fake)

    out_dir = tmp_path / "ejections"
    rc = qea.main(["--repo", qea.DEFAULT_REPO, "--date", day.isoformat(), "--out-dir", str(out_dir)])

    assert rc == 0
    record_path = out_dir / f"{day.isoformat()}.json"
    assert record_path.exists()
    on_disk = json.loads(record_path.read_text())
    assert on_disk["errors"] == []


# ---------------------------------------------------------------------------
# Pure-function unit tests.
# ---------------------------------------------------------------------------


def test_classify_author_agent_branch_wins_over_login():
    assert qea.classify_author("agent/air-m5/ops/x", "some-human") == "agent"


def test_classify_author_bot_login():
    assert qea.classify_author("fix/x", "github-actions[bot]") == "bot"


def test_classify_author_innocence_ordinary_human():
    assert qea.classify_author("fix/typo", "antonellosiano") == "human"


def test_classify_removal_reason_manual():
    assert qea.classify_removal_reason("manual", None) == "MANUAL"


def test_classify_removal_reason_merge_conflict():
    assert qea.classify_removal_reason("merge_conflict", None) == "CONFLICT"


def test_classify_removal_reason_failed_checks_infra_hint_true():
    assert qea.classify_removal_reason("failed_checks", True) == "INFRA"


def test_classify_removal_reason_failed_checks_infra_hint_false_or_none_defaults_code():
    assert qea.classify_removal_reason("failed_checks", False) == "CODE"
    assert qea.classify_removal_reason("failed_checks", None) == "CODE"


def test_classify_removal_reason_innocence_unmapped_is_unknown():
    assert qea.classify_removal_reason("something_brand_new", None) == "UNKNOWN"
    assert qea.classify_removal_reason(None, None) == "UNKNOWN"


def test_pair_queue_episodes_simple_pair():
    nodes = [
        {"kind": "added", "created_at": "T1"},
        {"kind": "removed", "created_at": "T2", "reason": "manual", "before_commit_oid": "sha1"},
    ]
    episodes, unresolved = qea.pair_queue_episodes(nodes)
    assert episodes == [{"enqueued_at": "T1", "kind": "removed", "created_at": "T2", "reason": "manual", "before_commit_oid": "sha1"}]
    assert unresolved == []


def test_pair_queue_episodes_dangling_removed_has_no_enqueued_at_never_guessed():
    nodes = [{"kind": "removed", "created_at": "T2", "reason": "manual", "before_commit_oid": "sha1"}]
    episodes, unresolved = qea.pair_queue_episodes(nodes)
    assert episodes[0]["enqueued_at"] is None
    assert unresolved == []


def test_pair_queue_episodes_dangling_added_is_unresolved_never_dropped():
    nodes = [{"kind": "added", "created_at": "T1"}]
    episodes, unresolved = qea.pair_queue_episodes(nodes)
    assert episodes == []
    assert unresolved == [{"kind": "added", "created_at": "T1"}]


def test_pair_queue_episodes_double_added_first_one_unresolved():
    nodes = [
        {"kind": "added", "created_at": "T1"},
        {"kind": "added", "created_at": "T2"},
        {"kind": "removed", "created_at": "T3", "reason": "manual", "before_commit_oid": "sha1"},
    ]
    episodes, unresolved = qea.pair_queue_episodes(nodes)
    assert len(episodes) == 1
    assert episodes[0]["enqueued_at"] == "T2"
    assert unresolved == [{"kind": "added", "created_at": "T1"}]


def test_extract_pr_shas_from_head_branch():
    sha = "a" * 40
    assert qea.extract_pr_shas_from_head_branch(f"gh-readonly-queue/main/pr-4181-{sha}") == (4181, sha)


def test_extract_pr_shas_from_head_branch_innocence_no_match():
    assert qea.extract_pr_shas_from_head_branch("gh-readonly-queue/main/deadbeef") is None
    assert qea.extract_pr_shas_from_head_branch(None) is None
