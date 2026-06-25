#!/usr/bin/env python3
"""Innocence+guilt test for the scar_test gate kind (A1 / Loop-B).

A guard merged without an innocence AND guilt test is the W83/84/85/86 family.
This proves check_scar_test:
  - GUILT: a re-biting scar (failing test) -> DISARMED; a missing test -> DISARMED;
    an erroring test -> DISARMED (handled, not a crash).
  - INNOCENCE: a passing test -> ARMED; a prose_only scar -> WARN (visible debt,
    never silently green/ARMED).

    python3 scripts/test_scar_test_gate.py
Exit 0 = all pass.
"""
from __future__ import annotations
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_the_verifiers as v  # noqa: E402


def _write(tmp: pathlib.Path, name: str, body: str) -> pathlib.Path:
    p = tmp / name
    p.write_text(body)
    return p


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp())
    passing = _write(tmp, "pass.py", "import sys\nprint('ok')\nsys.exit(0)\n")
    failing = _write(tmp, "fail.py", "import sys\nprint('regressed')\nsys.exit(1)\n")
    erroring = _write(tmp, "err.py", "import no_such_module_xyz\n")

    cases = [
        # name, gate, expected_verdict
        ("innocence: passing test -> ARMED",
         {"id": "p", "w_number": "W1", "target": str(passing)}, v.ARMED),
        ("innocence: prose_only -> WARN (visible debt, never ARMED)",
         {"id": "pr", "w_number": "W2", "prose_only": True, "target": ""}, v.WARN),
        ("guilt: failing test (scar re-bit) -> DISARMED",
         {"id": "f", "w_number": "W3", "target": str(failing)}, v.DISARMED),
        ("guilt: missing test -> DISARMED",
         {"id": "m", "w_number": "W4", "target": str(tmp / "nope.py")}, v.DISARMED),
        ("guilt: erroring test -> DISARMED (handled, no crash)",
         {"id": "e", "w_number": "W5", "target": str(erroring)}, v.DISARMED),
    ]

    fails = 0
    for name, gate, expect in cases:
        got = v.check_scar_test(gate).verdict
        ok = got == expect
        if not ok:
            fails += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] got={got:8} expect={expect:8} | {name}")

    # critical property: prose_only must NEVER be ARMED (that would be a silent green)
    pr = v.check_scar_test({"id": "x", "prose_only": True, "target": ""})
    if pr.verdict == v.ARMED:
        fails += 1
        print("  [FAIL] prose_only returned ARMED — silent-green leak!")
    else:
        print("  [PASS] prose_only never ARMED (no silent-green)")

    total = len(cases) + 1
    print(f"\n=== {'ALL ' + str(total) + ' PASS' if not fails else str(fails) + '/' + str(total) + ' FAIL'} ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
