"""translate-articles-cron-wrapper.sh must not promote a path another open PR carries.

2026-10-05: the post-publish poller's #7862 (bot/articles-translations-*) carried
indonesia-citizenship-….{id,it}.mdx; the hourly run, cut from main, translated the
same files again as #7867, and the queue left it CONFLICTING add/add once #7862
merged. The wrapper runs end to end here against a throwaway repo, a bare origin
and a fake `gh` that answers through the real `jq`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

WRAPPER = Path(__file__).resolve().parents[1] / "translate-articles-cron-wrapper.sh"
ART = "apps/mouth/src/content/articles"
POLLER_PATH = f"{ART}/immigration/citizenship.id.mdx"  # on the poller's open PR
FREE_PATH = f"{ART}/business/motorcycle.id.mdx"  # on no PR but an older hourly one
QUEUED_PATH = f"{ART}/tax-legal/coretax.id.mdx"  # on an older hourly PR holding a queue slot

pytestmark = pytest.mark.skipif(not (shutil.which("zsh") and shutil.which("jq")), reason="needs zsh and jq")

AGENT_START = """\
import pathlib, subprocess, sys
args, repo = sys.argv[1:], pathlib.Path.cwd()
log = pathlib.Path.home() / "agent_start.log"
log.write_text(log.read_text() + " ".join(args) + "\\n" if log.exists() else " ".join(args) + "\\n")
if "--task-id" in args:
    task = args[args.index("--task-id") + 1]
    wt = repo / ".worktrees" / f"mouth-{task}"
    subprocess.run(["git", "worktree", "add", "-q", "-b", f"agent/test/mouth/{task}", str(wt)], check=True)
    print(f"WORKTREE_READY {wt}")
