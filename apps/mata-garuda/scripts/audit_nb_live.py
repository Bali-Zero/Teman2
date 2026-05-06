#!/usr/bin/env python3
"""Audit 36 Round 1 candidates against live NotebookLM state.

T2 best-effort failure tolerance:
- T2.a: proactive cookie refresh (`nlm whoami` → if fail, `nlm login --clear`)
- T2.b: 1 retry + 5s backoff on transient MCP error per UUID
- T2.c: hard cap 50% — if more than half fail, abort with telegram alert.

Outputs:
- `scripts/data/nb_decomm_audit_2026-05-07.json` — per-UUID audit result
- `research/nb-archive/audit_log.md` — append-only audit trail
- `research/nb-archive/fuzzy_match_log_2026-05-07.md` — fuzzy match log

Side effect: re-runs `build_registry_from_manifest.py` to refresh
`_registry_data.py` after the manifest is rewritten with live data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data" / "nb_round1_candidates_2026-05-07.json"
AUDIT_OUT = REPO.parent.parent / "scripts" / "data" / "nb_decomm_audit_2026-05-07.json"
LOG_DIR = REPO.parent.parent / "research" / "nb-archive"
AUDIT_LOG = LOG_DIR / "audit_log.md"
FUZZY_LOG = LOG_DIR / "fuzzy_match_log_2026-05-07.md"

DRIFT_TOLERANCE = 1  # ±1 = consistent
DRIFT_DRIFTED_THRESHOLD = 5  # >5 absolute delta = drifted


class TransientMCPError(Exception):
    """Recoverable error during MCP call — eligible for 1 retry."""


def _run(cmd: list[str], timeout: int = 30) -> tuple[str, int, str]:
    """Subprocess wrapper. Returns (stdout, returncode, stderr)."""
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.stdout, proc.returncode, proc.stderr


def ensure_session_or_relogin() -> None:
    """T2.a: probe NLM session, force relogin if needed."""
    out, rc, err = _run(["nlm", "whoami"])
    if rc != 0:
        print("[T2.a] nlm whoami failed → forcing isolated login", file=sys.stderr)
        _run(["nlm", "login", "--clear"], timeout=300)


def mcp_query_notebook(uuid: str) -> dict[str, Any]:
    """Query NotebookLM for a single notebook. Raises TransientMCPError on retryable failures."""
    out, rc, err = _run(["nlm", "notebook", "info", uuid, "--json"])
    if rc != 0:
        if any(kw in (err + out).lower() for kw in ("timeout", "5xx", "connection", "transient")):
            raise TransientMCPError(err.strip() or out.strip())
        return {"source_count": None, "title": None, "error": err.strip() or out.strip()}
    return json.loads(out)


def audit_one_with_retry(uuid: str) -> dict[str, Any]:
    """T2.b: try once, retry once after 5s on TransientMCPError."""
    try:
        return mcp_query_notebook(uuid)
    except TransientMCPError:
        time.sleep(5)
        try:
            return mcp_query_notebook(uuid)
        except TransientMCPError as e:
            return {"source_count": None, "title": None, "error": f"transient_x2: {e}"}


def classify_drift(snapshot: int | None, live: int | None) -> str:
    if live is None:
        return "unknown_via_mcp_failure"
    if snapshot is None:
        return "consistent"
    delta = abs(snapshot - live)
    if delta <= DRIFT_TOLERANCE:
        return "consistent"
    if delta > DRIFT_DRIFTED_THRESHOLD:
        return "drifted"
    return "consistent"


def telegram_alert(msg: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = "1125336968"  # Zero
    if not token:
        print(f"[telegram-disabled] {msg}", file=sys.stderr)
        return
    import urllib.parse
    import urllib.request
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10)
    except Exception as e:  # noqa: BLE001
        print(f"[telegram-fail] {e}", file=sys.stderr)


def enforce_hard_cap(failures: int, total: int, threshold_pct: int) -> None:
    """T2.c: if failures/total exceeds threshold, abort phase with alert."""
    if total == 0:
        return
    pct = (failures / total) * 100
    if pct >= threshold_pct:
        msg = (
            f"NB-LIFECYCLE AUDIT ABORTED: failures={failures}/{total} ({pct:.0f}%) "
            f">= cap {threshold_pct}%. Re-run after Zero review."
        )
        telegram_alert(msg)
        print(msg, file=sys.stderr)
        raise SystemExit(2)


def append_audit_log(log_path: Path, uuid: str, action: str, note: str = "") -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    line = f"- {ts} | {uuid} | {action} | {note}\n"
    with log_path.open("a") as f:
        f.write(line)


def update_manifest_with_live_data(manifest: dict, live: dict[str, dict]) -> dict:
    for c in manifest["candidates"]:
        uuid = c["uuid"]
        info = live.get(uuid, {})
        c["name_live"] = info.get("title")
        c["source_count_live"] = info.get("source_count")
        c["drift_status"] = classify_drift(c["source_count_snapshot"], info.get("source_count"))
        # If drift is drifted or unknown, force ORPHAN_REVIEW (Zero re-decides).
        if c["drift_status"] in ("drifted", "unknown_via_mcp_failure"):
            c["proposed_action"] = "ORPHAN_REVIEW"
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-network", action="store_true", help="dry-run; do not call nlm")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    FUZZY_LOG.touch(exist_ok=True)

    if not args.skip_network:
        ensure_session_or_relogin()

    manifest = json.loads(MANIFEST.read_text())
    live: dict[str, dict] = {}
    fails = 0
    for c in manifest["candidates"]:
        uuid = c["uuid"]
        if args.skip_network:
            info = {"source_count": None, "title": None}
        else:
            info = audit_one_with_retry(uuid)
        if info.get("source_count") is None and not args.skip_network:
            fails += 1
        live[uuid] = info
        append_audit_log(AUDIT_LOG, uuid, "AUDITED", note=str(info))

    enforce_hard_cap(fails, len(manifest["candidates"]), threshold_pct=50)

    update_manifest_with_live_data(manifest, live)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text(json.dumps({"audited_at": dt.datetime.now(dt.timezone.utc).isoformat(), "live": live}, indent=2))

    # Trigger registry regen so _registry_data.py picks up the audited values.
    rebuilder = REPO / "scripts" / "build_registry_from_manifest.py"
    subprocess.run([sys.executable, str(rebuilder)], check=True)

    print(f"audit done: {len(live)} candidates, {fails} mcp fails")
    return 0


if __name__ == "__main__":
    sys.exit(main())
