#!/usr/bin/env python3
"""impact_map.py — static import-graph test selection for the PR lane.

Lever L2 from research/operations/2026-08-21-world-patterns-import-map.md
§1.2 ("Test Impact Analysis — start static, not ML"): `change_map.py`
(sibling in this directory) already decides, at DOMAIN granularity, whether
`backend-tests` runs at all. Once that job is selected to run, it has always
run every file under `backend/tests/` (1400+ modules) regardless of how
small the diff is — this module is the missing layer underneath: map the
PR's changed files to the pytest MODULES that can actually reach them via a
static Python import graph, and select only those.

SCOPE, DECLARED (do not widen without re-deriving safety): this module has a
static import graph for exactly one tree, `apps/backend-rag/backend/`. Any
changed path outside that tree — `apps/crm-cell/`, `packages/cell-core/`,
`scripts/bot/`, `data/*.json`, `requirements*.txt`, migrations, etc. — is
UNMAPPABLE by construction and forces `run_all=True`. So does anything a
static graph structurally cannot see: dynamic `importlib.import_module(...)`,
string-built dotted paths, plugin/env-var-driven wiring, and dependency/data
files a test reads via `open()` rather than `import`. This is why the
`merge_group` lane (this module's caller, `tests.yml`, invokes it ONLY on
`pull_request` — see that workflow) MUST stay the unconditional full suite:
a wrong or incomplete impact map here costs a slow PR-lane run, never a
missed regression, only because merge_group never scopes on this output.

CONFTEST: pytest applies a directory's `conftest.py` to every test in that
directory's subtree regardless of whether any test file literally imports
it. A changed `conftest.py` therefore selects every test file under its own
directory (recursively) — this is a directory rule, not a graph edge, and is
handled before the import-graph walk below.

ROOT OF TRUST: this file is extracted from BASE_SHA by tests.yml's `changes`
job, exactly like change_map.py (CRITICAL-1, 2026-08-14) — a PR that broke
backend/ code could otherwise edit its own copy of this file to under-select
its own regression's test. See that job's "Extract trusted classifier" step.
"""

from __future__ import annotations

import ast
import json
import sys
from collections.abc import Iterable
from pathlib import Path

ENUMERATION_ERROR = "__CHANGE_MAP_ENUMERATION_ERROR__"  # shared sentinel with change_map.py

# The only tree this module has a static import graph for (see module
# docstring "SCOPE, DECLARED"). Repo-relative, POSIX.
BACKEND_ROOT = "apps/backend-rag/backend"
TEST_DIR = f"{BACKEND_ROOT}/tests"
PACKAGE_ROOT_PREFIX = "apps/backend-rag/"  # PYTHONPATH=.:../crm-cell at that cwd


def _module_name(rel_path: str) -> str:
    """``apps/backend-rag/backend/services/x.py`` -> ``backend.services.x``."""

    within = rel_path[len(PACKAGE_ROOT_PREFIX) :]
    parts = within[: -len(".py")].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _own_package(module_name: str, is_init: bool) -> str:
    """The dotted package a module's relative imports resolve against."""

    if is_init:
        return module_name
    if "." in module_name:
        return module_name.rsplit(".", 1)[0]
    return ""


def _resolve_relative(package: str, level: int, module: str | None) -> str | None:
    """Mirrors ``importlib._bootstrap._resolve_name`` for ``from . import x``."""

    if not package:
        return None
    bits = package.rsplit(".", level - 1)
    if len(bits) < level:
        return None
    base = bits[0]
    return f"{base}.{module}" if module else base


def _candidates_for_import(node: ast.AST, own_package: str) -> list[str]:
    """Every dotted-name an import statement could touch.

    Deliberately over-inclusive: every ancestor-package prefix of a resolved
    target is added too, because Python imports (and executes) every
    ancestor package's ``__init__.py`` before the leaf. An extra edge only
    ever WIDENS selection (a test gets included that didn't strictly need
    to be); it can never narrow it — the direction this module's caller
    requires uncertainty to fail toward.
    """

    targets: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            bits = alias.name.split(".")
            targets.extend(".".join(bits[:i]) for i in range(1, len(bits) + 1))
    elif isinstance(node, ast.ImportFrom):
        base = (
            _resolve_relative(own_package, node.level, node.module)
            if node.level
            else node.module
        )
        if base:
            bits = base.split(".")
            targets.extend(".".join(bits[:i]) for i in range(1, len(bits) + 1))
            targets.extend(
                f"{base}.{alias.name}" for alias in node.names if alias.name != "*"
            )
    return targets


def _is_test_file(rel_path: str) -> bool:
    if not rel_path.startswith(TEST_DIR + "/"):
        return False
    # backend-tests' own pytest invocation passes `--ignore=backend/tests/e2e`
    # (a dedicated e2e-tests job owns that subtree) — mirror the same
    # exclusion here so a scoped selection can never hand pytest a path its
    # own `--ignore` flag would then filter back out, which for a selection
    # confined entirely to e2e/ would leave zero collected items under `-x`
    # (pytest exit 5), a spurious failure the always-ran-the-whole-directory
    # baseline could never hit.
    if rel_path.startswith(TEST_DIR + "/e2e/"):
        return False
    name = rel_path.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py")


