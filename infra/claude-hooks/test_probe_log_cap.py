#!/usr/bin/env python3
"""The probe log both write-guards append to is capped, and the cap never
touches a verdict.

Measured 2026-09-18 on M5: ~/.claude/l5_1_hook_probe.jsonl had grown to 4.7 MB
since June, one line per tool call from worktree_isolation.py and
worktree_file_write_check.py, no reader, no rotation.

  GUILT     (the cap bites): above PROBE_LOG_MAX_BYTES the next append keeps
            only the last PROBE_LOG_KEEP_LINES plus the new line, the newest
            entry is last, nothing older survives, no tmp file is left behind.
  INNOCENCE (nothing else changes): a small log is appended to and loses no
            line; a missing log is created; an unwritable location raises
            nothing — `_probe_log` stays a no-throw call for the hook's verdict.

    python3 infra/claude-hooks/test_probe_log_cap.py
Runnable standalone or under pytest. Not wired into a CI workflow step (the
same standing as test_mailbox_inject.py: editing .github/workflows/ is a
separate hot-zone surface).
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent

HOOKS = {
    "worktree_isolation.py": lambda mod, i: mod._probe_log({"tool_name": "Bash", "cwd": "/x", "tool_input": {"command": f"echo {i}"}}, "allow"),
    "worktree_file_write_check.py": lambda mod, i: mod._probe_log({"tool_name": "Write", "cwd": "/x"}, f"/x/f{i}.py", "allow"),
}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py") + "_cap", str(HERE / name))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _lines(p: pathlib.Path) -> list[str]:
    return p.read_text().splitlines()


def main() -> int:
    failures: list[str] = []
    for name, append in HOOKS.items():
        mod = _load(name)
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="probe_cap_"))
        log = tmp / "probe.jsonl"
        mod.PROBE_LOG = log
        mod.PROBE_LOG_MAX_BYTES = 5_000
        mod.PROBE_LOG_KEEP_LINES = 50

        def check(cond: bool, what: str) -> None:
            if not cond:
                failures.append(f"[{name}] {what}")

        append(mod, 0)
        check(log.exists() and len(_lines(log)) == 1, "missing log → created with one line")
        for i in range(1, 6):
            append(mod, i)
        check(len(_lines(log)) == 6, f"small log appended, nothing dropped (got {len(_lines(log))})")
        log.write_text("".join(json.dumps({"old": i}) + "\n" for i in range(500)))
        check(log.stat().st_size > mod.PROBE_LOG_MAX_BYTES, "fixture is above the cap")
        append(mod, 999)
        got = _lines(log)
        check(len(got) == 51, f"capped to KEEP_LINES + 1 (got {len(got)})")
        check(bool(got) and json.loads(got[0]) == {"old": 450}, "the kept tail starts at old line 450")
        check(bool(got) and "999" in got[-1] and "old" not in got[-1], "the newest entry is last")
        check(not list(tmp.glob("*.tmp")), "no tmp file left behind")
        append(mod, 1000)
        check(len(_lines(log)) == 52, "next append below the cap keeps everything")
        blocker = tmp / "not-a-dir"
        blocker.write_text("x")
        mod.PROBE_LOG = blocker / "probe.jsonl"
        try:
            append(mod, 1)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"[{name}] unwritable location raised {exc!r}")

    if failures:
        print(f"=== {len(failures)} FAIL ===")
        for f in failures:
            print("  [FAIL] " + f)
        return 1
    print("=== probe-log cap: ALL OK (both hooks) ===")
    return 0


def test_probe_log_cap():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
