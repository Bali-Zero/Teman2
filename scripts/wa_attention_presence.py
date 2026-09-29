#!/usr/bin/env python3
"""Presence check for the wa-mirror attention PII corpus (check-wa-attention-pii.yml).

Every test DEFINED in scripts/tests/test_wa_attention_*.py, found by AST, must appear in the
pytest junit report as run and unskipped. Constructs the AST cannot follow are refused (RED),
never guessed: a green run must mean every definition executed.
"""
from __future__ import annotations

import ast
import glob
import os
import sys
import xml.etree.ElementTree as ET

SUITE_GLOB = "scripts/tests/test_wa_attention_*.py"
CONFTESTS = ("conftest.py", "scripts/conftest.py", "scripts/tests/conftest.py")
KNOWN_SUITES = {
    "test_wa_attention_episode_tier",
    "test_wa_attention_pii_envelope",
    "test_wa_attention_presence_walk",
    "test_wa_attention_sender_phone",
}
# Hooks that can change whether/what a test body executes or how its outcome is reported.
# pytest_collection_modifyitems is deliberately absent: a dropped item is already RED (missing).
FORBIDDEN_HOOKS = {
    "pytest_plugins",
    "pytest_pycollect_makeitem",
    "pytest_pyfunc_call",
    "pytest_runtest_call",
    "pytest_runtest_makereport",
    "pytest_runtest_protocol",
}
FLOW = (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While, ast.Match)
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def is_fixture(node):
    for d in node.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name == "fixture":
            return True
    return False


def is_testcase_base(base):
    name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
    return name.endswith("TestCase")


def bound_names(node):
    if isinstance(node, ast.Import):
        return [(a.asname or a.name.split(".")[0]) for a in node.names]
    return [(a.asname or a.name) for a in node.names]


def walk(module, body, scope, expected, problems):
    seen = set()
    for node in body:
        here = f"{module}::{'.'.join(scope + [getattr(node, 'name', '')])}"
        if isinstance(node, (*FUNCS, ast.ClassDef)):
            if node.name in seen:
                problems.append(f"{here} defined twice in one scope")
            seen.add(node.name)
        if isinstance(node, FUNCS) and node.name.startswith("test"):
            if not is_fixture(node):
                expected.add((module, ".".join(scope + [node.name])))
        elif isinstance(node, ast.ClassDef):
            if any(is_testcase_base(b) for b in node.bases):
                problems.append(f"{here} is a unittest.TestCase subclass (collected regardless of its name; unsupported)")
            if node.name.startswith("Test"):
                bad_base = [b for b in node.bases if not (isinstance(b, ast.Name) and b.id == "object")]
                if bad_base or node.keywords:
                    problems.append(f"{here} has a base class or metaclass other than object (inherited tests are invisible to the AST; unsupported)")
                if any(isinstance(n, FUNCS) and n.name == "__init__" for n in node.body):
                    continue
                walk(module, node.body, scope + [node.name], expected, problems)
            else:
                stray = [n.name for n in node.body if isinstance(n, FUNCS) and n.name.startswith("test") and not is_fixture(n)]
                if stray:
                    problems.append(f"{here} is not named Test* but defines test methods {stray} (unsupported)")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for nm in bound_names(node):
                if nm == "*" or nm.startswith("test") or nm.startswith("Test"):
                    problems.append(f"{module}: import binds `{nm}`, a name pytest would collect but the AST does not see (unsupported)")
        elif isinstance(node, FLOW):
            for sub in ast.walk(node):
                if isinstance(sub, FUNCS) and sub.name.startswith("test") and not is_fixture(sub):
                    problems.append(f"{module}::{sub.name} defined under control flow (unsupported)")
                if isinstance(sub, ast.ClassDef) and sub.name.startswith("Test"):
                    problems.append(f"{module}::{sub.name} defined under control flow (unsupported)")
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                nm = getattr(t, "id", "")
                if nm.startswith("test") or nm.startswith("Test") or nm == "__test__":
                    problems.append(f"{module}::{nm} is a rebinding of a test name (unsupported)")


def hook_problems(label, tree):
    found = []
    for n in ast.walk(tree):
        names = []
        if isinstance(n, FUNCS):
            names = [n.name]
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            names = [getattr(t, "id", "") for t in targets]
        found += [f"{label}: defines `{nm}`, which can stop test bodies executing or rewrite outcomes (unsupported)" for nm in names if nm in FORBIDDEN_HOOKS]
    return found


def collect(root="."):
    expected, problems, modules = set(), [], set()
    for path in sorted(glob.glob(os.path.join(root, SUITE_GLOB))):
        module = os.path.basename(path)[: -len(".py")]
        modules.add(module)
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
        walk(module, tree.body, [], expected, problems)
        problems += hook_problems(module, tree)
    for rel in CONFTESTS:
        path = os.path.join(root, rel)
        if os.path.exists(path):
            problems += hook_problems(rel, ast.parse(open(path, encoding="utf-8").read(), filename=path))
    return expected, problems, modules


def read_junit(junit, modules):
    cases = list(ET.parse(junit).getroot().iter("testcase"))
    skipped, ran = [], set()
    for c in cases:
        parts = (c.get("classname") or "").split(".")
        idx = next((i for i, p in enumerate(parts) if p in modules), None)
        module = parts[idx] if idx is not None else ""
        qual = ".".join(parts[idx + 1 :] + [(c.get("name") or "").split("[")[0]]) if idx is not None else ""
        if c.find("skipped") is not None:
            skipped.append(f"{module}::{qual}")
        else:
            ran.add((module, qual))
    return cases, skipped, ran


def main(junit="junit.xml", root="."):
    expected, problems, modules = collect(root)
    cases, skipped, ran = read_junit(junit, modules)
    missing = sorted(f"{m}::{q}" for m, q in expected - ran)
    absent_suites = sorted(KNOWN_SUITES - modules)
    print(f"testcases={len(cases)} defined={len(expected)} skipped={len(skipped)} missing={len(missing)} problems={len(problems)} absent_suites={len(absent_suites)}")
    if not expected or skipped or missing or problems or absent_suites:
        print(f"::error::defined={len(expected)} skipped={skipped} missing={missing} problems={problems} absent_suites={absent_suites} - a skipped, absent, shadowed or deselected guard proves nothing (superscar #2)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
