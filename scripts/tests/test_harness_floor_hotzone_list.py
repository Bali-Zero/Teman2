"""Guilt + innocence for harness-floor.yml Step 2d (HOTZONE_PATTERNS may only grow
below floor 3, drift vs hot-zone-pr-gate.yml flagged) and its wiring into Step 3. Every
test runs the REAL step text pulled from the workflow; only `/tmp/` is re-pointed."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "harness-floor.yml"
LINTER, GATE = "scripts/evidence_pack_lint.py", ".github/workflows/hot-zone-pr-gate.yml"
STEPS = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["harness-floor"]["steps"]
STEP_IDS = [s.get("id") for s in STEPS]
BASE = 'HOTZONE_PATTERNS: tuple[str, ...] = (\n    "a/*",\n    "b.py",\n)\n\n\ndef f():\n    return HOTZONE_PATTERNS\n'
ADDS = BASE.replace('"b.py",', '"b.py",\n    "c/*",')
DROPS = BASE.replace('    "b.py",\n', "")
UTF7 = "# -*- coding: utf-7 -*-\n" + BASE + '# +AAo-HOTZONE_PATTERNS = ("a/*",)\n'
GATE_BASE = '      case "$f" in\n        a/*|\\\n        b.py)\n          HIT=1\n          ;;\n      esac\n'
GATE_ADDS = GATE_BASE.replace("b.py)", "b.py|\\\n        c/*)")
DRIFT = "::warning::HOTZONE_PATTERNS and hot-zone-pr-gate.yml's case-block differ"


def _run_block(step_id: str, tmp: Path) -> str:
    return STEPS[STEP_IDS.index(step_id)]["run"].replace("/tmp/", f"{tmp}/")


_ns: dict = {"__name__": "hzlist"}
exec(re.search(r"<<'PY'\n(.*?)\nPY\n", _run_block("hzlist", Path("/tmp")), re.S).group(1), _ns)
hotzone_patterns, case_block = _ns["hotzone_patterns"], _ns["case_block"]


def _env(**extra: str) -> dict:
    return {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, **extra}


def _bash(script: str, cwd: Path, out: Path, **env: str) -> tuple[dict, str]:
    out.touch()
    r = subprocess.run(["bash", "-e", "-c", script], cwd=cwd, env=_env(GITHUB_OUTPUT=str(out), **env), check=True, capture_output=True, text=True)
    return dict(line.split("=", 1) for line in out.read_text().splitlines() if "=" in line), r.stdout


def _run_hzlist(tmp, head, *, base=BASE, gate=GATE_BASE, main_after="", touched=(LINTER,), base_sha=""):
    repo = tmp / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "scripts").mkdir()

    def git(*a: str) -> str:
        cfg = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
        return subprocess.run(["git", *cfg, *a], cwd=repo, env=_env(), check=True, capture_output=True, text=True).stdout.strip()

    def commit(src: str | None, gate_src: str) -> str:
        (repo / LINTER).write_text(src) if src is not None else (repo / LINTER).unlink()
        (repo / GATE).write_text(gate_src)
        git("add", "-A")
        git("commit", "-qm", "c", "--allow-empty")
        return git("rev-parse", "HEAD")

    git("init", "-q")
    fork = main = commit(base, GATE_BASE)
    if main_after:  # main moves on after the PR forked: the step must compare against the FORK point (W102)
        main = commit(main_after, GATE_ADDS)
        git("checkout", "-q", fork)
    head_sha = commit(head, gate)
    (tmp / "changed-files.txt").write_text("".join(f"{p}\n" for p in touched))
    out, stdout = _bash(_run_block("hzlist", tmp), repo, tmp / "out", BASE_SHA=base_sha or main, HEAD_SHA=head_sha)
    return out["floor3"], DRIFT in stdout


def test_innocence_real_linter_and_gate_parse():
    got = hotzone_patterns((REPO_ROOT / LINTER).read_bytes())
    assert got and ".github/workflows/*" in got
    assert len(case_block((REPO_ROOT / GATE).read_text(encoding="utf-8")) or ()) >= 10


@pytest.mark.parametrize("extra", ['LABEL = "HOTZONE_PATTERNS"\n', "import re\nX = re.compile('x')\n", 'def g():\n    """HOTZONE_PATTERNS = ()"""\n'])
def test_innocence_mentions_that_bind_nothing(extra):
    assert hotzone_patterns(BASE + extra) == ("a/*", "b.py")


def test_guilt_commented_out_pattern_is_dropped():
    assert hotzone_patterns(BASE.replace('    "b.py",', '    # "b.py",')) == ("a/*",)


@pytest.mark.parametrize(
    "src",
    [
        BASE + "HOTZONE_PATTERNS = HOTZONE_PATTERNS[:1]\n",
        BASE + "del HOTZONE_PATTERNS\n",
        BASE + "def g():\n    global HOTZONE_PATTERNS\n",
        BASE + "from os import sep as HOTZONE_PATTERNS\n",
        BASE + "from os.path import *\n",
        BASE + "globals().update(HOTZONE_PATTERNS=())\n",
        BASE + "globals()['HOTZONE_PATTERNS'] = ()\n",
        BASE.replace('"b.py"', '"b" + ".py"'),
        BASE.replace("= (", "= [").replace(")\n\n", "]\n\n"),
        BASE.replace("HOTZONE_PATTERNS:", "HOTZONE_LIST:"),
        BASE + "def (:\n",
        BASE + 'exec("HOTZONE_" + "PATTERNS = ()")\n',
        BASE + 'import sys\nsetattr(sys.modules[__name__], "HOTZONE_" + "PATTERNS", ())\n',
        BASE + 'import sys\ngetattr(sys.modules[__name__], "__di" + "ct__")["HOTZONE_" + "PATTERNS"] = ()\n',
        BASE + "import importlib\n",
        BASE + '(lambda: 0).__globals__["HOTZONE_" + "PATTERNS"] = ()\n',
        UTF7.encode(),
    ],
    ids=["reassign", "del", "global", "import-as", "star-import", "keyword", "subscript-key", "concat", "list", "renamed", "syntax", "exec", "setattr", "getattr-dict", "importlib", "func-globals", "utf7-cookie"],
)
def test_guilt_unprovable_shapes_fail_closed(src):
    assert hotzone_patterns(src) is None


@pytest.mark.parametrize(
    "head,kw,expected",
    [
        (DROPS, {}, ("true", True)),
        (BASE + "HOTZONE_PATTERNS = ()\n", {}, ("true", False)),
        (None, {}, ("true", False)),
        (ADDS, {"base_sha": "0" * 40, "gate": GATE_ADDS}, ("true", False)),
        (ADDS, {"base": BASE + "HOTZONE_PATTERNS = ()\n", "gate": GATE_ADDS}, ("true", False)),
        (UTF7, {}, ("true", False)),
        (ADDS, {"gate": GATE_ADDS}, ("false", False)),
        (ADDS, {}, ("false", True)),
        (BASE, {"gate": GATE_ADDS, "touched": (GATE,)}, ("false", True)),
        (BASE.replace("return HOTZONE_PATTERNS", "return tuple(HOTZONE_PATTERNS)"), {}, ("false", False)),
        (DROPS, {"touched": ("docs/x.md",)}, ("false", False)),
        (BASE.replace("return", "return  "), {"main_after": ADDS}, ("false", False)),
    ],
    ids=[
        "guilt-drops", "guilt-unparseable-head", "guilt-linter-deleted", "guilt-no-merge-base", "guilt-unparseable-base", "guilt-utf7-cookie",
        "innocence-adds-both-lists", "flag-adds-tuple-only", "flag-gate-only-drift", "innocence-unrelated-edit", "innocence-neither-in-diff", "innocence-main-moved-on",
    ],
)
def test_step_2d_end_to_end(tmp_path, head, kw, expected):
    assert _run_hzlist(tmp_path, head, **kw) == expected


@pytest.mark.parametrize(
    "gate,expected",
    [
        ('    case "$f" in\n      a/*|b.py) HIT=1 ;;\n', {"a/*", "b.py"}),
        ('    # case "$f" in\n    #   z/*)\n' + GATE_BASE, {"a/*", "b.py"}),
        (GATE_BASE + GATE_BASE, None),
        ("no case arm here\n", None),
    ],
    ids=["one-line-arm", "commented-decoy-ignored", "two-arms-unreadable", "no-arm-unreadable"],
)
def test_case_block_reads_only_the_one_live_arm(gate, expected):
    assert case_block(gate) == expected


def test_step_2d_wiring():
    step, detfloor = STEPS[STEP_IDS.index("hzlist")], STEPS[STEP_IDS.index("detfloor")]
    assert step["env"]["BASE_SHA"] == "${{ github.event.merge_group.base_sha || github.event.pull_request.base.sha || 'main' }}"
    assert step["env"]["HEAD_SHA"] == "${{ github.event.merge_group.head_sha || github.event.pull_request.head.sha || github.sha }}"
    assert step["if"] == detfloor["if"] == "steps.kill_switch.outputs.disabled != 'true'"
    assert STEP_IDS.index("hzlist") < STEP_IDS.index("detfloor")
    assert detfloor["env"]["HZLIST_FLOOR3"] == "${{ steps.hzlist.outputs.floor3 }}"


@pytest.mark.parametrize("verdict,floor,source", [("true", "3", "path"), ("", "3", "path"), ("false", "1", "none")])
def test_step3_applies_the_verdict(tmp_path, verdict, floor, source):
    (tmp_path / "changed-files.txt").write_text(f"{LINTER}\n")
    (tmp_path / "net-lines-numstat.txt").write_text(f"1\t0\t{LINTER}\n")  # non-empty EXTRA_ARGS: macOS bash 3.2 + set -u
    env = {"NETLINES_AVAILABLE": "true", "WFPATCH_AVAILABLE": "false", "HZLIST_FLOOR3": verdict, "GITHUB_STEP_SUMMARY": str(tmp_path / "summary")}
    got, _ = _bash(_run_block("detfloor", tmp_path), REPO_ROOT, tmp_path / "out", **env)
    assert (got["floor"], got["source"]) == (floor, source)
