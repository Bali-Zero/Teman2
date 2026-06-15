#!/usr/bin/env python3
"""Test for _phase.is_plan_phase (phase-aware STEP 2).

Run: python infra/claude-hooks/test_phase.py  (exit 0 = all green)
Covers the proven snake_case signal, camelCase fallback, fail-safe-on-missing,
the NUZ_PHASE manual escape, and the NUZ_PHASE_AWARE_OFF kill-switch precedence.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _load():
    spec = importlib.util.spec_from_file_location("phase_uut", str(HERE / "_phase.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = _load()
    fails = 0

    def check(name, got, expect):
        nonlocal fails
        ok = got is expect
        if not ok:
            fails += 1
        print(f"  [{'OK ' if ok else 'FAIL'}] {got!s:5} expect={expect!s:5}  {name}")

    # Clean env baseline for the deterministic cases.
    for k in ("NUZ_PHASE", "NUZ_PHASE_AWARE_OFF"):
        os.environ.pop(k, None)

    # 1. proven snake_case signal
    check("permission_mode=plan", mod.is_plan_phase({"permission_mode": "plan"}), True)
    check("permission_mode=bypassPermissions",
          mod.is_plan_phase({"permission_mode": "bypassPermissions"}), False)
    check("permission_mode=default", mod.is_plan_phase({"permission_mode": "default"}), False)
    # 2. camelCase fallback (defensive)
    check("permissionMode=plan (camel fallback)",
          mod.is_plan_phase({"permissionMode": "plan"}), True)
    # 3. fail-safe: missing field / empty / wrong type → False
    check("empty dict", mod.is_plan_phase({}), False)
    check("no mode key", mod.is_plan_phase({"tool_name": "Bash"}), False)
    check("None payload", mod.is_plan_phase(None), False)
    check("str payload", mod.is_plan_phase("plan"), False)

    # 4. NUZ_PHASE=plan manual escape (no field) → True
    os.environ["NUZ_PHASE"] = "plan"
    check("NUZ_PHASE=plan, empty payload", mod.is_plan_phase({}), True)
    os.environ.pop("NUZ_PHASE")

    # 5. kill-switch precedence: wins even over a real plan signal AND manual escape
    os.environ["NUZ_PHASE_AWARE_OFF"] = "1"
    os.environ["NUZ_PHASE"] = "plan"
    check("OFF=1 beats permission_mode=plan",
          mod.is_plan_phase({"permission_mode": "plan"}), False)
    check("OFF=1 beats NUZ_PHASE=plan", mod.is_plan_phase({}), False)
    os.environ.pop("NUZ_PHASE_AWARE_OFF")
    os.environ.pop("NUZ_PHASE")

    print("=== ALL GREEN ===" if not fails else f"=== {fails} FAIL ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
