"""Make the `research_os` core package importable without a packaging change.

`packages/research-os-core` is a standalone, installable package
(`pyproject.toml`, setuptools) but it is not yet declared as a dependency of
`apps/backend-rag` anywhere (grepped: zero non-test consumers repo-wide as of
this writing). Rather than touch a shared `pyproject.toml`/requirements file
that other in-flight P04 lanes are also racing on, this module mirrors the
exact `sys.path` bootstrap the test suite already uses
(`apps/backend-rag/backend/tests/unit/research_os/conftest.py`): discover the
repo root by walking up for `packages/research-os-core`, then prepend it to
`sys.path` once. Importing this module (or any adapter module, which imports
it first) is the only setup required.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "packages" / "research-os-core").is_dir():
            return candidate
    raise RuntimeError("cannot locate repository root from research_os adapter path")


_PACKAGE_ROOT = _repo_root() / "packages" / "research-os-core"
_PACKAGE_ROOT_STR = str(_PACKAGE_ROOT)
if _PACKAGE_ROOT_STR not in sys.path:
    sys.path.insert(0, _PACKAGE_ROOT_STR)
