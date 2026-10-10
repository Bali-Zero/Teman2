"""hand_report.sh — phase E, step 1: the report the operator runs by hand must be the tick's merger.py, with the tick's files.

The 2026-10-10 recipe extracted merger.py and hosted_compare.py only; the report's stale-verdict judge loads runner.py beside
merger.py, so every hosted-stale row would have stayed FALSE_GREEN and READY could never be true (found by the follow-up's gate).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

LOCALCI = Path(__file__).resolve().parents[1]
SCRIPT = LOCALCI / "hand_report.sh"
TICK = LOCALCI / "localci_merger_tick.sh"
FILES_RE = re.compile(r"^for f in ([^;]+); do\b", re.M)


def extracted(text: str) -> set[str]:
    """The files a `for f in ...; do` loop extracts from scripts/localci/ with `git show ...:scripts/localci/$f`."""
    names: set[str] = set()
    for m in FILES_RE.finditer(text):
        body = text[m.end(): text.index("done", m.end())]
        if 'scripts/localci/$f"' in body:
            names |= set(m.group(1).split())
    return names


def test_the_hand_report_extracts_exactly_the_files_the_tick_extracts():
    tick = extracted(TICK.read_text())
    assert {"merger.py", "hosted_compare.py", "runner.py"} <= tick   # the parse itself still sees the tick's loops
    assert extracted(SCRIPT.read_text()) == tick


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()


STUB = '''import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
state = sys.argv[sys.argv.index("--state-dir") + 1]
json.dump({"argv": sys.argv[1:], "beside": sorted(os.listdir(here)), "here": here, "marker": open(os.path.join(here, "runner.py")).read(),
           "env": sorted(os.environ)}, open(os.path.join(state, "out.json"), "w"))
'''


def mirror(tmp_path, ref: str, marker: str) -> Path:
    src = tmp_path / "src"
    (src / "scripts" / "localci").mkdir(parents=True)
    for f in ("hosted_compare.py", "prune.py", "contexts_matrix.yaml"):
        (src / "scripts" / "localci" / f).write_text("# stand-in\n")
    (src / "scripts" / "localci" / "merger.py").write_text(STUB)
    (src / "scripts" / "localci" / "runner.py").write_text(marker)
    _git(tmp_path, "init", "-q", str(src))
    _git(src, "add", "-A")
    _git(src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
    state = tmp_path / "state"
    state.mkdir()
    _git(tmp_path, "clone", "-q", "--bare", str(src), str(state / "repo.git"))
    _git(state / "repo.git", "update-ref", ref, _git(src, "rev-parse", "HEAD"))
    (state / "venv" / "bin").mkdir(parents=True)
    (state / "venv" / "bin" / "python").symlink_to(sys.executable)
    return state


def run(state: Path) -> dict:
    env = {**os.environ, "GIT_DIR": "/nonexistent", "GH_TOKEN": "not-a-token", "PYTHONPATH": "/nonexistent"}
    subprocess.run(["bash", str(SCRIPT), str(state)], check=True, capture_output=True, text=True, env=env, timeout=60)
    return json.loads((state / "out.json").read_text())


def test_the_hand_report_runs_the_mirrors_merger_report_with_the_ticks_files_in_launchds_environment(tmp_path):
    state = mirror(tmp_path, "refs/merger/wrapper", "wrapper code")
    out = run(state)
    assert out["argv"] == ["report", "--repo", "Bali-Zero/Teman2", "--state-dir", str(state)]
    assert out["beside"] == sorted(extracted(TICK.read_text())) and out["marker"] == "wrapper code"
    assert not {"GH_TOKEN", "GIT_DIR", "PYTHONPATH"} & set(out["env"])   # the caller's shell does not reach the report
    assert not Path(out["here"]).exists()   # the extracted code is removed on exit


def test_without_the_wrapper_ref_the_hand_report_reads_the_base_ref(tmp_path):
    out = run(mirror(tmp_path, "refs/merger/base", "base code"))
    assert out["marker"] == "base code"
