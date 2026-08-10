#!/usr/bin/env python3
"""Intel Lake outbox drain (Wave 1, 2026-05-12).

Reads up to 100 pending rows from ~/.intel-lake-outbox.db and POSTs them
to the backend Fly endpoint `/api/intel/lake/observations:batch`.

Scheduled every 60s via LaunchAgent `com.balizero.intel-lake.outbox-drain.minute`.

Env required:
  INTEL_LAKE_PRODUCER_TOKEN  — bearer for X-Producer-Token header
  NUZANTARA_BACKEND_URL      — default https://nuzantara-rag.fly.dev
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from intel_lake_outbox import fetch_pending, mark_delivered, mark_failed, stats  # type: ignore

# Log routing fix (PR-B2 2026-05-20):
# Default `basicConfig` sends ALL levels to sys.stderr. Pro launchd captures
# stderr to ~/logs/intel-lake-outbox-drain.err — INFO routing noise grew to
# 841 KB while the stdout log stayed empty (false-alarm appearance).
# Split: INFO/DEBUG -> stdout, WARNING+ -> stderr.
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setLevel(logging.DEBUG)
_stdout_handler.addFilter(lambda r: r.levelno < logging.WARNING)
_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.WARNING)
_fmt = logging.Formatter("%(asctime)s %(levelname)s [outbox-drain] %(message)s")
_stdout_handler.setFormatter(_fmt)
_stderr_handler.setFormatter(_fmt)
logging.root.setLevel(logging.INFO)
logging.root.handlers = [_stdout_handler, _stderr_handler]
logger = logging.getLogger("intel-lake-outbox-drain")

BACKEND_URL = os.environ.get("NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev")
PRODUCER_TOKEN = os.environ.get("INTEL_LAKE_PRODUCER_TOKEN", "")
BATCH_SIZE = int(os.environ.get("INTEL_LAKE_DRAIN_BATCH", "100"))
HTTP_TIMEOUT = float(os.environ.get("INTEL_LAKE_DRAIN_TIMEOUT", "30"))


def main() -> int:
    if not PRODUCER_TOKEN:
        logger.error("INTEL_LAKE_PRODUCER_TOKEN missing — refusing to drain")
        return 2

    rows = fetch_pending(BATCH_SIZE)
    if not rows:
        # No work — print stats every 5 minutes (cheap)
        s = stats()
        if s["pending"] or s["abandoned"]:
            logger.info("idle (pending=%(pending)s delivered=%(delivered)s abandoned=%(abandoned)s)", s)
        return 0

    ids = [r[0] for r in rows]
    observations: list[dict[str, Any]] = []
    for _id, _producer, payload_json in rows:
        try:
            observations.append(json.loads(payload_json))
        except Exception as e:
            logger.warning("row %s malformed JSON: %s — abandoning", _id, e)
            # Mark as 10 attempts to abandon
            for _ in range(10):
                mark_failed(_id, f"malformed JSON: {e}")
            continue

    url = f"{BACKEND_URL.rstrip('/')}/api/intel/lake/observations-batch"
    payload = {"observations": observations}
    headers = {
        "X-Producer-Token": PRODUCER_TOKEN,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            body = r.json()
    except httpx.HTTPStatusError as e:
        # 401/413 etc. — definitely won't recover by retrying
        for _id in ids:
            mark_failed(_id, f"http {e.response.status_code}: {e.response.text[:200]}")
        logger.error("HTTP %s draining %s rows: %s", e.response.status_code, len(ids), e.response.text[:200])
        return 1
    except Exception as e:
        # Network / timeout — retryable, increment attempts and retry next tick
        for _id in ids:
            mark_failed(_id, f"network: {type(e).__name__}: {e}")
        logger.warning("network error draining %s rows: %s — will retry", len(ids), e)
        return 1

    accepted = int(body.get("accepted", 0))
    rejected = int(body.get("rejected", 0))

    # Mark all delivered to avoid infinite retry loops. The backend audit log
    # is the system of record for rejected items.
    #
    # However: a non-zero rejected count means producer-side data is being
    # silently dropped. Emit a WARNING + Telegram alert (debounced via state
    # file) when rejected > 0 — discovered 2026-05-13 that a `published_at`
    # bind error in intel_lake_service.py was silently dropping every item
    # with a date since Wave 4 deploy, with zero visibility from producers.
    mark_delivered(ids)
    if rejected > 0:
        logger.warning(
            "drained %s rows but %s REJECTED by backend — check intel_lake_audit_log on Fly. "
            "accepted=%s rejected=%s url=%s",
            len(ids), rejected, accepted, rejected, BACKEND_URL,
        )
        _alert_rejected(rejected, accepted, len(ids))
    else:
        logger.info(
            "drained %s rows (accepted=%s rejected=%s) → backend %s",
            len(ids), accepted, rejected, BACKEND_URL,
        )
    return 0


_GATEWAY_VERDICT_RE = re.compile(r"^tg_notify:\s*(\S+)", re.MULTILINE)


def _find_gateway() -> Path | None:
    """Locate scripts/tg_notify.py from EITHER place this file runs from.

    Two, because this drain has two homes: the repo keeps it one directory
    down (`scripts/intel-lake-outbox-drain/`) while the LaunchAgent runs
    `~/scripts/intel-lake-outbox-drain.py`, a flat HOME copy with no
    `tg_notify.py` beside it (superscar #1). Sibling first, then the
    repo-shaped parent, then the checkout — so the alarm survives whichever
    copy is executing instead of dying with the fork.
    """
    here = Path(__file__).resolve().parent
    for candidate in (
        here / "tg_notify.py",
        here.parent / "tg_notify.py",
        Path.home() / "nuzantara" / "scripts" / "tg_notify.py",
    ):
        if candidate.is_file():
            return candidate
    return None


def _alert_rejected(rejected: int, accepted: int, total: int) -> None:
    """Hand a backend-rejection alert to the tg_notify gateway.

    This runs every 60s, so it is one of the loudest possible senders in the
    fleet: a backend regression that rejects rows for an hour is 60 firings
    of the same fact. It used to hold that back with a private 30-minute
    state file and then POST straight to Telegram's sendMessage endpoint —
    outside the gateway's tier router, budget, digest and escalation ladder, and
    invisible to the ledger that exists to answer "how much did the organism
    send today?".

    The local cooldown is gone rather than kept: `--dedup-key` names the
    CONDITION (this organ, rejections) and the gateway's ladder is both wider
    and smarter than a flat 30 minutes. Deliberately NOT keyed on the counts —
    a key carrying `{rejected}/{total}` would mint a fresh one on every
    fluctuation and defeat every window (the defect #3677 cured at the
    sentinel).
    """
    text = (
        f"\U0001F534 intel-lake-outbox-drain: {rejected}/{total} items REJECTED by backend "
        f"(accepted={accepted}). Check intel_lake_audit_log on Fly for root cause."
    )
    gateway = _find_gateway()
    if gateway is None:
        # Loud in the log rather than silent: an alert that cannot be sent must
        # still leave a trace of not having been sent (W108).
        logger.warning("tg_notify gateway not found — alert NOT sent: %s", text)
        return
    cmd = [
        # Absolute interpreter (sys.executable), never a PATH lookup: the
        # alarm must not share a failure mode with the thing it reports (W108).
        sys.executable,
        str(gateway),
        "--tier",
        "p0",
        "--source",
        "intel-lake-outbox-drain",
        "--dedup-key",
        "intel-lake-outbox:rejected",
        "--",
        text,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("tg_notify unreachable (%s): %s", type(exc).__name__, exc)
        return
    # The gateway always exits 0 on purpose and prints its verdict on stderr;
    # reading the exit code would take every refusal for a success (W104).
    match = _GATEWAY_VERDICT_RE.search(proc.stderr or "")
    if match:
        logger.info("tg_notify: %s (rejected=%s)", match.group(1), rejected)
    else:
        tail = " ".join((proc.stderr or "").split())[-160:]
        logger.warning(
            "tg_notify printed no verdict (rc=%s): %s", proc.returncode, tail or "<empty>"
        )


if __name__ == "__main__":
    sys.exit(main())
