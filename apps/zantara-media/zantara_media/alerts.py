"""CRITICAL alerts for GARUDA — routed through the fleet Telegram gateway.

REWRITTEN 2026-08-06. This module used to POST straight to the Telegram API
with a token read from the caller's environment:

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — cannot send alert: %s", message)
        return

`garuda-indexer` runs from cron, and cron's environment does not carry that
variable. So every alert this module has ever been asked to send from cron
took the early return. Measured on Pro:

    $ grep -c invalid_grant ~/logs/cron-tmp/garuda-indexer.log
    141

The Drive OAuth credential was revoked; Google said so, out loud, on every
nightly run since at least 2026-07-27; the indexer crashed with exit=1 each
time; and the line that was supposed to tell somebody read
"TELEGRAM_BOT_TOKEN not set — cannot send alert". W108 exactly: the alarm
depends on something the environment it runs in does not provide, and it
leaves its failure in a log nobody reads instead of on the channel.

The cure is not to teach this module to find the secret — that is the
gateway's job, and it already does it (`scripts/tg_notify.py` falls back to
`~/.nuzantara-secrets.env` when the env is bare). Routing through it also
buys the dedup ladder, the tier budget and the spool, so a nightly crash
becomes about four messages a week instead of thirty.

Two rules kept from before: this never raises (an alert must not crash the
indexer), and it never blocks for long. One rule added: the outcome is always
LOGGED and returned, so "did it speak?" is answerable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_GATEWAY_TIMEOUT_S = 30.0


def _resolve_gateway() -> Path | None:
    """Locate `scripts/tg_notify.py`, most-explicit first.

    The package is installed into a venv outside the repo, so a purely
    relative resolution is not enough on its own — but it is kept last so a
    checkout in an unusual place still works.
    """
    candidates = [
        os.environ.get("NUZANTARA_REPO_ROOT"),
        str(Path.home() / "nuzantara"),
        str(Path(__file__).resolve().parents[3]),
    ]
    for root in candidates:
        if not root:
            continue
        gateway = Path(root) / "scripts" / "tg_notify.py"
        if gateway.is_file():
            return gateway
    return None


async def send_critical_alert(message: str, condition: str = "crash") -> bool:
    """Send a CRITICAL alert through the fleet gateway. Never raises.

    `condition` names WHAT is wrong, and becomes part of the dedup key. It is
    not the message: the message embeds an exception string that changes run
    to run, and a key derived from it would mint a fresh key every night and
    defeat the repeat ladder entirely (#3677). Callers with distinct failures
    must pass distinct conditions, or one will swallow the other.

    Returns True if the gateway accepted the alert.
    """
    gateway = _resolve_gateway()
    if gateway is None:
        # Loud, and carrying the payload: if the alert cannot leave the
        # machine, the log is the last place it exists. The old code logged
        # at WARNING and dropped the body's urgency with it.
        logger.error(
            "tg_notify.py not found (tried NUZANTARA_REPO_ROOT, ~/nuzantara, "
            "package-relative) — GARUDA alert NOT delivered: %s",
            message,
        )
        return False

    host = socket.gethostname().split(".")[0]
    dedup_key = f"garuda:{condition}:{host}"

    try:
        # sys.executable, not a PATH lookup: this runs inside the venv whose
        # health is one of the things being reported on, and resolving the
        # interpreter through PATH is how run_nb5_t4_monitor.sh ended up
        # reporting its failures on the interpreter that had just broken.
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(gateway),
            "--tier", "p0",
            "--source", "garuda",
            "--dedup-key", dedup_key,
            "--",
            f"🚨 GARUDA CRITICAL\n\n{message}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_GATEWAY_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        logger.error("tg_notify timed out after %ss — alert NOT delivered: %s",
                     _GATEWAY_TIMEOUT_S, message)
        return False
    except Exception as e:
        # Never raise — alerts must not crash the caller.
        logger.error("tg_notify could not be invoked (%s) — alert NOT delivered: %s",
                     e, message)
        return False

    ok = proc.returncode == 0
    # The rc is ALWAYS logged, success or not. A silent success is how you end
    # up unable to tell "it sent" from "it never ran".
    logger.log(
        logging.INFO if ok else logging.ERROR,
        "tg_notify rc=%s key=%s%s",
        proc.returncode,
        dedup_key,
        "" if ok else f" stderr={(stderr or b'').decode()[:300]}",
    )
    return ok
