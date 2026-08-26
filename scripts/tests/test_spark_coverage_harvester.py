"""Tests for scripts/army/spark_coverage_harvester.py (R7 harvester).

Contract under test (guilt + innocence, per cicatrix-superscar #3 antidote —
no guard ships without both directions):
  - GUILT: a codex/coverage-* branch that already has a PR (any state) is
    SKIPPED even though it has unmerged commits.
  - INNOCENCE: a codex/coverage-* branch with commits ahead of the base and
    no PR anywhere is SELECTED.
  - EDGE: a branch with zero commits ahead of the base is never selected,
    regardless of whether a PR exists for it (the generator's own cleanup
    already deleted it in the common case; this only guards a partial
    delete leaving a dangling empty-diff branch behind).

Also covers the real git wiring (discover_candidates/_commits_ahead) against
a throwaway local repo — the pure-function tests above prove the SELECTION
logic; this proves the plumbing that feeds it real numbers.
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "army"))

from spark_coverage_harvester import (  # noqa: E402
    Candidate,
    discover_candidates,
    guess_seat,
    in_automatic_window,
    select_branches_to_harvest,
)


def _candidate(branch="codex/coverage-foo_bar-20260827_030000", commits_ahead=1):
    return Candidate(
        branch=branch, module="foo_bar", ts="20260827_030000",
        commits_ahead=commits_ahead, on_remote=False, on_local=True,
    )


def test_guilt_branch_with_pr_is_skipped():
    c = _candidate(commits_ahead=3)
    selected, decided = select_branches_to_harvest([c], has_pr_fn=lambda b: True)
    assert selected == [], f"a branch with an existing PR must never be selected: {selected}"
    assert len(decided) == 1 and decided[0].action == "skipped-has-pr", decided


def test_innocence_branch_without_pr_is_selected():
    c = _candidate(commits_ahead=2)
    selected, decided = select_branches_to_harvest([c], has_pr_fn=lambda b: False)
    assert selected == [c], f"a branch with commits and no PR must be selected: {selected}"
    assert decided == [], f"a selected branch must not also appear as decided: {decided}"


def test_zero_commits_ahead_never_selected_even_without_a_pr():
    c = _candidate(commits_ahead=0)
    selected, decided = select_branches_to_harvest([c], has_pr_fn=lambda b: False)
    assert selected == [], f"a branch with 0 commits ahead must never be selected: {selected}"
    assert decided and decided[0].action == "skipped-no-commits", decided


def test_has_pr_fn_is_never_consulted_when_commits_ahead_is_zero():
    # Guard against a future refactor accidentally calling gh for branches
    # that can never be selected anyway — cheap, and proves the short-circuit.
    calls = []

    def spy(branch):
        calls.append(branch)
        return False

    select_branches_to_harvest([_candidate(commits_ahead=0)], has_pr_fn=spy)
    assert calls == [], f"has_pr_fn must not be called for a 0-commit branch: {calls}"


def test_guess_seat_reads_the_real_transcript_banner(tmp_path):
    log_dir = tmp_path
    (log_dir / "codex-output-20260827_030000.log").write_text(
        "--------\nworkdir: /x\nmodel: gpt-5.6-sol\nprovider: openai\n--------\n",
        encoding="utf-8",
    )
    seat = guess_seat(log_dir, "20260827_030000")
    assert seat == "codex-gpt-5.6-sol", seat


def test_guess_seat_never_fabricates_a_seat_when_log_is_missing(tmp_path):
    # This is the anti-hallucination guard for this module: the R7 spec
    # names `codex-gpt-5.3-codex-spark` for this row, but that seat belongs
    # to a DIFFERENT lane (army.spark_lane's -m flag) — this generator calls
    # `codex --profile power`, an undefined profile on this machine as of
    # 2026-08-27, so the true model varies with codex's own default.
    # Guessing either name without evidence would be exactly the fabrication
    # this codebase's anti-hallucination discipline exists to catch.
    seat = guess_seat(tmp_path, "20260827_030000")
    assert "gpt-5.3-codex-spark" not in seat, (
        f"guess_seat must never assert the spark seat without reading it from "
        f"the actual transcript: {seat}"
    )
    assert "unknown" in seat, seat


def test_in_automatic_window_true_at_0300_wita_false_at_1500_wita():
    import datetime
    from zoneinfo import ZoneInfo

    wita = ZoneInfo("Asia/Makassar")
    inside = datetime.datetime(2026, 8, 27, 3, 0, 0, tzinfo=wita).timestamp()
    outside = datetime.datetime(2026, 8, 27, 15, 0, 0, tzinfo=wita).timestamp()
    assert in_automatic_window(inside) is True
    assert in_automatic_window(outside) is False


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True)


def test_discover_candidates_against_a_real_repo_reports_correct_commit_count(tmp_path):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    _git(repo, "branch", "-M", "main")

    # Fake a bare "origin" remote so refs/remotes/origin/main exists — the
    # harvester diffs against `<remote>/<base>`, matching production usage
    # against a real GitHub remote rather than a bare local `main`.
    bare = str(tmp_path / "bare.git")
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
    _git(repo, "remote", "add", "origin", bare)
    _git(repo, "push", "-q", "-u", "origin", "main")

    _git(repo, "checkout", "-q", "-b", "codex/coverage-foo_bar-20260827_030000")
    open(os.path.join(repo, "t.py"), "w").write("x = 1\n")
    _git(repo, "add", "t.py")
    _git(repo, "commit", "-q", "-m", "test-only change")

    candidates = discover_candidates(repo, remote="origin", base="main")
    assert len(candidates) == 1, candidates
    c = candidates[0]
    assert c.branch == "codex/coverage-foo_bar-20260827_030000"
    assert c.module == "foo_bar"
    assert c.ts == "20260827_030000"
    assert c.commits_ahead == 1, c
    assert c.on_local is True
    assert c.on_remote is False


def test_discover_candidates_ignores_branches_outside_the_naming_scheme(tmp_path):
    repo = str(tmp_path / "repo2")
    os.makedirs(repo)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    _git(repo, "branch", "-M", "main")
    bare = str(repo) + "-bare.git"
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
    _git(repo, "remote", "add", "origin", bare)
    _git(repo, "push", "-q", "-u", "origin", "main")
    _git(repo, "checkout", "-q", "-b", "agent/nuzantara/ops/unrelated-lane")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "unrelated work")

    candidates = discover_candidates(repo, remote="origin", base="main")
    assert candidates == [], (
        f"a branch outside the codex/coverage-<module>-<ts> naming scheme "
        f"must never be treated as this harvester's to open a PR for: {candidates}"
    )
