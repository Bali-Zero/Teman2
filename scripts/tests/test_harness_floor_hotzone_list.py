"""Guilt + innocence for the hot-zone list's two guards. (1) harness-floor.yml Step 2d, the
floor-3 text check on HOTZONE_PATTERNS, run from the REAL step text in the YAML (only `/tmp/`
is re-pointed). (2) The behavioural check (coordinator ruling 2026-09-27, option B): the HEAD
linter's real floor computation must floor one path per pattern of hot-zone-pr-gate.yml's
case-block at 3, and the two lists must be identical. This file is itself in HOTZONE_PATTERNS."""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess
import sys
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
CASE = '      case "$f" in\n        a/*|\\\n        b.py)\n          HIT=1\n          ;;\n      esac\n'


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


def _run_hzlist(tmp, head, *, base=BASE, main_after="", touched=True, base_sha=""):
    repo = tmp / "repo"
    (repo / "scripts").mkdir(parents=True)

    def git(*a: str) -> str:
        cfg = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
        return subprocess.run(["git", *cfg, *a], cwd=repo, env=_env(), check=True, capture_output=True, text=True).stdout.strip()

    def commit(src: str | None) -> str:
        (repo / LINTER).write_text(src) if src is not None else (repo / LINTER).unlink()
        git("add", "-A")
        git("commit", "-qm", "c", "--allow-empty")
        return git("rev-parse", "HEAD")

    git("init", "-q")
    fork = main = commit(base)
    if main_after:  # main moves on after the PR forked: the step must compare against the FORK point (W102)
        main = commit(main_after)
        git("checkout", "-q", fork)
    head_sha = commit(head)
    (tmp / "changed-files.txt").write_text(f"{LINTER}\n" if touched else "docs/x.md\n")
    return _bash(_run_block("hzlist", tmp), repo, tmp / "out", BASE_SHA=base_sha or main, HEAD_SHA=head_sha)["floor3"]


def test_innocence_real_linter_parses():
    got = hotzone_patterns((REPO_ROOT / LINTER).read_bytes())
    assert got and ".github/workflows/*" in got and "scripts/tests/test_harness_floor_hotzone_list.py" in got


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
    "head,kw,floor3",
    [
        (DROPS, {}, "true"),
        (BASE + "HOTZONE_PATTERNS = ()\n", {}, "true"),
        (None, {}, "true"),
        (ADDS, {"base_sha": "0" * 40}, "true"),
        (ADDS, {"base": BASE + "HOTZONE_PATTERNS = ()\n"}, "true"),
        (UTF7, {}, "true"),
        (ADDS, {}, "false"),
        (BASE.replace("return HOTZONE_PATTERNS", "return tuple(HOTZONE_PATTERNS)"), {}, "false"),
        (DROPS, {"touched": False}, "false"),
        (BASE.replace("return", "return  "), {"main_after": ADDS}, "false"),
    ],
    ids=[
        "guilt-drops", "guilt-unparseable-head", "guilt-linter-deleted", "guilt-no-merge-base", "guilt-unparseable-base", "guilt-utf7-cookie",
        "innocence-adds", "innocence-unrelated-edit", "innocence-linter-not-in-diff", "innocence-main-moved-on",
    ],
)
def test_step_2d_end_to_end(tmp_path, head, kw, floor3):
    assert _run_hzlist(tmp_path, head, **kw) == floor3


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
    got = _bash(_run_block("detfloor", tmp_path), REPO_ROOT, tmp_path / "out", **env)
    assert (got["floor"], got["source"]) == (floor, source)


# --- the behavioural check: the oracle is the case-block, a workflow file (floor 3 to narrow) ---


def case_block(text: str) -> set[str] | None:
    """The patterns of the ONE live `case "$f" in ... esac`, else None (zero or several
    statements, or a statement with more than one arm: a second arm must not go unread)."""
    stmts = re.findall(r'^[ \t]*case "\$f" in\n(.*?)^[ \t]*esac\b', text, re.S | re.M)
    if len(stmts) != 1 or stmts[0].count(";;") != 1:
        return None
    return set(re.findall(r"[^\s|\\]+", stmts[0].split(")", 1)[0]))


def _narrowed(scripts: Path, patterns, tmp: Path) -> dict[str, str]:
    """{pattern: floor} for every pattern NOT floored at 3, computed the way CI computes it:
    `python3 <scripts>/evidence_pack_lint.py --print-floor` as __main__ with its real import
    closure, on a diff of ONE concrete path matching the pattern."""
    floors = {}
    for i, pat in enumerate(sorted(patterns)):
        assert "[" not in pat, f"no concrete-path synthesiser for {pat!r}"
        path = pat.replace("*", "x").replace("?", "x")
        assert fnmatch.fnmatchcase(path, pat)
        (tmp / f"cf{i}").write_text(f"{path}\n")
        r = subprocess.run([sys.executable, str(scripts / "evidence_pack_lint.py"), "--print-floor", "--changed-files-file", str(tmp / f"cf{i}")], cwd=scripts.parent, env=_env(), capture_output=True, text=True)
        floors[pat] = r.stdout.strip() or f"rc={r.returncode}: {r.stderr.strip()[-200:]}"
    return {p: f for p, f in floors.items() if f != "3"}


