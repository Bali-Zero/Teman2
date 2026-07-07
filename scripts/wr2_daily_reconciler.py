#!/usr/bin/env python3
"""WR2 daily reconciler — guarantees "one carousel per day, or a P0 that says why".

WHY (spec docs/specs/wr2-definitiva-v1.md R6): the pipeline is ONE-SHOT — the
topic-selector fires once at 05:10 WITA and picks one topic; if that draft dies
anywhere downstream (render_failed pile-up: 20 drafts, gaps 06-30/07-01/07-04)
the day is silently lost. Nothing retried, nothing alerted, nobody backfilled.

WHAT: launchd runs this 3x/day (09:00 / 13:00 / 18:00 WITA). Each tick:
  1. Look at TODAY's drafts (WITA day window) in war_room_drafts.
  2. Decide ONE action (pure function `decide()` — unit-tested):
       ok                    -> a draft reached rendered/pending_review/approved/published
       wait                  -> a draft is in-flight and fresh — let the pipeline work
       kick_stuck            -> in-flight but stale >2h — kickstart the supervisor
       requeue_render_failed -> today's draft failed with attempts left — requeue + kick renderer
       new_topic             -> nothing alive today — kickstart the topic-selector (dedup
                                skips dead topics, next-ranked gets picked)
  3. Apply it (UPDATE + launchctl kickstart), UNLESS --dry-run.
  4. Write the OUTCOME heartbeat ~/.organism/last_seen/pro.wr2_daily_carousel.json —
     this is the downstream state-delta probe (W89: never trust the producer's log).
  5. From ESCALATE_HOUR (17 WITA) on, a not-ok day fires a tg_notify P0.

Contracts: never raises out of main (exit 1 only on infra failure, with heartbeat
status=error); mutations are ownership-narrow (status-gated UPDATE); Legge 5 intact
(this schedules PRODUCTION, never publication).

Env: DATABASE_URL (required) · WR2_RECONCILER_ESCALATE_HOUR (default 17, WITA) ·
WR2_RECONCILER_STUCK_HOURS (default 2) · WR2_HTML_MAX_ATTEMPTS (default 3, same
knob as the renderer) · WR2_RECONCILER_DRY_RUN=1 == --dry-run.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("wr2.daily_reconciler")

WITA = timezone(timedelta(hours=8))
ORGAN_ID = "pro.wr2_daily_carousel"

# Draft states, from the war_room_drafts CHECK constraint (read live 2026-07-07).
TERMINAL_OK = {"rendered", "pending_review", "approved", "published"}
IN_FLIGHT = {
    "briefed", "briefed_facted", "researched", "concept", "drafts",
    "drafts_checked", "drafts_imaged", "drafts_imaged_facted",
    "drafts_imaged_checked", "rendering",
}
DEAD = {"fact_check_failed", "image_failed", "rejected", "missed", "rendered_shadow"}
# render_failed is dead-or-recoverable depending on the attempts counter.

LABEL_TOPIC_SELECTOR = "com.balizero.wr2.topic-selector"
LABEL_SUPERVISOR = "com.balizero.wr2.supervisor"
LABEL_HTML_APPLY = "com.balizero.wr2.html-apply"


@dataclass(frozen=True)
class Decision:
    action: str  # ok | wait | kick_stuck | requeue_render_failed | new_topic
    reason: str
    draft_id: str | None = None
    escalate: bool = False


def decide(
    rows: list[dict[str, Any]],
    now_wita: datetime,
    *,
    escalate_hour: int = 17,
    stuck_hours: float = 2.0,
    max_attempts: int = 3,
) -> Decision:
    """Pure decision core. `rows` = today's drafts (WITA window), each with
    id, status, attempts, updated_at (aware datetime), topic."""
    late = now_wita.hour >= escalate_hour

    for r in rows:
        if r["status"] in TERMINAL_OK:
            return Decision("ok", f"draft {r['id']} status={r['status']}", str(r["id"]))

    stuck_cutoff = now_wita.astimezone(timezone.utc) - timedelta(hours=stuck_hours)
    inflight = [r for r in rows if r["status"] in IN_FLIGHT]
    if inflight:
        # freshest in-flight draft decides wait-vs-kick
        freshest = max(inflight, key=lambda r: r["updated_at"])
        if freshest["updated_at"].astimezone(timezone.utc) >= stuck_cutoff:
            return Decision(
                "wait", f"draft {freshest['id']} in-flight ({freshest['status']}), fresh",
                str(freshest["id"]), escalate=late,
            )
        return Decision(
            "kick_stuck",
            f"draft {freshest['id']} stuck in {freshest['status']} "
            f">{stuck_hours}h (updated {freshest['updated_at'].isoformat()})",
            str(freshest["id"]), escalate=late,
        )

    recoverable = [
        r for r in rows
        if r["status"] == "render_failed" and int(r.get("attempts") or 0) < max_attempts
    ]
    if recoverable:
        r = recoverable[0]
        return Decision(
            "requeue_render_failed",
            f"draft {r['id']} render_failed attempts={r.get('attempts')}<{max_attempts}",
            str(r["id"]), escalate=late,
        )

    return Decision(
        "new_topic",
        f"no live draft today ({len(rows)} dead/absent) — pick next topic",
        None, escalate=late,
    )


def _kickstart(label: str, *, restart: bool = False) -> bool:
    """launchctl kickstart; never raises. Returns True on rc==0."""
    try:
        cmd = ["launchctl", "kickstart"]
        if restart:
            cmd.append("-k")
        cmd.append(f"gui/{os.getuid()}/{label}")
        res = subprocess.run(cmd, capture_output=True, timeout=30)
        ok = res.returncode == 0
        (logger.info if ok else logger.warning)(
            "kickstart %s rc=%s %s", label, res.returncode,
            (res.stderr or b"").decode(errors="replace").strip()[:200],
        )
        return ok
    except Exception as exc:  # noqa: BLE001
        logger.warning("kickstart %s failed: %s", label, exc)
        return False


def _tg_notify(tier: str, dedup_key: str, text: str) -> bool:
    """Route through the tg_notify gateway; never raises."""
    try:
        script = _REPO / "scripts" / "tg_notify.py"
        if not script.is_file():
            logger.warning("tg_notify.py missing at %s", script)
            return False
        res = subprocess.run(
            [sys.executable, str(script), "--tier", tier,
             "--source", "wr2-daily-reconciler", "--dedup-key", dedup_key, text],
            capture_output=True, timeout=30,
        )
        return res.returncode == 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("tg_notify failed: %s", exc)
        return False


def _heartbeat(status: str, note: str) -> None:
    try:
        from scripts.lib.heartbeat import organism_heartbeat

        organism_heartbeat(ORGAN_ID, status, note=note)
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat write failed: %s", exc)


async def _fetch_today(conn: Any, day_start_utc: datetime) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT id, status, COALESCE(html_render_attempts, 0) AS attempts,
               updated_at, topic, drive_url
          FROM war_room_drafts
         WHERE created_at >= $1
         ORDER BY created_at DESC
        """,
        day_start_utc,
    )
    return [dict(r) for r in rows]


