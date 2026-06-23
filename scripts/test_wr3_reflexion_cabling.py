#!/usr/bin/env python3
"""Innocence+guilt test for the A3 cabling of wr3_reflexion_synthesis.record_run
onto the unified core (scripts/lib/reflexion.py).

The cabling swaps WR3's private Delta-Gate copy for reflexion_core.record_run
(superscar #1 HOME-fork cure). This proves the swap is reader-safe (the state file
still records honestly), the WR3 status vocabulary maps correctly, an unmapped
status RAISES (no silent typo), and the tautology alarm is now reachable.

    python3 scripts/test_wr3_reflexion_cabling.py
Exit 0 = all pass.
"""
from __future__ import annotations
import importlib.util
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wr3_reflexion", str(HERE / "wr3_reflexion_synthesis.py"))
WR3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(WR3)
CORE = WR3.reflexion_core


def main() -> int:
    fails = 0

    def check(name: str, cond: bool) -> None:
        nonlocal fails
        if not cond:
            fails += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    tmp = pathlib.Path(tempfile.mkdtemp())

    # --- INNOCENCE: WR3 record_run still writes the state file, delegated to core ---
    sp = WR3.record_run(tmp, window_days=7, episodes_found=0, lessons_written=0,
                        status="NO_INPUT", notes="empty week")
    hist = CORE._load_json(sp)
    check("cabling: WR3 record_run persists via core (state file is a list)",
          isinstance(hist, list) and len(hist) == 1)
    check("cabling: NO_INPUT mapped to core NO_SIGNAL (honest empty run on disk)",
          hist[0]["status"] == CORE.NO_SIGNAL)
    check("cabling: WR3 episodes_found carried as core signals_found (reader-safe swap)",
          hist[0]["signals_found"] == 0 and hist[0]["loop"] == "wr3")

    # --- INNOCENCE: SYNTHESIZED maps to LEARNED, THIN_SIGNAL to NO_SIGNAL ---
    WR3.record_run(tmp, window_days=7, episodes_found=4, lessons_written=2, status="SYNTHESIZED")
    WR3.record_run(tmp, window_days=7, episodes_found=4, lessons_written=0, status="THIN_SIGNAL")
    hist = CORE._load_json(sp)
    statuses = [h["status"] for h in hist]
    check("cabling: SYNTHESIZED -> LEARNED", CORE.LEARNED in statuses)
    check("cabling: THIN_SIGNAL -> NO_SIGNAL", statuses[-1] == CORE.NO_SIGNAL)

    # --- GUILT: an unmapped/typo WR3 status RAISES (no silent bad record) ---
    try:
        WR3.record_run(tmp, window_days=7, episodes_found=1, lessons_written=1, status="GREEN_OK")
        check("cabling guilt: unmapped status raises ValueError", False)
    except ValueError:
        check("cabling guilt: unmapped status raises ValueError", True)

    # --- TAUTOLOGY ALARM now reachable from WR3 (was absent before cabling) ---
    t2 = pathlib.Path(tempfile.mkdtemp())
    for _ in range(CORE.HOT_WINDOW):
        WR3.record_run(t2, window_days=7, episodes_found=0, lessons_written=0, status="NO_INPUT")
    check("cabling: tautology alarm reachable — all-NO_INPUT window is tautological",
          CORE.is_tautological(t2) is True)
    # a SYNTHESIZED run breaks it
    WR3.record_run(t2, window_days=7, episodes_found=3, lessons_written=1, status="SYNTHESIZED")
    check("cabling: a SYNTHESIZED run clears the tautology alarm",
          CORE.is_tautological(t2) is False)

    # --- _warn_if_tautological is best-effort (never raises) ---
    try:
        WR3._warn_if_tautological(t2)
        WR3._warn_if_tautological(pathlib.Path("/nonexistent/path/xyz"))
        check("cabling: _warn_if_tautological never raises (best-effort)", True)
    except Exception:
        check("cabling: _warn_if_tautological never raises (best-effort)", False)

    total = 9
    print(f"\n=== {'ALL ' + str(total) + ' PASS' if not fails else str(fails) + ' FAIL'} ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
