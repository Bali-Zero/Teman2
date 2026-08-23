from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "packages" / "research-os-core").is_dir():
            return candidate
    raise RuntimeError("cannot locate repository root from research_os test path")


REPO_ROOT = _repo_root()
PACKAGE_ROOT = REPO_ROOT / "packages" / "research-os-core"
FIXTURES_ROOT = PACKAGE_ROOT / "fixtures"
sys.path.insert(0, str(PACKAGE_ROOT))


@pytest.fixture
def load_json() -> Any:
    def _load(path: Path) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    return _load
