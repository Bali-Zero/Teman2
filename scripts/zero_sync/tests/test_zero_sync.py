"""Offline tests for zero_sync: throwaway canonical + zero repos reached through file:// URLs."""
from __future__ import annotations

import fcntl
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("zero_sync", Path(__file__).resolve().parents[1] / "zero_sync.py")
zs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(zs)

PKG = '{\n  "name": "root",\n  "workspaces": [\n    "apps/mouth",\n    "apps/other",\n    "packages/core"\n  ],\n  "x": 1\n}\n'
PKG_PRUNED = '{\n  "name": "root",\n  "workspaces": [\n    "apps/mouth",\n    "packages/core"\n  ],\n  "x": 1\n}\n'
KEEP = "# keep\napps/mouth\napps/backend-rag\npackages/core\ndata/x.json\n"
CUT = "# cut\napps/backend-rag/data/team.json\napps/backend-rag/tests/cutdir\n"
LOCAL = "apps/backend-rag/data/team.synthetic.json\n"

NPM_STUB = """#!/bin/bash
if [ "$1" = "--version" ]; then echo 10.0.0; exit 0; fi
echo x >> "$NPM_STUB_COUNT"
{ echo LOCK; cat package.json; } > package-lock.json
"""

G = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def git(cwd, *args):
    return subprocess.run([*G, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def write(root: Path, files: dict, delete=()):
    for p in delete:
        (root / p).unlink()
    for p, c in files.items():
        f = root / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(c)


class World:
    def __init__(self, tmp: Path, monkeypatch):
        self.tmp = tmp
        self.canon = tmp / "canon"
        self.canon.mkdir()
        git(self.canon, "init", "-q", "-b", "main")
        git(self.canon, "config", "uploadpack.allowFilter", "true")
        git(self.canon, "config", "uploadpack.allowAnySHA1InWant", "true")
        self.canon_url = f"file://{self.canon}"
        self.canon_commit({
            "package.json": PKG, "package-lock.json": "orig-lock\n",
            "apps/mouth/package.json": '{"name":"mouth"}\n', "apps/mouth/a.txt": "a1\n",
            "apps/other/package.json": '{"name":"other"}\n', "apps/other/o.txt": "o\n",
            "packages/core/package.json": '{"name":"core"}\n',
            "data/x.json": "{}\n", "data/y.json": "{}\n",
            "apps/backend-rag/app.py": "print(1)\n",
            "apps/backend-rag/data/team.json": "STAFF\n",
            "apps/backend-rag/tests/cutdir/test_a.py": "x\n",
            ".github/workflows/ci.yml": "canonical ci\n",
            ".github/workflows/x.yml": "canonical x\n",
        }, "initial")
        self.zero_bare = tmp / "zero.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.zero_bare)], check=True)
        self.zero_url = f"file://{self.zero_bare}"
        self.zwork = tmp / "zwork"
        self.zwork.mkdir()
        git(self.zwork, "init", "-q", "-b", "main")
        self.zero_commit({
            ".slim/keep_paths.txt": KEEP, ".slim/cut_paths.txt": CUT, ".slim/local_paths.txt": LOCAL,
            ".github/workflows/ci.yml": "zero ci\n",
            "apps/backend-rag/data/team.synthetic.json": "synthetic\n",
            "package.json": PKG_PRUNED, "package-lock.json": "old\n",
        }, "import")
        stub = tmp / "npm-stub"
        stub.write_text(NPM_STUB)
        stub.chmod(0o755)
        self.npm = str(stub)
        self.count = tmp / "npm.count"
        monkeypatch.setenv("NPM_STUB_COUNT", str(self.count))
        monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp / "hb"))
        self.state = tmp / "state"

    def canon_commit(self, files, msg, delete=()):
        write(self.canon, files, delete)
        git(self.canon, "add", "-A")
        git(self.canon, "commit", "-q", "-m", msg)

    def zero_commit(self, files, msg, delete=()):
        if self.zero_bare.joinpath("refs/heads/main").exists():
            git(self.zwork, "fetch", "-q", self.zero_url, "main")
            git(self.zwork, "reset", "-q", "--hard", "FETCH_HEAD")
        write(self.zwork, files, delete)
        git(self.zwork, "add", "-A")
        git(self.zwork, "commit", "-q", "-m", msg)
        git(self.zwork, "push", "-q", self.zero_url, "HEAD:refs/heads/main")

    def run(self, *extra):
        return zs.main(["--state-dir", str(self.state), "--canonical-url", self.canon_url,
                        "--zero-url", self.zero_url, "--npm-cmd", self.npm, "--no-ci-check", *extra])

    def zero_tip(self):
        return git(self.zero_bare, "rev-parse", "main")

    def zero_files(self):
        return set(git(self.zero_bare, "ls-tree", "-r", "--name-only", "main").splitlines())

    def zero_show(self, path):
        return git(self.zero_bare, "show", f"main:{path}")

    def hb(self):
        return json.loads((self.tmp / "hb" / "mini.zero_sync.json").read_text())

    def npm_calls(self):
        return len(self.count.read_text().split()) if self.count.exists() else 0


