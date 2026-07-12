"""wr2_runtime_stamp — runtime provenance for WR2 organs (C2, deploy-fork content-gate).

The disease (cicatrix #1 / D5, lived 2026-06-30): an organ EXECUTES code that is
not the code the repo says is deployed — a stale deploy clone, a long-running
daemon that imported modules before the last pull, or locally-mutated files.
Exit codes and `launchctl list` cannot see it; only provenance can.

Every stamped organ writes ~/.organism/last_seen/<organ>.runtime.json:

    {ts, pid, host, checkout, head_sha, dirty, stale_modules[], errors[]}

- head_sha        git HEAD of the checkout the process ACTUALLY runs from
- dirty           `git status --porcelain` non-empty
- stale_modules   watched module files whose LIVE blob differs from the HEAD
                  blob (`git hash-object <live>` vs `git rev-parse HEAD:<rel>`)
                  — content compare, blob-per-file, NEVER mtime/three-dot (W88)
- errors          provenance gaps (git unavailable, module outside checkout…)

Consumers: wr2_html_render_apply (one-shot worker, stamps per run + gates the
render), wr2_supervisor (daemon, stamps at startup), wr2_supervisor_watchdog
(reads the stamps and alerts RUNTIME_STALE when stamp.head_sha ≠ the checkout's
CURRENT on-disk HEAD — the daemon-running-old-code detector).

Everything here is fail-open: a broken git must never break the organ — it
degrades to an `errors` entry the watchdog can still see.

Loaded via importlib (scripts/lib is not a package — cf. wr2_reflexion_synthesis).
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Gate modes for gate_verdict (env WR2_RUNTIME_SHA_GATE).
GATE_OFF = "off"
GATE_WARN = "warn"      # default: log-only, zero pipeline effects
GATE_STRICT = "strict"  # armed separately (PENDING-ARMS): refuse/abort


def _git(checkout: Path, *args: str) -> Optional[str]:
    """git -C <checkout> <args>; None on ANY failure (fail-open)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(checkout), *args],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip()
    except Exception:  # noqa: BLE001 — provenance must never crash the organ
        return None


def current_head(checkout: Path) -> Optional[str]:
    return _git(Path(checkout), "rev-parse", "HEAD")


def compute_runtime_stamp(checkout: Path, modules) -> dict:
    """Provenance of the code THIS process runs. Never raises."""
    checkout = Path(checkout).resolve()
    head = _git(checkout, "rev-parse", "HEAD")
    dirty_out = _git(checkout, "status", "--porcelain")

    errors = []
    if head is None:
        errors.append("git-head-unavailable")
    dirty = bool(dirty_out) if dirty_out is not None else None
    if dirty_out is None:
        errors.append("git-status-unavailable")

    stale = []
    for m in modules:
        try:
            rel = Path(m).resolve().relative_to(checkout)
        except (ValueError, OSError):
            errors.append(f"outside-checkout:{Path(m).name}")
            continue
        live_blob = _git(checkout, "hash-object", str(checkout / rel))
        head_blob = _git(checkout, "rev-parse", f"HEAD:{rel.as_posix()}")
        if live_blob is None or head_blob is None:
            errors.append(f"blob-unavailable:{rel.as_posix()}")
            continue
        if live_blob != head_blob:
            stale.append(rel.as_posix())

    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "checkout": str(checkout),
        "head_sha": head,
        "dirty": dirty,
        "stale_modules": stale,
        "errors": errors,
    }


def write_runtime_stamp(organ_id: str, stamp: dict) -> Optional[Path]:
    """Atomic write of ~/.organism/last_seen/<organ_id>.runtime.json.
    Returns the path, or None on failure. Never raises."""
    try:
        directory = Path.home() / ".organism" / "last_seen"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{organ_id}.runtime.json"
        tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(stamp, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return path
    except Exception:  # noqa: BLE001
        return None


def read_runtime_stamp(organ_id: str) -> Optional[dict]:
    """Read a stamp back; None when missing/unreadable (degrade-open)."""
    try:
        path = Path.home() / ".organism" / "last_seen" / f"{organ_id}.runtime.json"
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def gate_verdict(mode: str, stamp: dict, disk_head: Optional[str]) -> tuple:
    """(verdict, reason) for the render-finalize gate.

    verdict ∈ {"ok", "warn", "block"}. "block" happens ONLY in strict mode:
      - boot provenance impure (dirty / stale modules / no head) — a mutated
        runtime must not publish (red-team finding #4);
      - the checkout's on-disk HEAD moved vs the boot stamp (a deploy-pull
        landed mid-run: the process is now running code that no longer exists
        on disk).
    In warn mode (default) the same conditions log a warning and pass —
    zero live-pipeline behavior change until strict is armed.
    """
    if mode == GATE_OFF:
        return ("ok", "gate off")

    problems = []
    if stamp.get("head_sha") is None:
        problems.append("no-head-provenance")
    if stamp.get("dirty"):
        problems.append("dirty-checkout")
    if stamp.get("stale_modules"):
        problems.append("stale-modules:" + ",".join(stamp["stale_modules"]))
    if disk_head is not None and stamp.get("head_sha") is not None and disk_head != stamp["head_sha"]:
        problems.append(f"head-moved:{stamp['head_sha'][:12]}->{disk_head[:12]}")

    if not problems:
        return ("ok", "provenance clean")
    reason = "; ".join(problems)
    return ("block", reason) if mode == GATE_STRICT else ("warn", reason)
