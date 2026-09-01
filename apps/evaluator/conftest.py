"""Wire the pytest verbosity guard into this config root.

Byte-identical in every wired root — what it does and why it exists live in
``scripts/pytest_guards/pytest_verbosity_guard.py``; the wiring is checked by
``scripts/tests/test_pytest_verbosity_guard.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

for _ancestor in Path(__file__).resolve().parents:
    _guards = _ancestor / "scripts" / "pytest_guards"
    if (_guards / "pytest_verbosity_guard.py").is_file():
        if str(_guards) not in sys.path:
            sys.path.insert(0, str(_guards))
        break

from pytest_verbosity_guard import pytest_configure  # noqa: E402,F401
