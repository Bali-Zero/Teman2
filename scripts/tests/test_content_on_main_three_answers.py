"""A failed diff is "could not tell", never "already on main" (scar family #9).

Two deciders answer "is this content on main?" right before something is deleted:
`scripts/branch_graveyard_cleanup.sh::content_on_main()` (category 2 is what --apply
deletes) and `scripts/audit_agent_quarantine.py::classify()` (LANDED is what --apply
prunes). The question has three answers: yes (proved blob by blob), no, and could not
tell. Every checker error is "could not tell", and that answer never deletes.

Guilt cases inject the error with a fake `git` on PATH (or a real reverted merge);
innocence cases prove that squash, cherry-pick, plain merge and a really empty diff
still read as landed. Scratch repositories only: nothing here touches this repo, and
the graveyard only ever runs in DRY-RUN.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GRAVEYARD = REPO / "scripts" / "branch_graveyard_cleanup.sh"
QUARANTINE = REPO / "scripts" / "audit_agent_quarantine.py"
REAL_GIT = shutil.which("git")

FAKE_GIT = """#!/bin/bash
args="$*"
if [[ -n "${FAKE_GIT_RE:-}" && "$args" =~ $FAKE_GIT_RE ]]; then
    case "${FAKE_GIT_MODE:-fail}" in
        empty|lie) exit 0 ;;                      # exit 0 with EMPTY stdout
        partial) echo "keep.txt"; exit 128 ;;     # partial output, then fail
    esac
    echo "fatal: injected by test" >&2
    exit 128
