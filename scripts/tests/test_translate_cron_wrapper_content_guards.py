"""translate-articles-cron-wrapper.sh must ask the mouth content guards before it promotes.

2026-10-15: the hourly promote PRs (#8451..#8538) were red on both sides because the LLM
translation rewrote lines that e33-income-basis-copy.test.ts and
secondhome-article-claims.test.ts pin. The wrapper now runs scripts/mouth_content_guard.sh,
holds back the slug groups that fail, and promotes nothing when the guards cannot judge.
The wrapper runs end to end against a throwaway repo, a bare origin, a fake `gh` and a fake
vitest that is red on any article containing BAD (the guard's real subject is the content).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
ART = "apps/mouth/src/content/articles"
GUARD_FILES = ("src/lib/e33-income-basis-copy.test.ts", "src/i18n/secondhome-article-claims.test.ts")
ALPHA = [f"{ART}/business/alpha.id.mdx", f"{ART}/business/alpha.it.mdx"]
BETA = [f"{ART}/tax/beta.id.mdx"]
BAD = [f"{ART}/immigration/badslug.id.mdx", f"{ART}/immigration/badslug.it.mdx"]

pytestmark = pytest.mark.skipif(not (shutil.which("zsh") and shutil.which("bash")), reason="needs zsh and bash")

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
elif "--release" in args:
    task = args[args.index("--release") + 1]
    wt = repo / ".worktrees" / f"mouth-{task}"
    if wt.is_dir():
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], check=True)
"""

TRANSLATE = """\
import os, pathlib
root = pathlib.Path(os.environ["NUZANTARA_REPO_ROOT"])
for rel in filter(None, os.environ["FAKE_TRANSLATED"].split(",")):
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text("---\\nlocale: id\\n---\\n" + ("BAD\\n" if "badslug" in rel else "fine\\n"))
"""

FAKE_GH = """\
import json, os, pathlib, sys
args = sys.argv[1:]
with (pathlib.Path(os.environ["HOME"]) / "gh.log").open("a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "create"]:
    print("https://github.com/Bali-Zero/Teman2/pull/901")
elif args[:2] == ["pr", "list"] and "--head" in args:
    head = args[args.index("--head") + 1]
    states = json.loads(os.environ.get("FAKE_STALE_PR_STATES", "{}"))
    print(states.get(head, ""))
elif args[:2] == ["pr", "list"] and "--search" in args:
    older = os.environ.get("FAKE_OLDER_OPEN_PRS", "")
    if older:
        print(older)
elif args[:2] == ["api", "graphql"] and "mergeQueueEntry" in " ".join(args) and "pullRequests" not in " ".join(args):
    print(os.environ.get("FAKE_OLDER_QUEUED", "null"))
"""

# red on any BAD article; FAKE_MAIN_RED = red everywhere; FAKE_PAIR_RED = red only when alpha AND beta coexist
FAKE_VITEST = """\
#!/bin/bash
cat "$5" >> "$HOME/vitest-config.seen"
[ -n "${FAKE_MAIN_RED:-}" ] && exit 1
d=src/content/articles
grep -rqs BAD "$d" && exit 1
if [ -n "${FAKE_PAIR_RED:-}" ] && [ -n "$(find $d -name 'alpha*')" ] && [ -n "$(find $d -name 'beta*')" ]; then exit 1; fi
exit 0
"""


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def home(tmp_path: Path) -> Path:
    repo, origin, bin_dir = tmp_path / "nuzantara", tmp_path / "origin.git", tmp_path / "bin"
    for d in (repo / "scripts" / "lib", repo / "shared", bin_dir, tmp_path / "logs", tmp_path / "nm" / ".bin"):
        d.mkdir(parents=True)
    for name in ("translate-articles-cron-wrapper.sh", "mouth_content_guard.sh"):
        shutil.copy(SCRIPTS / name, repo / "scripts" / name)
    (repo / "scripts" / "agent_start.py").write_text(AGENT_START)
    (repo / "scripts" / "translate-articles.py").write_text(TRANSLATE)
    (repo / "scripts" / "lib" / "heartbeat.sh").write_text('echo "$2 $3" >> "$HOME/heartbeat.log"\n')
    (repo / ".gitignore").write_text(".worktrees/\n.venv\n")
    for g in GUARD_FILES:
        (repo / "apps" / "mouth" / g).parent.mkdir(parents=True, exist_ok=True)
        (repo / "apps" / "mouth" / g).write_text("// guard\n")
    (repo / "shared" / "escalations_pro.jsonl").write_text("")
    (repo / ".venv" / "bin").mkdir(parents=True)
    os.symlink(shutil.which("python3"), repo / ".venv" / "bin" / "python")
    (bin_dir / "gh").write_text(f"#!{shutil.which('python3')}\n{FAKE_GH}")
    (bin_dir / "gh").chmod(0o755)
    (tmp_path / "nm" / ".bin" / "vitest").write_text(FAKE_VITEST)
    (tmp_path / "nm" / ".bin" / "vitest").chmod(0o755)
    (tmp_path / "nm" / "typescript").mkdir()
    (tmp_path / "nm" / "typescript" / "package.json").write_text("{}")
    _git("init", "-q", "--bare", str(origin), cwd=tmp_path)
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", cwd=repo)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed", cwd=repo)
    _git("remote", "add", "origin", str(origin), cwd=repo)
    return tmp_path


