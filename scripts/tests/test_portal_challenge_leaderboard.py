"""Tests for scripts/portal_challenge_leaderboard.py — Portal Champion points.

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package — same convention as test_pending_arms_report.py. Only the pure
`score()` function is exercised here: everything else in the script shells
out to prod Postgres via scripts/pg.sh and is out of scope for a unit test.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

MODULE_PATH = Path(__file__).resolve().parent.parent / "portal_challenge_leaderboard.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("portal_challenge_leaderboard", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pcl = _load_module()


def test_score_weights_match_spec_section_9() -> None:
    """1 point/invited, 3/activated, 2/first_action (spec §9)."""
    assert pcl.score(2, 1, 1) == 2 * 1 + 1 * 3 + 1 * 2 == 7


def test_score_zero_invited_is_zero() -> None:
    assert pcl.score(0, 0, 0) == 0


def test_window_bounds_are_wita_day_boundaries_end_exclusive() -> None:
    start_ts, end_ts = pcl._window_bounds("2026-09-14", "2026-09-29")
    assert start_ts.startswith("2026-09-14T00:00:00")
    assert start_ts.endswith("+08:00")
    # end is INCLUSIVE per the CLI contract, so the exclusive SQL bound is
    # the NEXT day's midnight WITA.
    assert end_ts.startswith("2026-09-30T00:00:00")
    assert end_ts.endswith("+08:00")
