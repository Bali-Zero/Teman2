#!/usr/bin/env python3
"""Skip budget for a junit report: reported skips are declared, required tests executed, and the executed floor held.

    python scripts/localci/skip_budget.py <junit.xml> [--allow TEST_REGEX REASON_REGEX]... [--require TEST_REGEX]... [--min-executed N]

A test id is ``classname::name`` ('?' for a missing part); an xfail is a skip here; "executed" is a test case with no ``<skipped>`` child.
  --allow    explains a skip iff TEST_REGEX searches its id AND REASON_REGEX searches its reason (the junit ``message``, never the file path).
             Each allowance must explain EXACTLY ONE skip: none is STALE (it explains nothing in this report); two or more is
             OVERUSED, so one allowance cannot cover a whole module. A skip no allowance explains is UNDECLARED, and a skip that two or
             more allowances explain is AMBIGUOUS: a removed test's allowance could otherwise stay alive by matching another declared skip.
  --require  at least one EXECUTED test case must match; no executed match is MISSING, including when every match was deselected, never collected or skipped.
  --min-executed  a floor on executed cases (default 1): a report where nothing executed is never clean.
Junit omits deselected and never-collected tests. An omitted test with no matching --require is invisible if the executed floor still holds;
other executed cases can replace it in the count. This is not proof that every intended test ran.
A pattern that fails to compile, matches the empty string, or matches "\\x00\\x00" (a string no id or reason contains: this catches ``(?=.)``,
``.``, ``.+``, ``\\S``) is refused. Patterns in general are not policed: the exactly-one rule and the test-id binding are what bound a loose one.
A report with a ``<skipped>`` outside a ``<testcase>``, or whose testsuites do not add up to its test cases, is refused.

Failures and errors are not judged here — pytest's own exit code carries them. This reads the report only, and the report is
the one the same job wrote a step earlier: stdlib ElementTree, as in runner.py, no new dependency.

Exit 0 = nothing undeclared, stale, overused, ambiguous, missing or below the floor · 1 = at least one of those ·
2 = unusable input (unreadable or inconsistent report, a report with no test case, a bad or blanket pattern).
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
SENTINEL = "\x00\x00"


class BudgetError(ValueError):
    """The report or a pattern cannot be judged — refuse rather than print a count that looks like evidence."""


def compile_pattern(text: str, flag: str) -> re.Pattern:
    try:
        pattern = re.compile(text)
    except re.error as exc:
        raise BudgetError(f"{flag} {text!r}: {exc}") from exc
    if pattern.search("") or pattern.search(SENTINEL):
        raise BudgetError(f"{flag} {text!r} matches the empty string or a string no test id or reason contains, so it is a blanket")
    return pattern


def read_cases(report: Path) -> list[tuple[str, str | None]]:
    """[(test id, skip reason or None when the case executed)], one per ``<testcase>``."""
    try:
        root = ET.parse(report).getroot()
    except (OSError, ET.ParseError) as exc:
        raise BudgetError(f"{report}: {exc}") from exc
    cases = list(root.iter("testcase"))
    if not cases:
        raise BudgetError(f"{report}: no test case in the report")
    if sum(1 for _ in root.iter("skipped")) != sum(1 for case in cases for _ in case.iter("skipped")):
        raise BudgetError(f"{report}: a skipped element outside a test case")
    declared = [suite.get("tests") for suite in root.iter("testsuite")]
    if not all(n and n.isdigit() for n in declared) or sum(int(n) for n in declared) != len(cases):
        raise BudgetError(f"{report}: the testsuites declare {declared} tests but the report holds {len(cases)} test cases")
    out = []
    for case in cases:
        node = case.find("skipped")
        out.append((f"{case.get('classname') or '?'}::{case.get('name') or '?'}", None if node is None else skip_reason(node)))
    return out


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Skip budget for a junit report: declared skips, required tests, a floor on executed cases.")
    ap.add_argument("report", type=Path, help="path to a junit XML report (pytest --junitxml)")
    ap.add_argument("--allow", action="append", nargs=2, default=[], metavar=("TEST_REGEX", "REASON_REGEX"),
                    help="a declared skip: searched in the test id and in the skip reason; must explain exactly one skip (repeatable)")
    ap.add_argument("--require", action="append", default=[], metavar="TEST_REGEX", help="at least one executed test case must match (repeatable)")
    ap.add_argument("--min-executed", type=int, default=1, metavar="N", help="floor on executed test cases (default 1)")
    args = ap.parse_args(argv)
    try:
        allowances = [(compile_pattern(t, "--allow"), compile_pattern(r, "--allow")) for t, r in args.allow]
        required = [compile_pattern(t, "--require") for t in args.require]
        cases = read_cases(args.report)
    except BudgetError as exc:
        print(f"skip_budget: refusing — {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    skips = [(test, reason) for test, reason in cases if reason is not None]
    executed = [test for test, reason in cases if reason is None]
    matched = [[test for test, reason in skips if tp.search(test) and rp.search(reason)] for tp, rp in allowances]
    undeclared = [(test, reason) for test, reason in skips if not any(test in m for m in matched)]
    stale = [a for a, m in zip(args.allow, matched) if not m]
    overused = [(a, m) for a, m in zip(args.allow, matched) if len(m) > 1]
    ambiguous = [(test, n) for test, _ in skips if (n := sum(test in m for m in matched)) > 1]
    missing = [p for p in required if not any(p.search(test) for test in executed)]
    too_few = len(executed) < args.min_executed
    for test, reason in undeclared:
        print(f"UNDECLARED  {test}  [{reason}]")
    for test_rx, reason_rx in stale:
        print(f"STALE       --allow {test_rx!r} {reason_rx!r} explains no skip")
    for (test_rx, reason_rx), tests in overused:
        print(f"OVERUSED    --allow {test_rx!r} {reason_rx!r} explains {len(tests)} skips, not one: {', '.join(tests)}")
    for test, n in ambiguous:
        print(f"AMBIGUOUS   {test} is explained by {n} allowances, not one")
    for pattern in missing:
        print(f"MISSING     --require {pattern.pattern!r} matched no executed test")
    if too_few:
        print(f"TOO FEW     executed={len(executed)} < min-executed={args.min_executed}")
    print(f"cases={len(cases)} executed={len(executed)} skipped={len(skips)} undeclared={len(undeclared)} stale={len(stale)} "
          f"overused={len(overused)} missing={len(missing)} ambiguous={len(ambiguous)}")
    return EXIT_FOUND if undeclared or stale or overused or ambiguous or missing or too_few else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
