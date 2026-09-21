"""Every `services/research_os/` module with a `__main__` must survive `python -m`.

This file exists because a CLI shipped whose own `Bites:` line named a command that died
instantly: `intel_evidence_bridge.py` imported `research_os.hashing` ABOVE the
`_core_path` import that puts `packages/research-os-core` on `sys.path`.

The defect was invisible to every test in this directory, and that is the point:
`conftest.py` performs the same `sys.path.insert` at collection time, so under pytest the
import order cannot matter. It cannot matter in a subprocess either -- unless the
subprocess inherits a PYTHONPATH that already carries the package. So these tests spawn a
clean interpreter with the bootstrap deliberately REMOVED from the environment, which is
the only vantage point from which the ordering bug is observable at all.

Scoped honestly: this catches the ordering defect for modules that are RUNNABLE. Six
sibling modules under `services/research_os/` carry the same wrong order today and are not
covered here, because none of them has a `__main__` for this test to invoke. That debt is
tracked on `.claude/skills/modus/PENDING-ARMS.md:1352` (open since 2026-08-24), whose
arming step -- declare `packages/research-os-core` as a real dependency, then delete
`_core_path.py` and its imports -- cures all six at once and retires this test with them.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SERVICE_DIR = Path(__file__).resolve().parents[3] / "services" / "research_os"
_BACKEND_ROOT = Path(__file__).resolve().parents[3].parent


def _has_main_guard(path: Path) -> bool:
    """True when the module actually runs something under `if __name__ == "__main__"`."""

    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in test.comparators)
        ):
            return True
    return False


def _runnable_modules() -> list[str]:
    return sorted(
        f"backend.services.research_os.{p.stem}"
        for p in _SERVICE_DIR.glob("*.py")
        if not p.stem.startswith("_") and _has_main_guard(p)
    )


def _run_module(module: str) -> subprocess.CompletedProcess[str]:
    """Spawn `python -m <module>` with PYTHONPATH carrying ONLY the backend root.

    `packages/research-os-core` is deliberately absent: the module's own `_core_path`
    bootstrap is the only thing that may put it on `sys.path`, which is exactly the
    property under test.
    """

    env = dict(os.environ)
    env["PYTHONPATH"] = str(_BACKEND_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("INTEL_EVIDENCE_BRIDGE_DSN", None)
    return subprocess.run(
        [sys.executable, "-B", "-m", module, "--help"],
        cwd=_BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_at_least_one_module_is_runnable() -> None:
    """Innocence control: if this list ever empties, the tests below pass vacuously."""

    assert _runnable_modules(), "no runnable module found -- the test below would prove nothing"


@pytest.mark.parametrize("module", _runnable_modules())
def test_a_runnable_module_imports_cleanly_under_python_m(module: str) -> None:
    """`python -m <module>` must not die on an import. The bug this catches is an ORDER."""

    result = _run_module(module)

    assert "ModuleNotFoundError" not in result.stderr, (
        f"{module} cannot be run as `python -m`: {result.stderr.strip().splitlines()[-1:]}\n"
        "An import of `research_os.*` sits above the `_core_path` bootstrap."
    )
    assert result.returncode == 0, (
        f"{module} exited {result.returncode} on --help; stderr: {result.stderr.strip()[-400:]}"
    )
