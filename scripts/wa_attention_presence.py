#!/usr/bin/env python3
"""Presence check for the wa-mirror attention PII corpus (check-wa-attention-pii.yml).

Every test DEFINED in scripts/tests/test_wa_attention_*.py, found by AST, must appear in the
pytest junit report as run and unskipped. Constructs the AST cannot follow are refused (RED),
never guessed: a green run must mean every definition executed.

Scope of the refusals: the walk (`walk`, `flow_problems`) enters the module top level, including
control-flow blocks, and the bodies of collected Test* classes that have no __init__. The
assignment-target, load-of-a-test-name, decorator and reflection-call refusals apply in that
walked scope only. Not walked, hence not defended: other class bodies, function bodies, and
attribute names built at runtime. Anything not enumerated is not defended; deliberate reflection
is outside this tripwire's threat model.
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
    "test_wa_attention_result_guard",
    "test_wa_attention_presence_walk",
    "test_wa_attention_sender_phone",
}
# Hooks that can change whether/what a test body executes or how its outcome is reported.
# pytest_collection_modifyitems is here too: dropping an item is RED (missing), but it can also
# swap an item's body (`item.obj = ...`) and keep the identity, so it is refused outright.
FORBIDDEN_HOOKS = {
    "pytest_collection_modifyitems",
    "pytest_plugins",
    "pytest_pycollect_makeitem",
    "pytest_pyfunc_call",
    "pytest_report_teststatus",
    "pytest_runtest_call",
    "pytest_runtest_logreport",
    "pytest_runtest_makereport",
    "pytest_runtest_protocol",
    "pytest_sessionfinish",
    "pytest_unconfigure",
}
REFLECTION = {"setattr", "globals", "locals", "vars", "exec", "eval", "__import__", "register"}
TRUSTED_NAMES = {"pytest", "fixture"}
INTROSPECTION = {"__code__", "__dict__", "__globals__"}
FLOW = (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While, ast.Match)
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
BODY_SWAPS = {"obj", "_obj", "runtest", "function"}


def is_fixture(node, fixture_ok=frozenset()):
    """Only the real `pytest.fixture` counts; a look-alike decorator is not trusted (fail closed)."""
    for d in node.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Attribute) and target.attr == "fixture" and getattr(target.value, "id", "") == "pytest":
            return True
        if isinstance(target, ast.Name) and target.id == "fixture" and "fixture" in fixture_ok:
            return True
    return False


def decorator_ok(d):
    """Decorators known not to replace the decorated body: pytest.fixture and pytest.mark.*."""
    target = d.func if isinstance(d, ast.Call) else d
    if isinstance(target, ast.Name):
        return target.id == "fixture"
    chain = []
    while isinstance(target, ast.Attribute):
        chain.append(target.attr)
        target = target.value
    return isinstance(target, ast.Name) and target.id == "pytest" and (chain == ["fixture"] or chain[-1:] == ["mark"])


def is_testcase_base(base):
    name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
    return name.endswith("TestCase")


def is_test_name(nm):
    return nm.startswith("test") or nm.startswith("Test") or nm == "__test__"


def target_names(targets):
    return [n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)]


def binds(node):
    """Names a non-def statement binds, plus refusal reasons for imports that hide a name."""
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        flat = []
        for t in targets:
            flat += list(t.elts) if isinstance(t, (ast.Tuple, ast.List)) else [t]
        odd = [("<non-name target>", "nonname")] if any(not isinstance(t, ast.Name) for t in flat) else []
        return [(nm, "rebinding") for nm in target_names(targets)] + odd
    if isinstance(node, ast.Expr):
        names = []
        for c in ast.walk(node.value):
            if isinstance(c, ast.Call):
                names.append(c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", ""))
        return [(nm, "reflection") for nm in names if nm in REFLECTION]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        out = []
        for a in node.names:
            bound = a.asname or (a.name if isinstance(node, ast.ImportFrom) else a.name.split(".")[0])
            leaf = a.name.split(".")[-1]
            if bound in ("*", "object") or is_test_name(bound):
                out.append((bound, "import"))
            elif leaf.endswith("TestCase") or (leaf == "fixture" and a.asname):
                out.append((bound, "import"))
        return out
    return []


def loads_of(node, names):
    return sorted({n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in names})


def flow_problems(module, node):
    found = []
    for sub in ast.walk(node):
        if isinstance(sub, FUNCS) and sub.name.startswith("test"):
            found.append(f"{module}::{sub.name} defined under control flow (unsupported)")
        if isinstance(sub, ast.ClassDef) and sub.name.startswith("Test"):
            found.append(f"{module}::{sub.name} defined under control flow (unsupported)")
        for nm, kind in binds(sub):
            if kind in ("import", "reflection", "nonname") or is_test_name(nm) or nm in TRUSTED_NAMES:
                found.append(f"{module}::{nm} is bound under control flow by a {kind} (unsupported)")
    return found


def walk(module, body, scope, expected, problems, fixture_ok=frozenset(), outer=frozenset()):
    seen = set()
    test_names = set(outer) | {n.name for n in body if isinstance(n, FUNCS) and n.name.startswith("test") and not is_fixture(n, fixture_ok)}
    for node in body:
        if not isinstance(node, (*FUNCS, ast.ClassDef)):
            hit = loads_of(node, test_names)
            if hit:
                problems.append(f"{module}: a module/class-scope statement loads the test def(s) {hit}, so it can alias or mutate them (unsupported)")
        here = f"{module}::{'.'.join(scope + [getattr(node, 'name', '')])}"
        if isinstance(node, (*FUNCS, ast.ClassDef)):
            if node.name in seen:
                problems.append(f"{here} defined twice in one scope")
            seen.add(node.name)
        if isinstance(node, (*FUNCS, ast.ClassDef)) and node.name.startswith("Test" if isinstance(node, ast.ClassDef) else "test"):
            if not (isinstance(node, FUNCS) and is_fixture(node, fixture_ok)) and not all(decorator_ok(d) for d in node.decorator_list):
                problems.append(f"{here} carries a decorator other than pytest.fixture/pytest.mark.* (it may replace the body; unsupported)")
        if isinstance(node, FUNCS) and node.name.startswith("test"):
            if not is_fixture(node, fixture_ok):
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
                walk(module, node.body, scope + [node.name], expected, problems, fixture_ok, frozenset(test_names))
            else:
                stray = [n.name for n in ast.walk(node) if isinstance(n, FUNCS) and n.name.startswith("test") and not is_fixture(n, fixture_ok)]
                if stray:
                    problems.append(f"{here} is not named Test* but defines test methods {stray} (unsupported)")
        elif isinstance(node, FLOW):
            problems.extend(flow_problems(module, node))
        else:
            for nm, kind in binds(node):
                if kind == "import":
                    problems.append(f"{module}: import binds `{nm}`, which hides or injects a collectable name, a base, a fixture or `object` (unsupported)")
                elif kind == "nonname":
                    problems.append(f"{module}: assignment to a subscript/attribute target at module or class scope can rebind a collected test (unsupported)")
                elif kind == "reflection":
                    problems.append(f"{module}: module-level call to `{nm}` can rebind a collected test (unsupported)")
                elif is_test_name(nm) or nm in TRUSTED_NAMES:
                    problems.append(f"{module}::{nm} is a rebinding of a test name or of pytest/fixture (unsupported)")


def module_level(body):
    """Statements pytest sees as module attributes: the top level and control flow, not def/class bodies."""
    for node in body:
        yield node
        if isinstance(node, FLOW):
            for field in ("body", "orelse", "finalbody"):
                yield from module_level(getattr(node, field, []))
            for sub in [*getattr(node, "handlers", []), *getattr(node, "cases", [])]:
                yield from module_level(sub.body)


def hook_problems(label, tree):
    found = []
    for n in module_level(tree.body):
        names = []
        if isinstance(n, FUNCS):
            names = [n.name]
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and any(k.arg == "specname" for k in d.keywords):
                    found.append(f"{label}: `{n.name}` renames itself into a hook via specname (unsupported)")
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            names = target_names(targets)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            names = [a.asname or a.name.split(".")[-1] for a in n.names]
            if "*" in names:
                found.append(f"{label}: star import may inject a hook (unsupported)")
        found += [f"{label}: defines or binds `{nm}`, which can stop test bodies executing or rewrite outcomes (unsupported)" for nm in names if nm in FORBIDDEN_HOOKS]
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr in INTROSPECTION:
            found.append(f"{label}: touches `.{n.attr}`, which can swap a test's code or namespace (unsupported)")
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "register") or (isinstance(n, ast.Attribute) and n.attr == "pluginmanager"):
            found.append(f"{label}: touches the plugin manager, which can register a hook at runtime (unsupported)")
        targets = n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(n, (ast.AnnAssign, ast.AugAssign)) else []
        for t in targets:
            if isinstance(t, ast.Attribute) and t.attr in BODY_SWAPS:
                found.append(f"{label}: assigns `.{t.attr}`, which can swap a collected test's body (unsupported)")
    return found


def fixture_imports(tree):
    return frozenset(
        a.name for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "pytest" for a in n.names if a.name == "fixture" and not a.asname
    )


def scan_source(label, source):
    tree = ast.parse(source)
    expected, problems = set(), []
    walk(label, tree.body, [], expected, problems, fixture_imports(tree))
    return expected, problems + hook_problems(label, tree)


def collect(root="."):
    expected, problems, modules = set(), [], set()
    for path in sorted(glob.glob(os.path.join(root, SUITE_GLOB))):
        module = os.path.basename(path)[: -len(".py")]
        modules.add(module)
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
        walk(module, tree.body, [], expected, problems, fixture_imports(tree))
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