def _run(home: Path, translated: list[str], **env: str) -> subprocess.CompletedProcess[str]:
    full_env = {"HOME": str(home), "PATH": f"{home / 'bin'}:{os.environ['PATH']}",
                "FAKE_TRANSLATED": ",".join(translated), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                "MOUTH_GUARD_VITEST": str(home / "nm" / ".bin" / "vitest"), **env}
    return subprocess.run(["zsh", str(home / "nuzantara" / "scripts" / "translate-articles-cron-wrapper.sh")],
                          env=full_env, capture_output=True, text=True, timeout=120)


def _promoted(home: Path) -> set[str]:
    origin = home / "origin.git"
    heads = _git("for-each-ref", "--format=%(refname)", "refs/heads/", cwd=origin).split()
    return {p for h in heads for p in _git("ls-tree", "-r", "--name-only", h, cwd=origin).split()
            if p.startswith(ART)}


def _gh_calls(home: Path) -> list[list[str]]:
    log = home / "gh.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def _pr_body(home: Path) -> str:
    call = next(c for c in _gh_calls(home) if c[:2] == ["pr", "create"])
    return call[call.index("--body") + 1]


def _escalations(home: Path) -> list[dict]:
    text = (home / "nuzantara" / "shared" / "escalations_pro.jsonl").read_text()
    return [json.loads(line) for line in text.splitlines()]


def _heartbeat(home: Path) -> str:
    return (home / "heartbeat.log").read_text()


def test_the_group_that_fails_is_held_back_and_the_rest_is_promoted(home: Path) -> None:
    result = _run(home, ALPHA + BAD + BETA)

    assert result.returncode == 0, (home / "logs" / "translate-hourly-wrapper.log").read_text()
    assert _promoted(home) == set(ALPHA + BETA)
    assert "Held back by content guards" in _pr_body(home)
    assert "badslug" in _pr_body(home)
    assert "alpha" not in _pr_body(home)
    rows = _escalations(home)
    assert len(rows) == 1 and rows[0]["slugs"] == ["badslug"]
    assert _heartbeat(home).startswith("ok") and "held 1" in _heartbeat(home)


def test_when_every_guard_is_green_everything_is_promoted_and_nothing_is_held(home: Path) -> None:
    result = _run(home, ALPHA + BETA)

    assert result.returncode == 0
    assert _promoted(home) == set(ALPHA + BETA)
    assert "Held back" not in _pr_body(home)
    assert _escalations(home) == []
    assert "held" not in _heartbeat(home)


def test_when_every_group_fails_no_pr_opens_and_the_slugs_are_reported(home: Path) -> None:
    result = _run(home, BAD)

    assert result.returncode == 0
    assert _promoted(home) == set()
    assert not any(c[:2] == ["pr", "create"] for c in _gh_calls(home))
    assert "--release" in (home / "agent_start.log").read_text()
    assert _escalations(home)[0]["slugs"] == ["badslug"]
    assert _heartbeat(home).startswith("degraded") and "badslug" in _heartbeat(home)


def test_a_red_main_promotes_nothing_and_exits_with_its_own_code(home: Path) -> None:
    result = _run(home, ALPHA + BETA, FAKE_MAIN_RED="1")

    assert result.returncode == 2
    assert _promoted(home) == set()
    assert not any(c[:2] == ["pr", "create"] for c in _gh_calls(home))
    assert _heartbeat(home).startswith("degraded")
    assert _escalations(home) == []  # a red main is nobody's slug to hold


