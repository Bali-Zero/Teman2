"""A real temporary git repo (two commits) plus helpers to plan/run/review it with the real gate code."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

REAL_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REAL_REPO))
from scripts.localci import release_stub, runner  # noqa: E402

PY = sys.executable
ISOLATION_IMAGE = os.environ.get("LOCALCI_ISOLATION_IMAGE", runner.DEFAULT_ISOLATION_IMAGE)


def docker_image_ready() -> bool:
    import shutil
    d = shutil.which("docker")
    return bool(d) and subprocess.run([d, "image", "inspect", ISOLATION_IMAGE], capture_output=True).returncode == 0
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
BASE_FILES = {
    "scripts/check_ban_predicates.py": "GUARDED = True\n",
    "scripts/tests/test_ban_predicates.py": (
        "from pathlib import Path\n"
        "REPO_ROOT = Path(__file__).resolve().parents[2]\n"
        "GUARD = REPO_ROOT / 'scripts' / 'check_ban_predicates.py'\n"
        "def test_guard_exists():\n    assert GUARD.is_file()\n"
        "def test_guard_carries_no_banned_marker():\n    assert 'BANNED' + '_LITERAL' not in GUARD.read_text()\n"),
    "scripts/tests/test_empty_module.py": "VALUE = 1\n",
    "scripts/tests/test_allskip.py": "import pytest\n\ndef test_s():\n    pytest.skip('always')\n",
    "scripts/tests/test_fail.py": "def test_f():\n    assert False\n",
    "scripts/tests/test_broken.py": "def test_b(:\n",
}
CANDIDATE_FILES = {"scripts/tests/test_sample.py": "def test_a():\n    assert 1 + 1 == 2\n\ndef test_b():\n    assert 'x'.upper() == 'X'\n"}


def git(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True, env=GIT_ENV).stdout.strip()


def write(repo: Path, files: dict) -> None:
    for rel, body in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)


def make_repo(root: Path, candidate_files: dict | None = None) -> dict:
    repo = root / "wt"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    for f in runner.TRUSTED_CLASSIFIER_FILES:
        (repo / f).parent.mkdir(parents=True, exist_ok=True)
        (repo / f).write_bytes((REAL_REPO / f).read_bytes())
    write(repo, BASE_FILES)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    write(repo, candidate_files or CANDIDATE_FILES)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "candidate")
    return {"repo": repo, "base": base, "candidate": git(repo, "rev-parse", "HEAD"), "tree": git(repo, "rev-parse", "HEAD^{tree}"), "run": root / "run"}


def cmd_check(name: str, repo: Path, argv: list[str]) -> str:
    return f"{name}=" + json.dumps({"kind": "cmd", "cwd": str(repo), "cmd": argv, "purpose": "fixture"})


def pytest_check(name: str, repo: Path, modules: list[str]) -> str:
    return f"{name}=" + json.dumps({"kind": "pytest", "cwd": str(repo), "python": PY, "modules": modules, "purpose": "fixture"})


def plan(fx: dict, *extra: str, seat: str = "builder-a") -> None:
    iso = [] if "--isolation" in extra else ["--isolation", "none"]   # host-portable unit tests; the contained path is test_isolation.py's
    runner.main(["plan", "--run-dir", str(fx["run"]), "--worktree", str(fx["repo"]), "--base", fx["base"], "--python", PY, "--builder-seat", seat, *iso, *extra])


def run(fx: dict, *args: str) -> None:
    runner.main(["run", "--run-dir", str(fx["run"]), *args])


def load_state(fx: dict) -> dict:
    return json.loads((fx["run"] / "state" / "state.json").read_text())


def save_state(fx: dict, st: dict) -> None:
    (fx["run"] / "state" / "state.json").write_text(json.dumps(st))


def review_file(fx: dict, path: Path, **over) -> Path:
    rev = {"reviewed_candidate_sha": fx["candidate"], "reviewed_tree_sha": fx["tree"], "reviewed_base_sha": fx["base"],
           "reviewer_seat": "reviewer-k", "verdict": "PASS", "summary": "looks right"}
    rev.update(over)
    path.write_text(json.dumps(rev))
    return path


def import_review(fx: dict, tmp: Path, **over) -> None:
    runner.main(["review", "--run-dir", str(fx["run"]), "--file", str(review_file(fx, tmp / "review.json", **over))])


def contexts_file(fx: dict, path: Path, contexts: list[dict] | None = None) -> Path:
    import yaml

    if contexts is None:
        contexts = [{"name": n, "local": {"kind": "rule", "check": n}, "mapping": "executed"} for n in
                    ("policy.trusted_classifier_corpus", "policy.change_map", "tests.scripts_impacted", "policy.paid_anthropic_ban", "review.independent")]
        contexts += [{"name": n, "local": {"kind": "rule", "check": n}, "mapping": "not_applicable_rule"} for n in ("tests.backend_shards", "tests.frontend_mouth")]
    path.write_text(yaml.safe_dump({"contexts": contexts}))
    return path


def dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def make_running(fx: dict, name: str, attempts: int = 1) -> None:
    st = load_state(fx)
    st["checks"][name].update(status="RUNNING", pid=dead_pid(), started_at="2026-01-01T00:00:00Z", attempts=attempts, reason="executing")
    save_state(fx, st)


def status(fx: dict) -> dict:
    return runner.compute_status(fx["run"])


def green(fx: dict, tmp: Path, *extra: str, with_contexts: bool = True, with_review: bool = True, contexts: list[dict] | None = None) -> None:
    args = list(extra)
    if with_contexts:
        args += ["--contexts-file", str(contexts_file(fx, tmp / "contexts.yaml", contexts))]
    plan(fx, *args)
    run(fx)
    if with_review:
        import_review(fx, tmp)


class FakeEnv:
    """Deterministic env fingerprint: no pip/uv/import probing, mutable to simulate drift."""

    def __init__(self):
        self.env = {"python": "3.11.0", "pytest": "9.0.0", "platform": "test", "hostname": "h", "runner_version": runner.RUNNER_VERSION, "runner_sha256": "r" * 64,
                    "uv_version": None, "git_version": "git 2", "deps_lock_sha256": "d" * 64, "deps_lock_source": "fake", "tools": {}}

    def __call__(self, venv_py, checks=None):
        return copy.deepcopy(self.env)


def stub_propose(fx: dict, request: str, digest: str | None = None) -> dict:
    return release_stub.propose(fx["run"], request, fx["candidate"], digest)


def crafted_commit(repo: Path, entry_name: str = "..", under: str = "") -> str:
    """A commit whose tree carries a blob entry named `entry_name` (git itself refuses to build one with add/mktree), optionally under
    a directory path — what a hostile object store could hand `git ls-tree`."""
    def run(args: list[str], data: bytes | None = None) -> str:
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, input=data, env=GIT_ENV).stdout.decode().strip()
    blob = run(["hash-object", "-w", "--stdin"], b"escaped\n")
    tree = run(["hash-object", "-t", "tree", "-w", "--literally", "--stdin"], b"100644 " + entry_name.encode() + b"\0" + bytes.fromhex(blob))
    for part in reversed([p for p in under.split("/") if p]):
        tree = run(["mktree"], f"040000 tree {tree}\t{part}\n".encode())
    return run(["commit-tree", tree, "-m", "crafted"])
