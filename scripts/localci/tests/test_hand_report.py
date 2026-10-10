"""hand_report.sh — phase E, step 1: the report the operator runs by hand must be the tick's merger.py, with the tick's files.

The 2026-10-10 recipe extracted merger.py and hosted_compare.py only; the report's stale-verdict judge loads runner.py beside
merger.py, so every hosted-stale row would have stayed FALSE_GREEN and READY could never be true (found by the follow-up's gate).
"""
from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

LOCALCI = Path(__file__).resolve().parents[1]
SCRIPT = LOCALCI / "hand_report.sh"
TICK = LOCALCI / "localci_merger_tick.sh"
PLIST = LOCALCI.parents[1] / "infra" / "launchagents" / "com.balizero.localci-merger.plist"
LOOP_RE = re.compile(r"^[ \t]*for f in ([^;]+); do\b", re.M)
SHOW_RE = re.compile(r'\bshow "[^"]*:scripts/localci/([^"]+)"')


def extracted(text: str) -> set[str]:
    """Every file a script extracts from scripts/localci/ with `git show "<rev>:scripts/localci/<x>"`: the literal names, and
    the names of the `for f in ...; do` loop each `$f` show sits in. A show the parse cannot place fails the test, so a new
    extraction shape is never silently left out of the comparison."""
    shows = SHOW_RE.findall(text)   # any other shape (unquoted, cat-file, a flag, a split quote) fails here, never left out
    assert text.count(":scripts/localci/") == len(shows), "a scripts/localci/ extraction the parse cannot read"
    names: set[str] = set()
    loops = [(m.start(), text.index("done", m.end()), m.group(1).split()) for m in LOOP_RE.finditer(text)]
    for m in SHOW_RE.finditer(text):
        if m.group(1) != "$f":
            names.add(m.group(1))
            continue
        inside = [files for start, end, files in loops if start < m.start() < end]
        assert inside, f"a `show ...:scripts/localci/$f` outside any for-loop the parse reads: {text[m.start():m.end()]}"
        names |= set(inside[-1])
    return names


def test_the_hand_report_extracts_exactly_the_files_the_tick_extracts():
    tick = extracted(TICK.read_text())
    assert {"merger.py", "hosted_compare.py", "runner.py"} <= tick   # the parse itself still sees the tick's loops
    assert extracted(SCRIPT.read_text()) == tick


@pytest.mark.parametrize("line", ['git show --no-textconv "$SHA:scripts/localci/a.py" > a', "git show $SHA:scripts/localci/b.py > b",
                                  'git cat-file -p "$SHA:scripts/localci/c.py" > c', 'git show "$SHA":scripts/localci/d.py > d'])
def test_an_extraction_the_parse_cannot_read_fails_it(line):
    with pytest.raises(AssertionError, match="cannot read"):
        extracted(line + "\n")


def test_the_parse_sees_every_extraction_shape():
    assert extracted('  for f in a.py b.py; do\n    git show "$SHA:scripts/localci/$f" > x\n  done\n'
                     'git -C r show "$SHA:scripts/localci/c.yaml" > y\n') == {"a.py", "b.py", "c.yaml"}


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()


STUB = '''import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
state = sys.argv[sys.argv.index("--state-dir") + 1]
json.dump({"argv": sys.argv[1:], "beside": sorted(os.listdir(here)), "here": here, "marker": open(os.path.join(here, "runner.py")).read(),
           "env": dict(os.environ), "isolated": sys.flags.isolated}, open(os.path.join(state, "out.json"), "w"))
'''
# the tick's git isolation (localci_merger_tick.sh), and what bash and macOS add to any process by themselves
GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
           "GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null",
           "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false", "GIT_CONFIG_KEY_2": "core.attributesFile",
           "GIT_CONFIG_VALUE_2": "/dev/null"}
SHELL_ADDS = {"PWD", "OLDPWD", "SHLVL", "_", "__CF_USER_TEXT_ENCODING"}


def mirror(tmp_path, refs: dict[str, str]) -> Path:
    """A bare mirror whose refs (name -> runner.py marker) each point at their own commit, and a venv python beside it."""
    src = tmp_path / "src"
    (src / "scripts" / "localci").mkdir(parents=True)
    for f in ("hosted_compare.py", "prune.py", "contexts_matrix.yaml"):
        (src / "scripts" / "localci" / f).write_text("# stand-in\n")
    (src / "scripts" / "localci" / "merger.py").write_text(STUB)
    _git(tmp_path, "init", "-q", str(src))
    shas = {}
    for ref, marker in refs.items():
        (src / "scripts" / "localci" / "runner.py").write_text(marker)
        _git(src, "add", "-A")
        _git(src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", marker)
        shas[ref] = _git(src, "rev-parse", "HEAD")
    state = tmp_path / "state"
    state.mkdir()
    _git(tmp_path, "clone", "-q", "--bare", str(src), str(state / "repo.git"))
    for ref, sha in shas.items():
        _git(state / "repo.git", "update-ref", ref, sha)
    (state / "venv" / "bin").mkdir(parents=True)
    (state / "venv" / "bin" / "python").symlink_to(sys.executable)
    return state


def run(state: Path) -> dict:
    # a caller's shell full of what must not reach the report, the sentinel pre-set included
    env = {**os.environ, "GIT_DIR": "/nonexistent", "GH_TOKEN": "not-a-token", "PYTHONPATH": "/nonexistent",
           "LOCALCI_HAND_REPORT_CLEAN": "1", "LC_CTYPE": "en_US.ISO8859-1"}
    subprocess.run(["bash", str(SCRIPT), str(state)], check=True, capture_output=True, text=True, env=env, timeout=60)
    return json.loads((state / "out.json").read_text())


def test_the_hand_report_runs_the_mirrors_merger_report_with_the_ticks_files_in_launchds_environment(tmp_path):
    state = mirror(tmp_path, {"refs/merger/wrapper": "wrapper code"})
    out = run(state)
    assert out["argv"] == ["report", "--repo", "Bali-Zero/Teman2", "--state-dir", str(state)]
    assert out["beside"] == sorted(extracted(TICK.read_text())) and out["marker"] == "wrapper code"
    assert out["isolated"] == 1   # python -I, as the tick runs it
    env = out["env"]
    # Python's PEP 538 coercion sets LC_CTYPE itself under the C locale env -i leaves; the caller's own value never arrives
    assert env.pop("LC_CTYPE", "UTF-8") in {"UTF-8", "C.UTF-8"}
    assert set(env) - SHELL_ADDS == {"HOME", "PATH", "LOCALCI_HAND_REPORT_CLEAN", *GIT_ENV}   # nothing of the caller's shell
    assert env["PATH"] == plistlib.loads(PLIST.read_bytes())["EnvironmentVariables"]["PATH"]   # launchd's PATH, gh included
    assert {k: env[k] for k in GIT_ENV} == GIT_ENV and env["HOME"] == os.environ["HOME"]
    assert not Path(out["here"]).exists()   # the extracted code is removed on exit


def test_the_wrapper_ref_wins_over_the_base_ref(tmp_path):
    out = run(mirror(tmp_path, {"refs/merger/base": "base code", "refs/merger/wrapper": "wrapper code"}))
    assert out["marker"] == "wrapper code"


def test_without_the_wrapper_ref_the_hand_report_reads_the_base_ref(tmp_path):
    out = run(mirror(tmp_path, {"refs/merger/base": "base code"}))
    assert out["marker"] == "base code"
