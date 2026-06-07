#!/usr/bin/env python3
"""Anti-reward-hacking AST linter — P1 STRATO-1 (FASE-3 of the SOTA meta-dev-loop).

Spec: research/operations/specs/P1-verify-the-verifiers.md §3 STRATO-1, §7 #4.

An LLM agent that reward-hacks SABOTAGES the very detectors meant to catch it
(~12% of the time, Anthropic arXiv 2511.18397). The cheapest cheats are on the
TEST suite: make a test that always passes, so the green check is meaningless.
This linter flags the common patterns DETERMINISTICALLY (pure stdlib `ast`, no
semgrep dependency → runs identically on M5 / Pro / CI).

HONEST FRAMING (spec §7 #2, lines 177/203): this is a FIRST-LEVEL HEURISTIC,
EASILY EVADED, NOT a reliable barrier. A determined agent routes around it
(e.g. tautology hidden behind a helper). Its value is raising the cost of the
LAZY cheat and making the obvious ones visible in review — not proving tests are
honest. The reliable layer is STRATO-5 (human gate) + mutation testing (STRATO-2,
deferred). Treat a clean run as "no obvious test-cheating", never "tests are good".

Patterns flagged (each is a known test-reward-hack):
  RH001  assert True / assert 1 / assert <non-zero-const>   — tautological assert
  RH002  assert 1 == 1 / assert "x" == "x"                  — self-equal tautology
  RH003  pytest.raises(Exception) / pytest.raises(BaseException) — too-broad raises
  RH004  sys.exit(0) inside a test function                 — bail before the assert
  RH005  a test function with ZERO assert / pytest.raises / self.assert*  — asserts nothing

Usage:
    python3 scripts/lint_test_reward_hacking.py <path> [<path> ...]
    python3 scripts/lint_test_reward_hacking.py            # defaults to staged test files
Exit 0 = clean (or no test files). Exit 1 = at least one finding.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Broad exception types that make `pytest.raises(...)` assert almost nothing.
_BROAD_EXC = {"Exception", "BaseException"}
# Names that count as an assertion inside a test body.
_ASSERT_CALL_PREFIXES = ("assert",)  # self.assertEqual, self.assertTrue, ...


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.code} {self.message}"


def _is_test_file(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py")


def _const_is_truthy(node: ast.AST) -> bool:
    """True if node is a constant that is always truthy (assert <this> is tautological)."""
    return isinstance(node, ast.Constant) and bool(node.value) and not isinstance(
        node.value, str
    ) or (isinstance(node, ast.Constant) and node.value is True)


def _self_equal(cmp: ast.Compare) -> bool:
    """assert X == X with X a literal/Name compared to an identical literal/Name."""
    if len(cmp.ops) != 1 or not isinstance(cmp.ops[0], ast.Eq):
        return False
    left, right = cmp.left, cmp.comparators[0]
    return ast.dump(left) == ast.dump(right)


def _raises_is_broad(call: ast.Call) -> bool:
    """pytest.raises(Exception) / raises(BaseException) with no `match=`."""
    func = call.func
    is_raises = (isinstance(func, ast.Attribute) and func.attr == "raises") or (
        isinstance(func, ast.Name) and func.id == "raises"
    )
    if not is_raises:
        return False
    if any(kw.arg == "match" for kw in call.keywords):
        return False  # a match= narrows it → acceptable
    return any(isinstance(a, ast.Name) and a.id in _BROAD_EXC for a in call.args)


def _body_has_assertion(fn: ast.FunctionDef) -> bool:
    """True if the test body contains an assert, a self.assert*, or pytest.raises."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute):
                if f.attr.startswith("assert") or f.attr == "raises" or f.attr == "fail":
                    return True
            if isinstance(f, ast.Name) and (
                f.id.startswith("assert") or f.id == "raises"
            ):
                return True
        # `with pytest.raises(...)` counts (it's a Call captured above).
    return False


def _has_early_sys_exit(fn: ast.FunctionDef) -> bool:
    """sys.exit(0) / exit(0) anywhere in a test fn (bail before the real assert)."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            is_exit = (
                isinstance(f, ast.Attribute) and f.attr == "exit"
            ) or (isinstance(f, ast.Name) and f.id == "exit")
            if is_exit:
                return True
    return False


def lint_source(path: Path, source: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        # A test file that doesn't parse is its own problem; report and move on.
        return [Finding(str(path), e.lineno or 0, "RH000", f"unparseable: {e.msg}")]

    rel = str(path)

    # Assert-level checks (anywhere in the file).
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            test = node.test
            if _const_is_truthy(test):
                findings.append(
                    Finding(rel, node.lineno, "RH001", "tautological `assert <truthy-const>`")
                )
            elif isinstance(test, ast.Compare) and _self_equal(test):
                findings.append(
                    Finding(rel, node.lineno, "RH002", "self-equal tautology `assert X == X`")
                )
        if isinstance(node, ast.Call) and _raises_is_broad(node):
            findings.append(
                Finding(rel, node.lineno, "RH003",
                        "over-broad `pytest.raises(Exception)` (use a specific type or match=)")
            )

    # Function-level checks (only on test_* functions).
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            if _has_early_sys_exit(node):
                findings.append(
                    Finding(rel, node.lineno, "RH004",
                            f"`sys.exit/exit` inside test `{node.name}` (bails before asserting)")
                )
            if not _body_has_assertion(node):
                findings.append(
                    Finding(rel, node.lineno, "RH005",
                            f"test `{node.name}` asserts nothing (no assert / self.assert* / raises)")
                )
    return findings


def _staged_test_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=d"],
            capture_output=True, text=True, timeout=10, check=False,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    return [Path(p) for p in out.splitlines() if p.endswith(".py") and _is_test_file(Path(p))]


def main(argv: list[str]) -> int:
    if argv:
        targets = [Path(a) for a in argv]
    else:
        targets = _staged_test_files()
        if not targets:
            print("anti-reward-hacking: no staged test files — nothing to check.")
            return 0

    all_findings: list[Finding] = []
    for path in targets:
        if not path.is_file():
            continue
        if not _is_test_file(path):
            continue
        try:
            all_findings.extend(lint_source(path, path.read_text(encoding="utf-8")))
        except OSError as e:
            print(f"anti-reward-hacking: cannot read {path}: {e}", file=sys.stderr)

    if all_findings:
        print("anti-reward-hacking: test-cheating patterns detected "
              "(first-level heuristic — see file docstring on evasion):")
        for f in all_findings:
            print(f"  {f}")
        print(f"\n{len(all_findings)} finding(s). Fix the test(s) or justify in review.")
        return 1
    print(f"anti-reward-hacking: clean ({len(targets)} test file(s) checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
