#!/usr/bin/env python3
"""Activate + verify the rebuilt worktree-gc plist, writing INCREMENTALLY.

Every launchctl call has a hard timeout and the report is flushed after each
step, so a hang never leaves an empty report. Read /tmp/wtgc_activate_report.txt.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

PLIST = Path.home() / "Library" / "LaunchAgents" / "com.nuzantara.worktree-gc-universal.daily.plist"
LABEL = "com.nuzantara.worktree-gc-universal.daily"
REPORT = Path("/tmp/wtgc_activate_report.txt")
UID = os.getuid()
_out: list[str] = []


def flush() -> None:
    REPORT.write_text("\n".join(_out))


def log(s: str = "") -> None:
    _out.append(s)
    flush()


def run(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -99, "", f"TIMEOUT after {timeout}s"
    except Exception as exc:  # noqa: BLE001
        return -98, "", repr(exc)


def main() -> None:
    log("=== worktree-gc activation report ===")
    log(f"plist exists: {PLIST.exists()} size={PLIST.stat().st_size if PLIST.exists() else 0}")

    rc, so, se = run(["/usr/bin/plutil", "-lint", str(PLIST)])
    log(f"[lint] rc={rc} {so.strip()} {se.strip()}")

    rc, so, se = run(["/usr/bin/plutil", "-extract", "ProgramArguments", "json", str(PLIST)])
    log(f"[ProgramArguments] rc={rc} {so.strip()}")
    log(f"[has --apply?] {'--apply' in so}")

    rc, so, se = run(["/bin/launchctl", "bootout", f"gui/{UID}", str(PLIST)])
    log(f"[bootout] rc={rc} {(so or se).strip()[:160]}")

    rc, so, se = run(["/bin/launchctl", "bootstrap", f"gui/{UID}", str(PLIST)])
    log(f"[bootstrap] rc={rc} {(so or se).strip()[:160]}")

    rc, so, se = run(["/bin/launchctl", "list"])
    hits = [ln for ln in so.splitlines() if LABEL in ln]
    log(f"[list grep] {hits or 'NOT FOUND'}")

    rc, so, se = run(["/bin/launchctl", "print", f"gui/{UID}/{LABEL}"])
    log(f"[print rc] {rc}")
    if rc == 0:
        for ln in so.splitlines():
            s = ln.strip()
            if (s.startswith("state =") or s.startswith("path =")
                    or s.startswith("pid =") or "worktree_gc_universal" in s
                    or "--apply" in s or s.startswith("runs =")):
                log("  " + s)
    else:
        log("  print stderr: " + (se or "").strip()[:200])

    log("=== END ===")
    print(str(REPORT))


if __name__ == "__main__":
    main()