def test_missing_vitest_fails_closed_with_its_own_code(home: Path) -> None:
    result = _run(home, ALPHA + BETA, MOUTH_GUARD_VITEST=str(home / "nm" / ".bin" / "absent"))

    assert result.returncode == 3
    assert _promoted(home) == set()
    assert not any(c[:2] == ["pr", "create"] for c in _gh_calls(home))
    assert _heartbeat(home).startswith("degraded")


def test_missing_typescript_fails_closed(home: Path) -> None:
    shutil.rmtree(home / "nm" / "typescript")

    result = _run(home, ALPHA + BETA)

    assert result.returncode == 3
    assert _promoted(home) == set()


def test_a_final_set_that_is_red_though_each_group_is_green_promotes_nothing(home: Path) -> None:
    result = _run(home, ALPHA + BETA, FAKE_PAIR_RED="1")

    assert result.returncode == 5
    assert _promoted(home) == set()
    assert not any(c[:2] == ["pr", "create"] for c in _gh_calls(home))
    assert _heartbeat(home).startswith("degraded")


def test_the_generated_vitest_config_disables_the_results_cache(home: Path) -> None:
    # vitest's results cache lands in apps/mouth/node_modules, the SHARED symlink in a Pro worktree
    _run(home, ALPHA)

    seen = (home / "vitest-config.seen").read_text()
    assert "cache: false" in seen and "testTimeout" in seen


def _stub_guard(home: Path, rc: int) -> None:
    """The real guard, except it reports a tooling error when only the alpha group is on the tree."""
    guard = home / "nuzantara" / "scripts" / "mouth_content_guard.sh"
    shutil.copy(guard, guard.with_name("mouth_content_guard.real.sh"))
    guard.write_text(f"""#!/bin/bash
wt="${{@: -1}}"; a="$wt/apps/mouth/src/content/articles"
if [ "$1" != "--base" ] && [ -n "$(find "$a" -name 'alpha*')" ] && [ -z "$(find "$a" -name 'beta*')" ]; then exit {rc}; fi
exec bash "$(dirname "$0")/mouth_content_guard.real.sh" "$@"
""")


@pytest.mark.parametrize(("guard_rc", "wrapper_rc"), [(3, 3), (64, 4)])
def test_a_tooling_error_while_trying_one_group_is_never_read_as_green(home: Path, guard_rc: int, wrapper_rc: int) -> None:
    _stub_guard(home, guard_rc)

    result = _run(home, ALPHA + BETA, FAKE_PAIR_RED="1")  # full set red -> each group is tried alone

    assert result.returncode == wrapper_rc
    assert _promoted(home) == set()
    assert not any(c[:2] == ["pr", "create"] for c in _gh_calls(home))
    assert _heartbeat(home).startswith("degraded")


def _many(n: int) -> list[str]:
    return [f"{ART}/business/g{i}.id.mdx" for i in range(n)]


def test_more_than_60_slug_groups_cannot_be_bisected_and_promote_nothing(home: Path) -> None:
    result = _run(home, _many(60) + BAD)  # 61 groups, the full set red

    assert result.returncode == 4
    assert _promoted(home) == set()
    assert not any(c[:2] == ["pr", "create"] for c in _gh_calls(home))


def test_exactly_60_slug_groups_are_still_bisected(home: Path) -> None:
    result = _run(home, _many(59) + BAD[:1])  # 60 groups, one of them bad

    assert result.returncode == 0, (home / "logs" / "translate-hourly-wrapper.log").read_text()
    assert _promoted(home) == set(_many(59))


