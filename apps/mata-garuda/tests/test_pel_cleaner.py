"""W12: pel_cleaner XINFO parser + threshold logic tests."""
from __future__ import annotations
import sys
from pathlib import Path

# pel_cleaner lives in scripts/, not in the package — manual sys.path insert
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pel_cleaner  # noqa: E402


def test_parse_xinfo_consumers_two_consumers_one_pending():
    """Real Redis output: 2 consumers, debug-2 (ghost) + nlm_feeder_alerts-1 (alive)."""
    raw = (
        "name\n"
        "debug-2\n"
        "pending\n"
        "5\n"
        "idle\n"
        "1545500000\n"
        "inactive\n"
        "1545500000\n"
        "name\n"
        "nlm_feeder_alerts-1\n"
        "pending\n"
        "0\n"
        "idle\n"
        "26400000\n"
        "inactive\n"
        "26400000\n"
    )
    recs = pel_cleaner.parse_xinfo_consumers(raw)
    assert len(recs) == 2
    assert recs[0]["name"] == "debug-2"
    assert recs[0]["pending"] == "5"
    assert recs[0]["idle"] == "1545500000"
    assert recs[1]["name"] == "nlm_feeder_alerts-1"
    assert recs[1]["pending"] == "0"


def test_parse_xinfo_consumers_single():
    raw = "name\nnlm_feeder-1\npending\n82\nidle\n2049173\ninactive\n2049173\n"
    recs = pel_cleaner.parse_xinfo_consumers(raw)
    assert len(recs) == 1
    assert recs[0] == {"name": "nlm_feeder-1", "pending": "82", "idle": "2049173", "inactive": "2049173"}


def test_parse_xinfo_consumers_empty():
    assert pel_cleaner.parse_xinfo_consumers("") == []
    assert pel_cleaner.parse_xinfo_consumers("\n\n\n") == []


def test_thresholds_match_design():
    """Confirm thresholds: stale_pel=24h, ghost=30d, alive=24h."""
    assert pel_cleaner.STALE_PEL_IDLE_MS == 24 * 3600 * 1000
    assert pel_cleaner.GHOST_IDLE_MS == 30 * 86400 * 1000
    assert pel_cleaner.ALIVE_IDLE_MS_MAX == 24 * 3600 * 1000
    assert pel_cleaner.XCLAIM_MIN_IDLE_MS == 60_000
