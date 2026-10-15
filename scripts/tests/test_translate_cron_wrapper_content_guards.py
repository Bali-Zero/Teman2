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