def _verify_visibility_or_backfill(row: dict[str, Any], *, dry_run: bool) -> str:
    """Codex red-team #1/#15: DB status='rendered' is a PROXY — the outcome is
    "the human can see it": a review-queue entry + (ideally) durable PNGs.
    Verify by content; when the queue entry is missing (e.g. the visibility
    chain failed after persist), BACKFILL it from the DB row + whatever durable
    artifacts exist. Returns verified|backfilled|backfill_failed|dry_run."""
    try:
        import wr2_html_render_apply as viz  # same scripts/ dir, same venv

        qp = viz._default_output_root() / "queue" / "human-review-queue.json"
        draft_id = str(row["id"])
        if qp.exists():
            import json as _json

            try:
                queue = _json.loads(qp.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — corrupt queue: alert, don't guess
                _tg_notify("p0", "wr2-queue-corrupt",
                           f"🛑 WR2 review queue is corrupt JSON: {qp}")
                return "backfill_failed"
            if isinstance(queue, list) and any(
                isinstance(i, dict) and i.get("draft_id") == draft_id for i in queue
            ):
                return "verified"
        if dry_run:
            return "dry_run"
        # backfill: durable dir may or may not exist — reference what does
        candidates = sorted(
            (viz._default_output_root() / "carousel").glob(f"*-{draft_id[:8]}")
        )
        car_dir = candidates[-1] if candidates else (
            viz._default_output_root() / "carousel" / f"missing-{draft_id[:8]}"
        )
        slide_count = len(list((car_dir / "slides").glob("*.png"))) if car_dir.exists() else 0
        from datetime import datetime as _dt, timezone as _tz

        entry = viz._make_queue_entry(
            draft_id=draft_id, topic=str(row.get("topic") or ""),
            carousel_dir=car_dir, drive_url=str(row.get("drive_url") or ""),
            slide_count=slide_count, weak_count=0, fact_check_status=None,
            drafted_at=_dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        if slide_count == 0:
            # honest entry: no local slides — review happens on Drive
            entry["slides_dir"] = None
            entry["critic_summary"] = "backfilled by reconciler — local PNGs missing, review on Drive"
        viz._append_review_queue(entry)
        logger.info("visibility backfilled for draft %s (slides=%d)", draft_id, slide_count)
        return "backfilled"
    except Exception as exc:  # noqa: BLE001
        logger.warning("visibility verify/backfill failed: %s", exc, exc_info=exc)
        return "backfill_failed"


async def _apply(decision: Decision, conn: Any, *, dry_run: bool) -> None:
    if dry_run:
        logger.info("DRY-RUN: would apply %s (%s)", decision.action, decision.reason)
        return
    if decision.action == "requeue_render_failed" and decision.draft_id:
        res = await conn.execute(
            """
            UPDATE war_room_drafts
               SET status='drafts_imaged_checked', lease_owner=NULL,
                   lease_acquired_at=NULL, lease_heartbeat_at=NULL, updated_at=NOW()
             WHERE id=$1::uuid AND status='render_failed'
            """,
            decision.draft_id,
        )
        logger.info("requeue %s -> %s", decision.draft_id, res)
        _kickstart(LABEL_HTML_APPLY)
    elif decision.action == "new_topic":
        _kickstart(LABEL_TOPIC_SELECTOR)
        _kickstart(LABEL_SUPERVISOR, restart=False)
    elif decision.action == "kick_stuck":
        _kickstart(LABEL_SUPERVISOR, restart=False)
        _kickstart(LABEL_HTML_APPLY)
    # ok / wait: nothing to do


async def run(*, dry_run: bool) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        _heartbeat("error", "DATABASE_URL not set")
        return 1

    import asyncpg

    now_wita = datetime.now(WITA)
    day_start_wita = now_wita.replace(hour=0, minute=0, second=0, microsecond=0)
    day_start_utc = day_start_wita.astimezone(timezone.utc)

    escalate_hour = int(os.environ.get("WR2_RECONCILER_ESCALATE_HOUR", "17"))
    stuck_hours = float(os.environ.get("WR2_RECONCILER_STUCK_HOURS", "2"))
    max_attempts = int(os.environ.get("WR2_HTML_MAX_ATTEMPTS", "3"))

    try:
        conn = await asyncpg.connect(dsn, timeout=15)
    except Exception as exc:  # noqa: BLE001
        # Codex red-team #14/#20: an unreachable DB must NOT die silently — this
        # is exactly the "day ends with no carousel AND no P0" hole.
        logger.error("DB connect failed: %s", exc)
        _heartbeat("error", f"db connect failed: {exc}")
        _tg_notify(
            "p0", "wr2-reconciler-db-down",
            f"🛑 WR2 reconciler: DB unreachable ({type(exc).__name__}) — "
            f"nessuna garanzia sul carosello di oggi finché il pg-proxy non torna.",
        )
        return 1

    try:
        rows = await _fetch_today(conn, day_start_utc)
        decision = decide(
            rows, now_wita,
            escalate_hour=escalate_hour, stuck_hours=stuck_hours,
            max_attempts=max_attempts,
        )
        logger.info(
            "day=%s drafts_today=%d -> %s (%s)%s",
            now_wita.date(), len(rows), decision.action, decision.reason,
            " [ESCALATE]" if decision.escalate else "",
        )
        await _apply(decision, conn, dry_run=dry_run)

        if decision.action == "ok":
            ok_row = next(r for r in rows if r["status"] in TERMINAL_OK)
            vis = _verify_visibility_or_backfill(ok_row, dry_run=dry_run)
            if dry_run:
                logger.info("DRY-RUN: visibility=%s", vis)
                return 0
            if vis == "backfill_failed":
                _heartbeat("degraded", f"{decision.reason}; visibility={vis}")
                _tg_notify(
                    "p0", f"wr2-visibility-gap-{now_wita.date()}",
                    f"⚠️ WR2: carosello RENDERIZZATO oggi ma NON visibile in coda/app "
                    f"e il backfill è fallito (draft {decision.draft_id}). "
                    f"Il PNG vive su Drive; serve sguardo umano.",
                )
            else:
                _heartbeat("ok", f"{decision.reason}; visibility={vis}")
            return 0

        if dry_run:
            return 0

        if decision.escalate:
            _heartbeat("failed", f"{decision.action}: {decision.reason}")
            delivered = _tg_notify(
                "p0", f"wr2-no-carousel-{now_wita.date()}",
                f"🛑 WR2: NESSUN carosello oggi ({now_wita.date()}).\n"
                f"Stato: {decision.action} — {decision.reason}\n"
                f"Azione correttiva già tentata dal reconciler; serve sguardo umano "
                f"se domattina è ancora rosso.",
            )
            if not delivered:
                # gateway refused/absent — the heartbeat is the durable receptor
                _heartbeat("failed", f"{decision.action}: {decision.reason} (P0 NOT delivered)")
        else:
            _heartbeat("pending", f"{decision.action}: {decision.reason}")
        return 0
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="decide + log only; no DB writes, no kickstarts, no heartbeat")
    args = parser.parse_args()
    dry = args.dry_run or os.environ.get("WR2_RECONCILER_DRY_RUN") == "1"
    return asyncio.run(run(dry_run=dry))


if __name__ == "__main__":
    raise SystemExit(main())