def _closure_copy(tmp: Path, after_tuple: str = "", eligibility_tail: str = "", planted: str = "") -> Path:
    scripts = tmp / "scripts"
    shutil.copytree(REPO_ROOT / "scripts" / "conductor", scripts / "conductor", ignore=shutil.ignore_patterns("__pycache__"))
    src = (REPO_ROOT / LINTER).read_text(encoding="utf-8")
    end = src.index("\n)\n", src.index("HOTZONE_PATTERNS: tuple[str, ...] = (")) + 3
    (scripts / "evidence_pack_lint.py").write_text(src[:end] + after_tuple + src[end:], encoding="utf-8")
    elig = scripts / "conductor" / "review_eligibility.py"
    elig.write_text(elig.read_text(encoding="utf-8") + eligibility_tail, encoding="utf-8")
    if planted:
        (scripts / "_hz_planted.py").write_text(planted, encoding="utf-8")
    return scripts


def test_real_tuple_and_case_block_are_the_same_list():
    tup, case = hotzone_patterns((REPO_ROOT / LINTER).read_bytes()), case_block((REPO_ROOT / GATE).read_text(encoding="utf-8"))
    assert tup is not None and case is not None, "a list could not be read — drift cannot be ruled out"
    only_tuple, only_case = sorted(set(tup) - case), sorted(case - set(tup))
    assert not only_tuple and not only_case, (
        f"HOTZONE_PATTERNS and {GATE}'s case-block must list the same patterns (add to BOTH): "
        f"only in the tuple: {only_tuple}; only in the case-block: {only_case}"
    )


def test_head_linter_really_floors_every_oracle_pattern_at_3(tmp_path):
    oracle = case_block((REPO_ROOT / GATE).read_text(encoding="utf-8"))
    assert oracle, "the oracle case-block could not be read"
    assert _narrowed(REPO_ROOT / "scripts", oracle, tmp_path) == {}, "the HEAD linter no longer floors these hot-zone patterns at 3"


ORACLE = {".github/workflows/*", "apps/backend-rag/backend/db/migrations_v2/*", "fly.toml"}
DROP_WORKFLOWS = 'import sys\nm = sys.modules["__main__"]\nm.HOTZONE_PATTERNS = tuple(p for p in m.HOTZONE_PATTERNS if p != ".github/workflows/*")\n'


@pytest.mark.parametrize(
    "kw,narrowed",
    [
        ({}, set()),
        ({"after_tuple": 'HOTZONE_PATTERNS = HOTZONE_PATTERNS + ("c/*",)\n'}, set()),
        ({"after_tuple": "import _hz_planted  # noqa: E402,F401\n", "planted": DROP_WORKFLOWS}, {".github/workflows/*"}),
        ({"eligibility_tail": "\nimport fnmatch as _f\n_o = _f.fnmatchcase\n_f.fnmatchcase = lambda n, p: p != 'fly.toml' and _o(n, p)\n"}, {"fly.toml"}),
        ({"after_tuple": "import pickle\npickle.loads(b\"cbuiltins\\nexec\\n(S'import sys;m=sys.modules[\\\"__main__\\\"];m.HOTZONE_PATTERNS=m.HOTZONE_PATTERNS[1:]'\\ntR.\")\n"}, {"apps/backend-rag/backend/db/migrations_v2/*"}),
    ],
    ids=["innocence-unchanged", "innocence-added-pattern", "guilt-planted-module-rebinds", "guilt-closure-patches-fnmatch", "guilt-pickle-exec-rebinds"],
)
def test_behavioural_check_on_a_copy_of_the_closure(tmp_path, kw, narrowed):
    assert set(_narrowed(_closure_copy(tmp_path, **kw), ORACLE, tmp_path)) == narrowed


@pytest.mark.parametrize(
    "text,expected",
    [
        (CASE, {"a/*", "b.py"}),
        ('    case "$f" in\n      a/*|b.py) HIT=1 ;;\n    esac\n', {"a/*", "b.py"}),
        ('    # case "$f" in\n    #   z/*) ;;\n    # esac\n' + CASE, {"a/*", "b.py"}),
        ('    case "$f" in\n      a/*) HIT=1 ;;\n      c/*) HIT=1 ;;\n    esac\n', None),
        (CASE + CASE, None),
        ("no case statement here\n", None),
    ],
    ids=["multi-line-arm", "one-line-arm", "commented-decoy-ignored", "second-arm-refused", "two-statements-refused", "none-refused"],
)
def test_case_block_reader(text, expected):
    assert case_block(text) == expected
