#!/usr/bin/env python3
"""S3 / W55 — Weekly digest of cooldown-suppressed escalations.

The W55 GOTCHA (cicatrix 2026-05-25): per-job alert cooldown suppression
"presumes the operator sees a dashboard — but there is none. The operator
discovers the problem only when something visible breaks." This is the missing
weekly digest that closes that gap.

Two suppression mechanisms exist, both surfaced here:

1. **Escalation cooldown** (``~/.agent/decisions/escalation_cooldown.json``,
   4h per-job): gates both the sentinel Telegram alert AND — since S3
   (2026-06-02) — the DLQ-autopilot escalation writer. When the DLQ-autopilot
   skips an escalation it bumps ``suppressed_count`` on the job's entry; this
   digest reports + resets those counters.
2. **Alert dedup** (``~/.agent/decisions/alert_dedup.json``, 1h md5 window):
   reported as a coarse count only (keys are message hashes, not jobs).

Output: one Telegram message summarising the last 7 days. Run weekly via
``infra/launchd/com.nuzantara.escalations-digest.weekly.plist`` (Pro only —
the canonical node that owns escalation_cooldown.json).

Usage:
    python scripts/escalations_suppressed_digest.py            # send Telegram
    python scripts/escalations_suppressed_digest.py --dry-run  # print, no send
    python scripts/escalations_suppressed_digest.py --no-reset # don't reset counters
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

logger = logging.getLogger("escalations_suppressed_digest")

_AGENT_DIR = Path.home() / ".agent" / "decisions"
ESCALATION_STATE_FILE = _AGENT_DIR / "escalation_cooldown.json"
ALERT_DEDUP_FILE = _AGENT_DIR / "alert_dedup.json"

WINDOW_S = 7 * 86400

# Reuse the project's telegram convention (chat id default = Zero's chat).
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get(
    "TELEGRAM_ADMIN_CHAT_ID",
    os.environ.get("TELEGRAM_OWNER_CHAT_ID", os.environ.get("TELEGRAM_CHAT_ID", "1125336968")),
)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def build_digest(now: float | None = None) -> dict:
    """Compute the digest payload from the suppression state files.

    Returns a dict with: suppressed_jobs (job -> count), total_suppressed,
    dedup_recent (count of md5 dedup entries in the last 7d), and a rendered
    `text` for Telegram.
    """
    now = now if now is not None else time.time()
    cutoff = now - WINDOW_S

    esc = _load_json(ESCALATION_STATE_FILE)
    suppressed_jobs: dict[str, int] = {}
    for job, entry in esc.items():
        if not isinstance(entry, dict):
            continue
        count = int(entry.get("suppressed_count", 0))
        last = entry.get("last_suppressed_at", entry.get("escalation_sent_at", 0))
        if count > 0 and last and last >= cutoff:
            suppressed_jobs[job] = count

    dedup = _load_json(ALERT_DEDUP_FILE)
    dedup_recent = sum(
        1 for v in dedup.values()
        if isinstance(v, dict) and v.get("ts", 0) >= cutoff
    )

    total = sum(suppressed_jobs.values())
    ranked = sorted(suppressed_jobs.items(), key=lambda kv: kv[1], reverse=True)

    if total == 0 and dedup_recent == 0:
        text = (
            "🔕 Suppressed-alerts digest (7d)\n"
            "No escalations were suppressed by cooldown this week. "
            "Either all clear, or all signals got through."
        )
    else:
        lines = ["🔕 Suppressed-alerts digest (last 7d)"]
        if total:
            lines.append(
                f"{total} DLQ escalation(s) suppressed by 4h cooldown "
                f"across {len(ranked)} job(s):"
            )
            for job, n in ranked[:15]:
                lines.append(f"  • {job}: {n}×")
            if len(ranked) > 15:
                lines.append(f"  …and {len(ranked) - 15} more")
        if dedup_recent:
            lines.append(f"{dedup_recent} Telegram alert(s) deduped (1h md5 window).")
        lines.append(
            "These were hidden from you by suppression — review the DLQ "
            "(`dlq list`) + escalations SQLite if any look unexpected."
        )
        text = "\n".join(lines)

    return {
        "suppressed_jobs": suppressed_jobs,
        "total_suppressed": total,
        "dedup_recent": dedup_recent,
        "text": text,
    }


def reset_counters() -> int:
    """Reset all suppressed_count fields to 0 after a digest is emitted.

    Returns the number of jobs whose counter was reset. Best-effort.
    """
    esc = _load_json(ESCALATION_STATE_FILE)
    n = 0
    for job, entry in esc.items():
        if isinstance(entry, dict) and entry.get("suppressed_count"):
            entry["suppressed_count"] = 0
            n += 1
    if n:
        try:
            ESCALATION_STATE_FILE.write_text(json.dumps(esc))
        except OSError as exc:
            logger.warning("counter reset write failed (non-fatal): %s", exc)
            return 0
    return n


def send_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — printing instead")
        print(text)
        return False
    import urllib.error
    import urllib.parse
    import urllib.request

    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=data
    )
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
                logger.warning("telegram HTTP %s", resp.status)
                return False
        except urllib.error.HTTPError as e:
            if not (500 <= e.code < 600):
                logger.warning("telegram HTTP %s (non-retryable)", e.code)
                return False
        except Exception as e:  # noqa: BLE001 — transient network
            logger.warning("telegram attempt %d failed: %s", attempt, e)
        if attempt < 3:
            time.sleep(1 if attempt == 1 else 3)
    return False


def _main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--dry-run", action="store_true", help="print, do not send")
    p.add_argument("--no-reset", action="store_true",
                   help="do not reset suppressed_count after emitting")
    args = p.parse_args(argv)

    digest = build_digest()
    if args.dry_run:
        print(digest["text"])
        print(f"\n[dry-run] total_suppressed={digest['total_suppressed']} "
              f"dedup_recent={digest['dedup_recent']} (counters NOT reset)")
        return 0

    sent = send_telegram(digest["text"])
    logger.info("digest %s (total=%d)", "sent" if sent else "not sent",
                digest["total_suppressed"])
    if sent and not args.no_reset:
        n = reset_counters()
        logger.info("reset %d suppressed counters", n)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