@pytest.fixture
def w(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def test_exports_keep_dir_and_single_file_and_removes_cut(w):
    assert w.run() == 0
    files = w.zero_files()
    assert {"apps/mouth/a.txt", "apps/backend-rag/app.py", "data/x.json", "packages/core/package.json"} <= files
    assert "data/y.json" not in files  # innocence: sibling of a kept single file stays out
    assert "apps/other/o.txt" not in files
    assert "apps/backend-rag/data/team.json" not in files  # cut file
    assert "apps/backend-rag/tests/cutdir/test_a.py" not in files  # under a cut dir
    assert w.hb()["status"] == "ok"


def test_missing_keep_path_is_a_hard_error_naming_it(w, capsys):
    w.zero_commit({".slim/keep_paths.txt": KEEP + "nope/dir\n"}, "perimeter drift")
    tip = w.zero_tip()
    assert w.run() == 1
    assert "nope/dir" in capsys.readouterr().out
    assert w.zero_tip() == tip
    assert w.hb()["status"] == "error"


def test_zero_owned_paths_win_over_canonical(w):
    w.zero_commit({".github/workflows/z.yml": "z\n"}, "zero-owned noise")
    assert w.run() == 0
    assert w.zero_show(".github/workflows/ci.yml") == "zero ci"  # canonical has other content
    assert w.zero_show(".slim/keep_paths.txt").startswith("# keep")
    assert w.zero_show("apps/backend-rag/data/team.synthetic.json") == "synthetic"


def test_zero_owned_prefix_is_exclusive_even_if_keep_names_canonical_file(w):
    # keep names a canonical workflow zero does not have: it must NOT come back.
    w.zero_commit({".slim/keep_paths.txt": KEEP + ".github/workflows/x.yml\n"}, "keep names a workflow")
    assert w.run() == 0
    assert ".github/workflows/x.yml" not in w.zero_files()
    assert w.zero_show(".github/workflows/ci.yml") == "zero ci"


def test_local_path_preserved_when_canonical_has_a_file_there(w):
    w.canon_commit({"apps/backend-rag/data/team.synthetic.json": "canonical version\n"}, "same path")
    assert w.run() == 0
    assert w.zero_show("apps/backend-rag/data/team.synthetic.json") == "synthetic"


def test_workspace_pruning_and_lock_regeneration_cached(w):
    assert w.run() == 0
    assert w.zero_show("package.json") + "\n" == PKG_PRUNED
    lock = w.zero_show("package-lock.json")
    assert lock.startswith("LOCK") and "apps/other" not in lock
    assert w.npm_calls() == 1
    w.canon_commit({"apps/mouth/a.txt": "a2\n"}, "mouth change")  # lock inputs unchanged
    assert w.run() == 0
    assert w.npm_calls() == 1  # cache hit
    w.canon_commit({"apps/mouth/package.json": '{"name":"mouth","v":2}\n'}, "mouth pkg")
    assert w.run() == 0
    assert w.npm_calls() == 2  # input changed


def test_prune_workspaces_edits_text_only_and_rejects_globs():
    out, kept = zs.prune_workspaces(PKG, lambda x: x != "apps/other")
    assert out == PKG_PRUNED and kept == ["apps/mouth", "packages/core"]
    with pytest.raises(zs.SyncError):
        zs.prune_workspaces('{"workspaces": ["apps/*"]}', lambda x: True)


def test_noop_when_unchanged(w, capsys):
    assert w.run() == 0
    tip = w.zero_tip()
    assert w.run() == 0
    assert w.zero_tip() == tip
    assert "up to date" in capsys.readouterr().out
    assert w.hb()["note"].startswith("up to date")


def test_push_is_fast_forward_with_trailer_and_author(w):
    before = w.zero_tip()
    assert w.run() == 0
    after = w.zero_tip()
    assert git(w.zero_bare, "merge-base", "--is-ancestor", before, after) == ""
    assert git(w.zero_bare, "rev-parse", "main^") == before
    body = git(w.zero_bare, "log", "-1", "--format=%B", "main")
    canon_sha = git(w.canon, "rev-parse", "main")
    assert f"Zero-Sync-Canonical: {canon_sha}" in body
    assert body.startswith(f"sync: canonical {canon_sha[:10]}")
    assert "files changed" in body
    assert git(w.zero_bare, "log", "-1", "--format=%an", "main") == "zero-sync"


def test_divergence_refused_when_zero_changed_a_product_file(w, capsys):
    assert w.run() == 0
    w.zero_commit({"apps/mouth/a.txt": "direct fix on zero\n"}, "direct change")
    tip = w.zero_tip()
    assert w.run() == 3
    assert w.zero_tip() == tip  # nothing pushed
    assert "apps/mouth/a.txt" in capsys.readouterr().out
    hb = w.hb()
    assert hb["status"] == "error" and "apps/mouth/a.txt" in hb["note"]


def test_no_refusal_when_canonical_already_carries_the_same_change(w):
    assert w.run() == 0
    w.zero_commit({"apps/mouth/a.txt": "same\n"}, "direct change")
    w.canon_commit({"apps/mouth/a.txt": "same\n", "apps/mouth/b.txt": "b\n"}, "canonical lands it too")
    assert w.run() == 0
    assert w.zero_show("apps/mouth/b.txt") == "b"
    assert w.zero_show("apps/mouth/a.txt") == "same"


def test_refusal_for_a_file_added_only_on_zero(w):
    assert w.run() == 0
    w.zero_commit({"apps/mouth/only_zero.txt": "z\n"}, "zero-only file")
    assert w.run() == 3  # present-vs-absent counts


def test_second_sync_reads_previous_trailer_and_walks_only_newer_commits(w):
    assert w.run() == 0
    w.zero_commit({"apps/mouth/d.txt": "d\n"}, "direct D1")
    w.canon_commit({"apps/mouth/d.txt": "d\n", "apps/mouth/a.txt": "a2\n"}, "feat: touch mouth")
    w.canon_commit({"data/y.json": "{\"o\":1}\n"}, "chore: outside the perimeter")
    assert w.run() == 0
    body = git(w.zero_bare, "log", "-1", "--format=%B", "main")
    assert "feat: touch mouth" in body and "outside the perimeter" not in body
    repo = zs.Repo(w.state / "repo.git")
    repo.run("fetch", "-q", w.zero_url, "+refs/heads/main:refs/zero/main")
    commits, prev, tip_sync = zs.walk_unsynced(repo, "refs/zero/main")
    assert commits == [] and tip_sync
    assert prev == git(w.canon, "rev-parse", "main")
    # D1 sits behind the newest sync commit, so a later canonical delete of d.txt is not a refusal
    w.canon_commit({}, "drop d", delete=["apps/mouth/d.txt"])
    assert w.run() == 0
    assert "apps/mouth/d.txt" not in w.zero_files()
    # a new direct commit after the sync is the only one walked
    w.zero_commit({"apps/mouth/a.txt": "again\n"}, "direct D2")
    assert w.run() == 3


def test_push_rejected_when_zero_moves_between_fetch_and_push(w, monkeypatch):
    real = zs.prefetch

    def racing(repo, oids):
        real(repo, oids)
        w.zero_commit({"unrelated.txt": "raced\n"}, "zero moved")

    monkeypatch.setattr(zs, "prefetch", racing)
    assert w.run() == 4
    assert w.hb()["status"] == "warning"
    assert "unrelated.txt" in w.zero_files()
    assert "apps/mouth/a.txt" not in w.zero_files()  # our commit did not land


def test_dry_run_pushes_nothing_and_prints_stat(w, capsys):
    tip = w.zero_tip()
    assert w.run("--dry-run") == 0
    out = capsys.readouterr().out
    assert w.zero_tip() == tip
    assert "apps/mouth/a.txt" in out and "DIVERGENCE: none" in out
    assert not (w.tmp / "hb").exists()  # a dry run does not speak for the organ


def test_dry_run_reports_divergence_verdict(w, capsys):
    assert w.run() == 0
    w.zero_commit({"apps/mouth/a.txt": "direct\n"}, "direct")
    assert w.run("--dry-run") == 3
    assert "would REFUSE" in capsys.readouterr().out


def test_refuses_equal_urls(w, capsys):
    rc = zs.main(["--state-dir", str(w.state), "--canonical-url", "https://x/y/z.git",
                  "--zero-url", "https://X/y/z", "--no-ci-check"])
    assert rc == 2 and "equal" in capsys.readouterr().out


def test_second_instance_exits_zero_already_running(w, capsys):
    w.state.mkdir(parents=True)
    with open(w.state / "lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert w.run() == 0
    assert "already running" in capsys.readouterr().out
    assert "apps/mouth/a.txt" not in w.zero_files()
