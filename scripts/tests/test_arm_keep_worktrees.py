"""Tests for scripts/arm_keep_worktrees.py — the W80 fail-closed fixes.

Two defects, two cures, all offline against real temporary git repos
(`git init` in tmp_path, local bare "origin" — no network):

  Cure 1: a failing `git worktree list --porcelain` must make main() exit
          non-zero, never print "nothing to arm" and exit 0.
  Cure 2: a branch with no upstream (local-only agent/<host>/<lane>/...) or a
          detached HEAD must count unpushed commits against ALL
          remote-tracking refs; a counting failure fails closed (treated as
          unpushed), never reports 0.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "arm_keep_worktrees.py"


def _load_module():
    """Load scripts/arm_keep_worktrees.py as a module (neighbouring-test convention)."""
    module_name = "arm_keep_worktrees_under_test"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod  # dataclass-style introspection needs the lookup to succeed
    spec.loader.exec_module(mod)
    return mod


akw = _load_module()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "armkeep@test.local")
    _git(path, "config", "user.name", "armkeep-test")
    return path


def _commit_file(repo: Path, name: str, content: str, msg: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", msg)


def test_unpushed_local_only_branch_no_remote(tmp_path: Path) -> None:
    """(a) Local-only agent branch with one commit and no remote: >= 1 unpushed."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "base.txt", "base\n", "base commit")
    wt = tmp_path / ".worktrees" / "lane-a"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", "agent/air/infra/lane-a")
    _commit_file(wt, "wip.txt", "wip\n", "local-only commit")
    assert akw._unpushed(wt, "refs/heads/agent/air/infra/lane-a") >= 1


def test_unpushed_detached_head(tmp_path: Path) -> None:
    """(b) Detached HEAD with a commit not on any remote ref: >= 1 unpushed."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "base.txt", "base\n", "base commit")
    wt = tmp_path / ".worktrees" / "lane-b"
    _git(repo, "worktree", "add", "-q", "--detach", str(wt), "HEAD")
    _commit_file(wt, "detached.txt", "wip\n", "commit on detached head")
    assert akw._unpushed(wt, None) >= 1


def test_unpushed_fully_pushed_branch(tmp_path: Path) -> None:
    """(c) Branch fully pushed to a local bare origin: exactly 0 unpushed."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "base.txt", "base\n", "base commit")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "-u", "origin", "main")
    _git(repo, "branch", "agent/air/infra/lane-c", "main")
    _git(repo, "push", "-q", "-u", "origin", "agent/air/infra/lane-c")
    wt = tmp_path / ".worktrees" / "lane-c"
    _git(repo, "worktree", "add", "-q", str(wt), "agent/air/infra/lane-c")
    assert akw._unpushed(wt, "refs/heads/agent/air/infra/lane-c") == 0


def test_worktree_list_failure_exits_nonzero(monkeypatch, capsys) -> None:
    """(d) Failing `git worktree list` → main() exits non-zero, reason on stderr."""
    real_git = akw._git

    def fake_git(args, cwd=None):
        if args[:2] == ["worktree", "list"]:
            return subprocess.CompletedProcess(args, 1, "", "fatal: not a git repository")
        return real_git(args, cwd)

    monkeypatch.setattr(akw, "_git", fake_git)
    rc = akw.main([])
    assert rc != 0
    assert "worktree list" in capsys.readouterr().err