"""

TRANSLATE = """\
import os, pathlib
root = pathlib.Path(os.environ["NUZANTARA_REPO_ROOT"])
for rel in filter(None, os.environ["FAKE_TRANSLATED"].split(",")):
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text("---\\nlocale: id\\n---\\nhourly copy\\n")
"""

FAKE_GH = """\
import json, os, pathlib, subprocess, sys
args = sys.argv[1:]
home = pathlib.Path(os.environ["HOME"])
with (home / "gh.log").open("a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["api", "graphql"] and any("files(first" in a for a in args):
    if os.environ.get("FAKE_LIST_FAIL"):
        sys.stderr.write("HTTP 502\\n")
        sys.exit(1)
    page = (home / "open_prs.json").read_text()
    out = subprocess.run(["jq", "-r", args[args.index("--jq") + 1]], input=page,
                         capture_output=True, text=True, check=True)
    sys.stdout.write(out.stdout)
elif args[:2] == ["pr", "create"]:
    print("https://github.com/Bali-Zero/Teman2/pull/901")
"""


def _node(ref: str, paths: list[str], queued: bool = False) -> dict:
    return {"headRefName": ref, "mergeQueueEntry": {"state": "QUEUED"} if queued else None,
            "files": {"nodes": [{"path": p} for p in paths]}}


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def home(tmp_path: Path) -> Path:
    repo, origin, bin_dir = tmp_path / "nuzantara", tmp_path / "origin.git", tmp_path / "bin"
    for d in (repo / "scripts" / "lib", bin_dir, tmp_path / "logs"):
        d.mkdir(parents=True)
    shutil.copy(WRAPPER, repo / "scripts" / WRAPPER.name)
    (repo / "scripts" / "agent_start.py").write_text(AGENT_START)
    (repo / "scripts" / "translate-articles.py").write_text(TRANSLATE)
    (repo / "scripts" / "lib" / "heartbeat.sh").write_text('echo "$2 $3" >> "$HOME/heartbeat.log"\n')
    (repo / ".gitignore").write_text(".worktrees/\n.venv\n")
    (repo / ".venv" / "bin").mkdir(parents=True)
    os.symlink(shutil.which("python3"), repo / ".venv" / "bin" / "python")
    (bin_dir / "gh").write_text(f"#!{shutil.which('python3')}\n{FAKE_GH}")
    (bin_dir / "gh").chmod(0o755)
    _git("init", "-q", "--bare", str(origin), cwd=tmp_path)
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", cwd=repo)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed", cwd=repo)
    _git("remote", "add", "origin", str(origin), cwd=repo)
    (tmp_path / "open_prs.json").write_text(json.dumps({"data": {"repository": {"pullRequests": {
        "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": [_node("bot/articles-translations-20261005-115126", [POLLER_PATH]),
                  _node("agent/nuzantara/mouth/hourly-20261005113006", [FREE_PATH]),
                  _node("agent/nuzantara/mouth/hourly-20261005103006", [QUEUED_PATH], queued=True),
                  _node("agent/air-m5/intel/unrelated", [f"{ART}/business/other.mdx"])]}}}}))
    return tmp_path


def _run(home: Path, translated: list[str], **env: str) -> subprocess.CompletedProcess[str]:
    full_env = {"HOME": str(home), "PATH": f"{home / 'bin'}:{os.environ['PATH']}",
                "FAKE_TRANSLATED": ",".join(translated), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", **env}
    return subprocess.run(["zsh", str(home / "nuzantara" / "scripts" / WRAPPER.name)], env=full_env,
                          capture_output=True, text=True, timeout=60)


def _promoted(home: Path) -> set[str]:
    origin = home / "origin.git"
    heads = _git("for-each-ref", "--format=%(refname)", "refs/heads/", cwd=origin).split()
    return {p for h in heads for p in _git("ls-tree", "-r", "--name-only", h, cwd=origin).split()
            if p.startswith(ART)}


def _gh_calls(home: Path) -> list[list[str]]:
    log = home / "gh.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def test_a_path_another_open_pr_carries_is_yielded_the_rest_is_promoted(home: Path) -> None:
    result = _run(home, [POLLER_PATH, FREE_PATH, QUEUED_PATH])

    assert result.returncode == 0, (home / "logs" / "translate-hourly-wrapper.log").read_text()
    # the poller's path and the queued hourly PR's path are yielded; the older,
    # unqueued hourly PR is superseded by this run, so its path is promoted
    assert _promoted(home) == {FREE_PATH}


def test_when_every_path_is_carried_nothing_is_pushed_or_opened(home: Path) -> None:
    result = _run(home, [POLLER_PATH])

    assert result.returncode == 0
    assert _promoted(home) == set()
    assert not any(c[:2] == ["pr", "create"] for c in _gh_calls(home))
    assert "--release" in (home / "agent_start.log").read_text()


def test_a_carried_list_larger_than_a_pipe_buffer_still_yields(home: Path) -> None:
    # `print "$CARRIED" | grep -q` under pipefail: grep matched on line 1 and quit,
    # print died of SIGPIPE (141) on the rest, and the `if` read the match as a miss
    page = json.loads((home / "open_prs.json").read_text())
    filler = [_node(f"agent/air-m5/docs/big-{i}", [f"docs/{'x' * 80}/{i}/{j}.md" for j in range(100)])
              for i in range(40)]
    page["data"]["repository"]["pullRequests"]["nodes"] += filler
    (home / "open_prs.json").write_text(json.dumps(page))

    result = _run(home, [POLLER_PATH, FREE_PATH])

    assert result.returncode == 0
    assert _promoted(home) == {FREE_PATH}


def test_a_run_with_nothing_to_promote_does_not_scan_open_prs(home: Path) -> None:
    result = _run(home, [])

    assert result.returncode == 0
    assert not any(c[:2] == ["api", "graphql"] and any("files(first" in a for a in c) for c in _gh_calls(home))


def test_an_unreadable_pr_listing_promotes_nothing_and_says_degraded(home: Path) -> None:
    result = _run(home, [FREE_PATH], FAKE_LIST_FAIL="1")

    assert result.returncode != 0
    assert _promoted(home) == set()
    assert not any(c[:2] == ["pr", "create"] for c in _gh_calls(home))
    assert (home / "heartbeat.log").read_text().startswith("degraded")
