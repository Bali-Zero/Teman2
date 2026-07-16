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
                                (heartbeat stays running; not a dead-organ condition)
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
                str(freshest["id"]),
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
               updated_at, topic, drive_url, slides_json
          FROM war_room_drafts
         WHERE created_at >= $1
         ORDER BY created_at DESC
        """,
        day_start_utc,
    )
    return [dict(r) for r in rows]


def _row_intended_slide_count(row: dict[str, Any]) -> int | None:
    """DB-sourced ground truth: how many slides this draft's OWN input
    (war_room_drafts.slides_json) declares — independent of anything derived
    from disk. Returns None when unparseable (caller must not assume 0)."""
    import json as _json

    sj = row.get("slides_json")
    if sj is None:
        return None
    if isinstance(sj, str):
        try:
            sj = _json.loads(sj)
        except Exception:  # noqa: BLE001
            return None
    slides = sj.get("slides", sj) if isinstance(sj, dict) else sj
    return len(slides) if isinstance(slides, list) else None


def _verify_visibility_or_backfill(row: dict[str, Any], *, dry_run: bool) -> str:
    """Codex red-team #1/#15: DB status='rendered' is a PROXY — the outcome is
    "the human can see it": a review-queue entry + (ideally) durable PNGs.
    Verify by content; when the queue entry is missing (e.g. the visibility
    chain failed after persist), BACKFILL it from the DB row + whatever durable
    artifacts exist.

    Codex red-team HIGH #2 (2026-07-16): the append-if-missing path used to
    trust `slide_count` from a bare disk glob and append a normal reviewable
    "drafted" entry even when that count was 0 (a DB row already status=
    'rendered' but `_publish_visibility` failed AFTER wiping/never-populating
    slides_dir) — a real, reproduced scenario. Resolve the DRAFT'S OWN intent
    (war_room_drafts.slides_json) first: append as "drafted" only when disk
    matches that intent AND is > 0; otherwise mark render_incomplete instead
    of a lying "drafted".

    Returns verified|backfilled|backfilled_incomplete|backfill_failed|dry_run.
    """
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
        # A1: same derive_slide_count helper every writer routes through —
        # not a bare *.png glob, which would count staged chrome (logo.png)
        # as a "slide".
        slide_count = viz.derive_slide_count(car_dir / "slides") if car_dir.exists() else 0
        intended = _row_intended_slide_count(row)
        from datetime import datetime as _dt, timezone as _tz

        entry = viz._make_queue_entry(
            draft_id=draft_id, topic=str(row.get("topic") or ""),
            carousel_dir=car_dir, drive_url=str(row.get("drive_url") or ""),
            slide_count=slide_count, intended_slide_count=intended or 0,
            weak_count=0, fact_check_status=None,
            drafted_at=_dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        complete = intended is not None and intended > 0 and slide_count == intended
        if slide_count == 0:
            # honest entry: no local slides — review happens on Drive
            entry["slides_dir"] = None
            entry["critic_summary"] = "backfilled by reconciler — local PNGs missing, review on Drive"
        if not complete:
            # HIGH #2 fix: never append a normal "drafted" for a mismatch —
            # a human sees render_incomplete, not a reviewable-looking entry
            # that is secretly missing slides.
            now_iso = _dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            entry["state"] = RENDER_INCOMPLETE_STATE
            entry["state_history"] = [{
                "state": RENDER_INCOMPLETE_STATE, "at": now_iso,
                "by": "wr2-daily-reconciler",
                "reason": (
                    f"backfill: disk={slide_count} intended={intended!r} "
                    f"— not verifiably complete"
                ),
            }]
        viz._append_review_queue(entry)
        if complete:
            logger.info("visibility backfilled for draft %s (slides=%d)", draft_id, slide_count)
            return "backfilled"
        logger.warning(
            "visibility backfilled INCOMPLETE for draft %s (disk=%d intended=%r) "
            "— enqueued as render_incomplete", draft_id, slide_count, intended,
        )
        _tg_notify(
            "p1", f"wr2-visibility-incomplete-{draft_id}",
            f"⚠️ WR2: carosello draft {draft_id} rientrato in coda come "
            f"render_incomplete dal backfill (disco={slide_count}, "
            f"intento={intended!r}) — serve sguardo umano prima di pubblicare.",
        )
        return "backfilled_incomplete"
    except Exception as exc:  # noqa: BLE001
        logger.warning("visibility verify/backfill failed: %s", exc, exc_info=exc)
        return "backfill_failed"


# ── A3: queue completeness sweep + backfill (2026-07-16) ────────────────────
# "Nothing anywhere re-verifies slide_count vs reality" (design ground fact,
# live-measured: 13-16 mismatched entries, always the LAST slide missing on
# disk vs meta.json/queue's own recorded count — a post-render disk-level
# drift the render-time A1 gate cannot see, because it happens AFTER a
# carousel already reached 'drafted' honestly). This sweep is the durable
# receptor: it re-verifies every non-terminal queue entry against disk on
# every tick (report-only) and offers a dedicated one-shot backfill mode
# (mutating, --apply) for the classified 3-way fix.

# Anything not yet published is fair game for drift — broader than
# wr2_html_render_apply._REPOINTABLE_STATES (which is scoped to the REPOINT
# decision) because a completeness check must also catch e.g.
# 'applied_ready_for_damar'/'approved' entries sitting between review and
# Damar's manual IG publish.
TERMINAL_QUEUE_STATES = {"published", "published_with_edits", "archived"}

# New queue-level state (2026-07-16): an entry whose declared slide_count no
# longer matches verified disk reality and could NOT be safely explained as
# stale metadata (see _classify_completeness). Distinct from the DB-level
# 'render_failed' status (war_room_drafts) — this is a QUEUE-entry state, and
# every queue-server action (_damar-queue-server.py mark-published/rejected/
# flag) already refuses any state outside its own allow-list, so an entry in
# this state is inert to every existing consumer by construction — no new
# guard needed downstream.
RENDER_INCOMPLETE_STATE = "render_incomplete"


@dataclass(frozen=True)
class CompletenessMismatch:
    entry_id: str
    draft_id: str | None
    state: str
    declared: int
    disk: int
    expected: int | None
    expected_source: str  # "intended_slide_count" | "slides.json" | "none"
    classification: str  # "queue_stale" | "genuinely_incomplete" | "unknown_intent" | "dirless"


def _resolve_expected_count(
    car_dir: Path, entry: dict[str, Any] | None = None,
) -> tuple[int | None, str]:
    """Ground-truth intended slide count, best signal first.

    Codex red-team HIGH #4 (2026-07-16): meta.json's plain `slide_count`
    field is NOT independent ground truth — `_persist_local_artifacts`
    computes it from the SAME disk scan this sweep re-checks, so it can
    NEVER disagree with disk by construction. Trusting it as "expected" used
    to let a genuine post-render loss be misclassified as `queue_stale` (a
    lived scenario: intent/queue=9, disk=8, meta.slide_count=8 — the backfill
    "fixed" the queue down to 8 and called the carousel complete).

    Priority:
      1. entry["intended_slide_count"] — DB-sourced (war_room_drafts.
         slides_json), persisted once at render time, independent of disk.
      2. car_dir/meta.json["intended_slide_count"] — same DB-sourced value,
         redundant persistence (covers entries whose queue record predates
         this field but whose artifact dir was re-persisted since this fix).
      3. car_dir/slides.json — an actual render-input spec file, when one
         exists beside the artifact (manual-import / rerender_local path).
      4. Nothing — meta.json's bare disk-echoing `slide_count` is
         deliberately NOT used as a fallback anymore.
    Returns (None, "none") when nothing independent is available — callers
    must classify that as `unknown_intent`, never assume completeness."""
    import json as _json

    if entry is not None:
        v = entry.get("intended_slide_count")
        if isinstance(v, int) and v > 0:
            return v, "intended_slide_count"

    mj = car_dir / "meta.json"
    if mj.is_file():
        try:
            meta = _json.loads(mj.read_text(encoding="utf-8"))
            v = meta.get("intended_slide_count")
            if isinstance(v, int) and v > 0:
                return v, "intended_slide_count"
        except Exception:  # noqa: BLE001
            logger.warning("unreadable meta.json at %s", mj, exc_info=True)

    sj = car_dir / "slides.json"
    if sj.is_file():
        try:
            data = _json.loads(sj.read_text(encoding="utf-8"))
            slides = data.get("slides", data) if isinstance(data, dict) else data
            if isinstance(slides, list):
                return len(slides), "slides.json"
        except Exception:  # noqa: BLE001 — unreadable slides.json, fall through
            logger.warning("unreadable slides.json at %s", sj, exc_info=True)

    return None, "none"


def _resolve_slides_dir(entry: dict[str, Any], carousel_root: Path) -> Path | None:
    """Resolve an entry's slides directory across schema/path drift
    (2026-07-17 fix — live case: `indonesia-visafree-myth-reality`, 8 real
    PNGs on disk, mis-marked dirless/render_incomplete).

    OLD-style queue entries (pre-`slides_dir` field, still live in the
    queue) carry only `carousel_path` (often `~`-prefixed) and NO
    `slides_dir` key at all. Trusting a missing `slides_dir` as "no dir" —
    the pre-fix behavior — misclassified a real, fully-rendered carousel as
    dirless.

    Resolution order — only when ALL three fail is the entry genuinely
    dirless:
      1. entry["slides_dir"], expanduser()'d, if it is a real directory.
      2. entry["carousel_path"], expanduser()'d — either already IS the
         slides dir, or is the carousel dir one level up (try + "slides").
      3. Suffix-match under `carousel_root` by the entry's own dir basename
         (from carousel_path) or topic_slug — mirrors the app's own
         `*-{draft_id[:8]}`-style matching convention (see
         `_verify_visibility_or_backfill`) for entries whose recorded path
         has since drifted (re-persisted/renamed carousel dir).
    """
    sd = entry.get("slides_dir")
    if sd:
        p = Path(sd).expanduser()
        if p.is_dir():
            return p

    cp = entry.get("carousel_path")
    cp_path: Path | None = None
    if cp:
        cp_path = Path(cp).expanduser()
        if cp_path.name == "slides" and cp_path.is_dir():
            return cp_path
        candidate = cp_path / "slides"
        if candidate.is_dir():
            return candidate

    needles = [n for n in (cp_path.name if cp_path is not None else None,
                           entry.get("topic_slug")) if n]
    if needles and carousel_root.is_dir():
        for needle in needles:
            for m in sorted(carousel_root.glob(f"*{needle}*")):
                candidate = m / "slides"
                if candidate.is_dir():
                    return candidate
    return None


def _classify_completeness(*, disk: int, expected: int | None) -> str:
    """4-way classification (design spec A3; extended HIGH #3/#4, 2026-07-16):

    (i)    queue_stale         — disk matches the independently-resolved
                                  expected count; only the queue's own
                                  slide_count field disagrees. The carousel
                                  IS complete — fix the number in place.
    (ii)   genuinely_incomplete — expected is known and != disk: a real slide
                                  is missing (or extra) vs a TRUSTED source.
                                  Never silently renumber to "fix" this.
    (iii)  unknown_intent      — no independent source exists at all (HIGH
                                  #4): we cannot safely tell whether disk or
                                  the queue's declared count is the wrong
                                  one. Report only, NEVER mutate/renumber —
                                  blindly assuming "disk must be right" here
                                  is exactly the bug this classification
                                  exists to stop.
    Caller handles the separate "dirless" case (no slides_dir) itself."""
    if expected is None:
        return "unknown_intent"
    return "queue_stale" if expected == disk else "genuinely_incomplete"


def check_completeness(
    queue_path: Path | None = None,
) -> list[CompletenessMismatch]:
    """Read-only sweep: every non-terminal queue entry, disk-verified.

    Never mutates. Pure reporting — the dedicated backfill mode (`--backfill-
    completeness [--apply]`) applies the fix; the regular 3x/day tick calls
    this in report-only mode so a drift is VISIBLE the same day it's found,
    without racing an in-flight render/repoint with an automatic mutation.
    """
    import json as _json

    import wr2_html_render_apply as viz  # same scripts/ dir, same venv

    qp = queue_path or (viz._default_output_root() / "queue" / "human-review-queue.json")
    if not qp.exists():
        return []
    try:
        queue = _json.loads(qp.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — corrupt queue is _queue_hygiene_sweep's/
        # the append-writers' problem to surface; this sweep just skips it.
        logger.warning("completeness sweep: queue unreadable at %s", qp, exc_info=True)
        return []
    if not isinstance(queue, list):
        return []

    carousel_root = viz._default_output_root() / "carousel"
    mismatches: list[CompletenessMismatch] = []
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        state = entry.get("state")
        if state in TERMINAL_QUEUE_STATES:
            continue
        declared = entry.get("slide_count")
        if not isinstance(declared, int):
            continue
        entry_id = str(entry.get("id") or entry.get("item_id") or "?")
        slides_dir = _resolve_slides_dir(entry, carousel_root)
        if slides_dir is None:
            mismatches.append(CompletenessMismatch(
                entry_id=entry_id, draft_id=entry.get("draft_id"), state=state,
                declared=declared, disk=0, expected=None, expected_source="none",
                classification="dirless",
            ))
            continue
        disk = viz.derive_slide_count(slides_dir)
        car_dir = slides_dir.parent
        # HIGH #3 (2026-07-16): resolve expected BEFORE any disk==declared
        # shortcut — a queue whose declared count happens to match disk can
        # still be WRONG against a trusted independent source (e.g.
        # slides.json says 9, queue==disk==8 — both agree with each other and
        # BOTH are wrong; the old `if disk == declared: continue` never even
        # looked at slides.json in that case, so this class of loss was
        # invisible to the sweep entirely).
        expected, expected_source = _resolve_expected_count(car_dir, entry)
        disagreement = declared != disk or (expected is not None and expected != disk)
        if not disagreement:
            continue  # honest end-to-end: queue, disk, and any known intent all agree
        classification = _classify_completeness(disk=disk, expected=expected)
        mismatches.append(CompletenessMismatch(
            entry_id=entry_id, draft_id=entry.get("draft_id"), state=state,
            declared=declared, disk=disk, expected=expected,
            expected_source=expected_source, classification=classification,
        ))
    return mismatches


def apply_completeness_backfill(
    queue_path: Path | None = None,
    *,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Apply the 3-way backfill classification under the queue's fcntl lock
    (same lock file + tmp+rename protocol as wr2_html_render_apply.
    _append_review_queue / wr2_queue_hygiene.sweep_queue — never a second,
    unsynchronized writer). Returns one report dict per mismatch, in dry-run
    or applied form. Re-reads + re-checks under the lock so a concurrent
    render/repoint between the report-only check and this call cannot be
    clobbered by a stale decision."""
    import fcntl
    import json as _json

    import wr2_html_render_apply as viz  # same scripts/ dir, same venv

    qp = queue_path or (viz._default_output_root() / "queue" / "human-review-queue.json")
    if not qp.exists():
        return []
    carousel_root = viz._default_output_root() / "carousel"
    lock_path = qp.with_suffix(".lock")
    reports: list[dict[str, Any]] = []
    with open(lock_path, "w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            try:
                queue = _json.loads(qp.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — corrupt queue: never guess, never write
                logger.warning("backfill: queue unreadable at %s", qp, exc_info=True)
                return []
            if not isinstance(queue, list):
                return []

            changed = False
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for entry in queue:
                if not isinstance(entry, dict):
                    continue
                state = entry.get("state")
                if state in TERMINAL_QUEUE_STATES:
                    continue
                declared = entry.get("slide_count")
                if not isinstance(declared, int):
                    continue
                entry_id = str(entry.get("id") or entry.get("item_id") or "?")
                slides_dir = _resolve_slides_dir(entry, carousel_root)
                if slides_dir is None:
                    report = {
                        "entry_id": entry_id, "classification": "dirless",
                        "declared": declared, "disk": 0, "action": "mark_render_incomplete",
                    }
                    if not dry_run and state != RENDER_INCOMPLETE_STATE:
                        entry["state"] = RENDER_INCOMPLETE_STATE
                        entry.setdefault("state_history", []).append({
                            "state": RENDER_INCOMPLETE_STATE, "at": now_iso,
                            "by": "wr2-daily-reconciler-backfill",
                            "reason": "dirless: slides_dir/carousel_path/suffix-match all missing",
                        })
                        changed = True
                    reports.append(report)
                    continue
                disk = viz.derive_slide_count(slides_dir)
                car_dir = slides_dir.parent
                # HIGH #3: resolve expected BEFORE any disk==declared
                # shortcut — see the matching comment in check_completeness.
                expected, expected_source = _resolve_expected_count(car_dir, entry)
                disagreement = declared != disk or (expected is not None and expected != disk)
                if not disagreement:
                    continue
                classification = _classify_completeness(disk=disk, expected=expected)
                if classification == "queue_stale":
                    report = {
                        "entry_id": entry_id, "classification": classification,
                        "declared": declared, "disk": disk, "expected": expected,
                        "expected_source": expected_source,
                        "action": f"fix slide_count {declared} -> {disk}",
                    }
                    if not dry_run:
                        entry["slide_count"] = disk
                        entry.setdefault("state_history", []).append({
                            "state": state, "at": now_iso,
                            "by": "wr2-daily-reconciler-backfill",
                            "reason": f"slide_count corrected {declared} -> {disk} "
                                      f"(disk matches {expected_source} at {expected})",
                        })
                        changed = True
                    reports.append(report)
                elif classification == "genuinely_incomplete":
                    report = {
                        "entry_id": entry_id, "classification": classification,
                        "declared": declared, "disk": disk, "expected": expected,
                        "expected_source": expected_source,
                        "action": "mark_render_incomplete",
                    }
                    if not dry_run and state != RENDER_INCOMPLETE_STATE:
                        entry["slide_count"] = disk  # never lie about physical reality
                        entry["state"] = RENDER_INCOMPLETE_STATE
                        entry.setdefault("state_history", []).append({
                            "state": RENDER_INCOMPLETE_STATE, "at": now_iso,
                            "by": "wr2-daily-reconciler-backfill",
                            "reason": (
                                f"genuinely incomplete: expected {expected} "
                                f"({expected_source}) but disk has {disk}"
                            ),
                        })
                        changed = True
                    reports.append(report)
                else:  # unknown_intent (HIGH #4): NEVER mutate — no independent
                    # source exists to tell whether disk or the queue's own
                    # declared count is the wrong one. Report only, so a human
                    # can look, instead of guessing "disk must be right".
                    reports.append({
                        "entry_id": entry_id, "classification": classification,
                        "declared": declared, "disk": disk, "expected": expected,
                        "expected_source": expected_source,
                        "action": "report_only (no independent ground truth — refusing to guess)",
                    })

            if not dry_run and changed:
                tmp = qp.with_suffix(f".tmp.{os.getpid()}")
                tmp.write_text(_json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, qp)
                logger.info("completeness backfill applied: %d entries mutated", len(reports))
            return reports
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def _completeness_report(*, dry_run: bool) -> None:
    """Report-only completeness sweep, called every regular tick (A3). Never
    mutates the queue — the fix lives in `--backfill-completeness [--apply]`,
    run as a dedicated one-shot so a mid-render/repoint entry can never be
    clobbered by an automatic mutation racing the pipeline's own writer.
    Best-effort: a sweep failure must never affect the day's decision."""
    try:
        mismatches = check_completeness()
        if not mismatches:
            return
        logger.warning(
            "completeness sweep: %d non-terminal queue entr(y/ies) mismatched: %s",
            len(mismatches),
            [(m.entry_id, m.classification, f"declared={m.declared} disk={m.disk}") for m in mismatches[:10]],
        )
        if dry_run:
            return
        _tg_notify(
            "digest", f"wr2-completeness-{datetime.now(WITA).date()}",
            f"🧩 WR2 completeness sweep: {len(mismatches)} entry con slide_count "
            f"disallineato dal disco (drift post-render, non un render partial "
            f"nuovo). Esegui `wr2_daily_reconciler.py --backfill-completeness "
            f"--apply` per correggerli (classificazione: queue_stale / "
            f"genuinely_incomplete / unknown_intent / dirless — unknown_intent "
            f"non viene mai auto-corretto).",
        )
    except Exception as exc:  # noqa: BLE001 — never break the reconciler tick
        logger.warning("completeness sweep failed: %s", exc, exc_info=exc)


def _queue_hygiene_sweep(*, dry_run: bool) -> None:
    """W96 immune organ: quarantine malformed review-queue entries every tick.

    Junk contract lives in wr2_queue_hygiene.is_junk_entry (drafted + blank
    topic + never published). Best-effort — a hygiene failure must never
    affect the day's decision; a non-empty sweep is alerted (fail-visible)."""
    try:
        import wr2_queue_hygiene as hyg  # same scripts/ dir, same venv

        report = hyg.sweep_queue(dry_run=dry_run)
        if report.moved:
            logger.info(
                "queue hygiene: %s %d junk entries: %s",
                "would quarantine" if dry_run else "quarantined",
                len(report.moved), report.moved[:5],
            )
            if not dry_run:
                _tg_notify(
                    "p2", f"wr2-queue-hygiene-{datetime.now(WITA).date()}",
                    f"🧹 WR2 queue hygiene: {len(report.moved)} entry malformate "
                    f"(drafted, topic vuoto) spostate in quarantena.",
                )
    except Exception as exc:  # noqa: BLE001 — never break the reconciler tick
        logger.warning("queue hygiene sweep failed: %s", exc, exc_info=exc)


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
        try:
            return await _tick(
                conn, now_wita, day_start_utc, dry_run=dry_run,
                escalate_hour=escalate_hour, stuck_hours=stuck_hours,
                max_attempts=max_attempts,
            )
        except Exception as exc:  # noqa: BLE001 — never-raises contract (red-team MED)
            logger.error("reconciler tick crashed: %s", exc, exc_info=exc)
            _heartbeat("error", f"tick crashed: {type(exc).__name__}: {exc}")
            _tg_notify(
                "p0", "wr2-reconciler-crash",
                f"🛑 WR2 reconciler CRASHED mid-tick: {type(exc).__name__}: {exc} — "
                f"nessuna garanzia sul carosello di oggi.",
            )
            return 1
    finally:
        await conn.close()


async def _tick(
    conn: Any,
    now_wita: datetime,
    day_start_utc: datetime,
    *,
    dry_run: bool,
    escalate_hour: int,
    stuck_hours: float,
    max_attempts: int,
) -> int:
    _queue_hygiene_sweep(dry_run=dry_run)
    _completeness_report(dry_run=dry_run)
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
        elif vis == "backfilled_incomplete":
            # HIGH #2: the entry landed as render_incomplete, not a lying
            # "drafted" — degraded (not "failed", the P1 alert already fired
            # inside _verify_visibility_or_backfill; not "ok", a human still
            # needs to look before this carousel can be reviewed/published).
            _heartbeat("degraded", f"{decision.reason}; visibility={vis}")
        else:
            _heartbeat("ok", f"{decision.reason}; visibility={vis}")
        return 0

    if dry_run:
        return 0

    if decision.action == "wait":
        _heartbeat("running", f"{decision.action}: {decision.reason}")
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


def repair_false_incomplete(
    queue_path: Path | None = None,
    *,
    dry_run: bool = True,
    exclude_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """One-shot repair (2026-07-17): the pre-fix dirless bug (missing/stale
    `slides_dir` misread as "no dir" for old-schema `carousel_path`-only
    entries — see `_resolve_slides_dir`) marked genuinely-complete carousels
    render_incomplete. This scans every CURRENT `render_incomplete` entry and,
    using the FIXED resolution, restores it to `drafted` when the resolved
    slides dir actually has >=1 real slide PNG on disk.

    Report-only by default; `--apply` mutates under the queue's fcntl lock +
    tmp+rename protocol (same as `apply_completeness_backfill`) so a
    concurrent render/repoint cannot be clobbered by a stale decision.
    `exclude_ids` (operator override, e.g. `--exclude-id` repeatable on the
    CLI) hard-excludes specific entry ids — for a genuinely-bad carousel that
    happens to also be in render_incomplete. Never touches any other state
    (published/terminal or otherwise) — this repair is scoped exclusively to
    undoing the false positives this specific bug produced."""
    import fcntl
    import json as _json

    import wr2_html_render_apply as viz  # same scripts/ dir, same venv

    qp = queue_path or (viz._default_output_root() / "queue" / "human-review-queue.json")
    if not qp.exists():
        return []
    excludes = exclude_ids or set()
    carousel_root = viz._default_output_root() / "carousel"
    lock_path = qp.with_suffix(".lock")
    reports: list[dict[str, Any]] = []
    with open(lock_path, "w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            try:
                queue = _json.loads(qp.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — corrupt queue: never guess, never write
                logger.warning("repair-false-incomplete: queue unreadable at %s", qp, exc_info=True)
                return []
            if not isinstance(queue, list):
                return []

            changed = False
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for entry in queue:
                if not isinstance(entry, dict):
                    continue
                if entry.get("state") != RENDER_INCOMPLETE_STATE:
                    continue  # scoped strictly to this state — never touches anything else
                entry_id = str(entry.get("id") or entry.get("item_id") or "?")
                if entry_id in excludes:
                    continue
                slides_dir = _resolve_slides_dir(entry, carousel_root)
                if slides_dir is None:
                    continue  # genuinely dirless even under the fixed resolution — leave it
                disk = viz.derive_slide_count(slides_dir)
                if disk < 1:
                    continue  # resolved a dir, but it's empty — not a false positive
                report = {
                    "entry_id": entry_id, "resolved_slides_dir": str(slides_dir),
                    "disk": disk, "action": "restore_to_drafted",
                }
                if not dry_run:
                    entry["state"] = "drafted"
                    entry["slide_count"] = disk
                    entry["slides_dir"] = str(slides_dir)
                    entry.setdefault("state_history", []).append({
                        "state": "drafted", "at": now_iso,
                        "by": "wr2-daily-reconciler-repair-false-incomplete",
                        "reason": (
                            f"restored: fixed slides_dir resolution finds {disk} "
                            f"real PNG(s) on disk — pre-fix dirless bug had missed "
                            f"the carousel_path-only/suffix-match resolution"
                        ),
                    })
                    changed = True
                reports.append(report)

            if not dry_run and changed:
                tmp = qp.with_suffix(f".tmp.{os.getpid()}")
                tmp.write_text(_json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, qp)
                logger.info("repair-false-incomplete applied: %d entries restored", len(reports))
            return reports
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def _cmd_repair_false_incomplete(apply: bool, exclude_ids: list[str]) -> int:
    """One-shot CLI mode: restore render_incomplete entries wrongly marked
    dirless by the pre-fix bug back to drafted, when the FIXED resolution
    finds real PNGs. Report-only by default; --apply mutates."""
    import json as _json

    reports = repair_false_incomplete(dry_run=not apply, exclude_ids=set(exclude_ids))
    print(_json.dumps({"apply": apply, "count": len(reports), "reports": reports}, indent=2))
    return 0


def _cmd_backfill_completeness(apply: bool) -> int:
    """One-shot mode (A3): apply the 3-way completeness classification to
    every non-terminal queue entry. Default dry-run (report only); --apply
    mutates under the queue's fcntl lock. Intended to be run once on Pro
    (queue source of truth) right after this fix merges, to clear the
    pre-existing mismatch backlog — the regular tick's `_completeness_report`
    keeps reporting new drift afterward, but never auto-applies."""
    import json as _json

    reports = apply_completeness_backfill(dry_run=not apply)
    print(_json.dumps({"apply": apply, "count": len(reports), "reports": reports}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="decide + log only; no DB writes, no kickstarts, no heartbeat")
    parser.add_argument(
        "--backfill-completeness", action="store_true",
        help="one-shot: classify+report queue/disk slide_count mismatches (A3); "
             "no DB, no decide()/kickstart. Combine with --apply to mutate.",
    )
    parser.add_argument(
        "--repair-false-incomplete", action="store_true",
        help="one-shot: restore render_incomplete entries wrongly marked dirless "
             "by the pre-2026-07-17 slides_dir resolution bug (old-schema "
             "carousel_path-only entries) back to drafted, when the FIXED "
             "resolution finds real PNGs on disk. Report-only by default; "
             "combine with --apply to mutate. Combine with --exclude-id to "
             "hard-exclude specific entries.",
    )
    parser.add_argument(
        "--exclude-id", action="append", default=[], metavar="ENTRY_ID",
        help="with --repair-false-incomplete: hard-exclude this entry id from "
             "restoration (repeatable)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="with --backfill-completeness or --repair-false-incomplete: "
             "actually mutate the queue (default: report only)",
    )
    args = parser.parse_args()
    if args.repair_false_incomplete:
        return _cmd_repair_false_incomplete(apply=args.apply, exclude_ids=args.exclude_id)
    if args.backfill_completeness:
        return _cmd_backfill_completeness(apply=args.apply)
    dry = args.dry_run or os.environ.get("WR2_RECONCILER_DRY_RUN") == "1"
    return asyncio.run(run(dry_run=dry))


if __name__ == "__main__":
    raise SystemExit(main())
