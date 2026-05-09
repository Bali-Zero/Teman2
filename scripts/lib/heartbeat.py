"""heartbeat.py — Python sibling of scripts/lib/heartbeat.sh.

Writes a single-line JSON heartbeat to ~/.organism/last_seen/<organ_id>.json.
Atomic via write-to-tmp + os.replace. Idempotent. Never raises.

Usage:
    from scripts.lib.heartbeat import organism_heartbeat
    organism_heartbeat("pro.my_organ", "ok")
    organism_heartbeat("pro.my_organ", "error", note="rc=42 timeout")

Standalone:
    python -m scripts.lib.heartbeat pro.my_organ ok
    python -m scripts.lib.heartbeat pro.my_organ error "rc=42"
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".organism" / "last_seen"


def organism_heartbeat(organ_id: str, status: str = "ok", note: str = "", *, last_seen_dir: Path | None = None) -> bool:
    """Write a heartbeat. Returns True on success, False otherwise (never raises)."""
    try:
        directory = Path(last_seen_dir) if last_seen_dir is not None else Path(os.environ.get("ORGANISM_LAST_SEEN_DIR", str(_DEFAULT_DIR)))
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{organ_id}.json"
        payload = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "note": str(note)[:500],
        }
        tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: heartbeat.py <organ_id> [status] [note]", file=sys.stderr)
        return 2
    organ_id = sys.argv[1]
    status = sys.argv[2] if len(sys.argv) > 2 else "ok"
    note = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
    ok = organism_heartbeat(organ_id, status, note)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