def _local_repo_with_worktree(tmp_path: Path, monkeypatch, name: str = "lane-x") -> tuple[Path, Path]:
    """Real repo + linked worktree; REPO_ROOT is redirected so the script never touches the live repo."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "base.txt", "base\n", "base commit")
    wt = tmp_path / ".worktrees" / name
    _git(repo, "worktree", "add", "-q", str(wt), "-b", f"agent/air/infra/{name}")
    monkeypatch.setattr(akw, "REPO_ROOT", repo)
    return repo, wt


def test_unpushed_count_failure_fails_closed_without_branch(tmp_path: Path) -> None:
    """(e) P1(a): the fallback rev-list really fails (cwd is no git repo) -> must read as unpushed, never 0."""
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    assert akw._unpushed(not_a_repo, None) >= 1


def test_unpushed_count_failure_fails_closed_with_branch(tmp_path: Path) -> None:
    """(f) Same failure on the branch path (both counts fail) -> unpushed, never 0."""
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    assert akw._unpushed(not_a_repo, "refs/heads/agent/air/infra/gone") >= 1


def test_unpushed_unparseable_count_fails_closed(monkeypatch, tmp_path: Path) -> None:
    """(g) rc=0 but garbage stdout is not a zero either."""
    monkeypatch.setattr(
        akw, "_git", lambda args, cwd=None: subprocess.CompletedProcess(args, 0, "not-a-number\n", ""),
    )
    assert akw._unpushed(tmp_path, "refs/heads/x") >= 1
    assert akw._unpushed(tmp_path, None) >= 1


def test_arm_clean_worktree_with_local_commit_preserves_head(tmp_path: Path, monkeypatch) -> None:
    """(h) P1(b): clean tree, unpushed commit -> `stash create` is empty; arming must still leave a ref on HEAD."""
    repo, wt = _local_repo_with_worktree(tmp_path, monkeypatch)
    _commit_file(wt, "wip.txt", "wip\n", "local-only commit")
    head = _git(wt, "rev-parse", "HEAD").stdout.strip()
    ok, msg = akw._arm_one(wt, apply=True)
    assert ok, msg
    refs = _git(repo, "for-each-ref", "refs/agent-quarantine/", "--format=%(objectname)").stdout.split()
    assert head in refs, f"frozen reported but HEAD {head} is on no quarantine ref: {msg}"


def test_arm_reports_failure_when_ref_cannot_be_written_clean(tmp_path: Path, monkeypatch) -> None:
    """(i) Clean tree + the preserving ref cannot be written -> NOT frozen."""
    repo, wt = _local_repo_with_worktree(tmp_path, monkeypatch)
    _commit_file(wt, "wip.txt", "wip\n", "local-only commit")
    slug = akw._slug(wt)
    _git(repo, "update-ref", f"refs/agent-quarantine/{slug}-head/blocker", "HEAD")  # D/F conflict
    ok, msg = akw._arm_one(wt, apply=True)
    assert not ok, f"reported frozen with nothing preserved: {msg}"


def test_arm_reports_failure_when_ref_cannot_be_written_dirty(tmp_path: Path, monkeypatch) -> None:
    """(j) Dirty tree + update-ref fails -> NOT frozen (previously returned True)."""
    repo, wt = _local_repo_with_worktree(tmp_path, monkeypatch)
    (wt / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    slug = akw._slug(wt)
    _git(repo, "update-ref", f"refs/agent-quarantine/{slug}/blocker", "HEAD")  # D/F conflict
    ok, msg = akw._arm_one(wt, apply=True)
    assert not ok, f"reported frozen with nothing preserved: {msg}"
    assert (wt / "dirty.txt").exists()
    assert _git(wt, "diff", "--cached", "--name-only").stdout.strip() == "", "index must be left unstaged"


def test_main_arms_clean_worktree_with_commits_end_to_end(tmp_path: Path, monkeypatch, capsys) -> None:
    """(k) main() selects the clean-but-unpushed worktree and the commit is really preserved."""
    repo, wt = _local_repo_with_worktree(tmp_path, monkeypatch)
    _commit_file(wt, "wip.txt", "wip\n", "local-only commit")
    head = _git(wt, "rev-parse", "HEAD").stdout.strip()
    assert akw.main(["--names", wt.name]) == 0
    refs = _git(repo, "for-each-ref", "refs/agent-quarantine/", "--format=%(objectname)").stdout.split()
    assert head in refs
    assert "armed" in capsys.readouterr().out


def test_list_quarantine_git_failure_is_not_an_empty_list(tmp_path: Path, monkeypatch, capsys) -> None:
    """(l) A failing for-each-ref must not print "no quarantine refs." and exit 0."""
    monkeypatch.setattr(akw, "REPO_ROOT", tmp_path)  # tmp_path is no git repo
    assert akw.main(["--list"]) != 0
    captured = capsys.readouterr()
    assert "no quarantine refs" not in captured.out
    assert "cannot list" in captured.err


def test_unpushed_nonzero_rc_with_zero_stdout_is_not_zero(monkeypatch, tmp_path: Path) -> None:
    """(m) rc!=0 must be decisive even if stdout happens to read "0"."""
    monkeypatch.setattr(
        akw, "_git", lambda args, cwd=None: subprocess.CompletedProcess(args, 1, "0\n", "boom"),
    )
    assert akw._unpushed(tmp_path, None) >= 1
    assert akw._unpushed(tmp_path, "refs/heads/x") >= 1


def test_arm_dirty_tree_stash_create_failure_is_not_frozen(tmp_path: Path, monkeypatch) -> None:
    """(n) `stash create` failing on a DIRTY tree must not fall through to pinning HEAD and report frozen."""
    _repo, wt = _local_repo_with_worktree(tmp_path, monkeypatch)
    (wt / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    real_git = akw._git

    def fake_git(args, cwd=None):
        if args[:2] == ["stash", "create"]:
            return subprocess.CompletedProcess(args, 1, "", "fatal: stash create failed")
        return real_git(args, cwd)

    monkeypatch.setattr(akw, "_git", fake_git)
    ok, msg = akw._arm_one(wt, apply=True)
    assert not ok, f"dirty work captured nowhere but reported frozen: {msg}"
    assert (wt / "dirty.txt").exists()


def test_arm_reset_failure_is_reported_but_work_stays_preserved(tmp_path: Path, monkeypatch) -> None:
    """(o) Codex: a failing `git reset` leaves the index staged — say so; the ref still holds the work."""
    repo, wt = _local_repo_with_worktree(tmp_path, monkeypatch)
    (wt / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    real_git = akw._git

    def fake_git(args, cwd=None):
        if args == ["reset"]:
            return subprocess.CompletedProcess(args, 1, "", "fatal: reset failed")
        return real_git(args, cwd)

    monkeypatch.setattr(akw, "_git", fake_git)
    ok, msg = akw._arm_one(wt, apply=True)
    assert ok, msg
    assert "index" in msg and "staged" in msg
    assert _git(repo, "for-each-ref", "refs/agent-quarantine/").stdout.strip()
