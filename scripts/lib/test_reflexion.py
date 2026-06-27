#!/usr/bin/env python3
"""Innocence+guilt test for scripts/lib/reflexion.py (A3 reflexion core).

A component merged without innocence AND guilt tests is the W83/84/85/86 family.
This proves the Delta Gate records honestly, the noise-bound holds, the MOS
promote-gate blocks un-promoted lessons, and the FTS5 hyphen-sanitize works.

    python3 scripts/lib/test_reflexion.py
Exit 0 = all pass.
"""
from __future__ import annotations
import importlib.util
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("reflexion", str(HERE / "reflexion.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def main() -> int:
    fails = 0

    def check(name: str, cond: bool) -> None:
        nonlocal fails
        if not cond:
            fails += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    tmp = pathlib.Path(tempfile.mkdtemp())

    # --- DELTA GATE: a NO_SIGNAL run is recorded on disk, not silent ---
    sp = R.record_run(tmp, loop="demo", signals_found=0, lessons_written=0,
                      status=R.NO_SIGNAL, notes="nothing to learn")
    hist = R._load_json(sp)
    check("delta-gate: NO_SIGNAL run is persisted (not a silent exit)",
          isinstance(hist, list) and len(hist) == 1 and hist[0]["status"] == R.NO_SIGNAL)

    # --- DELTA GATE: invalid status rejected (guilt) ---
    try:
        R.record_run(tmp, loop="demo", signals_found=1, lessons_written=1, status="GREEN")
        check("delta-gate: invalid status rejected", False)
    except ValueError:
        check("delta-gate: invalid status rejected", True)

    # --- TAUTOLOGY ALARM (A2-on-the-loop): 3 NO_SIGNAL in a row -> True ---
    for _ in range(2):
        R.record_run(tmp, loop="demo", signals_found=0, lessons_written=0, status=R.NO_SIGNAL)
    check("tautology alarm fires after HOT_WINDOW all-NO_SIGNAL runs",
          R.is_tautological(tmp) is True)
    # a LEARNED run breaks the tautology
    R.record_run(tmp, loop="demo", signals_found=2, lessons_written=1, status=R.LEARNED)
    check("tautology alarm clears after a LEARNED run", R.is_tautological(tmp) is False)

    # --- NOISE BOUND: lessons.md keeps only HOT_WINDOW bullets ---
    ld = tmp / "lessons"
    for i in range(6):
        R.write_lesson_file(ld, loop="demo", lesson=f"lesson number {i}")
    p = ld / "demo.lessons.md"
    bullets = [ln for ln in p.read_text().splitlines() if ln.strip().startswith("- ")]
    check(f"noise bound: lessons.md capped at HOT_WINDOW={R.HOT_WINDOW}",
          len(bullets) == R.HOT_WINDOW)
    check("noise bound: keeps the NEWEST lessons (lesson 5 present, lesson 0 evicted)",
          any("lesson number 5" in b for b in bullets) and not any("number 0" in b for b in bullets))

    # --- PROMOTE-GATE (superscar #6): un-promoted lesson NEVER hits MOS ---
    calls = {"n": 0}
    fake_cli = tmp / "fake_mem"
    fake_cli.write_text("#!/bin/sh\nexit 0\n"); fake_cli.chmod(0o755)
    # promoted=False must short-circuit BEFORE shelling out
    ok_blocked = R.save_lesson_mos("demo", "phantom lesson", promoted=False, mem_cli=fake_cli)
    check("promote-gate: un-promoted lesson is BLOCKED from MOS (returns False)", ok_blocked is False)
    # promoted=True does attempt the save (fake cli returns 0)
    ok_saved = R.save_lesson_mos("demo", "real lesson", promoted=True, mem_cli=fake_cli)
    check("promote-gate: promoted lesson reaches the MOS save path", ok_saved is True)

    # --- FTS5 HYPHEN SANITIZE: loop key with '-' is hyphen-free in stored artifacts ---
    p2 = R.write_lesson_file(ld, loop="wr2-design", lesson="x")
    check("fts5 sanitize: hyphenated loop name -> underscore filename (no '-')",
          "wr2_design" in p2.name and "wr2-design" not in p2.name)

    # --- CONSOLIDATION: dedup-by-content + cap ---
    ld2 = tmp / "lessons2"
    for _ in range(4):
        R.write_lesson_file(ld2, loop="dup", lesson="identical lesson")  # same content 4x
    dropped = R.consolidate_lessons(ld2, loop="dup")
    after = [ln for ln in (ld2 / "dup.lessons.md").read_text().splitlines() if ln.strip().startswith("- ")]
    check("consolidation: dedups identical lessons to 1", len(after) == 1)

    total = 11
    print(f"\n=== {'ALL ' + str(total) + ' PASS' if not fails else str(fails) + ' FAIL'} ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