def _discover_modules(repo_root: Path) -> dict[str, str]:
    """module name -> repo-relative POSIX path, for every ``.py`` under BACKEND_ROOT."""

    base = repo_root / BACKEND_ROOT
    if not base.is_dir():
        return {}
    modules: dict[str, str] = {}
    for path in base.rglob("*.py"):
        rel = path.relative_to(repo_root).as_posix()
        modules[_module_name(rel)] = rel
    return modules


def _build_reverse_graph(
    modules: dict[str, str], repo_root: Path
) -> tuple[dict[str, set[str]], list[str]]:
    """``dependents[module]`` = set of modules that (transitively-eligible) import it."""

    dependents: dict[str, set[str]] = {name: set() for name in modules}
    parse_errors: list[str] = []
    for module_name, rel in modules.items():
        is_init = rel.endswith("/__init__.py") or rel == f"{BACKEND_ROOT}/__init__.py"
        own_package = _own_package(module_name, is_init)
        try:
            source = (repo_root / rel).read_text(encoding="utf-8", errors="surrogateescape")
            tree = ast.parse(source, filename=rel)
        except (SyntaxError, ValueError, OSError):
            parse_errors.append(rel)
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for target in _candidates_for_import(node, own_package):
                    bucket = dependents.get(target)
                    if bucket is not None:
                        bucket.add(module_name)
    return dependents, parse_errors


def _transitive_dependents(start: set[str], graph: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    queue = list(start)
    while queue:
        current = queue.pop()
        for dep in graph.get(current, ()):
            if dep not in seen:
                seen.add(dep)
                queue.append(dep)
    return seen


def _fail_open(changed_count: int, reason: str, **extra: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "changed_file_count": changed_count,
        "run_all": True,
        "reason": reason,
        "selected_tests": [],
        **extra,
    }


def compute(paths: Iterable[str], repo_root: Path) -> dict[str, object]:
    """Build the static test-impact recommendation for ``paths`` under ``repo_root``."""

    raw_paths = list(paths)
    if ENUMERATION_ERROR in raw_paths:
        return _fail_open(0, "enumeration_failed")

    changed = sorted({p.strip() for p in raw_paths if p.strip()})
    if not changed:
        return _fail_open(0, "empty_changed_set")

    out_of_scope = [
        p for p in changed if not (p.startswith(BACKEND_ROOT + "/") and p.endswith(".py"))
    ]
    if out_of_scope:
        return _fail_open(
            len(changed), "out_of_scope_path", out_of_scope_paths=sorted(out_of_scope)
        )

    modules = _discover_modules(repo_root)
    dependents, parse_errors = _build_reverse_graph(modules, repo_root)
    if parse_errors:
        return _fail_open(len(changed), "unparseable_module", parse_errors=sorted(parse_errors))

    rel_by_module = modules
    module_by_rel = {rel: name for name, rel in rel_by_module.items()}
    test_modules = {
        name: rel for name, rel in rel_by_module.items() if _is_test_file(rel)
    }

    changed_modules: set[str] = set()
    conftest_dirs: list[str] = []
    missing: list[str] = []
    for rel in changed:
        basename = rel.rsplit("/", 1)[-1]
        if basename == "conftest.py":
            conftest_dirs.append(rel.rsplit("/", 1)[0])
            continue
        module_name = module_by_rel.get(rel)
        if module_name is None:
            # In-scope path (backend/**/*.py) that isn't in the CURRENT tree —
            # most commonly a deletion. Static analysis of what depended on a
            # module that no longer exists is exactly the "uncertain" case
            # the caller's contract requires to fail toward the full suite.
            missing.append(rel)
            continue
        changed_modules.add(module_name)

    if missing:
        return _fail_open(len(changed), "unresolvable_changed_path", missing_paths=sorted(missing))

    selected: set[str] = set()
    for conftest_dir in conftest_dirs:
        prefix = conftest_dir + "/"
        selected.update(rel for rel in test_modules.values() if rel.startswith(prefix))

    if changed_modules:
        impacted = _transitive_dependents(changed_modules, dependents) | changed_modules
        selected.update(rel_by_module[m] for m in impacted if m in test_modules)

    if not selected:
        # A real, in-scope, resolvable change with zero test-module
        # dependents (transitive or otherwise) — declared uncertain per the
        # caller's contract ("empty list" is explicitly a fail-open trigger),
        # not treated as "nothing to verify".
        return _fail_open(len(changed), "empty_impact_set")

    return {
        "schema_version": 1,
        "changed_file_count": len(changed),
        "run_all": False,
        "reason": "scoped",
        "selected_tests": sorted(selected),
        "selected_test_count": len(selected),
        "total_test_count": len(test_modules),
    }


def _read_paths(argv: list[str]) -> list[str]:
    if argv:
        return [line for arg in argv for line in arg.splitlines()]
    return sys.stdin.read().splitlines()


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    repo_root = Path.cwd()
    if args[:1] == ["--repo-root"]:
        repo_root = Path(args[1])
        args = args[2:]
    result = compute(_read_paths(args), repo_root)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