def test_superseding_an_older_promote_pr_closes_without_delete_branch_and_releases_its_worktree(home: Path) -> None:
    repo = home / "nuzantara"
    old_task = "hourly-20261016053020"
    old_branch = f"agent/nuzantara/mouth/{old_task}"
    old_wt = repo / ".worktrees" / f"mouth-{old_task}"
    _git("worktree", "add", "-q", "-b", old_branch, str(old_wt), cwd=repo)
    _git("push", "-q", "-u", "origin", old_branch, cwd=old_wt)
    old_oid = _git("rev-parse", "HEAD", cwd=old_wt).strip()
    dirty_task = "hourly-20261016054000"
    dirty_branch = f"agent/nuzantara/mouth/{dirty_task}"
    dirty_wt = repo / ".worktrees" / f"mouth-{dirty_task}"
    _git("worktree", "add", "-q", "-b", dirty_branch, str(dirty_wt), cwd=repo)
    _git("push", "-q", "-u", "origin", dirty_branch, cwd=dirty_wt)
    dirty_oid = _git("rev-parse", "HEAD", cwd=dirty_wt).strip()
    (dirty_wt / "wip.txt").write_text("unsaved\n")
    ahead_task = "hourly-20261016055000"
    ahead_branch = f"agent/nuzantara/mouth/{ahead_task}"
    ahead_wt = repo / ".worktrees" / f"mouth-{ahead_task}"
    _git("worktree", "add", "-q", "-b", ahead_branch, str(ahead_wt), cwd=repo)
    _git("push", "-q", "-u", "origin", ahead_branch, cwd=ahead_wt)
    ahead_pushed_oid = _git("rev-parse", "HEAD", cwd=ahead_wt).strip()
    (ahead_wt / "local.txt").write_text("committed locally\n")
    _git("-c", "user.name=t", "-c", "user.email=t@t", "add", "local.txt", cwd=ahead_wt)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "local-only", cwd=ahead_wt)

    result = _run(
        home,
        ALPHA,
        FAKE_OLDER_OPEN_PRS=f"850 {old_oid} {old_branch}\n851 {dirty_oid} {dirty_branch}\n852 {ahead_pushed_oid} {ahead_branch}",
    )

    assert result.returncode == 0, (home / "logs" / "translate-hourly-wrapper.log").read_text()
    close_calls = [c for c in _gh_calls(home) if c[:2] == ["pr", "close"]]
    assert [c[:3] for c in close_calls] == [["pr", "close", "850"], ["pr", "close", "851"], ["pr", "close", "852"]]
    assert all("--delete-branch" not in c for c in close_calls)
    assert not old_wt.exists()
    assert dirty_wt.is_dir() and (dirty_wt / "wip.txt").read_text() == "unsaved\n"
    assert ahead_wt.is_dir() and (ahead_wt / "local.txt").read_text() == "committed locally\n"
    agent_log = (home / "agent_start.log").read_text()
    assert f"--release {old_task} --force" in agent_log
    assert f"--release {dirty_task} --force" not in agent_log
    assert f"--release {ahead_task} --force" not in agent_log
    remote_heads = _git("for-each-ref", "--format=%(refname)", "refs/heads/", cwd=home / "origin.git").split()
    assert f"refs/heads/{old_branch}" not in remote_heads
    assert f"refs/heads/{dirty_branch}" in remote_heads
    assert f"refs/heads/{ahead_branch}" in remote_heads


def test_startup_reaps_closed_or_merged_hourly_worktrees_and_spares_open_ones(home: Path) -> None:
    repo = home / "nuzantara"
    states = {}
    for suffix, state in (("010000", "CLOSED"), ("020000", "MERGED"), ("030000", "OPEN"), ("040000", "CLOSED"), ("050000", "CLOSED")):
        task = f"hourly-20261016{suffix}"
        branch = f"agent/nuzantara/mouth/{task}"
        wt = repo / ".worktrees" / f"mouth-{task}"
        _git("worktree", "add", "-q", "-b", branch, str(wt), cwd=repo)
        pr_oid = _git("rev-parse", "HEAD", cwd=wt).strip()
        states[branch] = f"{state} {pr_oid}" if state != "OPEN" else "OPEN "
    (repo / ".worktrees" / "mouth-hourly-20261016040000" / "dirty.txt").write_text("wip\n")
    ahead_wt = repo / ".worktrees" / "mouth-hourly-20261016050000"
    (ahead_wt / "local.txt").write_text("unpushed commit\n")
    _git("-c", "user.name=t", "-c", "user.email=t@t", "add", "local.txt", cwd=ahead_wt)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "local-only", cwd=ahead_wt)

    result = _run(home, [], FAKE_STALE_PR_STATES=json.dumps(states))

    assert result.returncode == 0, (home / "logs" / "translate-hourly-wrapper.log").read_text()
    assert not (repo / ".worktrees" / "mouth-hourly-20261016010000").exists()
    assert not (repo / ".worktrees" / "mouth-hourly-20261016020000").exists()
    assert (repo / ".worktrees" / "mouth-hourly-20261016030000").is_dir()
    assert (repo / ".worktrees" / "mouth-hourly-20261016040000").is_dir()
    assert ahead_wt.is_dir() and (ahead_wt / "local.txt").read_text() == "unpushed commit\n"
    log_lines = (home / "agent_start.log").read_text().splitlines()
    assert "--release hourly-20261016010000 --force" in log_lines
    assert "--release hourly-20261016020000 --force" in log_lines
    assert "--release hourly-20261016030000 --force" not in log_lines
    assert "--release hourly-20261016040000 --force" not in log_lines
    assert "--release hourly-20261016050000 --force" not in log_lines

