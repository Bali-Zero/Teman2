"""Bootstrap for the R2 naga engine tests: core package on `sys.path`, R1's reference by path.

R1's `research_os_reader_reference.py` / `research_os_admission_reference.py` live under the
SIBLING test package `tests/unit/research_os/` (R1 may not write under `services/**`, so its
executable specification lives in the test tree). Loading them by absolute file path via
`importlib` — rather than relying on pytest's package/import-mode resolution for a cross-package
relative import — is robust regardless of how `--import-mode=importlib` assigns dotted module
names to the two sibling packages (`tests/unit/__init__.py` exists, `tests/__init__.py` does
not, so the two directories do not share one importable package root).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "packages" / "research-os-core").is_dir():
            return candidate
    raise RuntimeError("cannot locate repository root from the naga test path")


REPO_ROOT = _repo_root()
PACKAGE_ROOT = REPO_ROOT / "packages" / "research-os-core"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

R1_TEST_DIR = REPO_ROOT / "apps" / "backend-rag" / "backend" / "tests" / "unit" / "research_os"
P06_BUNDLE = (
    REPO_ROOT
    / "research/operations/execution/research-os-v1.0.0/evidence/p06/ros-v1-p06-naga-prep-b01"
)


def _load_r1_module(name: str) -> ModuleType:
    """Load one of R1's test-tree reference modules by absolute path, cached in `sys.modules`."""

    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, R1_TEST_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load R1 reference module {name!r} from {R1_TEST_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def r1_reader_reference() -> ModuleType:
    """R1's committed `research_os_reader_reference` module — the D3 executable specification."""

    return _load_r1_module("research_os_reader_reference")


@pytest.fixture(scope="session")
def r1_admission_reference() -> ModuleType:
    """R1's committed `research_os_admission_reference` module — the D4 executable specification."""

    return _load_r1_module("research_os_admission_reference")


@pytest.fixture
def load_json() -> Any:
    def _load(path: Path) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    return _load
