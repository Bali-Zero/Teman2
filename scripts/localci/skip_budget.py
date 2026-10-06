#!/usr/bin/env python3
"""Skip budget for a junit report: a skipped test proves nothing, so every skip has to be declared.

    python scripts/localci/skip_budget.py <junit.xml> [--allow REGEX ...]

Each ``--allow`` is a regular expression searched in a skip's REASON (the junit ``message``, never the file
path; an xfail is a skip here). A skip no pattern explains is UNDECLARED. A pattern that explains no skip is STALE: when a skip
goes away its allowance is removed by hand, it does not linger as a hole for the next one. A pattern that
matches the empty string would explain every skip and is refused.

Failures and errors are not judged here — pytest's own exit code carries them. This reads the report only,
and the report is the one the same job wrote a step earlier: stdlib ElementTree, as in runner.py, no new dependency.

Exit 0 = every skip declared, every allowance used · 1 = an undeclared skip or a stale allowance ·
2 = unusable input (unreadable or malformed report, a report with no test case, a bad or blanket pattern).
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
import xml.etree.ElementTree as ET  # noqa: S314 — own junit, written by this job; see the module docstring
from pathlib import Path

EXIT_OK = 0
EXIT_FOUND = 1
EXIT_BAD_INPUT = 2
COLLECTION_SKIPPED = "collection skipped"


class BudgetError(ValueError):
    """The report cannot be judged — refuse rather than print a count that looks like evidence."""


def compile_allowances(raw: list[str]) -> list[re.Pattern]:
    patterns = []
    for text in raw:
        try:
            pattern = re.compile(text)
        except re.error as exc:
            raise BudgetError(f"--allow {text!r}: {exc}") from exc
        if pattern.search(""):
            raise BudgetError(f"--allow {text!r} matches the empty string, so it would explain every skip")
        patterns.append(pattern)
    return patterns


def read_skips(report: Path) -> tuple[int, list[tuple[str, str]]]:
    """(test cases in the report, [(test id, skip reason)])."""
    try:
        root = ET.parse(report).getroot()
    except (OSError, ET.ParseError) as exc:
        raise BudgetError(f"{report}: {exc}") from exc
    cases = list(root.iter("testcase"))
    if not cases:
        raise BudgetError(f"{report}: no test case in the report")
    skips = [(f"{case.get('classname') or '?'}::{case.get('name') or '?'}", skip_reason(node)) for case in cases for node in case.iter("skipped")]
    return len(cases), skips


def skip_reason(node: ET.Element) -> str:
    """The junit ``message``, never the node text: the text carries the test's file path, and a pattern must not match a file name.

    One exception pytest forces: a module skipped at collection (``importorskip``) has the generic message
    "collection skipped" and its reason only inside the text, as ``repr((path, line, "Skipped: <reason>"))``.
    """
    message = node.get("message") or ""
    if message != COLLECTION_SKIPPED:
        return message
    try:
        detail = ast.literal_eval((node.text or "").strip())[2]
    except (ValueError, SyntaxError, TypeError, IndexError, MemoryError, RecursionError):
        return message
    return detail.removeprefix("Skipped: ") if isinstance(detail, str) else message


def judge(skips: list[tuple[str, str]], patterns: list[re.Pattern]) -> tuple[list[tuple[str, str]], list[str]]:
    undeclared = [(test, reason) for test, reason in skips if not any(p.search(reason) for p in patterns)]
    stale = [p.pattern for p in patterns if not any(p.search(reason) for _, reason in skips)]
    return undeclared, stale


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Skip budget for a junit report: every skip must be explained by an --allow pattern.")
    ap.add_argument("report", type=Path, help="path to a junit XML report (pytest --junitxml)")
    ap.add_argument("--allow", action="append", default=[], metavar="REGEX", help="a declared skip: regex searched in the skip reason (repeatable)")
    args = ap.parse_args(argv)
    try:
        patterns = compile_allowances(args.allow)
        total, skips = read_skips(args.report)
    except BudgetError as exc:
        print(f"skip_budget: refusing — {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    undeclared, stale = judge(skips, patterns)
    for test, reason in undeclared:
        print(f"UNDECLARED  {test}  [{reason}]")
    for pattern in stale:
        print(f"STALE       --allow {pattern!r} explains no skip")
    print(f"cases={total} executed={total - len(skips)} skipped={len(skips)} undeclared={len(undeclared)} stale={len(stale)}")
    return EXIT_FOUND if undeclared or stale else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
