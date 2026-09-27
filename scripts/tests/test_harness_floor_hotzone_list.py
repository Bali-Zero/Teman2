"""Guilt + innocence for harness-floor.yml Step 2d (HOTZONE_PATTERNS may only grow
below floor 3), its wiring into Step 3, and tuple-vs-case-block drift. Every test runs
the REAL step text pulled from the workflow; only `/tmp/` is re-pointed at tmp_path."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "harness-floor.yml"
GATE = REPO_ROOT / ".github" / "workflows" / "hot-zone-pr-gate.yml"
LINTER = "scripts/evidence_pack_lint.py"
STEPS = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["harness-floor"]["steps"]
STEP_IDS = [s.get("id") for s in STEPS]
BASE = 'HOTZONE_PATTERNS: tuple[str, ...] = (\n    "a/*",\n    "b.py",\n)\n\n\ndef f():\n    return HOTZONE_PATTERNS\n'
ADDS = BASE.replace('"b.py",', '"b.py",\n    "c/*",')
DROPS = BASE.replace('    "b.py",\n', "")


def _run_block(step_id: str, tmp: Path) -> str:
    return STEPS[STEP_IDS.index(step_id)]["run"].replace("/tmp/", f"{tmp}/")


_ns: dict = {"__name__": "hzlist"}
exec(re.search(r"<<'PY'\n(.*?)\nPY\n", _run_block("hzlist", Path("/tmp")), re.S).group(1), _ns)
hotzone_patterns = _ns["hotzone_patterns"]


def _env(**extra: str) -> dict:
    return {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, **extra}


def _bash(script: str, cwd: Path, out: Path, **env: str) -> dict:
    out.touch()
    subprocess.run(["bash", "-e", "-c", script], cwd=cwd, env=_env(GITHUB_OUTPUT=str(out), **env), check=True, capture_output=True)
    return dict(line.split("=", 1) for line in out.read_text().splitlines() if "=" in line)


def _run_hzlist(tmp: Path, head: str | None, *, touched: bool = True, base_sha: str = "") -> dict:
    repo = tmp / "repo"
    (repo / "scripts").mkdir(parents=True)

    def git(*a: str) -> str:
        cfg = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
        return subprocess.run(["git", *cfg, *a], cwd=repo, env=_env(), check=True, capture_output=True, text=True).stdout.strip()

    git("init", "-q")
    for i, src in enumerate((BASE, head)):
        if src is None:
            (repo / LINTER).unlink()
        else:
            (repo / LINTER).write_text(src)
        git("add", "-A")
        git("commit", "-qm", str(i), "--allow-empty")
    (tmp / "changed-files.txt").write_text(f"{LINTER}\n" if touched else "docs/x.md\n")
    base = base_sha or git("rev-parse", "HEAD~1")
    return _bash(_run_block("hzlist", tmp), repo, tmp / "out", BASE_SHA=base, HEAD_SHA=git("rev-parse", "HEAD"))


def test_innocence_real_linter_parses():
    got = hotzone_patterns((REPO_ROOT / LINTER).read_text(encoding="utf-8"))
    assert got and ".github/workflows/*" in got


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
    ],
    ids=["reassign", "del", "global", "import-as", "star-import", "keyword", "subscript-key", "concat", "list", "renamed", "syntax"],
)
def test_guilt_unprovable_shapes_fail_closed(src):
    assert hotzone_patterns(src) is None


@pytest.mark.parametrize(
    "head,kw,floor3",
    [
        (DROPS, {}, "true"),
        (BASE + "HOTZONE_PATTERNS = ()\n", {}, "true"),
        (None, {}, "true"),
        (ADDS, {"base_sha": "0" * 40}, "true"),
        (ADDS, {}, "false"),
        (BASE.replace("return HOTZONE_PATTERNS", "return tuple(HOTZONE_PATTERNS)"), {}, "false"),
        (DROPS, {"touched": False}, "false"),
    ],
    ids=["guilt-drops", "guilt-unparseable-head", "guilt-linter-deleted", "guilt-no-merge-base", "innocence-adds", "innocence-unrelated-edit", "innocence-linter-not-in-diff"],
)
def test_step_2d_end_to_end(tmp_path, head, kw, floor3):
    assert _run_hzlist(tmp_path, head, **kw)["floor3"] == floor3


@pytest.mark.parametrize("verdict,floor,source", [("true", "3", "path"), ("", "3", "path"), ("false", "1", "none")])
def test_step3_applies_the_verdict(tmp_path, verdict, floor, source):
    assert STEP_IDS.index("hzlist") < STEP_IDS.index("detfloor")
    assert STEPS[STEP_IDS.index("detfloor")]["env"]["HZLIST_FLOOR3"] == "${{ steps.hzlist.outputs.floor3 }}"
    (tmp_path / "changed-files.txt").write_text(f"{LINTER}\n")
    (tmp_path / "net-lines-numstat.txt").write_text(f"1\t0\t{LINTER}\n")  # non-empty EXTRA_ARGS: macOS bash 3.2 + set -u
    env = {"NETLINES_AVAILABLE": "true", "WFPATCH_AVAILABLE": "false", "HZLIST_FLOOR3": verdict, "GITHUB_STEP_SUMMARY": str(tmp_path / "summary")}
    got = _bash(_run_block("detfloor", tmp_path), REPO_ROOT, tmp_path / "out", **env)
    assert (got["floor"], got["source"]) == (floor, source)


def case_block_patterns(text: str) -> tuple[str, ...] | None:
    blocks = re.findall(r'case "\$f" in\n(.*?)\)\n', text, re.S)
    return tuple(re.findall(r"[^\s|\\]+", blocks[0])) if len(blocks) == 1 else None


def drift(linter_src: str, gate_src: str) -> tuple[list[str], list[str]]:
    tup, case = hotzone_patterns(linter_src), case_block_patterns(gate_src)
    assert tup is not None and case is not None, "a list could not be read — drift cannot be ruled out"
    return sorted(set(tup) - set(case)), sorted(set(case) - set(tup))


def test_real_tuple_matches_hot_zone_gate_case_block():
    only_tuple, only_case = drift((REPO_ROOT / LINTER).read_text(encoding="utf-8"), GATE.read_text(encoding="utf-8"))
    assert (only_tuple, only_case) == ([], []), f"only in HOTZONE_PATTERNS: {only_tuple}; only in the case-block: {only_case}"


def test_drift_guilt_and_innocence():
    gate = '    case "$f" in\n      a/*|\\\n      b.py)\n        HIT=1\n'
    assert drift(BASE, gate) == ([], [])
    assert drift(BASE, gate.replace("a/*|\\\n      ", "")) == (["a/*"], [])
    assert drift(DROPS, gate) == ([], ["b.py"])
    with pytest.raises(AssertionError):
        drift(BASE, gate + gate)