fi
exec "%s" "$@"
"""

FAKE_GH = "#!/bin/bash\nexit 1\n"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Hermetic git identity/config plus a bin dir holding the fake git and gh."""
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("")
    for k, v in {
        "GIT_CONFIG_GLOBAL": str(gitconfig),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("FAKE_GIT_RE", raising=False)
    monkeypatch.delenv("FAKE_GIT_MODE", raising=False)
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    (fakebin / "git").write_text(FAKE_GIT % REAL_GIT)
    (fakebin / "gh").write_text(FAKE_GH)
    for f in fakebin.iterdir():
        f.chmod(0o755)
    return fakebin


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run([REAL_GIT, *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, path: str, text: str | None, msg: str) -> str:
    p = repo / path
    if text is None:
        p.unlink()
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _scenario(work: Path) -> dict[str, str]:
    """Build one repo holding every case. Returns branch -> tip sha.

    base: a.txt c.txt d.txt keep.txt p.txt
      squash   : edits a.txt; main gets the same bytes as an unrelated commit
      cherry   : edits c.txt; main cherry-picks it
      plain    : adds q.txt; main merges it --no-ff (an ancestor of main)
      reverted : adds r.txt; main merges it --no-ff, then reverts the merge
      empty    : adds then removes e.txt (diff vs merge-base is REALLY empty)
      deleted  : deletes d.txt; main deletes d.txt too
      unmerged : adds u.txt; never reaches main
    """
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _commit(work, "keep.txt", "root\n", "root")
    for f in ("a.txt", "c.txt", "d.txt", "p.txt"):
        (work / f).write_text(f"{f} v1\n")
    base = _commit(work, "keep.txt", "root\nbase\n", "base")
    tips: dict[str, str] = {}

    def branch(name: str, steps: list[tuple[str, str | None]]) -> None:
        _git(work, "checkout", "-q", "-b", name, base)
        for i, (path, text) in enumerate(steps):
            tips[name] = _commit(work, path, text, f"{name} {i}")
        _git(work, "checkout", "-q", "main")

    branch("squash", [("a.txt", "a.txt v2\n")])
    branch("cherry", [("c.txt", "c.txt v2\n")])
    branch("plain", [("q.txt", "q\n")])
    branch("reverted", [("r.txt", "r\n")])
    branch("empty", [("e.txt", "e\n"), ("e.txt", None)])
    branch("deleted", [("d.txt", None)])
    branch("unmerged", [("u.txt", "u\n")])

    _commit(work, "a.txt", "a.txt v2\n", "squash-merge of squash")
    _git(work, "cherry-pick", "-x", tips["cherry"])
    _git(work, "merge", "-q", "--no-ff", "-m", "merge plain", "plain")
    _git(work, "merge", "-q", "--no-ff", "-m", "merge reverted", "reverted")
    _git(work, "revert", "--no-edit", "-m", "1", "HEAD")
    _commit(work, "d.txt", None, "main deletes d.txt")
    _commit(work, "keep.txt", "root\nbase\nmain moves on\n", "main moves on")
    return tips


# --------------------------------------------------------------------------- #
# branch_graveyard_cleanup.sh — DRY-RUN against a scratch origin
# --------------------------------------------------------------------------- #
SECTION_RE = re.compile(r"^### (.*)$")
ITEM_RE = re.compile(r"^  - `origin/([^`]+)`")


def _graveyard_sections(stdout: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = None
    for line in stdout.splitlines():
        m = SECTION_RE.match(line)
        if m:
            cur = m.group(1)
            out[cur] = []
            continue
        m = ITEM_RE.match(line)
        if m and cur is not None:
            out[cur].append(m.group(1))
    return out


def _section(sections: dict[str, list[str]], prefix: str) -> list[str] | None:
    for title, items in sections.items():
        if title.startswith(prefix):
            return items
    return None


@pytest.fixture
def graveyard_repo(tmp_path, env):
    work = tmp_path / "work"
    tips = _scenario(work)
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "origin", "main", *tips.keys())
    return work, tips


def _run_graveyard(work: Path, fakebin: Path, tmp_path: Path, **inject: str) -> dict[str, list[str]]:
    run_env = {k: v for k, v in os.environ.items() if not k.startswith("BRANCH_CLEANUP_")}
    run_env.update({
        "PATH": f"{fakebin}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "REPOMAP_REPO_ROOT": str(work),
    })
    run_env.update(inject)
    r = subprocess.run(["/bin/bash", str(GRAVEYARD)], env=run_env, capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "Mode: DRY-RUN" in r.stdout
    return _graveyard_sections(r.stdout)


def test_graveyard_innocence_landed_content_still_deletable(graveyard_repo, env, tmp_path):
    work, _ = graveyard_repo
    s = _run_graveyard(work, env, tmp_path)
    merged = _section(s, "Merged & deletable")
    content = _section(s, "Content-on-main & deletable")
    assert sorted(merged) == ["plain", "reverted"]  # category 1 is ancestry (lossless: still reachable)
    assert sorted(content) == ["cherry", "empty", "squash"]
    assert "unmerged" not in merged + content
    assert not _section(s, "Could not tell")


@pytest.mark.parametrize("mode", ["fail", "empty", "partial"])
def test_graveyard_failed_diff_is_could_not_tell(graveyard_repo, env, tmp_path, mode):
    work, _ = graveyard_repo
    s = _run_graveyard(work, env, tmp_path, FAKE_GIT_RE=r"^diff --name-only", FAKE_GIT_MODE=mode)
    content = _section(s, "Content-on-main & deletable")
    undecided = _section(s, "Could not tell")
    assert "unmerged" not in content, "a failed diff authorised a deletion"
    assert undecided is not None and "unmerged" in undecided
    if mode == "empty":
        # an empty answer is believed only when the trees really are equal
        assert "empty" in content


def test_graveyard_failed_merge_base_is_could_not_tell(graveyard_repo, env, tmp_path):
    work, _ = graveyard_repo
    s = _run_graveyard(work, env, tmp_path, FAKE_GIT_RE=r"^merge-base [^-]")
    assert "unmerged" not in _section(s, "Content-on-main & deletable")
    assert "unmerged" in (_section(s, "Could not tell") or [])


def test_graveyard_failed_blob_read_never_matches(graveyard_repo, env, tmp_path):
    work, _ = graveyard_repo
    s = _run_graveyard(work, env, tmp_path, FAKE_GIT_RE=r"^ls-tree")
    assert "unmerged" not in _section(s, "Content-on-main & deletable")
    assert "unmerged" in (_section(s, "Could not tell") or [])


def test_graveyard_lying_blob_read_never_matches(graveyard_repo, env, tmp_path):
    """git that exits 0 with EMPTY stdout lies: every path reads absent."""
    work, _ = graveyard_repo
    s = _run_graveyard(work, env, tmp_path, FAKE_GIT_RE=r"^ls-tree", FAKE_GIT_MODE="lie")
    assert "unmerged" not in _section(s, "Content-on-main & deletable")


def test_graveyard_failed_ancestor_check_is_could_not_tell(graveyard_repo, env, tmp_path):
    """A failed --is-ancestor probe is could-not-tell, never category 1."""
    work, _ = graveyard_repo
    s = _run_graveyard(work, env, tmp_path, FAKE_GIT_RE=r"^merge-base --is-ancestor")
    assert "plain" not in _section(s, "Merged & deletable")
    assert "plain" in (_section(s, "Could not tell") or [])


# --------------------------------------------------------------------------- #
# audit_agent_quarantine.py — classify() is read-only; called directly
# --------------------------------------------------------------------------- #
@pytest.fixture
def quarantine(tmp_path, env, monkeypatch):
    work = tmp_path / "work"
    tips = _scenario(work)
    spec = importlib.util.spec_from_file_location("audit_agent_quarantine_ut", QUARANTINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "REPO_ROOT", work)
    monkeypatch.setattr(mod, "MAIN_REF", "main")
    monkeypatch.setenv("PATH", f"{env}:{os.environ['PATH']}")
    return mod, tips, work


@pytest.mark.parametrize("name", ["squash", "cherry", "plain", "empty", "deleted"])
def test_quarantine_innocence_landed(quarantine, name):
    mod, tips, _ = quarantine
    assert mod.classify(tips[name])["verdict"] == mod.R_LANDED


def test_quarantine_innocence_plain_merge_reason_unchanged(quarantine):
    mod, tips, _ = quarantine
    assert mod.classify(tips["plain"])["reason"] == "ancestor-of-main"


def test_quarantine_innocence_snapshot_payload_on_main(quarantine):
    """An `add -A` snapshot whose payload already landed is still LANDED."""
    mod, tips, work = quarantine
    _git(work, "checkout", "-q", "squash")
    snap = _commit(work, "c.txt", "c.txt v2\n", "snapshot")
    _git(work, "checkout", "-q", "main")
    assert mod.classify(snap)["verdict"] == mod.R_LANDED


def test_quarantine_unique_content_is_kept(quarantine):
    mod, tips, _ = quarantine
    assert mod.classify(tips["unmerged"])["verdict"] == mod.R_UNIQUE


def test_quarantine_reverted_merge_is_not_landed(quarantine):
    """Ancestry is not content: a merged-then-reverted branch is an ancestor of
    main while its file is gone from main's tree."""
    mod, tips, work = quarantine
    assert _git(work, "merge-base", "--is-ancestor", tips["reverted"], "main") == ""
    assert mod.classify(tips["reverted"])["verdict"] == mod.R_UNIQUE


@pytest.mark.parametrize("mode", ["fail", "empty", "partial"])
def test_quarantine_failed_diff_is_could_not_tell(quarantine, monkeypatch, mode):
    mod, tips, work = quarantine
    monkeypatch.setenv("FAKE_GIT_RE", r"^diff --name-only")
    monkeypatch.setenv("FAKE_GIT_MODE", mode)
    f = mod.classify(tips["unmerged"])
    assert f["verdict"] == mod.R_AMBIGUOUS, f
    assert f["reason"], "could-not-tell must say why"
    if mode == "empty":
        # a net-zero branch still carries a payload (its last commit), so an
        # empty answer about that payload is a lie the trees expose ...
        assert mod.classify(tips["empty"])["verdict"] == mod.R_AMBIGUOUS
        # ... while a commit that changes nothing at all is REALLY empty: still landed
        base = _git(work, "merge-base", "main", tips["unmerged"])
        _git(work, "checkout", "-q", "-b", "noop", base)
        _git(work, "commit", "-q", "--allow-empty", "-m", "noop")
        noop = _git(work, "rev-parse", "HEAD")
        _git(work, "checkout", "-q", "main")
        assert mod.classify(noop)["verdict"] == mod.R_LANDED


def test_quarantine_failed_blob_read_is_could_not_tell(quarantine, monkeypatch):
    mod, tips, _ = quarantine
    monkeypatch.setenv("FAKE_GIT_RE", r"^(rev-parse [^ ]+:|ls-tree|cat-file --batch)")
    f = mod.classify(tips["unmerged"])
    assert f["verdict"] == mod.R_AMBIGUOUS, f


@pytest.mark.parametrize("probe", [r"^rev-list", r"^merge-base --is-ancestor"])
def test_quarantine_failed_ancestry_walk_is_could_not_tell(quarantine, monkeypatch, probe):
    mod, tips, _ = quarantine
    monkeypatch.setenv("FAKE_GIT_RE", probe)
    f = mod.classify(tips["plain"])
    assert f["verdict"] == mod.R_AMBIGUOUS, f


def test_quarantine_lying_tree_read_is_could_not_tell(quarantine, monkeypatch):
    """git that exits 0 with EMPTY stdout lies: an empty tree listing is
    believed by nobody -> ambiguous, never 'absent on both sides'."""
    mod, tips, _ = quarantine
    monkeypatch.setenv("FAKE_GIT_RE", r"^ls-tree")
    monkeypatch.setenv("FAKE_GIT_MODE", "lie")
    f = mod.classify(tips["unmerged"])
    assert f["verdict"] == mod.R_AMBIGUOUS, f


def test_quarantine_unresolvable_merge_base_is_could_not_tell(quarantine, monkeypatch):
    mod, tips, _ = quarantine
    monkeypatch.setenv("FAKE_GIT_RE", r"^merge-base [^-]")
    monkeypatch.setenv("FAKE_GIT_MODE", "fail")
    f = mod.classify(tips["unmerged"])
    assert f["verdict"] == mod.R_AMBIGUOUS, f
    assert f["reason"] == "merge-base-unresolvable"


def test_quarantine_failed_delta_diff_is_could_not_tell(quarantine, monkeypatch):
    """A snapshot commit on the unmerged tip: only the delta diff is failed,
    the authored diff is honest -> the failure is pinned to the payload."""
    mod, tips, work = quarantine
    _git(work, "checkout", "-q", "unmerged")
    snap = _commit(work, "u2.txt", "u2\n", "snapshot on unmerged tip")
    _git(work, "checkout", "-q", "main")
    monkeypatch.setenv("FAKE_GIT_RE", rf"^diff --name-only -z {tips['unmerged']}")
    monkeypatch.setenv("FAKE_GIT_MODE", "fail")
    f = mod.classify(snap)
    assert f["verdict"] == mod.R_AMBIGUOUS, f
    assert f["reason"] == "delta-diff-failed"


def test_quarantine_ref_on_main_first_parent_line_is_could_not_tell(quarantine):
    """Safe-direction change: an ancestor sitting ON main's first-parent line
    has no knowable fork point -> ambiguous (kept), never LANDED."""
    mod, _, work = quarantine
    on_line = _git(work, "rev-parse", "main~1")
    assert mod.classify(on_line)["verdict"] == mod.R_AMBIGUOUS
